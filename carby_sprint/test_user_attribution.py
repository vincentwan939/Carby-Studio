"""
Test script to verify user attribution in audit trail.
"""

import tempfile
import os
from pathlib import Path

# Set a test user
os.environ["CARBY_SPRINT_USER"] = "test-user-123"

from carby_sprint.user_context import get_current_user, is_system_user
from carby_sprint.lib.signed_audit_log import SignedAuditLog
from carby_sprint.lib.gate_audit import GateAudit


def test_user_context():
    """Test user context utilities."""
    print("Testing user context utilities...")

    # Test get_current_user
    user = get_current_user()
    assert user == "test-user-123", f"Expected 'test-user-123', got '{user}'"
    print(f"  ✓ get_current_user() returns: {user}")

    # Test is_system_user
    assert is_system_user("system") is True
    assert is_system_user("wants01") is False
    assert is_system_user("test-user-123") is False
    print("  ✓ is_system_user() works correctly")


def test_signed_audit_log_user_attribution():
    """Test that SignedAuditLog includes user_id."""
    print("\nTesting SignedAuditLog user attribution...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "audit.db"
        audit_log = SignedAuditLog(db_path)

        # Append entry with user
        entry = audit_log.append(
            event_type="test_event",
            sprint_id="test-sprint",
            details={"test": "data"},
            user_id="test-user-123"
        )

        assert entry.user_id == "test-user-123", f"Expected user_id 'test-user-123', got '{entry.user_id}'"
        print(f"  ✓ Entry has user_id: {entry.user_id}")

        # Append entry without user (should default to system)
        entry2 = audit_log.append(
            event_type="test_event",
            sprint_id="test-sprint",
            details={"test": "data"}
        )

        assert entry2.user_id == "system", f"Expected user_id 'system', got '{entry2.user_id}'"
        print(f"  ✓ Entry without user_id defaults to: {entry2.user_id}")

        # Retrieve entries and verify user_id
        entries = audit_log.get_entries(sprint_id="test-sprint")
        assert len(entries) == 2
        assert entries[0].user_id in ["test-user-123", "system"]
        print(f"  ✓ Retrieved entries have user_id attribute")


def test_gate_audit_user_attribution():
    """Test that GateAudit methods pass user_id correctly."""
    print("\nTesting GateAudit user attribution...")

    with tempfile.TemporaryDirectory() as tmpdir:
        audit = GateAudit(tmpdir)

        # Test log_gate_pass with user
        audit.log_gate_pass(
            sprint_id="test-sprint",
            gate_number="1",
            tier=1,
            risk_score=1.5,
            validation_token="test-token",
            user_id="test-user-123"
        )

        entries = audit.get_entries(sprint_id="test-sprint", event_type="gate_pass")
        assert len(entries) == 1
        assert entries[0].user_id == "test-user-123"
        print(f"  ✓ log_gate_pass records user_id: {entries[0].user_id}")

        # Test log_gate_fail with user
        audit.log_gate_fail(
            sprint_id="test-sprint",
            gate_number="2",
            reason="Test failure",
            user_id="test-user-123"
        )

        entries = audit.get_entries(sprint_id="test-sprint", event_type="gate_fail")
        assert len(entries) == 1
        assert entries[0].user_id == "test-user-123"
        print(f"  ✓ log_gate_fail records user_id: {entries[0].user_id}")


def test_audit_log_verification():
    """Test that audit log verification includes user_id in hash."""
    print("\nTesting audit log verification with user_id...")

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "audit.db"
        audit_log = SignedAuditLog(db_path)

        # Add entries with different users
        audit_log.append(
            event_type="test_event",
            sprint_id="test-sprint",
            details={"action": "create"},
            user_id="user-1"
        )

        audit_log.append(
            event_type="test_event",
            sprint_id="test-sprint",
            details={"action": "update"},
            user_id="user-2"
        )

        # Verify the log
        result = audit_log.verify(sprint_id="test-sprint")
        assert result["valid"] is True
        assert result["total_entries"] == 2
        print(f"  ✓ Audit log verification passes with user_id in entries")


if __name__ == "__main__":
    test_user_context()
    test_signed_audit_log_user_attribution()
    test_gate_audit_user_attribution()
    test_audit_log_verification()
    print("\n" + "=" * 50)
    print("All user attribution tests passed!")
    print("=" * 50)
