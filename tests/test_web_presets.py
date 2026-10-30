"""Tests for the web API's preset and sealed-lore support."""

import httpx
import pytest

from storyline.presets import BUNDLED_PRESETS
from storyline.workspace import StorySetup
from storyline.workspace.file_story import SETUP_FILENAME
from storyline.workspace.file_workspace import FileWorkspace
from tests.web_support import ALICE, http_client, local_app, multi_user_app

LORE = "---\nsummary: {summary}\nkeywords: k\n---\nBody.\n"


@pytest.mark.asyncio
async def test_listing_presets_returns_every_bundled_preset_with_the_default_first(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        response = await client.get("/api/presets")

    assert response.status_code == 200
    presets = response.json()["presets"]
    assert [preset["id"] for preset in presets] == [preset.id for preset in BUNDLED_PRESETS]
    assert presets[0]["id"] == "co-writing"
    assert all(preset["title"] and preset["description"] for preset in presets)
    assert set(presets[0]) == {"id", "title", "description"}


@pytest.mark.asyncio
async def test_listing_presets_needs_credentials_when_authentication_is_on(tmp_path) -> None:
    async with http_client(multi_user_app(tmp_path)) as client:
        anonymous = await client.get("/api/presets")
        signed_in = await client.get("/api/presets", headers=ALICE)

    assert anonymous.status_code == 401
    assert signed_in.status_code == 200


@pytest.mark.asyncio
async def test_creating_a_story_as_a_preset_records_its_setup(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        created = await client.post("/api/stories", json={"name": "harbor", "preset": "co-writing"})
        omitted = await client.post("/api/stories", json={"name": "mill"})

    assert created.status_code == omitted.status_code == 201
    for name in ("harbor", "mill"):
        story = await FileWorkspace(root=tmp_path / "workspace").open_story(name=name)
        assert await story.read_setup() == StorySetup(preset="co-writing")
        assert (tmp_path / "workspace" / name / SETUP_FILENAME).is_file()


@pytest.mark.asyncio
async def test_creating_a_story_as_an_unknown_preset_is_a_bad_request_and_creates_nothing(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        response = await client.post("/api/stories", json={"name": "harbor", "preset": "no-such-preset"})
        listed = await client.get("/api/stories")

    assert response.status_code == 400
    assert "no-such-preset" in response.json()["detail"]
    assert listed.json()["stories"] == []


async def _story_with_sealed_lore(client: httpx.AsyncClient, tmp_path) -> None:
    await client.post("/api/stories", json={"name": "harbor"})
    story = await FileWorkspace(root=tmp_path / "workspace").open_story(name="harbor")
    await story.write_lore(filename="city.md", content=LORE.format(summary="The city."))
    await story.write_lore(filename="sealed/vera.md", content=LORE.format(summary="What Vera wants."))


@pytest.mark.asyncio
async def test_the_lore_list_flags_sealed_files_after_the_stories_own(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _story_with_sealed_lore(client, tmp_path)
        listed = await client.get("/api/stories/harbor/lore")

    assert [(file["filename"], file["sealed"]) for file in listed.json()["files"]] == [("city.md", False), ("sealed/vera.md", True)]


@pytest.mark.asyncio
async def test_a_sealed_file_can_be_read_by_its_path(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await _story_with_sealed_lore(client, tmp_path)
        read = await client.get("/api/stories/harbor/lore/sealed/vera.md")
        deeper = await client.get("/api/stories/harbor/lore/sealed/sub/vera.md")
        elsewhere = await client.get("/api/stories/harbor/lore/other/vera.md")

    assert read.status_code == 200
    assert read.json() == {"filename": "sealed/vera.md", "text": LORE.format(summary="What Vera wants.")}
    assert deeper.status_code == elsewhere.status_code == 404


@pytest.mark.asyncio
async def test_a_story_whose_setup_names_an_unknown_preset_cannot_be_opened(tmp_path) -> None:
    async with http_client(local_app(tmp_path)) as client:
        await client.post("/api/stories", json={"name": "harbor"})
        story = await FileWorkspace(root=tmp_path / "workspace").open_story(name="harbor")
        await story.write_setup(setup=StorySetup(preset="gone"))
        response = await client.get("/api/stories/harbor/script")

    assert response.status_code == 422
