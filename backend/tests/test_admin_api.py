from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.admin import router
from backend.app.database import get_db
from backend.app.dependencies import get_current_user_required
from backend.app.models.admin_query_review import AdminQueryReview
from backend.app.models.chat import ChatMessage, ChatSession
from backend.app.models.social_account import SocialAccount
from backend.app.models.user import User
from backend.app.models.user_usage import UserUsage

app = FastAPI()
app.include_router(router)


def override_get_current_user_required_admin():
    return User(id=1, role="admin", email="admin@example.com", nickname="Admin", is_active=True, daily_chat_limit=100)


def override_get_current_user_required_user():
    return User(id=2, role="user", email="user@example.com", nickname="User", is_active=True, daily_chat_limit=20)


def override_get_current_user_required_analyst():
    return User(id=3, role="analyst", email="analyst@example.com", nickname="Analyst", is_active=True, daily_chat_limit=50)


def override_get_db():
    return AsyncMock()


app.dependency_overrides[get_db] = override_get_db


def make_client():
    return TestClient(app)


def test_admin_api_unauthorized():
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db
    client = make_client()
    response = client.get("/api/admin/me")
    assert response.status_code == 401


def test_admin_api_forbidden_for_regular_user():
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_user
    client = make_client()
    response = client.get("/api/admin/me")
    assert response.status_code == 403


def test_admin_api_me_for_admin():
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = make_client()
    response = client.get("/api/admin/me")
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


@patch("backend.app.admin._log_admin_action", new_callable=AsyncMock)
def test_admin_api_update_user_audit_log(mock_log_action):
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = make_client()

    mock_db = AsyncMock()
    mock_user = User(id=42, role="user", email="test@example.com", nickname="Test", is_active=True, daily_chat_limit=20)
    user_result = Mock()
    user_result.scalar_one_or_none.return_value = mock_user
    usage_result = Mock()
    usage_result.scalar_one_or_none.return_value = None
    mock_db.execute.side_effect = [user_result, usage_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.patch("/api/admin/users/42", json={"daily_chat_limit": 50, "is_active": False})
    assert response.status_code == 200
    assert response.json()["daily_chat_limit"] == 50
    assert response.json()["is_active"] is False

    kwargs = mock_log_action.call_args.kwargs
    assert kwargs["action"] == "user.update"
    assert kwargs["target_id"] == "42"
    assert kwargs["before_state"] == {"daily_chat_limit": 20, "is_active": True}
    assert kwargs["after_state"] == {"daily_chat_limit": 50, "is_active": False}


def test_admin_api_update_user_forbidden_for_analyst():
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_analyst
    client = make_client()
    response = client.patch("/api/admin/users/42", json={"daily_chat_limit": 50})
    assert response.status_code == 403


def test_admin_api_user_detail_returns_identities_sessions_and_usage():
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = make_client()

    now = datetime.now(timezone.utc)
    mock_db = AsyncMock()
    user = User(id=11, role="user", email="seeker@example.com", nickname="Seeker", is_active=True, daily_chat_limit=20, created_at=now, last_login=now)
    today_usage = UserUsage(user_id=11, usage_date=date.today(), chat_count=4, tokens_used=1200)
    identity = SocialAccount(
        id=8,
        user_id=11,
        provider="google",
        provider_user_id="google-123",
        provider_email="seeker@example.com",
        created_at=now,
        last_used_at=now,
    )
    session = ChatSession(
        id=5,
        session_uuid="session-abc",
        user_id=11,
        title="Four Noble Truths",
        summary="A summary",
        is_active=True,
        is_archived=False,
        message_count=6,
        created_at=now,
        last_message_at=now,
    )
    usage_history = UserUsage(user_id=11, usage_date=date.today(), chat_count=4, tokens_used=1200)

    user_result = Mock()
    user_result.scalar_one_or_none.return_value = user
    today_usage_result = Mock()
    today_usage_result.scalar_one_or_none.return_value = today_usage
    social_result = Mock()
    social_result.scalars.return_value.all.return_value = [identity]
    sessions_result = Mock()
    sessions_result.scalars.return_value.all.return_value = [session]
    usage_history_result = Mock()
    usage_history_result.scalars.return_value.all.return_value = [usage_history]
    audit_result = Mock()
    audit_result.all.return_value = []

    mock_db.execute.side_effect = [
        user_result,
        today_usage_result,
        social_result,
        sessions_result,
        usage_history_result,
        audit_result,
    ]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/admin/users/11")
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["nickname"] == "Seeker"
    assert payload["social_accounts"][0]["provider"] == "google"
    assert payload["recent_sessions"][0]["session_uuid"] == "session-abc"
    assert payload["recent_usage"][0]["chat_count"] == 4


def test_admin_api_query_detail_returns_trace_review_and_sources():
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = make_client()

    now = datetime.now(timezone.utc)
    mock_db = AsyncMock()
    session = ChatSession(id=7, session_uuid="session-123", user_id=2, created_at=now, message_count=2)
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
    review = AdminQueryReview(id=1, message_id=102, status="open", reason="bad_answer", note="Needs follow-up", created_at=now, updated_at=now)

    selected_result = Mock()
    selected_result.one_or_none.return_value = (query_message, session, user)
    answer_result = Mock()
    answer_result.scalar_one_or_none.return_value = answer_message
    review_result = Mock()
    review_result.scalar_one_or_none.return_value = review
    mock_db.execute.side_effect = [selected_result, answer_result, review_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/admin/queries/101")
    assert response.status_code == 200
    payload = response.json()
    assert payload["review_target_message_id"] == 102
    assert payload["answer"]["provider"] == "gemini_vertex"
    assert payload["answer"]["trace_json"]["prompt"]["id"] == "normal_v1"
    assert payload["review"]["status"] == "open"


@patch("backend.app.admin._log_admin_action", new_callable=AsyncMock)
def test_admin_api_query_review_upserts_and_audits(mock_log_action):
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = make_client()

    mock_db = AsyncMock()
    message = ChatMessage(id=102, session_id=7, role="assistant", content="Answer")
    message_result = Mock()
    message_result.scalar_one_or_none.return_value = message
    existing_review_result = Mock()
    existing_review_result.scalar_one_or_none.return_value = None

    created_review = AdminQueryReview(
        id=4,
        message_id=102,
        status="open",
        reason="bad_answer",
        note="Escalate",
        created_by_admin_id=1,
        updated_by_admin_id=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    refresh_mock = AsyncMock()
    refresh_mock.side_effect = lambda obj: None
    mock_db.refresh = refresh_mock
    mock_db.add = Mock()
    mock_db.execute.side_effect = [message_result, existing_review_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    def add_and_capture(obj):
        if isinstance(obj, AdminQueryReview):
            obj.id = created_review.id
            obj.created_at = created_review.created_at
            obj.updated_at = created_review.updated_at
        return None

    mock_db.add.side_effect = add_and_capture

    response = client.patch("/api/admin/queries/102/review", json={"status": "open", "reason": "bad_answer", "note": "Escalate"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "open"
    assert payload["reason"] == "bad_answer"
    assert mock_log_action.call_args.kwargs["action"] == "query.review"


def test_admin_api_query_review_forbidden_for_analyst():
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_analyst
    client = make_client()
    response = client.patch("/api/admin/queries/102/review", json={"status": "resolved"})
    assert response.status_code == 403


def test_admin_api_session_detail_returns_timeline():
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = make_client()

    now = datetime.now(timezone.utc)
    mock_db = AsyncMock()
    session = ChatSession(id=7, session_uuid="session-123", user_id=2, created_at=now, last_message_at=now, message_count=2, is_active=True, is_archived=False)
    user = User(id=2, role="user", email="testuser@example.com", nickname="TestUser", is_active=True, daily_chat_limit=20)
    query_message = ChatMessage(id=101, session_id=7, role="user", content="Question", created_at=now)
    answer_message = ChatMessage(id=102, session_id=7, role="assistant", content="Answer", created_at=now, trace_json={"provider": "gemini_vertex"}, sources_count=2)
    review = AdminQueryReview(id=1, message_id=102, status="resolved")

    session_result = Mock()
    session_result.one_or_none.return_value = (session, user)
    messages_result = Mock()
    messages_result.all.return_value = [(query_message, None), (answer_message, review)]
    mock_db.execute.side_effect = [session_result, messages_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/admin/sessions/session-123")
    assert response.status_code == 200
    payload = response.json()
    assert payload["session_uuid"] == "session-123"
    assert len(payload["messages"]) == 2
    assert payload["messages"][1]["provider"] == "gemini_vertex"
    assert payload["messages"][1]["review_status"] == "resolved"


def test_admin_api_data_explorer_schema_and_rows():
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_analyst
    client = make_client()

    schema_response = client.get("/api/admin/data/tables/users/schema")
    assert schema_response.status_code == 200
    columns = schema_response.json()["columns"]
    assert any(column["name"] == "email" for column in columns)

    mock_db = AsyncMock()
    count_result = Mock()
    count_result.scalar_one.return_value = 1
    row_result = Mock()
    row_result.scalars.return_value.all.return_value = [
        User(id=55, role="user", email="person@example.com", nickname="Person", is_active=True, daily_chat_limit=20)
    ]
    mock_db.execute.side_effect = [count_result, row_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    rows_response = client.get("/api/admin/data/tables/users/rows")
    assert rows_response.status_code == 200
    payload = rows_response.json()
    assert payload["total"] == 1
    assert payload["rows"][0]["email"].startswith("pe")
    assert payload["rows"][0]["nickname"] == "Person"


@patch("backend.app.admin.analyze_observability_messages")
@patch("backend.app.admin.analyze_observability_logs")
def test_admin_api_observability_returns_reliability_metrics(
    mock_analyze_observability,
    mock_analyze_observability_messages,
):
    app.dependency_overrides[get_current_user_required] = override_get_current_user_required_admin
    client = make_client()

    mock_analyze_observability.return_value = {
        "usage_log_available": True,
        "total_queries": 120,
        "cache_hit_rate": 25.0,
        "by_day": {
            "2026-04-16": {
                "cached_queries": 5,
                "cache_hit_rate": 25.0,
            }
        },
    }
    mock_analyze_observability_messages.return_value = {
        "window_days": 7,
        "metrics_source": "database",
        "latency_metrics_available": True,
        "cache_metrics_available": True,
        "cost_metrics_available": True,
        "cost_metrics_estimated": True,
        "total_queries": 110,
        "queries_with_latency": 100,
        "queries_with_cost": 95,
        "cache_queries_sample": 8,
        "cache_hit_rate": 7.27,
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
                "cached_queries": 2,
                "cache_hit_rate": 10.0,
                "avg_latency_ms": 1700,
                "p95_latency_ms": 3500,
            }
        },
    }

    mock_db = AsyncMock()
    messages_result = Mock()
    messages_result.all.return_value = [("2026-04-16T00:00:00Z", 1200, 800, "gemini-2.5-pro", "normal")]
    answers_result = Mock()
    answers_result.one.return_value = (10, 2, 3.4)
    user_limits_result = Mock()
    user_limits_result.scalar_one.return_value = 4
    anon_limits_result = Mock()
    anon_limits_result.scalar_one.return_value = 7
    mock_db.execute.side_effect = [messages_result, answers_result, user_limits_result, anon_limits_result]
    app.dependency_overrides[get_db] = lambda: mock_db

    response = client.get("/api/admin/observability?days=7")
    assert response.status_code == 200
    payload = response.json()
    assert payload["window_days"] == 7
    assert payload["metrics_source"] == "database"
    assert payload["usage_log_available"] is True
    assert payload["latency_metrics_available"] is True
    assert payload["cache_metrics_available"] is True
    assert payload["cost_metrics_available"] is True
    assert payload["cost_metrics_estimated"] is True
    assert payload["queries_with_cost"] == 95
    assert payload["cache_queries_sample"] == 8
    assert payload["cache_hit_rate"] == 7.27
    assert payload["avg_cost_per_query_usd"] == 0.012345
    assert payload["zero_source_answers_24h"] == 2
    assert payload["zero_source_rate_24h"] == 20.0
    assert payload["rate_limited_users_today"] == 4
