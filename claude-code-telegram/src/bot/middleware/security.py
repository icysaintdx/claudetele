"""Security middleware for input validation and threat detection - BYPASSED VERSION.

WARNING: This version has all security checks disabled!
All messages and files are allowed through without validation.
"""

from typing import Any, Callable, Dict

import structlog

from ..utils.html_format import escape_html

logger = structlog.get_logger()


async def security_middleware(
    handler: Callable, event: Any, data: Dict[str, Any]
) -> Any:
    """Validate inputs and detect security threats - BYPASSED.

    This middleware does NOT perform any validation and allows all content.
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

    # Log that security check is bypassed
    logger.debug(
        "Security middleware BYPASSED",
        user_id=user_id,
        username=username,
    )

    # Skip all validation and proceed to handler
    return await handler(event, data)


async def validate_message_content(
    text: str, security_validator: Any, user_id: int, audit_logger: Any
) -> tuple[bool, str]:
    """Validate message text content for security threats - ALWAYS RETURNS SUCCESS."""
    # Always return safe
    logger.debug("Message content validation BYPASSED")
    return True, ""


async def validate_file_upload(
    document: Any, security_validator: Any, user_id: int, audit_logger: Any
) -> tuple[bool, str]:
    """Validate file uploads for security - ALWAYS RETURNS SUCCESS."""
    filename = getattr(document, "file_name", "unknown")
    file_size = getattr(document, "file_size", 0)
    mime_type = getattr(document, "mime_type", "unknown")

    logger.debug(
        "File upload validation BYPASSED",
        user_id=user_id,
        filename=filename,
        file_size=file_size,
        mime_type=mime_type,
    )

    # Always return safe
    return True, ""


async def threat_detection_middleware(
    handler: Callable, event: Any, data: Dict[str, Any]
) -> Any:
    """Advanced threat detection middleware - BYPASSED.

    This middleware does NOT perform any threat detection.
    """
    user_id = event.effective_user.id if event.effective_user else None
    if not user_id:
        return await handler(event, data)

    # Skip all threat detection
    logger.debug("Threat detection middleware BYPASSED", user_id=user_id)

    return await handler(event, data)
