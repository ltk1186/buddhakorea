"""
Admin API Router
================
Internal-only endpoints for operations, support, analytics, and safe data exploration.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import String, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .dependencies import require_roles
from .models.admin_audit_log import AdminAuditLog
from .models.admin_query_review import AdminQueryReview
from .models.chat import ChatMessage, ChatSession
from .models.social_account import SocialAccount
from .models.user import User
from .models.user_usage import ANONYMOUS_DAILY_LIMIT, AnonymousUsage, UserUsage
from .privacy import mask_pii
from .quota import get_client_ip, hash_ip
from .usage_tracker import (
    analyze_observability_logs,
    analyze_observability_messages,
    analyze_usage_logs,
    get_recent_queries,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])

READ_ROLES = {"admin", "ops", "support", "analyst"}
USER_EDIT_ROLES = {"admin", "ops", "support"}
AUDIT_READ_ROLES = {"admin", "ops"}
REVIEW_WRITE_ROLES = {"admin", "ops", "support"}
FULL_PII_ROLES = {"admin", "ops", "support"}
REVIEW_STATUSES = {"open", "resolved", "ignored"}
REVIEW_REASONS = {
    "bad_answer",
    "hallucination",
    "missing_source",
    "bad_source",
    "abuse",
    "other",
}


class AdminSummaryResponse(BaseModel):
    users_total: int
    users_active: int
    users_suspended: int
    today_queries_logged_in: int
    today_queries_anonymous: int
    today_tokens_used: int
    messages_last_24h: int
    usage_last_7_days: Dict[str, Any]


class AdminUserSummary(BaseModel):
    id: int
    email: Optional[str]
    nickname: str
    role: str
    is_active: bool
    daily_chat_limit: int
    last_login: Optional[str]
    created_at: Optional[str]
    today_usage: int


class AdminUserIdentity(BaseModel):
    id: int
    provider: str
    provider_user_id: str
    provider_email: Optional[str]
    token_expires_at: Optional[str]
    created_at: Optional[str]
    last_used_at: Optional[str]


class AdminUserSessionSummary(BaseModel):
    id: int
    session_uuid: str
    title: Optional[str]
    summary: Optional[str]
    is_active: bool
    is_archived: bool
    message_count: int
    created_at: Optional[str]
    last_message_at: Optional[str]


class AdminUserUsageEntry(BaseModel):
    usage_date: str
    chat_count: int
    tokens_used: int


class AdminUserDetailResponse(BaseModel):
    user: AdminUserSummary
    social_accounts: List[AdminUserIdentity]
    recent_sessions: List[AdminUserSessionSummary]
    recent_usage: List[AdminUserUsageEntry]
    recent_audit: List[Dict[str, Any]]


class AdminUserUpdateRequest(BaseModel):
    daily_chat_limit: Optional[int] = Field(default=None, ge=0, le=1000)
    is_active: Optional[bool] = None


class AdminQueryReviewSummary(BaseModel):
    id: int
    message_id: int
    status: str
    reason: Optional[str]
    note: Optional[str]
    created_by_admin_id: Optional[int]
    updated_by_admin_id: Optional[int]
    created_at: Optional[str]
    updated_at: Optional[str]


class AdminQueryReviewUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(open|resolved|ignored)$")
    reason: Optional[str] = None
    note: Optional[str] = Field(default=None, max_length=4000)


class AdminQueryEntry(BaseModel):
    id: int
    session_uuid: Optional[str]
    user_id: Optional[int]
    user_nickname: Optional[str]
    user_email: Optional[str]
    role: str
    content: str
    model_used: Optional[str]
    sources_count: int
    response_mode: Optional[str]
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    created_at: str
    sources_json: Optional[Any]
    review_status: Optional[str] = None


class AdminQueryMessageDetail(BaseModel):
    id: int
    role: str
    content: str
    created_at: str


class AdminQueryAnswerDetail(BaseModel):
    id: int
    content: str
    created_at: str
    model_used: Optional[str]
    provider: Optional[str]
    response_mode: Optional[str]
    tokens_used: Optional[int]
    latency_ms: Optional[int]
    sources_count: int
    sources_json: Optional[Any]
    trace_json: Optional[Any]


class AdminQueryDetailResponse(BaseModel):
    selected_message_id: int
    review_target_message_id: Optional[int]
    session_uuid: Optional[str]
    session_message_count: int
    user_id: Optional[int]
    user_nickname: Optional[str]
    user_email: Optional[str]
    query: Optional[AdminQueryMessageDetail]
    answer: Optional[AdminQueryAnswerDetail]
    review: Optional[AdminQueryReviewSummary]


class AdminSessionTimelineMessage(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    model_used: Optional[str]
    response_mode: Optional[str]
    provider: Optional[str]
    sources_count: int
    review_status: Optional[str]


class AdminSessionDetailResponse(BaseModel):
    id: int
    session_uuid: str
    user_id: Optional[int]
    user_nickname: Optional[str]
    user_email: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    is_active: bool
    is_archived: bool
    message_count: int
    created_at: Optional[str]
    last_message_at: Optional[str]
    messages: List[AdminSessionTimelineMessage]


class AdminAuditEntry(BaseModel):
    id: int
    admin_user_id: Optional[int]
    admin_email: Optional[str]
    action: str
    target_type: str
    target_id: Optional[str]
    before_state: Optional[Dict[str, Any]]
    after_state: Optional[Dict[str, Any]]
    context: Optional[Dict[str, Any]]
    created_at: str


class AdminReliabilityDayEntry(BaseModel):
    date: str
    queries: int
    cost_usd: Optional[float]
    cached_queries: Optional[int]
    cache_hit_rate: Optional[float]
    avg_latency_ms: Optional[int]
    p95_latency_ms: Optional[int]


class AdminReliabilityResponse(BaseModel):
    window_days: int
    metrics_source: str
    usage_log_available: bool
    latency_metrics_available: bool
    cache_metrics_available: bool
    cost_metrics_available: bool
    cost_metrics_estimated: bool
    total_queries: int
    queries_with_latency: int
    queries_with_cost: int
    cache_queries_sample: int
    cache_hit_rate: Optional[float]
    avg_cost_per_query_usd: Optional[float]
    avg_latency_ms: Optional[int]
    p50_latency_ms: Optional[int]
    p95_latency_ms: Optional[int]
    slow_query_threshold_ms: int
    slow_queries: int
    answers_last_24h: int
    zero_source_answers_24h: int
    zero_source_rate_24h: float
    avg_sources_per_answer_24h: float
    rate_limited_users_today: int
    rate_limited_anonymous_today: int
    daily: List[AdminReliabilityDayEntry]


class AdminDataTableSummary(BaseModel):
    name: str
    label: str
    description: str
    searchable_columns: List[str]


class AdminDataTableColumn(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool


class AdminDataTableSchemaResponse(BaseModel):
    table: AdminDataTableSummary
    columns: List[AdminDataTableColumn]


class AdminDataTableRowsResponse(BaseModel):
    table: AdminDataTableSummary
    total: int
    limit: int
    offset: int
    rows: List[Dict[str, Any]]


def _mask_email(email: Optional[str]) -> Optional[str]:
    if not email:
        return None
    parts = email.split("@")
    if len(parts) != 2:
        return "***"
    local, domain = parts
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[:2] + "*" * (len(local) - 2)
    return f"{masked_local}@{domain}"


def _iso(value: Any) -> Optional[str]:
    return value.isoformat() if value else None


def _can_view_email(admin_user: User) -> bool:
    return admin_user.role in FULL_PII_ROLES


def _serialize_user_summary(user: User, today_usage: int, admin_user: User) -> AdminUserSummary:
    email = user.email if _can_view_email(admin_user) else _mask_email(user.email)
    return AdminUserSummary(
        id=user.id,
        email=email,
        nickname=user.nickname,
        role=user.role,
        is_active=user.is_active,
        daily_chat_limit=user.daily_chat_limit,
        last_login=_iso(user.last_login),
        created_at=_iso(user.created_at),
        today_usage=today_usage,
    )


def _serialize_review(review: Optional[AdminQueryReview]) -> Optional[AdminQueryReviewSummary]:
    if not review:
        return None
    return AdminQueryReviewSummary(
        id=review.id,
        message_id=review.message_id,
        status=review.status,
        reason=review.reason,
        note=review.note,
        created_by_admin_id=review.created_by_admin_id,
        updated_by_admin_id=review.updated_by_admin_id,
        created_at=_iso(review.created_at),
        updated_at=_iso(review.updated_at),
    )


async def _log_admin_action(
    db: AsyncSession,
    request: Request,
    admin_user: User,
    action: str,
    target_type: str,
    target_id: Optional[str],
    before_state: Optional[Dict[str, Any]],
    after_state: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None,
) -> None:
    ip = get_client_ip(request)
    entry = AdminAuditLog(
        admin_user_id=admin_user.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        before_state=before_state,
        after_state=after_state,
        context=context,
        ip_hash=hash_ip(ip) if ip and ip != "unknown" else None,
        user_agent=request.headers.get("User-Agent"),
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()


def _build_table_summary(name: str, config: Dict[str, Any]) -> AdminDataTableSummary:
    return AdminDataTableSummary(
        name=name,
        label=config["label"],
        description=config["description"],
        searchable_columns=config["searchable_columns"],
    )


def _serialize_explorer_value(column_name: str, value: Any, admin_user: User) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if column_name in {"email", "provider_email"}:
        return value if _can_view_email(admin_user) else _mask_email(value)
    if column_name == "content":
        return mask_pii(value)
    if column_name in {"access_token", "refresh_token", "access_token_encrypted", "refresh_token_encrypted"}:
        return "[redacted]"
    return value


EXPLORER_TABLES: Dict[str, Dict[str, Any]] = {
    "users": {
        "label": "Users",
        "description": "Core account records and support controls.",
        "model": User,
        "searchable_columns": ["email", "nickname", "role"],
        "hidden_columns": set(),
    },
    "social_accounts": {
        "label": "Social Accounts",
        "description": "OAuth provider identities linked to users.",
        "model": SocialAccount,
        "searchable_columns": ["provider", "provider_user_id", "provider_email"],
        "hidden_columns": {"access_token", "refresh_token", "access_token_encrypted", "refresh_token_encrypted", "raw_profile"},
    },
    "chat_sessions": {
        "label": "Chat Sessions",
        "description": "Conversation sessions and summary metadata.",
        "model": ChatSession,
        "searchable_columns": ["session_uuid", "title", "summary"],
        "hidden_columns": set(),
    },
    "chat_messages": {
        "label": "Chat Messages",
        "description": "Persisted user and assistant messages.",
        "model": ChatMessage,
        "searchable_columns": ["role", "content", "model_used", "response_mode"],
        "hidden_columns": set(),
    },
    "user_usage": {
        "label": "User Usage",
        "description": "Daily logged-in usage counters.",
        "model": UserUsage,
        "searchable_columns": ["user_id"],
        "hidden_columns": set(),
    },
    "anonymous_usage": {
        "label": "Anonymous Usage",
        "description": "Daily anonymous usage counters by hashed IP.",
        "model": AnonymousUsage,
        "searchable_columns": ["ip_hash"],
        "hidden_columns": set(),
    },
    "admin_audit_logs": {
        "label": "Admin Audit Logs",
        "description": "Immutable admin action history.",
        "model": AdminAuditLog,
        "searchable_columns": ["action", "target_type", "target_id"],
        "hidden_columns": set(),
    },
    "admin_query_reviews": {
        "label": "Query Reviews",
        "description": "Operator review state for problematic messages.",
        "model": AdminQueryReview,
        "searchable_columns": ["status", "reason", "message_id"],
        "hidden_columns": set(),
    },
}


def _get_explorer_config(table_name: str) -> Dict[str, Any]:
    config = EXPLORER_TABLES.get(table_name)
    if not config:
        raise HTTPException(status_code=404, detail="Explorer table not found")
    return config


@router.get("/me")
async def get_admin_me(admin_user: User = Depends(require_roles(READ_ROLES))) -> Dict[str, Any]:
    return {
        "id": admin_user.id,
        "email": admin_user.email,
        "nickname": admin_user.nickname,
        "role": admin_user.role,
        "is_active": admin_user.is_active,
    }


@router.get("/summary", response_model=AdminSummaryResponse)
async def get_admin_summary(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> AdminSummaryResponse:
    users_total_stmt = select(func.count(User.id))
    users_active_stmt = select(func.count(User.id)).where(User.is_active == True)
    total_result = await db.execute(users_total_stmt)
    active_result = await db.execute(users_active_stmt)
    users_total = total_result.scalar_one() or 0
    users_active = active_result.scalar_one() or 0
    users_suspended = max(0, users_total - users_active)

    today = date.today()
    usage_stmt = select(
        func.coalesce(func.sum(UserUsage.chat_count), 0),
        func.coalesce(func.sum(UserUsage.tokens_used), 0),
    ).where(UserUsage.usage_date == today)
    usage_result = await db.execute(usage_stmt)
    today_queries_logged_in, today_tokens_used = usage_result.one()

    anon_stmt = select(func.coalesce(func.sum(AnonymousUsage.chat_count), 0)).where(
        AnonymousUsage.usage_date == today
    )
    anon_result = await db.execute(anon_stmt)
    today_queries_anonymous = anon_result.scalar_one() or 0

    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_messages_stmt = select(func.count(ChatMessage.id)).where(ChatMessage.created_at >= cutoff)
    recent_messages_result = await db.execute(recent_messages_stmt)
    messages_last_24h = recent_messages_result.scalar_one() or 0

    usage_last_7_days = analyze_usage_logs(days=7)

    return AdminSummaryResponse(
        users_total=users_total,
        users_active=users_active,
        users_suspended=users_suspended,
        today_queries_logged_in=int(today_queries_logged_in or 0),
        today_queries_anonymous=int(today_queries_anonymous or 0),
        today_tokens_used=int(today_tokens_used or 0),
        messages_last_24h=messages_last_24h,
        usage_last_7_days=usage_last_7_days,
    )


@router.get("/users", response_model=List[AdminUserSummary])
async def list_users(
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> List[AdminUserSummary]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    stmt = select(User).order_by(User.created_at.desc())
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.nickname.ilike(like)))
    if status == "active":
        stmt = stmt.where(User.is_active == True)
    elif status == "suspended":
        stmt = stmt.where(User.is_active == False)

    result = await db.execute(stmt.offset(offset).limit(limit))
    users = result.scalars().all()
    user_ids = [user.id for user in users]

    usage_map: Dict[int, int] = {}
    if user_ids:
        usage_result = await db.execute(
            select(UserUsage).where(UserUsage.user_id.in_(user_ids), UserUsage.usage_date == date.today())
        )
        for usage in usage_result.scalars().all():
            usage_map[usage.user_id] = usage.chat_count

    return [_serialize_user_summary(user, usage_map.get(user.id, 0), admin_user) for user in users]


@router.get("/users/{user_id}", response_model=AdminUserDetailResponse)
async def get_user_detail(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> AdminUserDetailResponse:
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    usage_result = await db.execute(
        select(UserUsage).where(UserUsage.user_id == user_id, UserUsage.usage_date == date.today())
    )
    today_usage = usage_result.scalar_one_or_none()

    social_result = await db.execute(
        select(SocialAccount).where(SocialAccount.user_id == user_id).order_by(SocialAccount.created_at.asc())
    )
    sessions_result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.last_message_at.desc(), ChatSession.id.desc())
        .limit(10)
    )
    usage_history_result = await db.execute(
        select(UserUsage)
        .where(UserUsage.user_id == user_id)
        .order_by(UserUsage.usage_date.desc())
        .limit(14)
    )
    audit_result = await db.execute(
        select(AdminAuditLog, User)
        .outerjoin(User, AdminAuditLog.admin_user_id == User.id)
        .where(AdminAuditLog.target_type == "user", AdminAuditLog.target_id == str(user_id))
        .order_by(AdminAuditLog.created_at.desc())
        .limit(10)
    )

    identities = []
    for account in social_result.scalars().all():
        provider_email = account.provider_email if _can_view_email(admin_user) else _mask_email(account.provider_email)
        identities.append(
            AdminUserIdentity(
                id=account.id,
                provider=account.provider,
                provider_user_id=account.provider_user_id,
                provider_email=provider_email,
                token_expires_at=_iso(account.token_expires_at),
                created_at=_iso(account.created_at),
                last_used_at=_iso(account.last_used_at),
            )
        )

    sessions = [
        AdminUserSessionSummary(
            id=session.id,
            session_uuid=session.session_uuid,
            title=session.title,
            summary=mask_pii(session.summary) if session.summary else None,
            is_active=session.is_active,
            is_archived=session.is_archived,
            message_count=session.message_count or 0,
            created_at=_iso(session.created_at),
            last_message_at=_iso(session.last_message_at),
        )
        for session in sessions_result.scalars().all()
    ]

    recent_usage = [
        AdminUserUsageEntry(
            usage_date=entry.usage_date.isoformat(),
            chat_count=entry.chat_count,
            tokens_used=entry.tokens_used,
        )
        for entry in usage_history_result.scalars().all()
    ]

    recent_audit = []
    for audit_entry, audit_admin in audit_result.all():
        recent_audit.append(
            {
                "id": audit_entry.id,
                "admin_email": audit_admin.email if audit_admin else None,
                "action": audit_entry.action,
                "before_state": audit_entry.before_state,
                "after_state": audit_entry.after_state,
                "created_at": _iso(audit_entry.created_at),
            }
        )

    return AdminUserDetailResponse(
        user=_serialize_user_summary(user, today_usage.chat_count if today_usage else 0, admin_user),
        social_accounts=identities,
        recent_sessions=sessions,
        recent_usage=recent_usage,
        recent_audit=recent_audit,
    )


@router.get("/users/{user_id}/sessions", response_model=List[AdminUserSessionSummary])
async def get_user_sessions(
    user_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> List[AdminUserSessionSummary]:
    limit = min(max(limit, 1), 50)
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == user_id)
        .order_by(ChatSession.last_message_at.desc(), ChatSession.id.desc())
        .limit(limit)
    )
    return [
        AdminUserSessionSummary(
            id=session.id,
            session_uuid=session.session_uuid,
            title=session.title,
            summary=mask_pii(session.summary) if session.summary else None,
            is_active=session.is_active,
            is_archived=session.is_archived,
            message_count=session.message_count or 0,
            created_at=_iso(session.created_at),
            last_message_at=_iso(session.last_message_at),
        )
        for session in result.scalars().all()
    ]


@router.get("/users/{user_id}/usage", response_model=List[AdminUserUsageEntry])
async def get_user_usage(
    user_id: int,
    days: int = 14,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> List[AdminUserUsageEntry]:
    days = min(max(days, 1), 60)
    cutoff = date.today() - timedelta(days=days - 1)
    result = await db.execute(
        select(UserUsage)
        .where(UserUsage.user_id == user_id, UserUsage.usage_date >= cutoff)
        .order_by(UserUsage.usage_date.desc())
    )
    return [
        AdminUserUsageEntry(
            usage_date=entry.usage_date.isoformat(),
            chat_count=entry.chat_count,
            tokens_used=entry.tokens_used,
        )
        for entry in result.scalars().all()
    ]


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
async def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(USER_EDIT_ROLES)),
) -> AdminUserSummary:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    before_state = {"daily_chat_limit": user.daily_chat_limit, "is_active": user.is_active}
    updated = False
    if payload.daily_chat_limit is not None:
        user.daily_chat_limit = payload.daily_chat_limit
        updated = True
    if payload.is_active is not None:
        user.is_active = payload.is_active
        updated = True
    if not updated:
        raise HTTPException(status_code=400, detail="No fields provided for update")

    await db.commit()
    await db.refresh(user)

    after_state = {"daily_chat_limit": user.daily_chat_limit, "is_active": user.is_active}
    await _log_admin_action(
        db=db,
        request=request,
        admin_user=admin_user,
        action="user.update",
        target_type="user",
        target_id=str(user.id),
        before_state=before_state,
        after_state=after_state,
        context={"source": "admin_api"},
    )

    usage_result = await db.execute(
        select(UserUsage).where(UserUsage.user_id == user.id, UserUsage.usage_date == date.today())
    )
    usage_record = usage_result.scalar_one_or_none()
    return _serialize_user_summary(user, usage_record.chat_count if usage_record else 0, admin_user)


@router.get("/queries", response_model=List[AdminQueryEntry])
async def list_queries(
    limit: int = 50,
    offset: int = 0,
    role: Optional[str] = None,
    session_uuid: Optional[str] = None,
    user_id: Optional[int] = None,
    review_status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> List[AdminQueryEntry]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    stmt = (
        select(ChatMessage, ChatSession, User, AdminQueryReview)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .outerjoin(User, ChatSession.user_id == User.id)
        .outerjoin(AdminQueryReview, AdminQueryReview.message_id == ChatMessage.id)
    )
    if role:
        stmt = stmt.where(ChatMessage.role == role)
    if session_uuid:
        stmt = stmt.where(ChatSession.session_uuid == session_uuid)
    if user_id:
        stmt = stmt.where(ChatSession.user_id == user_id)
    if review_status == "unreviewed":
        stmt = stmt.where(AdminQueryReview.id.is_(None))
    elif review_status in REVIEW_STATUSES:
        stmt = stmt.where(AdminQueryReview.status == review_status)

    result = await db.execute(stmt.order_by(ChatMessage.created_at.desc()).offset(offset).limit(limit))
    entries = result.all()

    response_entries = []
    for message, session, user, review in entries:
        email = user.email if (user and _can_view_email(admin_user)) else _mask_email(user.email if user else None)
        masked_content = mask_pii(message.content)
        if len(masked_content) > 400:
            masked_content = masked_content[:400] + "..."
        response_entries.append(
            AdminQueryEntry(
                id=message.id,
                session_uuid=session.session_uuid if session else None,
                user_id=user.id if user else None,
                user_nickname=user.nickname if user else None,
                user_email=email,
                role=message.role,
                content=masked_content,
                model_used=message.model_used,
                sources_count=message.sources_count or 0,
                response_mode=message.response_mode,
                tokens_used=message.tokens_used,
                latency_ms=message.latency_ms,
                created_at=_iso(message.created_at) or "",
                sources_json=message.sources_json,
                review_status=review.status if review else None,
            )
        )
    return response_entries


@router.get("/queries/{message_id}", response_model=AdminQueryDetailResponse)
async def get_query_detail(
    message_id: int,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> AdminQueryDetailResponse:
    result = await db.execute(
        select(ChatMessage, ChatSession, User)
        .join(ChatSession, ChatMessage.session_id == ChatSession.id)
        .outerjoin(User, ChatSession.user_id == User.id)
        .where(ChatMessage.id == message_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Query message not found")

    selected_message, session, user = row
    email = user.email if (user and _can_view_email(admin_user)) else _mask_email(user.email if user else None)

    query_message: Optional[ChatMessage] = None
    answer_message: Optional[ChatMessage] = None
    if selected_message.role == "assistant":
        answer_result = await db.execute(select(ChatMessage).where(ChatMessage.id == selected_message.id))
        answer_message = answer_result.scalar_one_or_none()
        query_result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == selected_message.session_id,
                ChatMessage.role == "user",
                ChatMessage.created_at <= selected_message.created_at,
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        query_message = query_result.scalar_one_or_none()
    else:
        query_message = selected_message
        answer_result = await db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == selected_message.session_id,
                ChatMessage.role == "assistant",
                ChatMessage.created_at >= selected_message.created_at,
            )
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .limit(1)
        )
        answer_message = answer_result.scalar_one_or_none()

    review_target_message_id = answer_message.id if answer_message else selected_message.id
    review_result = await db.execute(select(AdminQueryReview).where(AdminQueryReview.message_id == review_target_message_id))
    review = review_result.scalar_one_or_none()

    return AdminQueryDetailResponse(
        selected_message_id=selected_message.id,
        review_target_message_id=review_target_message_id,
        session_uuid=session.session_uuid if session else None,
        session_message_count=session.message_count or 0,
        user_id=user.id if user else None,
        user_nickname=user.nickname if user else None,
        user_email=email,
        query=AdminQueryMessageDetail(
            id=query_message.id,
            role=query_message.role,
            content=mask_pii(query_message.content),
            created_at=_iso(query_message.created_at) or "",
        ) if query_message else None,
        answer=AdminQueryAnswerDetail(
            id=answer_message.id,
            content=mask_pii(answer_message.content),
            created_at=_iso(answer_message.created_at) or "",
            model_used=answer_message.model_used,
            provider=(answer_message.trace_json or {}).get("provider"),
            response_mode=answer_message.response_mode,
            tokens_used=answer_message.tokens_used,
            latency_ms=answer_message.latency_ms,
            sources_count=answer_message.sources_count or 0,
            sources_json=answer_message.sources_json,
            trace_json=answer_message.trace_json or None,
        ) if answer_message else None,
        review=_serialize_review(review),
    )


@router.patch("/queries/{message_id}/review", response_model=AdminQueryReviewSummary)
async def update_query_review(
    message_id: int,
    payload: AdminQueryReviewUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(REVIEW_WRITE_ROLES)),
) -> AdminQueryReviewSummary:
    if payload.reason and payload.reason not in REVIEW_REASONS:
        raise HTTPException(status_code=400, detail="Invalid review reason")

    message_result = await db.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    message = message_result.scalar_one_or_none()
    if not message:
        raise HTTPException(status_code=404, detail="Query message not found")

    review_result = await db.execute(select(AdminQueryReview).where(AdminQueryReview.message_id == message_id))
    review = review_result.scalar_one_or_none()
    before_state = None
    if review:
        before_state = {"status": review.status, "reason": review.reason, "note": review.note}
        review.status = payload.status
        review.reason = payload.reason
        review.note = payload.note
        review.updated_by_admin_id = admin_user.id
        review.updated_at = datetime.now(timezone.utc)
    else:
        review = AdminQueryReview(
            message_id=message_id,
            status=payload.status,
            reason=payload.reason,
            note=payload.note,
            created_by_admin_id=admin_user.id,
            updated_by_admin_id=admin_user.id,
        )
        db.add(review)

    await db.commit()
    await db.refresh(review)

    await _log_admin_action(
        db=db,
        request=request,
        admin_user=admin_user,
        action="query.review",
        target_type="chat_message",
        target_id=str(message_id),
        before_state=before_state,
        after_state={"status": review.status, "reason": review.reason, "note": review.note},
        context={"source": "admin_api"},
    )
    return _serialize_review(review)


@router.get("/sessions/{session_uuid}", response_model=AdminSessionDetailResponse)
async def get_session_detail(
    session_uuid: str,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> AdminSessionDetailResponse:
    session_result = await db.execute(
        select(ChatSession, User)
        .outerjoin(User, ChatSession.user_id == User.id)
        .where(ChatSession.session_uuid == session_uuid)
    )
    row = session_result.one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    session, user = row
    email = user.email if (user and _can_view_email(admin_user)) else _mask_email(user.email if user else None)

    messages_result = await db.execute(
        select(ChatMessage, AdminQueryReview)
        .outerjoin(AdminQueryReview, AdminQueryReview.message_id == ChatMessage.id)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )

    messages = []
    for message, review in messages_result.all():
        messages.append(
            AdminSessionTimelineMessage(
                id=message.id,
                role=message.role,
                content=mask_pii(message.content),
                created_at=_iso(message.created_at) or "",
                model_used=message.model_used,
                response_mode=message.response_mode,
                provider=(message.trace_json or {}).get("provider"),
                sources_count=message.sources_count or 0,
                review_status=review.status if review else None,
            )
        )

    return AdminSessionDetailResponse(
        id=session.id,
        session_uuid=session.session_uuid,
        user_id=user.id if user else None,
        user_nickname=user.nickname if user else None,
        user_email=email,
        title=session.title,
        summary=mask_pii(session.summary) if session.summary else None,
        is_active=bool(session.is_active),
        is_archived=bool(session.is_archived),
        message_count=session.message_count or 0,
        created_at=_iso(session.created_at),
        last_message_at=_iso(session.last_message_at),
        messages=messages,
    )


@router.get("/usage-stats")
async def get_admin_usage_stats(
    days: int = 7,
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> Dict[str, Any]:
    days = min(max(1, days), 90)
    stats = analyze_usage_logs(days=days)
    return {
        "period_days": days,
        "total_queries": stats.get("total_queries", 0),
        "cached_queries": stats.get("cached_queries", 0),
        "api_queries": stats.get("total_queries", 0) - stats.get("cached_queries", 0),
        "total_cost_usd": round(stats.get("total_cost", 0.0), 4),
        "tokens": {
            "input": stats.get("input_tokens", 0),
            "output": stats.get("output_tokens", 0),
            "total": stats.get("total_tokens", 0),
        },
        "by_mode": stats.get("by_mode", {}),
        "by_model": stats.get("by_model", {}),
        "by_day": stats.get("by_day", {}),
    }


@router.get("/usage/recent")
async def get_admin_recent_usage(
    limit: int = 20,
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> List[Dict[str, Any]]:
    limit = min(max(limit, 1), 100)
    return get_recent_queries(limit=limit)


@router.get("/observability", response_model=AdminReliabilityResponse)
async def get_admin_observability(
    days: int = 7,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> AdminReliabilityResponse:
    days = min(max(1, days), 30)
    reliability = analyze_observability_logs(days=days)
    cutoff_window = datetime.now(timezone.utc) - timedelta(days=days)
    messages_result = await db.execute(
        select(
            ChatMessage.created_at,
            ChatMessage.latency_ms,
            ChatMessage.tokens_used,
            ChatMessage.model_used,
            ChatMessage.response_mode,
        ).where(ChatMessage.role == "assistant", ChatMessage.created_at >= cutoff_window)
    )
    message_rows = messages_result.all()
    db_reliability = analyze_observability_messages(message_rows, days=days)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    answers_result = await db.execute(
        select(
            func.count(ChatMessage.id),
            func.coalesce(func.sum(case((ChatMessage.sources_count == 0, 1), else_=0)), 0),
            func.coalesce(func.avg(ChatMessage.sources_count), 0.0),
        ).where(ChatMessage.role == "assistant", ChatMessage.created_at >= cutoff)
    )
    answers_last_24h, zero_source_answers_24h, avg_sources_per_answer_24h = answers_result.one()

    today = date.today()
    rate_limited_users_result = await db.execute(
        select(func.count(UserUsage.id))
        .join(User, UserUsage.user_id == User.id)
        .where(UserUsage.usage_date == today, UserUsage.chat_count >= User.daily_chat_limit)
    )
    rate_limited_anonymous_result = await db.execute(
        select(func.count(AnonymousUsage.id)).where(
            AnonymousUsage.usage_date == today,
            AnonymousUsage.chat_count >= ANONYMOUS_DAILY_LIMIT,
        )
    )

    answers_count = int(answers_last_24h or 0)
    zero_source_count = int(zero_source_answers_24h or 0)
    zero_source_rate = round((zero_source_count / answers_count) * 100, 2) if answers_count > 0 else 0.0

    merged_daily = dict(db_reliability.get("by_day", {}))
    metrics_source = "database"
    daily_entries = [
        AdminReliabilityDayEntry(
            date=day,
            queries=entry["queries"],
            cost_usd=round(float(entry["cost_usd"]), 6) if entry.get("cost_usd") is not None else None,
            cached_queries=entry.get("cached_queries"),
            cache_hit_rate=float(entry["cache_hit_rate"]) if entry.get("cache_hit_rate") is not None else None,
            avg_latency_ms=entry["avg_latency_ms"],
            p95_latency_ms=entry["p95_latency_ms"],
        )
        for day, entry in sorted(merged_daily.items(), reverse=True)
    ]

    return AdminReliabilityResponse(
        window_days=db_reliability["window_days"],
        metrics_source=metrics_source,
        usage_log_available=bool(reliability.get("usage_log_available", False)),
        latency_metrics_available=bool(db_reliability.get("latency_metrics_available", False)),
        cache_metrics_available=bool(db_reliability.get("cache_metrics_available", False)),
        cost_metrics_available=bool(db_reliability.get("cost_metrics_available", False)),
        cost_metrics_estimated=bool(db_reliability.get("cost_metrics_estimated", False)),
        total_queries=db_reliability["total_queries"],
        queries_with_latency=db_reliability["queries_with_latency"],
        queries_with_cost=db_reliability["queries_with_cost"],
        cache_queries_sample=db_reliability.get("cache_queries_sample", 0),
        cache_hit_rate=(
            float(db_reliability["cache_hit_rate"])
            if db_reliability.get("cache_hit_rate") is not None
            else None
        ),
        avg_cost_per_query_usd=(
            float(db_reliability["avg_cost_per_query_usd"])
            if db_reliability.get("avg_cost_per_query_usd") is not None
            else None
        ),
        avg_latency_ms=db_reliability["avg_latency_ms"],
        p50_latency_ms=db_reliability["p50_latency_ms"],
        p95_latency_ms=db_reliability["p95_latency_ms"],
        slow_query_threshold_ms=db_reliability["slow_query_threshold_ms"],
        slow_queries=db_reliability["slow_queries"],
        answers_last_24h=answers_count,
        zero_source_answers_24h=zero_source_count,
        zero_source_rate_24h=zero_source_rate,
        avg_sources_per_answer_24h=round(float(avg_sources_per_answer_24h or 0.0), 2),
        rate_limited_users_today=int(rate_limited_users_result.scalar_one() or 0),
        rate_limited_anonymous_today=int(rate_limited_anonymous_result.scalar_one() or 0),
        daily=daily_entries,
    )


@router.get("/audit-logs", response_model=List[AdminAuditEntry])
async def list_admin_audit_logs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(AUDIT_READ_ROLES)),
) -> List[AdminAuditEntry]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)
    result = await db.execute(
        select(AdminAuditLog, User)
        .outerjoin(User, AdminAuditLog.admin_user_id == User.id)
        .order_by(AdminAuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        AdminAuditEntry(
            id=audit_log.id,
            admin_user_id=audit_log.admin_user_id,
            admin_email=user.email if user else None,
            action=audit_log.action,
            target_type=audit_log.target_type,
            target_id=audit_log.target_id,
            before_state=audit_log.before_state,
            after_state=audit_log.after_state,
            context=audit_log.context,
            created_at=_iso(audit_log.created_at) or "",
        )
        for audit_log, user in result.all()
    ]


@router.get("/data/tables", response_model=List[AdminDataTableSummary])
async def list_explorer_tables(
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> List[AdminDataTableSummary]:
    return [_build_table_summary(name, config) for name, config in EXPLORER_TABLES.items()]


@router.get("/data/tables/{table_name}/schema", response_model=AdminDataTableSchemaResponse)
async def get_explorer_table_schema(
    table_name: str,
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> AdminDataTableSchemaResponse:
    config = _get_explorer_config(table_name)
    model = config["model"]
    hidden_columns = config["hidden_columns"]
    columns = [
        AdminDataTableColumn(
            name=column.name,
            type=str(column.type),
            nullable=bool(column.nullable),
            primary_key=bool(column.primary_key),
        )
        for column in model.__table__.columns
        if column.name not in hidden_columns
    ]
    return AdminDataTableSchemaResponse(table=_build_table_summary(table_name, config), columns=columns)


@router.get("/data/tables/{table_name}/rows", response_model=AdminDataTableRowsResponse)
async def get_explorer_table_rows(
    table_name: str,
    search: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES)),
) -> AdminDataTableRowsResponse:
    config = _get_explorer_config(table_name)
    model = config["model"]
    hidden_columns = config["hidden_columns"]
    searchable_columns = config["searchable_columns"]

    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)

    stmt = select(model)
    count_stmt = select(func.count()).select_from(model)
    if search:
        like = f"%{search.strip()}%"
        filters = [getattr(model, column).cast(String).ilike(like) for column in searchable_columns]
        if filters:
            stmt = stmt.where(or_(*filters))
            count_stmt = count_stmt.where(or_(*filters))

    order_column = getattr(model, "created_at", None) or getattr(model, "usage_date", None) or getattr(model, "id")
    stmt = stmt.order_by(order_column.desc()).offset(offset).limit(limit)

    total_result = await db.execute(count_stmt)
    rows_result = await db.execute(stmt)
    rows = []
    for row in rows_result.scalars().all():
        serialized = {}
        for column in model.__table__.columns:
            if column.name in hidden_columns:
                continue
            serialized[column.name] = _serialize_explorer_value(column.name, getattr(row, column.name), admin_user)
        rows.append(serialized)

    return AdminDataTableRowsResponse(
        table=_build_table_summary(table_name, config),
        total=int(total_result.scalar_one() or 0),
        limit=limit,
        offset=offset,
        rows=rows,
    )
