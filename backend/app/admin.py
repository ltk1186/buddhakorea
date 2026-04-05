"""
Admin API Router
================
Internal-only endpoints for operations, support, and analytics.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_db
from .dependencies import require_roles
from .models.admin_audit_log import AdminAuditLog
from .models.chat import ChatMessage, ChatSession
from .models.user import User
from .models.user_usage import UserUsage, AnonymousUsage
from .privacy import mask_pii
from .quota import get_client_ip, hash_ip
from .usage_tracker import analyze_usage_logs, get_recent_queries

router = APIRouter(prefix="/api/admin", tags=["admin"])

READ_ROLES = {"admin", "ops", "support", "analyst"}
USER_EDIT_ROLES = {"admin", "ops", "support"}
AUDIT_READ_ROLES = {"admin", "ops"}


class AdminSummaryResponse(BaseModel):
    """High-level operational summary."""
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


class AdminUserUpdateRequest(BaseModel):
    daily_chat_limit: Optional[int] = Field(default=None, ge=0, le=1000)
    is_active: Optional[bool] = None


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


async def _log_admin_action(
    db: AsyncSession,
    request: Request,
    admin_user: User,
    action: str,
    target_type: str,
    target_id: Optional[str],
    before_state: Optional[Dict[str, Any]],
    after_state: Optional[Dict[str, Any]],
    context: Optional[Dict[str, Any]] = None
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
        created_at=datetime.now(timezone.utc)
    )
    db.add(entry)
    await db.commit()


@router.get("/me")
async def get_admin_me(
    admin_user: User = Depends(require_roles(READ_ROLES))
) -> Dict[str, Any]:
    return {
        "id": admin_user.id,
        "email": admin_user.email,
        "nickname": admin_user.nickname,
        "role": admin_user.role,
        "is_active": admin_user.is_active
    }


@router.get("/summary", response_model=AdminSummaryResponse)
async def get_admin_summary(
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES))
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
        func.coalesce(func.sum(UserUsage.tokens_used), 0)
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
        usage_last_7_days=usage_last_7_days
    )


@router.get("/users", response_model=List[AdminUserSummary])
async def list_users(
    search: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES))
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

    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    users = result.scalars().all()

    today = date.today()
    user_ids = [user.id for user in users]
    usage_map: Dict[int, int] = {}
    if user_ids:
        usage_stmt = select(UserUsage).where(
            UserUsage.user_id.in_(user_ids),
            UserUsage.usage_date == today
        )
        usage_result = await db.execute(usage_stmt)
        for usage in usage_result.scalars().all():
            usage_map[usage.user_id] = usage.chat_count

    can_view_email = admin_user.role in {"admin", "ops", "support"}
    summaries: List[AdminUserSummary] = []
    for user in users:
        email = user.email if can_view_email else _mask_email(user.email)
        summaries.append(
            AdminUserSummary(
                id=user.id,
                email=email,
                nickname=user.nickname,
                role=user.role,
                is_active=user.is_active,
                daily_chat_limit=user.daily_chat_limit,
                last_login=user.last_login.isoformat() if user.last_login else None,
                created_at=user.created_at.isoformat() if user.created_at else None,
                today_usage=usage_map.get(user.id, 0)
            )
        )

    return summaries


@router.patch("/users/{user_id}", response_model=AdminUserSummary)
async def update_user(
    user_id: int,
    payload: AdminUserUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(USER_EDIT_ROLES))
) -> AdminUserSummary:
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    before_state = {
        "daily_chat_limit": user.daily_chat_limit,
        "is_active": user.is_active
    }

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

    after_state = {
        "daily_chat_limit": user.daily_chat_limit,
        "is_active": user.is_active
    }

    await _log_admin_action(
        db=db,
        request=request,
        admin_user=admin_user,
        action="user.update",
        target_type="user",
        target_id=str(user.id),
        before_state=before_state,
        after_state=after_state,
        context={"source": "admin_api"}
    )

    today = date.today()
    usage_stmt = select(UserUsage).where(
        UserUsage.user_id == user.id,
        UserUsage.usage_date == today
    )
    usage_result = await db.execute(usage_stmt)
    usage_record = usage_result.scalar_one_or_none()
    today_usage = usage_record.chat_count if usage_record else 0

    return AdminUserSummary(
        id=user.id,
        email=user.email,
        nickname=user.nickname,
        role=user.role,
        is_active=user.is_active,
        daily_chat_limit=user.daily_chat_limit,
        last_login=user.last_login.isoformat() if user.last_login else None,
        created_at=user.created_at.isoformat() if user.created_at else None,
        today_usage=today_usage
    )


@router.get("/queries", response_model=List[AdminQueryEntry])
async def list_queries(
    limit: int = 50,
    offset: int = 0,
    role: Optional[str] = None,
    session_uuid: Optional[str] = None,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(READ_ROLES))
) -> List[AdminQueryEntry]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    stmt = select(ChatMessage, ChatSession, User).join(
        ChatSession,
        ChatMessage.session_id == ChatSession.id
    ).outerjoin(
        User,
        ChatSession.user_id == User.id
    )

    if role:
        stmt = stmt.where(ChatMessage.role == role)
    if session_uuid:
        stmt = stmt.where(ChatSession.session_uuid == session_uuid)
    if user_id:
        stmt = stmt.where(ChatSession.user_id == user_id)

    stmt = stmt.order_by(ChatMessage.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)
    entries = result.all()

    can_view_email = admin_user.role in {"admin", "ops", "support"}
    response_entries: List[AdminQueryEntry] = []
    for message, session, user in entries:
        email = user.email if (user and can_view_email) else _mask_email(user.email if user else None)
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
                created_at=message.created_at.isoformat() if message.created_at else "",
                sources_json=message.sources_json
            )
        )

    return response_entries


@router.get("/usage-stats")
async def get_admin_usage_stats(
    days: int = 7,
    admin_user: User = Depends(require_roles(READ_ROLES))
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
            "total": stats.get("total_tokens", 0)
        },
        "by_mode": stats.get("by_mode", {}),
        "by_model": stats.get("by_model", {}),
        "by_day": stats.get("by_day", {})
    }


@router.get("/usage/recent")
async def get_admin_recent_usage(
    limit: int = 20,
    admin_user: User = Depends(require_roles(READ_ROLES))
) -> List[Dict[str, Any]]:
    limit = min(max(limit, 1), 100)
    return get_recent_queries(limit=limit)


@router.get("/audit-logs", response_model=List[AdminAuditEntry])
async def list_admin_audit_logs(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    admin_user: User = Depends(require_roles(AUDIT_READ_ROLES))
) -> List[AdminAuditEntry]:
    limit = min(max(limit, 1), 200)
    offset = max(offset, 0)

    stmt = select(AdminAuditLog, User).outerjoin(User, AdminAuditLog.admin_user_id == User.id)
    stmt = stmt.order_by(AdminAuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(stmt)

    entries: List[AdminAuditEntry] = []
    for audit_log, user in result.all():
        entries.append(
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
                created_at=audit_log.created_at.isoformat() if audit_log.created_at else ""
            )
        )

    return entries
