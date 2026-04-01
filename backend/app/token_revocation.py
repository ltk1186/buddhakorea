"""Token revocation utilities for checking and managing invalidated tokens."""

from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from loguru import logger

from .models.revoked_token import RevokedToken


async def is_token_revoked(
    db: AsyncSession,
    social_account_id: int,
    token_type: str = "access"
) -> bool:
    """
    Check if a token has been revoked.

    Args:
        db: Database session
        social_account_id: Social account ID
        token_type: 'access' or 'refresh'

    Returns:
        True if token is revoked, False otherwise
    """
    try:
        stmt = select(RevokedToken).where(
            RevokedToken.social_account_id == social_account_id,
            RevokedToken.token_type == token_type,
        )
        result = await db.execute(stmt)
        revoked = result.scalar_one_or_none()
        return revoked is not None
    except Exception as e:
        logger.error(f"Error checking token revocation: {e}")
        return False


async def revoke_token(
    db: AsyncSession,
    social_account_id: int,
    token_type: str = "access",
    reason: str = "logout",
    metadata: Optional[dict] = None
) -> None:
    """
    Revoke a token.

    Args:
        db: Database session
        social_account_id: Social account ID
        token_type: 'access' or 'refresh'
        reason: Reason for revocation (logout, reauth, compromise, etc.)
        metadata: Additional context (user agent, IP, etc.)
    """
    try:
        # Check if already revoked
        is_revoked = await is_token_revoked(db, social_account_id, token_type)
        if is_revoked:
            logger.debug(f"Token already revoked: social_account_id={social_account_id}, type={token_type}")
            return

        # Create revocation record
        revoked_token = RevokedToken(
            social_account_id=social_account_id,
            token_type=token_type,
            revoked_at=datetime.now(timezone.utc),
            reason=reason,
            metadata=metadata or {}
        )
        db.add(revoked_token)
        await db.commit()
        logger.info(f"Token revoked: social_account_id={social_account_id}, type={token_type}, reason={reason}")

    except Exception as e:
        logger.error(f"Error revoking token: {e}")
        await db.rollback()
        raise


async def revoke_all_tokens(
    db: AsyncSession,
    social_account_id: int,
    reason: str = "logout",
    metadata: Optional[dict] = None
) -> None:
    """
    Revoke all tokens for a social account (access and refresh).

    Args:
        db: Database session
        social_account_id: Social account ID
        reason: Reason for revocation
        metadata: Additional context
    """
    try:
        await revoke_token(db, social_account_id, "access", reason, metadata)
        await revoke_token(db, social_account_id, "refresh", reason, metadata)
        logger.info(f"All tokens revoked for social_account_id={social_account_id}")
    except Exception as e:
        logger.error(f"Error revoking all tokens: {e}")
        raise
