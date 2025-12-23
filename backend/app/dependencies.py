"""
FastAPI Dependencies
====================
Reusable dependencies for authentication, authorization, and database access.
"""

import time
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from . import auth
from .database import get_db
from .models.user import User


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.

    Use this dependency when authentication is optional.
    Example: Anonymous users can chat but logged-in users get history saved.
    """
    # Try to get token from cookie first
    token = request.cookies.get("access_token")

    # Fall back to Authorization header
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return None

    # Decode and validate token
    payload = auth.decode_access_token(token)
    if not payload:
        return None

    # Check expiration
    exp = payload.get("exp", 0)
    if exp < time.time():
        return None

    # Get user from database
    user_id = payload.get("user_id")
    if not user_id:
        return None

    stmt = select(User).where(User.id == user_id, User.is_active == True)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    return user


async def get_current_user_required(
    user: Optional[User] = Depends(get_current_user_optional)
) -> User:
    """
    Get current user, raise 401 if not authenticated.

    Use this dependency when authentication is required.
    Example: Viewing chat history, updating profile.
    """
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user


async def get_admin_user(
    user: User = Depends(get_current_user_required)
) -> User:
    """
    Get current user and verify admin role.

    Use this dependency for admin-only endpoints.
    """
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin access required."
        )
    return user


class TokenInfo:
    """Information about the current auth token."""
    def __init__(self, user_id: Optional[int], expires_at: float, is_valid: bool):
        self.user_id = user_id
        self.expires_at = expires_at
        self.is_valid = is_valid
        self.time_remaining = max(0, expires_at - time.time())


async def get_token_info(request: Request) -> TokenInfo:
    """
    Get information about the current token without fetching user.

    Useful for checking token validity/expiration without DB hit.
    """
    token = request.cookies.get("access_token")
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        return TokenInfo(None, 0, False)

    payload = auth.decode_access_token(token)
    if not payload:
        return TokenInfo(None, 0, False)

    exp = payload.get("exp", 0)
    user_id = payload.get("user_id")
    is_valid = exp > time.time()

    return TokenInfo(user_id, exp, is_valid)
