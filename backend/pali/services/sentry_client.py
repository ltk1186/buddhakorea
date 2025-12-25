"""
Sentry error tracking integration.
"""
from functools import wraps
from typing import Optional, Callable, Any
import sentry_sdk

from ..config import settings


def init_sentry():
    """Initialize Sentry SDK if DSN is configured."""
    if settings.SENTRY_DSN:
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENVIRONMENT,
            traces_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 1.0,
            profiles_sample_rate=0.1 if settings.ENVIRONMENT == "production" else 1.0,
            send_default_pii=False,
        )


def capture_exception(error: Exception, extra: Optional[dict] = None):
    """Capture an exception and send to Sentry."""
    if settings.SENTRY_DSN:
        with sentry_sdk.push_scope() as scope:
            if extra:
                for key, value in extra.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_exception(error)


def capture_message(message: str, level: str = "info", extra: Optional[dict] = None):
    """Capture a message and send to Sentry."""
    if settings.SENTRY_DSN:
        with sentry_sdk.push_scope() as scope:
            if extra:
                for key, value in extra.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_message(message, level=level)


def set_user_context(user_id: str, email: Optional[str] = None):
    """Set user context for Sentry."""
    if settings.SENTRY_DSN:
        sentry_sdk.set_user({
            "id": user_id,
            "email": email,
        })


def add_breadcrumb(
    message: str,
    category: str = "info",
    data: Optional[dict] = None
):
    """Add a breadcrumb for debugging."""
    if settings.SENTRY_DSN:
        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            data=data or {},
        )


def capture_exceptions(func: Callable) -> Callable:
    """
    Decorator to capture exceptions and send to Sentry.
    Works with both sync and async functions.
    """
    @wraps(func)
    async def async_wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            capture_exception(e)
            raise

    @wraps(func)
    def sync_wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            capture_exception(e)
            raise

    # Return appropriate wrapper based on function type
    import asyncio
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper
