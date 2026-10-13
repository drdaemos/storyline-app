"""Who is making a request."""

import asyncio
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from clerk_backend_api.security import AuthenticateRequestOptions, RequestState, authenticate_request

from storyline.web.errors import AuthenticationError

logger = logging.getLogger(__name__)

LOCAL_USER_ID = "local"
SESSION_TOKEN_TYPE = "session_token"


class Authenticator(Protocol):
    """Resolves the user a request belongs to."""

    async def authenticate(self, headers: Mapping[str, str]) -> str:
        """Return the id of the user who sent a request with these headers, or raise ``AuthenticationError``."""


class SingleUserAuthenticator:
    """Authentication switched off: every request comes from the one local user."""

    async def authenticate(self, headers: Mapping[str, str]) -> str:
        return LOCAL_USER_ID


@dataclass(frozen=True)
class _BearerRequest:
    """What Clerk's request authentication reads: the headers, and nothing else, so a cookie can never log anyone in."""

    headers: Mapping[str, str]


class ClerkAuthenticator:
    """Verifies the Clerk session token sent as ``Authorization: Bearer <token>``; the user is the token's subject.

    With a ``jwt_key`` (the instance's PEM public key) tokens are verified without any network call; otherwise Clerk's
    signing keys are fetched with the ``secret_key``.
    """

    def __init__(self, *, secret_key: str | None = None, jwt_key: str | None = None, authorized_parties: Sequence[str] | None = None) -> None:
        if not secret_key and not jwt_key:
            raise ValueError("Clerk authentication needs a secret key or a JWT key.")
        self._options = AuthenticateRequestOptions(
            secret_key=secret_key or None,
            jwt_key=jwt_key.replace("\\n", "\n") if jwt_key else None,  # env files often hold the PEM's line breaks as backslash-n

            authorized_parties=list(authorized_parties) if authorized_parties else None,
            accepts_token=[SESSION_TOKEN_TYPE],
        )

    async def authenticate(self, headers: Mapping[str, str]) -> str:
        token = _bearer_token(headers)
        if token is None:
            raise AuthenticationError("Sign in to use Storyline.")
        # Verification can fetch signing keys over the network, so it must not block the event loop.
        state = await asyncio.to_thread(self._verify, token)
        if not state.is_signed_in or state.payload is None:
            raise AuthenticationError(state.message or "The session token was not accepted.")
        user_id = state.payload.get("sub")
        if not isinstance(user_id, str) or not user_id:
            raise AuthenticationError("The session token does not name a user.")
        return user_id

    def _verify(self, token: str) -> RequestState:
        try:
            return authenticate_request(_BearerRequest({"Authorization": f"Bearer {token}"}), self._options)
        except Exception as error:
            logger.warning("Session token verification failed: %s", error)
            raise AuthenticationError("The session token could not be verified.") from error


def _bearer_token(headers: Mapping[str, str]) -> str | None:
    scheme, _, token = headers.get("authorization", "").strip().partition(" ")
    token = token.strip()
    return token if scheme.lower() == "bearer" and token else None
