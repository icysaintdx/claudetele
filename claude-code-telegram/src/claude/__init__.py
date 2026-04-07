"""Claude Code integration module."""

from .exceptions import (
    ClaudeError,
    ClaudeParsingError,
    ClaudeProcessError,
    ClaudeSessionError,
    ClaudeTimeoutError,
)
from .facade import ClaudeIntegration
from .local_bun_integration import LocalBunManager
from .sdk_integration import ClaudeResponse, ClaudeSDKManager, StreamUpdate
from .session import (
    ClaudeSession,
    SessionManager,
    SessionStorage,
)

__all__ = [
    # Exceptions
    "ClaudeError",
    "ClaudeParsingError",
    "ClaudeProcessError",
    "ClaudeSessionError",
    "ClaudeTimeoutError",
    # Main integration
    "ClaudeIntegration",
    # Core components
    "ClaudeSDKManager",
    "LocalBunManager",
    "ClaudeResponse",
    "StreamUpdate",
    "SessionManager",
    "SessionStorage",
    "ClaudeSession",
]
