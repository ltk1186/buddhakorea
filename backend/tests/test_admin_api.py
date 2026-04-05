import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch

from backend.app.admin import router
from backend.app.dependencies import get_current_user_required, require_roles, get_db
from backend.app.models.user import User

app = FastAPI()
app.include_router(router)

def override_get_current_user_required_admin():
    return User(id=1, role="admin", email="admin@example.com", nickname="Admin", is_active=True, daily_chat_limit=100)

def override_get_current_user_required_user():
    return User(id=2, role="user", email="user@example.com", nickname="User", is_active=True, daily_chat_limit=20)

def override_get_current_user_required_analyst():
    return User(id=3, role="analyst", email="analyst@example.com", nickname="Analyst", is_active=True, daily_chat_limit=50)

def override_get_db():
    mock_db = AsyncMock()
    return mock_db

app.dependency_overrides[get_db] = override_get_db

def test_admin_api_unauthorized():
    """Test that endpoints are inaccessible without authentication."""
    # Remove overrides for a clean test
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    
    client = TestClient(app)
    response = client.get("/api/admin/me")
    assert response.status_code == 401

def test_admin_api_forbidden_for_regular_user():
    """Test that a regular user cannot access admin endpoints."""
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_user
    client = TestClient(app)
    
    response = client.get("/api/admin/me")
    assert response.status_code == 403

def test_admin_api_me_for_admin():
    """Test that an admin user can access /api/admin/me."""
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = TestClient(app)
    
    response = client.get("/api/admin/me")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"

@patch("backend.app.admin._log_admin_action", new_callable=AsyncMock)
def test_admin_api_update_user_audit_log(mock_log_action):
    """Test that updating a user triggers an audit log."""
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = TestClient(app)
    
    # Mock DB execute to return a fake user
    mock_db = AsyncMock()
    mock_user = User(id=42, role="user", email="test@example.com", nickname="Test", is_active=True, daily_chat_limit=20)
    
    # Setup mock_db.execute().scalar_one_or_none() to return mock_user
    mock_result = Mock()
    mock_result.scalar_one_or_none.return_value = mock_user
    # Also need to mock usage execute which returns scalar_one_or_none
    mock_usage_result = Mock()
    mock_usage_result.scalar_one_or_none.return_value = None
    
    mock_db.execute.side_effect = [mock_result, mock_usage_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    payload = {"daily_chat_limit": 50, "is_active": False}
    response = client.patch("/api/admin/users/42", json=payload)
    
    assert response.status_code == 200
    assert response.json()["daily_chat_limit"] == 50
    assert response.json()["is_active"] == False
    
    # Verify the audit log function was called
    mock_log_action.assert_called_once()
    kwargs = mock_log_action.call_args.kwargs
    assert kwargs["action"] == "user.update"
    assert kwargs["target_type"] == "user"
    assert kwargs["target_id"] == "42"
    assert kwargs["before_state"] == {"daily_chat_limit": 20, "is_active": True}
    assert kwargs["after_state"] == {"daily_chat_limit": 50, "is_active": False}

def test_admin_api_update_user_forbidden_for_analyst():
    """Test that an analyst cannot update a user."""
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_analyst
    client = TestClient(app)
    
    payload = {"daily_chat_limit": 50}
    response = client.patch("/api/admin/users/42", json=payload)
    
    assert response.status_code == 403
