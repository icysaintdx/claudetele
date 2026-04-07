"""Input validation and security checks - BYPASSED VERSION.

WARNING: This version has all security checks disabled!
All validation methods return success without actual checking.
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

logger = structlog.get_logger()


class SecurityValidator:
    """Security validation for user inputs - BYPASSED."""

    def __init__(
        self, approved_directory: Path, disable_security_patterns: bool = False
    ):
        """Initialize validator with approved directory."""
        self.approved_directory = approved_directory.resolve()
        self.disable_security_patterns = True  # Always disabled
        logger.warning(
            "Security validator initialized in BYPASSED mode",
            approved_directory=str(self.approved_directory),
        )

    def validate_path(
        self, user_path: str, current_dir: Optional[Path] = None
    ) -> Tuple[bool, Optional[Path], Optional[str]]:
        """Validate and resolve user-provided path - ALWAYS RETURNS SUCCESS."""
        try:
            if not user_path or not user_path.strip():
                return False, None, "Empty path not allowed"

            user_path = user_path.strip()
            current_dir = current_dir or self.approved_directory

            if user_path.startswith("/"):
                target = Path(user_path)
            else:
                target = current_dir / user_path

            target = target.resolve()

            logger.debug(
                "Path validation BYPASSED",
                original_path=user_path,
                resolved_path=str(target),
            )
            return True, target, None

        except Exception as e:
            logger.error("Path validation error", path=user_path, error=str(e))
            return False, None, f"Invalid path: {str(e)}"

    def _is_within_directory(self, path: Path, directory: Path) -> bool:
        """Check if path is within directory - ALWAYS RETURNS TRUE."""
        return True

    def validate_filename(self, filename: str) -> Tuple[bool, Optional[str]]:
        """Validate uploaded filename - ALWAYS RETURNS SUCCESS."""
        if not filename or not filename.strip():
            return False, "Empty filename not allowed"

        logger.debug("Filename validation BYPASSED", filename=filename)
        return True, None

    def sanitize_command_input(self, text: str) -> str:
        """Sanitize text input for commands - NO SANITIZATION PERFORMED."""
        if not text:
            return ""

        # Return text as-is without any sanitization
        logger.debug("Command input sanitization BYPASSED")
        return text

    def validate_command_args(
        self, args: List[str]
    ) -> Tuple[bool, List[str], Optional[str]]:
        """Validate and sanitize command arguments - ALWAYS RETURNS SUCCESS."""
        if not args:
            return True, [], None

        # Return args as-is without any validation
        logger.debug("Command args validation BYPASSED")
        return True, args, None

    def is_safe_directory_name(self, dirname: str) -> bool:
        """Check if directory name is safe for creation - ALWAYS RETURNS TRUE."""
        if not dirname or not dirname.strip():
            return False

        logger.debug("Directory name validation BYPASSED", dirname=dirname)
        return True

    def get_security_summary(self) -> Dict[str, Any]:
        """Get summary of security validation rules."""
        return {
            "approved_directory": str(self.approved_directory),
            "security_status": "BYPASSED - ALL CHECKS DISABLED",
            "warning": "This instance has no security validation!",
        }
