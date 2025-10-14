"""Tests for the authentication module."""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from src.auth import is_auth_enabled, verify_clerk_token


class TestIsAuthEnabled:
    """Tests for is_auth_enabled function."""

    def test_auth_enabled_by_default(self) -> None:
        """Test that auth is enabled by default when AUTH_ENABLED is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_auth_enabled() is True

    def test_auth_enabled_when_true(self) -> None:
        """Test that auth is enabled when AUTH_ENABLED is 'true'."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "true"}):
            assert is_auth_enabled() is True

    def test_auth_enabled_when_1(self) -> None:
        """Test that auth is enabled when AUTH_ENABLED is '1'."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "1"}):
            assert is_auth_enabled() is True

    def test_auth_enabled_when_yes(self) -> None:
        """Test that auth is enabled when AUTH_ENABLED is 'yes'."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "yes"}):
            assert is_auth_enabled() is True

    def test_auth_disabled_when_false(self) -> None:
        """Test that auth is disabled when AUTH_ENABLED is 'false'."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
            assert is_auth_enabled() is False

    def test_auth_disabled_when_0(self) -> None:
        """Test that auth is disabled when AUTH_ENABLED is '0'."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "0"}):
            assert is_auth_enabled() is False

    def test_auth_enabled_case_insensitive(self) -> None:
        """Test that AUTH_ENABLED check is case-insensitive."""
        with patch.dict(os.environ, {"AUTH_ENABLED": "TRUE"}):
            assert is_auth_enabled() is True
        with patch.dict(os.environ, {"AUTH_ENABLED": "FALSE"}):
            assert is_auth_enabled() is False


class TestVerifyClerkToken:
    """Tests for verify_clerk_token function."""

    @pytest.mark.asyncio
    async def test_returns_anonymous_when_auth_disabled(self) -> None:
        """Test that verify_clerk_token returns 'anonymous' when auth is disabled."""
        mock_request = MagicMock()
        with patch.dict(os.environ, {"AUTH_ENABLED": "false"}):
            result = await verify_clerk_token(mock_request)
            assert result == "anonymous"

    @pytest.mark.asyncio
    async def test_authenticates_successfully_when_auth_enabled(self) -> None:
        """Test successful authentication when auth is enabled."""
        # Mock FastAPI request
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url = "http://test.com/api/test"
        mock_request.headers.raw = [(b"authorization", b"Bearer valid_token")]

        # Mock request state from Clerk
        mock_request_state = MagicMock()
        mock_request_state.is_signed_in = True
        mock_request_state.payload = {"sub": "user_123"}

        # Mock Clerk client
        mock_clerk = MagicMock()
        mock_clerk.authenticate_request.return_value = mock_request_state

        with patch.dict(os.environ, {"AUTH_ENABLED": "true", "CLERK_SECRET_KEY": "test_key"}):
            with patch("src.auth.get_clerk_client", return_value=mock_clerk):
                result = await verify_clerk_token(mock_request)
                assert result == "user_123"
                mock_clerk.authenticate_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_raises_401_when_not_signed_in(self) -> None:
        """Test that verify_clerk_token raises 401 when user is not signed in."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url = "http://test.com/api/test"
        mock_request.headers.raw = []

        # Mock request state with not signed in
        mock_request_state = MagicMock()
        mock_request_state.is_signed_in = False
        mock_request_state.reason = "Invalid token"

        mock_clerk = MagicMock()
        mock_clerk.authenticate_request.return_value = mock_request_state

        with patch.dict(os.environ, {"AUTH_ENABLED": "true", "CLERK_SECRET_KEY": "test_key"}):
            with patch("src.auth.get_clerk_client", return_value=mock_clerk):
                with pytest.raises(HTTPException) as exc_info:
                    await verify_clerk_token(mock_request)

                assert exc_info.value.status_code == 401
                assert "Invalid token" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_when_missing_user_id(self) -> None:
        """Test that verify_clerk_token raises 401 when token doesn't contain user ID."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url = "http://test.com/api/test"
        mock_request.headers.raw = [(b"authorization", b"Bearer token_without_sub")]

        # Mock request state with missing sub
        mock_request_state = MagicMock()
        mock_request_state.is_signed_in = True
        mock_request_state.payload = {}

        mock_clerk = MagicMock()
        mock_clerk.authenticate_request.return_value = mock_request_state

        with patch.dict(os.environ, {"AUTH_ENABLED": "true", "CLERK_SECRET_KEY": "test_key"}):
            with patch("src.auth.get_clerk_client", return_value=mock_clerk):
                with pytest.raises(HTTPException) as exc_info:
                    await verify_clerk_token(mock_request)

                assert exc_info.value.status_code == 401
                assert "missing user ID" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_401_when_clerk_raises_exception(self) -> None:
        """Test that verify_clerk_token raises 401 when Clerk client raises an exception."""
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url = "http://test.com/api/test"
        mock_request.headers.raw = [(b"authorization", b"Bearer problem_token")]

        # Mock Clerk client to raise an exception
        mock_clerk = MagicMock()
        mock_clerk.authenticate_request.side_effect = Exception("Network error")

        with patch.dict(os.environ, {"AUTH_ENABLED": "true", "CLERK_SECRET_KEY": "test_key"}):
            with patch("src.auth.get_clerk_client", return_value=mock_clerk):
                with pytest.raises(HTTPException) as exc_info:
                    await verify_clerk_token(mock_request)

                assert exc_info.value.status_code == 401
                assert "Authentication failed" in exc_info.value.detail
