"""
Gate audit logging with signed audit log integration.

Provides tamper-evident audit logging for all gate operations
using hash chains and HMAC signatures.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .signed_audit_log import SignedAuditLog


class GateAudit:
    """
    Audit logging for gate operations with integrity verification.

    Uses SignedAuditLog for tamper-evident logging of all
    gate-related events.
    """

    def __init__(self, output_dir: str = ".carby-sprints"):
        """
        Initialize gate audit logger.

        Args:
            output_dir: Directory containing sprint data
        """
        self.output_dir: Path = Path(output_dir)
        self.db_path: Path = self.output_dir / "audit.db"
        self._audit_log: Optional[SignedAuditLog] = None

    @property
    def audit_log(self) -> SignedAuditLog:
        """Lazy initialization of signed audit log."""
        if self._audit_log is None:
            self._audit_log = SignedAuditLog(self.db_path)
        return self._audit_log

    def log_gate_pass(
        self,
        sprint_id: str,
        gate_number: str,
        tier: int,
        risk_score: float,
        validation_token: str,
        forced: bool = False,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log a gate pass event.

        Args:
            sprint_id: ID of the sprint
            gate_number: Gate number (1-5)
            tier: Validation tier (1 or 2)
            risk_score: Calculated risk score
            validation_token: Token used for validation
            forced: Whether this was a forced pass
            user_id: ID of the user who performed the action
        """
        self.audit_log.append(
            event_type="gate_pass",
            sprint_id=sprint_id,
            details={
                "gate_number": gate_number,
                "tier": tier,
                "risk_score": risk_score,
                "validation_token": validation_token,
                "forced": forced,
            },
            user_id=user_id,
        )

    def log_gate_fail(
        self,
        sprint_id: str,
        gate_number: str,
        reason: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log a gate failure event.

        Args:
            sprint_id: ID of the sprint
            gate_number: Gate number (1-5)
            reason: Failure reason
            user_id: ID of the user who performed the action
        """
        self.audit_log.append(
            event_type="gate_fail",
            sprint_id=sprint_id,
            details={
                "gate_number": gate_number,
                "reason": reason,
            },
            user_id=user_id,
        )

    def log_sprint_start(
        self,
        sprint_id: str,
        project: str,
        duration_days: int,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log sprint start event.

        Args:
            sprint_id: ID of the sprint
            project: Project name
            duration_days: Sprint duration in days
            user_id: ID of the user who performed the action
        """
        self.audit_log.append(
            event_type="sprint_start",
            sprint_id=sprint_id,
            details={
                "project": project,
                "duration_days": duration_days,
            },
            user_id=user_id,
        )

    def log_sprint_complete(
        self,
        sprint_id: str,
        final_status: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log sprint completion event.

        Args:
            sprint_id: ID of the sprint
            final_status: Final sprint status
            user_id: ID of the user who performed the action
        """
        self.audit_log.append(
            event_type="sprint_complete",
            sprint_id=sprint_id,
            details={
                "final_status": final_status,
            },
            user_id=user_id,
        )

    def log_work_item_add(
        self,
        sprint_id: str,
        work_item_id: str,
        title: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log work item addition.

        Args:
            sprint_id: ID of the sprint
            work_item_id: Work item ID
            title: Work item title
            user_id: ID of the user who performed the action
        """
        self.audit_log.append(
            event_type="work_item_add",
            sprint_id=sprint_id,
            details={
                "work_item_id": work_item_id,
                "title": title,
            },
            user_id=user_id,
        )

    def log_work_item_complete(
        self,
        sprint_id: str,
        work_item_id: str,
        user_id: Optional[str] = None,
    ) -> None:
        """
        Log work item completion.

        Args:
            sprint_id: ID of the sprint
            work_item_id: Work item ID
            user_id: ID of the user who performed the action
        """
        self.audit_log.append(
            event_type="work_item_complete",
            sprint_id=sprint_id,
            details={
                "work_item_id": work_item_id,
            },
            user_id=user_id,
        )

    def verify(self, sprint_id: Optional[str] = None) -> dict[str, Any]:
        """
        Verify audit log integrity.

        Args:
            sprint_id: Optional sprint ID to filter verification

        Returns:
            Verification results
        """
        return self.audit_log.verify(sprint_id)

    def get_entries(
        self,
        sprint_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> list[Any]:
        """
        Get audit log entries.

        Args:
            sprint_id: Filter by sprint ID
            event_type: Filter by event type
            limit: Maximum entries to return

        Returns:
            List of audit entries
        """
        return self.audit_log.get_entries(sprint_id, event_type, limit)


def get_audit_logger(output_dir: str = ".carby-sprints") -> GateAudit:
    """Get a gate audit logger instance."""
    return GateAudit(output_dir)
