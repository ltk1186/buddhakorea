"""
Auth and current-user routers.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .. import database
from ..models.social_account import SocialAccount
from ..models.user import User
from ..models.user_usage import UserUsage
from ..quota import get_usage_info


class AdminLoginRequest(BaseModel):
    email: str = Field(..., description="Admin email")
    password: str = Field(..., min_length=1, description="Admin password")


def create_auth_router(
    *,
    config: Any,
    auth_module: Any,
    get_current_user_optional_dep: Any,
) -> APIRouter:
    router = APIRouter(tags=["auth"])

    def get_cookie_settings(request: Request) -> Dict[str, Any]:
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if config.cookie_secure is None:
            is_secure = forwarded_proto == "https" or request.url.scheme == "https"
        else:
            is_secure = config.cookie_secure

        samesite = (config.cookie_samesite or "lax").lower()
        if samesite not in {"lax", "strict", "none"}:
            samesite = "lax"

        cookie_kwargs: Dict[str, Any] = {
            "httponly": True,
            "secure": is_secure,
            "samesite": samesite,
        }
        if config.cookie_domain:
            cookie_kwargs["domain"] = config.cookie_domain
        return cookie_kwargs

    def hash_admin_password(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def verify_admin_credentials(email: str, password: str) -> bool:
        if not config.admin_email:
            return False
        if email.strip().lower() != config.admin_email.strip().lower():
            return False
        if config.admin_password_hash:
            return hmac.compare_digest(hash_admin_password(password), config.admin_password_hash)
        if config.admin_password:
            return hmac.compare_digest(password, config.admin_password)
        return False

    @router.post("/api/admin/login")
    async def admin_password_login(
        payload: AdminLoginRequest,
        request: Request,
        db: AsyncSession = Depends(database.get_db),
    ):
        if not config.admin_email or not (config.admin_password or config.admin_password_hash):
            raise HTTPException(status_code=500, detail="Admin login not configured")
        if not verify_admin_credentials(payload.email, payload.password):
            raise HTTPException(status_code=401, detail="Invalid admin credentials")

        result = await db.execute(select(User).where(User.email == payload.email))
        user = result.scalar_one_or_none()
        if not user:
            nickname = payload.email.split("@")[0] if "@" in payload.email else "Admin"
            user = User(email=payload.email, nickname=nickname, role="admin", is_active=True)
            db.add(user)
            await db.flush()
        else:
            user.role = "admin"
            user.is_active = True

        user.last_login = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

        access_token, refresh_token = auth_module.create_token_pair(user.id, user.email)
        response = JSONResponse({"status": "ok", "user_id": user.id, "role": user.role})
        base_cookie_kwargs = get_cookie_settings(request)
        response.set_cookie("access_token", access_token, max_age=60 * 15, path="/", **base_cookie_kwargs)
        response.set_cookie("refresh_token", refresh_token, max_age=60 * 60 * 24 * 7, path="/auth", **base_cookie_kwargs)
        return response

    @router.get("/auth/login/{provider}")
    async def login(provider: str, request: Request):
        redirect_uri = request.url_for("auth_callback", provider=provider)
        redirect_uri_str = str(redirect_uri)
        if redirect_uri_str.startswith("http://") and "localhost" not in redirect_uri_str:
            redirect_uri_str = redirect_uri_str.replace("http://", "https://", 1)
        state = auth_module.generate_oauth_state()
        return await auth_module.oauth.create_client(provider).authorize_redirect(
            request, redirect_uri_str, state=state
        )

    @router.get("/auth/callback/{provider}", name="auth_callback")
    async def auth_callback(
        provider: str,
        request: Request,
        state: str = None,
        db: AsyncSession = Depends(database.get_db),
    ):
        try:
            if state and not auth_module.validate_oauth_state(state):
                return RedirectResponse(url="/?auth_error=invalid_state")

            client = auth_module.oauth.create_client(provider)
            token = await client.authorize_access_token(request)
            access_token = token.get("access_token")

            if provider == "google":
                user_info = token.get("userinfo") or await client.userinfo(token=token)
            elif provider == "naver":
                import httpx
                async with httpx.AsyncClient() as http_client:
                    resp = await http_client.get(
                        "https://openapi.naver.com/v1/nid/me",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    user_info = resp.json()
            elif provider == "kakao":
                import httpx
                async with httpx.AsyncClient() as http_client:
                    resp = await http_client.get(
                        "https://kapi.kakao.com/v2/user/me",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    user_info = resp.json()
            else:
                user_info = token.get("userinfo") or {}

            if provider == "naver":
                naver_response = user_info.get("response", {})
                email = naver_response.get("email")
                provider_user_id = str(naver_response.get("id", ""))
                nickname = naver_response.get("nickname", naver_response.get("name", "User"))
                profile_img = naver_response.get("profile_image", "")
            elif provider == "kakao":
                kakao_account = user_info.get("kakao_account", {})
                profile = kakao_account.get("profile", {})
                email = kakao_account.get("email")
                provider_user_id = str(user_info.get("id", ""))
                nickname = profile.get("nickname", "User")
                profile_img = profile.get("profile_image_url", profile.get("thumbnail_image_url", ""))
            else:
                email = user_info.get("email")
                provider_user_id = str(user_info.get("sub", user_info.get("id")))
                nickname = user_info.get("name", user_info.get("nickname", "User"))
                profile_img = user_info.get("picture", user_info.get("profile_image", ""))

            if not email:
                if provider == "kakao":
                    email = f"kakao_{provider_user_id}@kakao.local"
                else:
                    raise HTTPException(400, "Email not provided by social provider")

            social_result = await db.execute(
                select(SocialAccount).where(
                    SocialAccount.provider == provider,
                    SocialAccount.provider_user_id == provider_user_id,
                )
            )
            social_account = social_result.scalar_one_or_none()

            if social_account:
                user_result = await db.execute(select(User).where(User.id == social_account.user_id))
                user = user_result.scalar_one_or_none()
                if not user:
                    raise HTTPException(400, "User not found for social account")
                social_account.last_used_at = datetime.now(timezone.utc)
                user.last_login = datetime.now(timezone.utc)
                user.profile_img = profile_img
            else:
                user_result = await db.execute(select(User).where(User.email == email))
                user = user_result.scalar_one_or_none()
                if not user:
                    user = User(
                        email=email,
                        nickname=nickname,
                        profile_img=profile_img,
                        provider=provider,
                        social_id=provider_user_id,
                    )
                    db.add(user)
                    await db.flush()

                db.add(
                    SocialAccount(
                        user_id=user.id,
                        provider=provider,
                        provider_user_id=provider_user_id,
                        provider_email=email,
                        raw_profile=dict(user_info) if user_info else None,
                    )
                )
                user.last_login = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(user)

            access_token, refresh_token = auth_module.create_token_pair(user.id, user.email)
            response = RedirectResponse(url="/", status_code=302)
            base_cookie_kwargs = get_cookie_settings(request)
            response.set_cookie("access_token", access_token, max_age=60 * 15, path="/", **base_cookie_kwargs)
            response.set_cookie("refresh_token", refresh_token, max_age=60 * 60 * 24 * 7, path="/auth", **base_cookie_kwargs)
            return response
        except Exception as exc:
            import urllib.parse
            detail = urllib.parse.quote(str(exc))
            return RedirectResponse(url=f"/?auth_error=failed&detail={detail}")

    @router.get("/api/users/me")
    async def get_current_user_info(request: Request, db: AsyncSession = Depends(database.get_db)):
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        if not token:
            raise HTTPException(401, "Not authenticated")

        payload = auth_module.decode_access_token(token)
        if not payload or not payload.get("user_id"):
            raise HTTPException(401, "Invalid token")

        result = await db.execute(select(User).where(User.id == payload["user_id"]))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(404, "User not found")

        usage_result = await db.execute(
            select(UserUsage).where(UserUsage.user_id == user.id, UserUsage.usage_date == date.today())
        )
        today_usage_record = usage_result.scalar_one_or_none()
        social_result = await db.execute(select(SocialAccount).where(SocialAccount.user_id == user.id))
        social_accounts = social_result.scalars().all()

        return {
            "id": user.id,
            "email": user.email,
            "nickname": user.nickname,
            "profile_img": user.profile_img,
            "profile_image_url": user.profile_img,
            "provider": user.provider,
            "daily_limit": user.daily_chat_limit,
            "today_usage": today_usage_record.chat_count if today_usage_record else 0,
            "created_at": user.created_at.isoformat() if user.created_at else None,
            "social_accounts": [
                {
                    "provider": social.provider,
                    "provider_email": social.provider_email,
                    "created_at": social.created_at.isoformat() if social.created_at else None,
                }
                for social in social_accounts
            ],
        }

    @router.post("/auth/logout")
    async def logout(request: Request):
        response = JSONResponse({"status": "logged_out"})
        cookie_kwargs = get_cookie_settings(request)
        response.delete_cookie("access_token", path="/", **cookie_kwargs)
        response.delete_cookie("refresh_token", path="/auth", **cookie_kwargs)
        return response

    @router.post("/auth/refresh")
    async def refresh_access_token(
        request: Request,
        db: AsyncSession = Depends(database.get_db),
    ):
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(401, "No refresh token")

        payload = auth_module.decode_refresh_token(refresh_token)
        if not payload or not payload.get("user_id"):
            raise HTTPException(401, "Invalid or expired refresh token")

        result = await db.execute(
            select(User).where(User.id == payload["user_id"], User.is_active == True)
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(401, "User not found or inactive")

        access_token = auth_module.create_access_token({"user_id": user.id, "sub": user.email})
        response = JSONResponse({"status": "refreshed"})
        cookie_kwargs = get_cookie_settings(request)
        cookie_kwargs.update({"key": "access_token", "value": access_token, "max_age": 60 * 15, "path": "/"})
        response.set_cookie(**cookie_kwargs)
        return response

    @router.get("/api/users/me/usage")
    async def get_my_usage(
        request: Request,
        db: AsyncSession = Depends(database.get_db),
        user: Optional[User] = Depends(get_current_user_optional_dep),
    ):
        return await get_usage_info(db, request, user)

    return router
