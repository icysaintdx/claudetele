"""Telegram bot authentication middleware - BYPASSED VERSION.

WARNING: This version allows ALL users without authentication!
"""

from datetime import UTC, datetime
from typing import Any, Callable, Dict

import structlog

logger = structlog.get_logger()


async def auth_middleware(handler: Callable, event: Any, data: Dict[str, Any]) -> Any:
    """Check authentication before processing messages - BYPASSED.

    This middleware allows ALL users through without authentication.
    """
    # Extract user information
    user_id = event.effective_user.id if event.effective_user else None
    username = (
        getattr(event.effective_user, "username", None)
        if event.effective_user
        else None
    )

    if not user_id:
        logger.warning("No user information in update")
        return

    # Log that auth check is bypassed
    logger.debug(
        "Authentication BYPASSED - allowing all users",
        user_id=user_id,
        username=username,
    )

    # Continue to handler without any authentication check
    return await handler(event, data)


async def require_auth(handler: Callable, event: Any, data: Dict[str, Any]) -> Any:
    """Decorator-style middleware that requires authentication - BYPASSED."""
    # Allow all users
    return await handler(event, data)


async def admin_required(handler: Callable, event: Any, data: Dict[str, Any]) -> Any:
    """Middleware that requires admin privileges - BYPASSED.

    This version allows ALL users to use admin commands.
    """
    # Allow all users
    return await handler(event, data)
