"""Tests for authentication: Clerk session tokens verified without any network call, and how users map to workspaces."""

import time
from collections.abc import Mapping
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from starlette.datastructures import Headers

from storyline.agent import create_writer_agent
from storyline.web.app import create_app
from storyline.web.auth import ClerkAuthenticator, SingleUserAuthenticator
from storyline.web.errors import AuthenticationError, InvalidUserIdError
from storyline.web.user_workspaces import DirectoryUserWorkspaces
from tests.web_support import DEFAULT_MODEL, http_client


def _key_pair() -> tuple[rsa.RSAPrivateKey, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_pem = private_key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return private_key, public_pem


PRIVATE_KEY, PUBLIC_KEY = _key_pair()
OTHER_PRIVATE_KEY, _ = _key_pair()


def _token(*, key: rsa.RSAPrivateKey = PRIVATE_KEY, **claims: object) -> str:
    now = int(time.time())
    payload = {"sub": "user_2abc", "iat": now - 5, "exp": now + 300, **claims}
    return jwt.encode({name: value for name, value in payload.items() if value is not None}, key, algorithm="RS256")


def _bearer(token: str) -> Headers:
    return Headers({"Authorization": f"Bearer {token}"})


def _clerk(*, authorized_parties: list[str] | None = None) -> ClerkAuthenticator:
    return ClerkAuthenticator(jwt_key=PUBLIC_KEY, authorized_parties=authorized_parties)


# Clerk session tokens


@pytest.mark.asyncio
async def test_a_valid_session_token_identifies_the_user_by_its_subject() -> None:
    assert await _clerk().authenticate(_bearer(_token(sub="user_2abc"))) == "user_2abc"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "headers",
    [
        Headers({}),
        Headers({"Authorization": "Bearer"}),
        Headers({"Authorization": "Bearer "}),
        Headers({"Authorization": "Basic dXNlcjpwYXNz"}),
        Headers({"Authorization": "Bearer garbage"}),
        Headers({"Authorization": "Bearer a.b.c"}),
        _bearer(_token(exp=int(time.time()) - 3600, iat=int(time.time()) - 7200)),
        _bearer(_token(key=OTHER_PRIVATE_KEY)),
        _bearer(_token(sub=None)),
        _bearer("ak_" + _token()),
        Headers({"Cookie": f"__session={_token()}"}),
    ],
    ids=["missing", "bare-scheme", "empty-token", "wrong-scheme", "garbage", "malformed-jwt", "expired", "wrong-signature", "no-subject", "api-key-prefix", "cookie-only"],
)
async def test_anything_but_a_valid_bearer_session_token_is_rejected(headers: Mapping[str, str]) -> None:
    with pytest.raises(AuthenticationError):
        await _clerk().authenticate(headers)


@pytest.mark.asyncio
async def test_authorized_parties_restrict_which_apps_tokens_are_accepted() -> None:
    authenticator = _clerk(authorized_parties=["https://storyline.example"])

    assert await authenticator.authenticate(_bearer(_token(azp="https://storyline.example"))) == "user_2abc"
    with pytest.raises(AuthenticationError):
        await authenticator.authenticate(_bearer(_token(azp="https://elsewhere.example")))
    with pytest.raises(AuthenticationError):
        await authenticator.authenticate(_bearer(_token()))


@pytest.mark.asyncio
async def test_a_jwt_key_kept_on_one_line_with_escaped_newlines_works() -> None:
    authenticator = ClerkAuthenticator(jwt_key=PUBLIC_KEY.strip().replace("\n", "\\n"))

    assert await authenticator.authenticate(_bearer(_token())) == "user_2abc"


def test_clerk_authentication_needs_a_key() -> None:
    with pytest.raises(ValueError, match="key"):
        ClerkAuthenticator()


@pytest.mark.asyncio
async def test_without_authentication_everyone_is_the_same_local_user() -> None:
    authenticator = SingleUserAuthenticator()

    assert await authenticator.authenticate(Headers({})) == await authenticator.authenticate(_bearer("anything"))


def _clerk_app(tmp_path: Path):
    return create_app(
        authenticator=_clerk(),
        workspaces=DirectoryUserWorkspaces(tmp_path / "data"),
        agent=create_writer_agent(),
        default_model_name=DEFAULT_MODEL,
        static_dir=tmp_path / "no-frontend",
    )


@pytest.mark.asyncio
async def test_the_api_serves_a_user_with_a_valid_clerk_token_from_their_own_directory(tmp_path) -> None:
    async with http_client(_clerk_app(tmp_path)) as client:
        created = await client.post("/api/stories", json={"name": "harbor"}, headers={"Authorization": f"Bearer {_token(sub='user_2abc')}"})
        listed = await client.get("/api/stories", headers={"Authorization": f"Bearer {_token(sub='user_2abc')}"})

    assert created.status_code == 201
    assert listed.json() == {"stories": ["harbor"], "active": "harbor"}
    assert (tmp_path / "data" / "users" / "user_2abc" / "harbor").is_dir()


@pytest.mark.asyncio
async def test_the_api_rejects_missing_and_garbage_clerk_tokens_with_401(tmp_path) -> None:
    async with http_client(_clerk_app(tmp_path)) as client:
        anonymous = await client.get("/api/stories")
        garbage = await client.get("/api/stories", headers={"Authorization": "Bearer garbage"})
        forged = await client.get("/api/stories", headers={"Authorization": f"Bearer {_token(key=OTHER_PRIVATE_KEY)}"})
        health = await client.get("/health")

    for response in (anonymous, garbage, forged):
        assert response.status_code == 401
        assert response.json()["detail"]
    assert health.status_code == 200
    assert not (tmp_path / "data").exists()


# Where each user's stories live


@pytest.mark.parametrize("user_id", ["user_2abc", "alice", "A-b_9", "u" * 128])
def test_each_user_gets_a_workspace_under_the_users_directory(tmp_path, user_id: str) -> None:
    workspaces = DirectoryUserWorkspaces(tmp_path / "data")

    assert workspaces.workspace_for(user_id).root == (tmp_path / "data").resolve() / "users" / user_id


def test_a_user_always_gets_the_same_workspace_object_and_users_get_different_ones(tmp_path) -> None:
    workspaces = DirectoryUserWorkspaces(tmp_path)

    assert workspaces.workspace_for("alice") is workspaces.workspace_for("alice")
    assert workspaces.workspace_for("alice") is not workspaces.workspace_for("bob")


@pytest.mark.parametrize("user_id", ["", "..", ".", "../outside", "a/b", "a\\b", "C:evil", "user id", ".hidden", "-lead", "a\x00b", "über", "u" * 129, "a\n"])
def test_user_ids_that_are_unsafe_in_a_path_are_refused(tmp_path, user_id: str) -> None:
    with pytest.raises(InvalidUserIdError):
        DirectoryUserWorkspaces(tmp_path).workspace_for(user_id)
