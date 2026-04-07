"""Rate limiting middleware for Telegram bot - BYPASSED VERSION.

WARNING: This version has all rate limiting disabled!
All requests are allowed through without any limits.
"""

from typing import Any, Callable, Dict

import structlog

logger = structlog.get_logger()


async def rate_limit_middleware(
    handler: Callable, event: Any, data: Dict[str, Any]
) -> Any:
    """Check rate limits before processing messages - BYPASSED.

    This middleware allows ALL requests without any rate limiting.
    """
    user_id = event.effective_user.id if event.effective_user else None
    username = (
        getattr(event.effective_user, "username", None)
        if event.effective_user
        else None
    )

    if not user_id:
        logger.warning("No user information in update")
        return await handler(event, data)

    # Log that rate limiting is bypassed
    logger.debug(
        "Rate limiting BYPASSED",
        user_id=user_id,
        username=username,
    )

    # Continue to handler without any rate limit checks
    return await handler(event, data)


def estimate_message_cost(event: Any) -> float:
    """Estimate the cost of processing a message - RETURNS MINIMAL COST."""
    # Return minimal cost
    return 0.0


async def cost_tracking_middleware(
    handler: Callable, event: Any, data: Dict[str, Any]
) -> Any:
    """Track actual costs after processing - BYPASSED."""
    # Execute handler without any cost tracking
    return await handler(event, data)


async def burst_protection_middleware(
    handler: Callable, event: Any, data: Dict[str, Any]
) -> Any:
    """Additional burst protection for high-frequency requests - BYPASSED.

    This middleware does NOT provide any burst protection.
    """
    # Allow all requests without burst protection
    return await handler(event, data)
