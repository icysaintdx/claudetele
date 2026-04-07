"""Security audit logging - MINIMAL VERSION.

This version has all audit logging disabled for performance.
"""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger()


@dataclass
class AuditEvent:
    """Security audit event - NOT ACTUALLY STORED."""

    timestamp: datetime
    user_id: int
    event_type: str
    success: bool
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    risk_level: str = "low"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/logging."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditStorage:
    """Abstract interface for audit event storage - NO-OP IMPLEMENTATION."""

    async def store_event(self, event: AuditEvent) -> None:
        """Store audit event - DOES NOTHING."""
        pass

    async def get_events(
        self,
        user_id: Optional[int] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Retrieve audit events - RETURNS EMPTY LIST."""
        return []

    async def get_security_violations(
        self, user_id: Optional[int] = None, limit: int = 100
    ) -> List[AuditEvent]:
        """Get security violations - RETURNS EMPTY LIST."""
        return []


class InMemoryAuditStorage(AuditStorage):
    """In-memory audit storage - DOES NOT STORE ANYTHING."""

    def __init__(self, max_events: int = 10000):
        self.events: List[AuditEvent] = []
        self.max_events = max_events

    async def store_event(self, event: AuditEvent) -> None:
        """Store event in memory - DOES NOTHING."""
        # Event is not stored
        pass

    async def get_events(
        self,
        user_id: Optional[int] = None,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get filtered events - RETURNS EMPTY LIST."""
        return []

    async def get_security_violations(
        self, user_id: Optional[int] = None, limit: int = 100
    ) -> List[AuditEvent]:
        """Get security violations - RETURNS EMPTY LIST."""
        return []


class AuditLogger:
    """Security audit logger - NO-OP IMPLEMENTATION."""

    def __init__(self, storage: AuditStorage):
        self.storage = storage
        logger.info("Audit logger initialized in NO-OP mode")

    async def log_auth_attempt(
        self,
        user_id: int,
        success: bool,
        method: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log authentication attempt - DOES NOTHING."""
        pass

    async def log_session_event(
        self,
        user_id: int,
        action: str,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Log session-related events - DOES NOTHING."""
        pass

    async def log_command(
        self,
        user_id: int,
        command: str,
        args: List[str],
        success: bool,
        working_directory: Optional[str] = None,
        execution_time: Optional[float] = None,
        exit_code: Optional[int] = None,
    ) -> None:
        """Log command execution - DOES NOTHING."""
        pass

    async def log_file_access(
        self,
        user_id: int,
        file_path: str,
        action: str,
        success: bool,
        file_size: Optional[int] = None,
    ) -> None:
        """Log file access - DOES NOTHING."""
        pass

    async def log_security_violation(
        self,
        user_id: int,
        violation_type: str,
        details: str,
        severity: str = "medium",
        attempted_action: Optional[str] = None,
    ) -> None:
        """Log security violation - DOES NOTHING."""
        pass

    async def log_rate_limit_exceeded(
        self,
        user_id: int,
        limit_type: str,
        current_usage: float,
        limit_value: float,
    ) -> None:
        """Log rate limit exceeded - DOES NOTHING."""
        pass

    def _assess_command_risk(self, command: str, args: List[str]) -> str:
        """Assess risk level of command execution - ALWAYS RETURNS 'low'."""
        return "low"

    def _assess_file_access_risk(self, file_path: str, action: str) -> str:
        """Assess risk level of file access - ALWAYS RETURNS 'low'."""
        return "low"

    async def get_user_activity_summary(
        self, user_id: int, hours: int = 24
    ) -> Dict[str, Any]:
        """Get activity summary for user - RETURNS EMPTY SUMMARY."""
        return {
            "user_id": user_id,
            "period_hours": hours,
            "total_events": 0,
            "event_types": {},
            "risk_levels": {},
            "success_rate": 0,
            "security_violations": 0,
            "last_activity": None,
        }

    async def get_security_dashboard(self) -> Dict[str, Any]:
        """Get security dashboard data - RETURNS EMPTY DASHBOARD."""
        return {
            "period": "24_hours",
            "total_events": 0,
            "security_violations": 0,
            "active_users": 0,
            "risk_distribution": {},
            "top_violation_types": {},
            "authentication_failures": 0,
        }
