"""Errors the web interface reports, and how each one is answered over HTTP."""

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from storyline.room import RoomBusyError


class AuthenticationError(Exception):
    """Raised when a request does not identify a user."""


class InvalidUserIdError(ValueError):
    """Raised when a user id could not be used safely as the name of a storage location."""


class InvalidRequestError(ValueError):
    """Raised when a request asks for something that can never work: a bad name, an empty prompt."""


class StoryNotFoundError(LookupError):
    """Raised when the user has no story of that name."""


class LoreFileNotFoundError(LookupError):
    """Raised when the story has no lore file of that name."""


def register_error_handlers(app: FastAPI) -> None:
    """Answer every web error with ``{"detail": "<message>"}`` and the status the API contract names for it."""
    app.add_exception_handler(AuthenticationError, _answer(401, headers={"WWW-Authenticate": "Bearer"}))
    app.add_exception_handler(InvalidUserIdError, _answer(401, headers={"WWW-Authenticate": "Bearer"}))
    app.add_exception_handler(InvalidRequestError, _answer(400))
    app.add_exception_handler(StoryNotFoundError, _answer(404))
    app.add_exception_handler(LoreFileNotFoundError, _answer(404))
    app.add_exception_handler(RoomBusyError, _answer(409))
    app.add_exception_handler(RequestValidationError, _answer_malformed_request)


type ErrorHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]


def _answer(status_code: int, *, headers: dict[str, str] | None = None) -> ErrorHandler:
    async def handle(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"detail": str(error)}, status_code=status_code, headers=headers)

    return handle


async def _answer_malformed_request(_: Request, error: Exception) -> JSONResponse:
    if not isinstance(error, RequestValidationError):
        raise error
    problems = "; ".join(f"{'.'.join(str(part) for part in problem['loc'] if part != 'body')}: {problem['msg']}" for problem in error.errors())
    return JSONResponse({"detail": problems or "Invalid request."}, status_code=400)
