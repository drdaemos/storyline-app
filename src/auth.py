"""
Authentication module using Clerk.

This module provides centralized authentication for FastAPI endpoints using Clerk's backend API.
It verifies JWT tokens from the Authorization header and extracts user information.
"""

import os
from typing import Annotated

from clerk_backend_api import AuthenticateRequestOptions, Clerk
from fastapi import Depends, HTTPException, Request, status


# Check if authentication is enabled
def is_auth_enabled() -> bool:
    """Check if authentication is enabled via AUTH_ENABLED environment variable."""
    return os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")


# Initialize Clerk client
def get_clerk_client() -> Clerk:
    """Get the Clerk client instance."""
    clerk_secret_key = os.getenv("CLERK_SECRET_KEY")
    if not clerk_secret_key:
        raise RuntimeError("CLERK_SECRET_KEY environment variable is not set")
    return Clerk(bearer_auth=clerk_secret_key)


async def verify_clerk_token(request: Request) -> str:
    """
    Verify the Clerk JWT token from the request.

    If AUTH_ENABLED is false, returns a default user ID without verification.
    Otherwise, verifies the token with Clerk and extracts the user ID.

    Args:
        request: The FastAPI request object

    Returns:
        The user ID extracted from the verified token, or "anonymous" if auth is disabled

    Raises:
        HTTPException: If auth is enabled and the token is invalid or verification fails
    """
    # If authentication is disabled, return a default user ID
    if not is_auth_enabled():
        return "anonymous"

    try:
        clerk = get_clerk_client()

        # Authenticate the request with Clerk
        request_state = clerk.authenticate_request(request, AuthenticateRequestOptions())

        # Check if the request is authenticated
        if not request_state.is_signed_in:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Authentication failed: {request_state.reason or 'Not signed in'}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Extract user ID from the token payload
        user_id = request_state.payload.get("sub") if request_state.payload else None
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return user_id

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


# Dependency for protected endpoints
UserIdDep = Annotated[str, Depends(verify_clerk_token)]
