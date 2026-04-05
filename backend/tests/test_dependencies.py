import pytest
from fastapi import HTTPException
from unittest.mock import Mock, AsyncMock

from backend.app.dependencies import get_admin_user, require_roles
from backend.app.models.user import User

@pytest.mark.asyncio
async def test_get_admin_user_success():
    """Test that an admin user is allowed."""
    user = User(id=1, role="admin")
    result = await get_admin_user(user=user)
    assert result == user

@pytest.mark.asyncio
async def test_get_admin_user_forbidden():
    """Test that a non-admin user is forbidden."""
    user = User(id=2, role="user")
    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user(user=user)
    assert exc_info.value.status_code == 403

@pytest.mark.asyncio
async def test_require_roles_success():
    """Test that require_roles allows users with the required role."""
    dependency = require_roles({"ops", "admin"})
    
    # Test ops user
    user_ops = User(id=1, role="ops")
    result1 = await dependency(user=user_ops)
    assert result1 == user_ops

    # Test admin user
    user_admin = User(id=2, role="admin")
    result2 = await dependency(user=user_admin)
    assert result2 == user_admin

@pytest.mark.asyncio
async def test_require_roles_forbidden():
    """Test that require_roles forbids users without the required role."""
    dependency = require_roles({"ops", "admin"})
    
    user_analyst = User(id=3, role="analyst")
    with pytest.raises(HTTPException) as exc_info:
        await dependency(user=user_analyst)
    assert exc_info.value.status_code == 403
