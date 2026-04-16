import pytest
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock, patch

from backend.app.admin import router
from backend.app.dependencies import get_current_user_required, require_roles, get_db
from backend.app.models.chat import ChatMessage, ChatSession
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


def test_admin_api_query_detail_returns_trace_and_sources():
    """Test read-only query investigation detail response."""
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = TestClient(app)

    mock_db = AsyncMock()
    now = datetime.now(timezone.utc)
    session = ChatSession(id=7, session_uuid="session-123", user_id=2, created_at=now)
    user = User(id=2, role="user", email="testuser@example.com", nickname="TestUser", is_active=True, daily_chat_limit=20)
    query_message = ChatMessage(id=101, session_id=7, role="user", content="What is the Four Noble Truths?", created_at=now)
    answer_message = ChatMessage(
        id=102,
        session_id=7,
        role="assistant",
        content="The Four Noble Truths explain suffering.",
        model_used="gemini-2.5-pro",
        response_mode="normal",
        sources_count=3,
        sources_json=[{"title": "Saṃyutta Nikāya", "chunk_id": "sn-1"}],
        tokens_used=240,
        latency_ms=4200,
        trace_json={"provider": "gemini_vertex", "prompt": {"id": "normal_v1"}},
        created_at=now,
    )

    selected_result = Mock()
    selected_result.one_or_none.return_value = (query_message, session, user)
    answer_result = Mock()
    answer_result.scalar_one_or_none.return_value = answer_message
    mock_db.execute.side_effect = [selected_result, answer_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/admin/queries/101")

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_message_id"] == 101
    assert payload["session_uuid"] == "session-123"
    assert payload["user_nickname"] == "TestUser"
    assert payload["query"]["id"] == 101
    assert payload["answer"]["id"] == 102
    assert payload["answer"]["provider"] == "gemini_vertex"
    assert payload["answer"]["model_used"] == "gemini-2.5-pro"
    assert payload["answer"]["sources_count"] == 3
    assert payload["answer"]["trace_json"]["prompt"]["id"] == "normal_v1"


@patch("backend.app.admin.analyze_observability_logs")
def test_admin_api_observability_returns_reliability_metrics(mock_analyze_observability):
    """Test reliability-focused observability aggregation response."""
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = TestClient(app)

    mock_analyze_observability.return_value = {
        "window_days": 7,
        "usage_log_available": True,
        "total_queries": 120,
        "queries_with_latency": 100,
        "cache_hit_rate": 25.0,
        "avg_cost_per_query_usd": 0.012345,
        "avg_latency_ms": 1800,
        "p50_latency_ms": 1400,
        "p95_latency_ms": 4200,
        "slow_query_threshold_ms": 30000,
        "slow_queries": 3,
        "by_day": {
            "2026-04-16": {
                "queries": 20,
                "cost_usd": 0.4,
                "cached_queries": 5,
                "cache_hit_rate": 25.0,
                "avg_latency_ms": 1700,
                "p95_latency_ms": 3500
            }
        }
    }

    mock_db = AsyncMock()
    answers_result = Mock()
    answers_result.one.return_value = (10, 2, 3.4)
    user_limits_result = Mock()
    user_limits_result.scalar_one.return_value = 4
    anon_limits_result = Mock()
    anon_limits_result.scalar_one.return_value = 7
    mock_db.execute.side_effect = [answers_result, user_limits_result, anon_limits_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/admin/observability?days=7")

    assert response.status_code == 200
    payload = response.json()
    assert payload["window_days"] == 7
    assert payload["usage_log_available"] == True
    assert payload["total_queries"] == 120
    assert payload["cache_hit_rate"] == 25.0
    assert payload["p95_latency_ms"] == 4200
    assert payload["zero_source_answers_24h"] == 2
    assert payload["zero_source_rate_24h"] == 20.0
    assert payload["avg_sources_per_answer_24h"] == 3.4
    assert payload["rate_limited_users_today"] == 4
    assert payload["rate_limited_anonymous_today"] == 7
    assert payload["daily"][0]["date"] == "2026-04-16"
