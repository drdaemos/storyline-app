"""Tests for the web API: every route's success path and error statuses, users kept apart, and the frontend fallback."""

import shutil
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from storyline.agent import create_writer_agent
from storyline.web.app import create_app
from storyline.web.user_workspaces import DirectoryUserWorkspaces
from storyline.workspace.file_workspace import FileWorkspace
from tests.web_support import ALICE, BOB, DEFAULT_MODEL, FakeAuthenticator, ScriptedWriter, http_client, local_app, multi_user_app, rooms_of

LORE = "---\nsummary: Harbor town.\nkeywords: harbor, fog\n---\n\nFog every morning."


def _workspace(tmp_path: Path) -> FileWorkspace:
    """The workspace of the app built by ``local_app``, opened independently to prepare and inspect files."""
    return FileWorkspace(root=tmp_path / "workspace")


async def _create(client: httpx.AsyncClient, name: str, headers: dict[str, str] | None = None) -> httpx.Response:
    return await client.post("/api/stories", json={"name": name}, headers=headers)


@pytest.mark.asyncio
async def test_health_needs_no_credentials(tmp_path) -> None:
    async with http_client(multi_user_app(tmp_path)) as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# Stories


@pytest.mark.asyncio
async def test_a_new_workspace_lists_no_stories_and_no_active_one(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        response = await client.get("/api/stories")

    assert response.status_code == 200
    assert response.json() == {"stories": [], "active": None}


@pytest.mark.asyncio
async def test_creating_a_story_returns_201_lists_it_and_makes_it_active(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        created = await _create(client, "harbor")
        await _create(client, "mill")
        listed = await client.get("/api/stories")

    assert created.status_code == 201
    assert created.json() == {"name": "harbor"}
    assert listed.json() == {"stories": ["harbor", "mill"], "active": "mill"}
    assert (tmp_path / "workspace" / "harbor").is_dir()


@pytest.mark.asyncio
async def test_the_active_story_is_null_once_that_story_is_gone(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        await _create(client, "mill")
        shutil.rmtree(tmp_path / "workspace" / "mill")
        listed = await client.get("/api/stories")

    assert listed.json() == {"stories": ["harbor"], "active": None}


@pytest.mark.asyncio
async def test_creating_a_story_that_exists_or_with_a_bad_name_is_a_bad_request(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        duplicate = await _create(client, "harbor")
        dotted = await _create(client, ".hidden")
        slashed = await _create(client, "a/b")
        blank = await _create(client, "   ")
        no_name = await client.post("/api/stories", json={})
        not_json = await client.post("/api/stories", content="nonsense")

    for response in (duplicate, dotted, slashed, blank, no_name, not_json):
        assert response.status_code == 400
        assert isinstance(response.json()["detail"], str)
        assert response.json()["detail"]
    assert "already exists" in duplicate.json()["detail"]


# Operations on a story


@pytest.mark.asyncio
async def test_sending_a_prompt_is_accepted_and_the_turn_runs_to_completion_without_anyone_listening(tmp_path) -> None:
    app = local_app(tmp_path, model=ScriptedWriter("The writer ", "replies.").model)
    async with http_client(app) as client:
        await _create(client, "harbor")

        accepted = await client.post("/api/stories/harbor/prompts", json={"text": "Begin."})
        await rooms_of(app).wait_until_idle()
        undone = await client.post("/api/stories/harbor/undo")

    assert accepted.status_code == 202
    assert accepted.json() == {}
    assert undone.json() == {"undone": True}
    assert rooms_of(app).open_rooms == 0


@pytest.mark.asyncio
async def test_prompt_errors(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        empty = await client.post("/api/stories/harbor/prompts", json={"text": ""})
        blank = await client.post("/api/stories/harbor/prompts", json={"text": "  \n"})
        no_text = await client.post("/api/stories/harbor/prompts", json={})
        unknown = await client.post("/api/stories/missing/prompts", json={"text": "Hello."})

    assert [response.status_code for response in (empty, blank, no_text, unknown)] == [400, 400, 400, 404]
    assert unknown.json()["detail"]


@pytest.mark.asyncio
async def test_undo_and_clear_are_refused_while_the_writer_works_and_work_once_it_is_done(tmp_path) -> None:
    writer = ScriptedWriter("Working ", "on it.", hold_after=1)
    app = local_app(tmp_path, model=writer.model)
    async with http_client(app) as client:
        await _create(client, "harbor")
        await client.post("/api/stories/harbor/prompts", json={"text": "Begin."})
        await writer.holding.wait()

        undo_while_working = await client.post("/api/stories/harbor/undo")
        clear_while_working = await client.post("/api/stories/harbor/clear")
        writer.release.set()
        await rooms_of(app).wait_until_idle()
        undo = await client.post("/api/stories/harbor/undo")
        undo_again = await client.post("/api/stories/harbor/undo")

    assert undo_while_working.status_code == 409
    assert clear_while_working.status_code == 409
    assert "working" in undo_while_working.json()["detail"]
    assert undo.json() == {"undone": True}
    assert undo_again.json() == {"undone": False}


@pytest.mark.asyncio
async def test_clearing_the_conversation_returns_204_and_leaves_nothing_to_undo(tmp_path) -> None:
    app = local_app(tmp_path, model=ScriptedWriter("Reply.").model)
    async with http_client(app) as client:
        await _create(client, "harbor")
        await client.post("/api/stories/harbor/prompts", json={"text": "Begin."})
        await rooms_of(app).wait_until_idle()

        cleared = await client.post("/api/stories/harbor/clear")
        undo = await client.post("/api/stories/harbor/undo")

    assert cleared.status_code == 204
    assert cleared.content == b""
    assert undo.json() == {"undone": False}


@pytest.mark.asyncio
async def test_interrupting_stops_the_turn_and_returns_204(tmp_path) -> None:
    writer = ScriptedWriter("Started ", "never finished.", hold_after=1)
    app = local_app(tmp_path, model=writer.model)
    async with http_client(app) as client:
        await _create(client, "harbor")
        await client.post("/api/stories/harbor/prompts", json={"text": "Begin."})
        await writer.holding.wait()

        interrupted = await client.post("/api/stories/harbor/interrupt")
        await rooms_of(app).wait_until_idle()
        undo = await client.post("/api/stories/harbor/undo")

    assert interrupted.status_code == 204
    assert undo.json() == {"undone": True}


@pytest.mark.asyncio
async def test_interrupting_an_idle_story_changes_nothing(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        interrupted = await client.post("/api/stories/harbor/interrupt")
        unknown = await client.post("/api/stories/missing/interrupt")

    assert interrupted.status_code == 204
    assert unknown.status_code == 404


@pytest.mark.asyncio
async def test_setting_the_model_is_remembered_in_the_story(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        changed = await client.put("/api/stories/harbor/model", json={"model_name": "openrouter:other/model"})
        story = await _workspace(tmp_path).open_story(name="harbor")

    assert changed.status_code == 204
    assert await story.read_model_name() == "openrouter:other/model"


@pytest.mark.asyncio
async def test_set_model_errors(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        blank = await client.put("/api/stories/harbor/model", json={"model_name": "  "})
        missing_field = await client.put("/api/stories/harbor/model", json={})
        unknown = await client.put("/api/stories/missing/model", json={"model_name": "openrouter:other/model"})

    assert [response.status_code for response in (blank, missing_field, unknown)] == [400, 400, 404]


@pytest.mark.asyncio
async def test_a_model_no_turn_could_run_on_is_refused_and_not_remembered(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        refused = await client.put("/api/stories/harbor/model", json={"model_name": "not-a-valid-model"})
        story = await _workspace(tmp_path).open_story(name="harbor")

    assert refused.status_code == 400
    assert "not-a-valid-model" in refused.json()["detail"]
    assert await story.read_model_name() is None


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["nul", "CON", "aux.txt", "x" * 101])
async def test_story_names_the_filesystem_cannot_hold_are_refused(tmp_path, name: str) -> None:
    async with http_client(local_app(tmp_path)) as client:
        refused = await _create(client, name)
        stories = await client.get("/api/stories")

    assert refused.status_code == 400
    assert refused.json()["detail"]
    assert stories.json() == {"stories": [], "active": None}


@pytest.mark.asyncio
async def test_operations_on_an_unknown_story_are_not_found(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        responses = [
            await client.post("/api/stories/missing/undo"),
            await client.post("/api/stories/missing/clear"),
            await client.get("/api/stories/missing/script"),
            await client.get("/api/stories/missing/lore"),
            await client.get("/api/stories/missing/lore/ines.md"),
            await client.get("/api/stories/missing/events"),
        ]

    assert [response.status_code for response in responses] == [404] * 6
    assert all(response.json()["detail"] for response in responses)


@pytest.mark.asyncio
async def test_reading_the_script(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        empty = await client.get("/api/stories/harbor/script")
        await (await _workspace(tmp_path).open_story(name="harbor")).append_script(text="Fog rolled in.")
        written = await client.get("/api/stories/harbor/script")

    assert empty.status_code == 200
    assert empty.json() == {"text": ""}
    assert written.json() == {"text": "Fog rolled in."}


@pytest.mark.asyncio
async def test_listing_and_reading_lore(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _create(client, "harbor")
        story = await _workspace(tmp_path).open_story(name="harbor")
        await story.write_lore(filename="ines.md", content=LORE)
        (tmp_path / "workspace" / "harbor" / "notes.md").write_text("Plain notes, no header.", encoding="utf-8")

        listed = await client.get("/api/stories/harbor/lore")
        read = await client.get("/api/stories/harbor/lore/ines.md")
        missing = await client.get("/api/stories/harbor/lore/nobody.md")
        script_name = await client.get("/api/stories/harbor/lore/script.md")

    assert listed.status_code == 200
    assert listed.json() == {
        "files": [
            {"filename": "ines.md", "summary": "Harbor town.", "keywords": "harbor, fog", "sealed": False},
            {"filename": "notes.md", "summary": None, "keywords": None, "sealed": False},
        ]
    }
    assert read.status_code == 200
    assert read.json() == {"filename": "ines.md", "text": LORE}
    assert missing.status_code == 404
    assert missing.json()["detail"]
    assert script_name.status_code == 404


# Users


@pytest.mark.asyncio
async def test_requests_without_valid_credentials_are_unauthorized_when_authentication_is_on(tmp_path) -> None:
    async with http_client(multi_user_app(tmp_path)) as client:
        anonymous = await client.get("/api/stories")
        garbage = await client.get("/api/stories", headers={"Authorization": "Bearer garbage"})
        wrong_scheme = await client.get("/api/stories", headers={"Authorization": "Basic alice-token"})
        create = await client.post("/api/stories", json={"name": "harbor"})
        events = await client.get("/api/stories/harbor/events")

    for response in (anonymous, garbage, wrong_scheme, create, events):
        assert response.status_code == 401
        assert response.json()["detail"]
        assert response.headers["www-authenticate"] == "Bearer"
    assert not (tmp_path / "data").exists()


@pytest.mark.asyncio
async def test_users_have_separate_stories_on_disk_and_in_the_api(tmp_path) -> None:
    async with http_client(multi_user_app(tmp_path)) as client:
        await _create(client, "harbor", ALICE)
        await (await FileWorkspace(root=tmp_path / "data" / "users" / "alice").open_story(name="harbor")).append_script(text="Alice's secret chapter.")

        bob_stories = await client.get("/api/stories", headers=BOB)
        bob_script = await client.get("/api/stories/harbor/script", headers=BOB)
        bob_prompt = await client.post("/api/stories/harbor/prompts", json={"text": "Hello."}, headers=BOB)
        bob_lore = await client.get("/api/stories/harbor/lore", headers=BOB)
        bob_events = await client.get("/api/stories/harbor/events", headers=BOB)
        bob_creates_the_same_name = await _create(client, "harbor", BOB)
        bob_script_after = await client.get("/api/stories/harbor/script", headers=BOB)
        alice_script = await client.get("/api/stories/harbor/script", headers=ALICE)
        alice_stories = await client.get("/api/stories", headers=ALICE)

    assert bob_stories.json() == {"stories": [], "active": None}
    assert [response.status_code for response in (bob_script, bob_prompt, bob_lore, bob_events)] == [404] * 4
    assert bob_creates_the_same_name.status_code == 201
    assert bob_script_after.json() == {"text": ""}
    assert alice_script.json() == {"text": "Alice's secret chapter."}
    assert alice_stories.json() == {"stories": ["harbor"], "active": "harbor"}
    assert (tmp_path / "data" / "users" / "bob" / "harbor").is_dir()


@pytest.mark.asyncio
async def test_users_working_at_once_keep_their_conversations_apart(tmp_path) -> None:
    app = multi_user_app(tmp_path, model=ScriptedWriter("A reply.").model)
    async with http_client(app) as client:
        await _create(client, "harbor", ALICE)
        await _create(client, "harbor", BOB)
        await client.post("/api/stories/harbor/prompts", json={"text": "Alice writes."}, headers=ALICE)
        await rooms_of(app).wait_until_idle()

        bob_undo = await client.post("/api/stories/harbor/undo", headers=BOB)
        alice_undo = await client.post("/api/stories/harbor/undo", headers=ALICE)

    assert bob_undo.json() == {"undone": False}
    assert alice_undo.json() == {"undone": True}


@pytest.mark.asyncio
async def test_a_user_id_that_is_not_safe_as_a_directory_name_is_unauthorized(tmp_path) -> None:
    app: FastAPI = create_app(
        authenticator=FakeAuthenticator({"evil-token": "../outside"}),
        workspaces=DirectoryUserWorkspaces(tmp_path / "data"),
        agent=create_writer_agent(),
        default_model_name=DEFAULT_MODEL,
        static_dir=tmp_path / "no-frontend",
    )
    async with http_client(app) as client:
        response = await _create(client, "harbor", {"Authorization": "Bearer evil-token"})

    assert response.status_code == 401
    assert not (tmp_path / "outside").exists()
    assert not (tmp_path / "data").exists()


# The built frontend


@pytest.fixture
def frontend(tmp_path) -> Path:
    static = tmp_path / "frontend"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<html>storyline</html>", encoding="utf-8")
    (static / "assets" / "app.js").write_text("console.log('app')", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("not for the web", encoding="utf-8")
    return static


@pytest.mark.asyncio
async def test_the_built_frontend_is_served_with_a_fallback_to_index_for_app_routes(tmp_path, frontend) -> None:
    async with http_client(local_app(tmp_path, static_dir=frontend)) as client:
        root = await client.get("/")
        asset = await client.get("/assets/app.js")
        app_route = await client.get("/stories/harbor")
        escaped = await client.get("/%2e%2e/secret.txt")
        health = await client.get("/health")
        stories = await client.get("/api/stories")

    assert root.text == "<html>storyline</html>"
    assert asset.text == "console.log('app')"
    assert app_route.text == "<html>storyline</html>"
    assert "not for the web" not in escaped.text
    assert health.json() == {"status": "ok"}
    assert stories.json() == {"stories": [], "active": None}


@pytest.mark.asyncio
async def test_api_paths_are_never_answered_with_the_frontend(tmp_path, frontend) -> None:
    async with http_client(local_app(tmp_path, static_dir=frontend)) as client:
        unknown = await client.get("/api/nothing-here")
        bare = await client.get("/api")

    assert unknown.status_code == 404
    assert unknown.json() == {"detail": "Not Found"}
    assert bare.status_code == 404


@pytest.mark.asyncio
async def test_without_a_frontend_build_the_api_still_works(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        root = await client.get("/")
        stories = await client.get("/api/stories")

    assert root.status_code == 404
    assert stories.status_code == 200
