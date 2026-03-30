"""
Test suite for audit log integrity verification.

Tests the cryptographic integrity protection features:
- HMAC-SHA256 signatures for each log entry
- Hash chain linking entries (previous entry hash in current entry)
- Verification method to detect tampering
"""

import pytest
import tempfile
import json
import sqlite3
import hashlib
import hmac
from pathlib import Path
from datetime import datetime

from carby_sprint.lib.signed_audit_log import SignedAuditLog, AuditEntry
from carby_sprint.lib.gate_audit import GateAudit


class TestHMACSignature:
    """Test HMAC-SHA256 signature creation and verification."""

    def test_entry_has_hmac_signature(self):
        """Test that each entry has an HMAC-SHA256 signature."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            entry = audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            # Signature should exist and be 64 chars (SHA-256 hex)
            assert entry.signature is not None
            assert len(entry.signature) == 64
            assert all(c in "0123456789abcdef" for c in entry.signature)

    def test_signature_verifies_correctly(self):
        """Test that valid signatures pass verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            result = audit_log.verify()
            assert result["valid"] is True
            assert result["total_entries"] == 1
            assert len(result["tampered_entries"]) == 0

    def test_tampered_signature_detected(self):
        """Test that tampered signatures are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            # Tamper with the signature in the database
            with sqlite3.connect(db_path) as conn:
                cursor = conn.execute("SELECT signature FROM audit_log WHERE id = 1")
                row = cursor.fetchone()
                fake_sig = "fake_signature_" + row[0][16:]
                conn.execute("UPDATE audit_log SET signature = ?", (fake_sig,))
                conn.commit()

            result = audit_log.verify()
            assert result["valid"] is False
            assert len(result["tampered_entries"]) == 1
            assert result["tampered_entries"][0]["reason"] == "invalid_signature"


class TestHashChain:
    """Test hash chain linking between entries."""

    def test_first_entry_has_genesis_previous_hash(self):
        """Test that first entry uses genesis hash as previous."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            entry = audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            # First entry should have genesis hash
            assert entry.previous_hash == "0" * 64

    def test_subsequent_entries_link_to_previous(self):
        """Test that entries form a chain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            entry1 = audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            entry2 = audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "update"},
            )

            # Second entry's previous_hash should be first entry's entry_hash
            assert entry2.previous_hash == entry1.entry_hash

    def test_chain_verification_passes_for_valid_chain(self):
        """Test that valid chains pass verification."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            for i in range(5):
                audit_log.append(
                    event_type="test_event",
                    sprint_id="test-sprint",
                    details={"action": f"step_{i}"},
                )

            result = audit_log.verify()
            assert result["valid"] is True
            assert result["total_entries"] == 5
            assert len(result["broken_chain_at"]) == 0

    def test_broken_chain_detected(self):
        """Test that broken chains are detected."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "update"},
            )

            # Tamper with the previous_hash in the second entry
            with sqlite3.connect(db_path) as conn:
                conn.execute("UPDATE audit_log SET previous_hash = 'tampered_hash' WHERE id = 2")
                conn.commit()

            result = audit_log.verify()
            assert result["valid"] is False
            assert len(result["broken_chain_at"]) == 1
            assert result["broken_chain_at"][0]["id"] == 2


class TestEntryHashIntegrity:
    """Test entry hash computation and integrity."""

    def test_entry_hash_computed_correctly(self):
        """Test that entry hash is computed from entry data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            entry = audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            # Hash should be 64 chars (SHA-256 hex)
            assert len(entry.entry_hash) == 64
            assert all(c in "0123456789abcdef" for c in entry.entry_hash)

    def test_tampered_entry_data_detected(self):
        """Test that tampered entry data is detected via hash mismatch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            # Tamper with the details field
            with sqlite3.connect(db_path) as conn:
                conn.execute("UPDATE audit_log SET details = '{\"tampered\": true}' WHERE id = 1")
                conn.commit()

            result = audit_log.verify()
            assert result["valid"] is False
            assert len(result["tampered_entries"]) > 0
            assert result["tampered_entries"][0]["reason"] == "hash_mismatch"


class TestGateAuditIntegration:
    """Test GateAudit integration with integrity features."""

    def test_gate_pass_logged_with_integrity(self):
        """Test that gate pass events are logged with full integrity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = GateAudit(tmpdir)

            audit.log_gate_pass(
                sprint_id="test-sprint",
                gate_number="1",
                tier=1,
                risk_score=1.5,
                validation_token="test-token",
                user_id="test-user"
            )

            # Verify the log
            result = audit.verify("test-sprint")
            assert result["valid"] is True
            assert result["total_entries"] == 1

    def test_multiple_events_form_chain(self):
        """Test that multiple gate events form a hash chain."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = GateAudit(tmpdir)

            # Log multiple events
            audit.log_sprint_start("sprint-1", "Test Project", 7, "user-1")
            audit.log_gate_pass("sprint-1", "1", 1, 1.5, "token-1", "user-1")
            audit.log_work_item_add("sprint-1", "item-1", "Test Item", "user-1")
            audit.log_work_item_complete("sprint-1", "item-1", "user-1")
            audit.log_sprint_complete("sprint-1", "completed", "user-1")

            # Verify all events
            result = audit.verify("sprint-1")
            assert result["valid"] is True
            assert result["total_entries"] == 5
            assert len(result["broken_chain_at"]) == 0
            assert len(result["tampered_entries"]) == 0

    def test_cross_sprint_isolation(self):
        """Test that different sprints have isolated chains."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = GateAudit(tmpdir)

            # Log events for sprint-1
            audit.log_sprint_start("sprint-1", "Project A", 7, "user-1")
            audit.log_gate_pass("sprint-1", "1", 1, 1.5, "token-1", "user-1")

            # Log events for sprint-2
            audit.log_sprint_start("sprint-2", "Project B", 14, "user-2")
            audit.log_gate_pass("sprint-2", "1", 1, 2.0, "token-2", "user-2")

            # Verify sprint-1
            result1 = audit.verify("sprint-1")
            assert result1["valid"] is True
            assert result1["total_entries"] == 2

            # Verify sprint-2
            result2 = audit.verify("sprint-2")
            assert result2["valid"] is True
            assert result2["total_entries"] == 2

            # Verify all (should include all 4 entries)
            result_all = audit.verify()
            assert result_all["valid"] is True
            assert result_all["total_entries"] == 4


class TestJSONExportIntegrity:
    """Test JSON export includes integrity data."""

    def test_export_includes_all_integrity_fields(self):
        """Test that JSON export includes all integrity fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path, key="test-key-12345")

            audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            export_path = Path(tmpdir) / "audit_export.json"
            audit_log.export_to_json(export_path)

            # Read the exported JSON
            with open(export_path) as f:
                exported = json.load(f)

            assert len(exported) == 1
            entry = exported[0]

            # Verify all integrity fields are present
            assert "previous_hash" in entry
            assert "entry_hash" in entry
            assert "signature" in entry
            assert len(entry["previous_hash"]) == 64
            assert len(entry["entry_hash"]) == 64
            assert len(entry["signature"]) == 64


class TestKeyManagement:
    """Test HMAC key management."""

    def test_key_from_environment(self):
        """Test that key can be loaded from environment."""
        import os
        os.environ["CARBY_AUDIT_KEY"] = "env-test-key-12345"

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path)

            entry = audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            assert entry.signature is not None
            assert len(entry.signature) == 64

        del os.environ["CARBY_AUDIT_KEY"]

    def test_key_auto_generation(self):
        """Test that key is auto-generated if not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            audit_log = SignedAuditLog(db_path)

            entry = audit_log.append(
                event_type="test_event",
                sprint_id="test-sprint",
                details={"action": "create"},
            )

            assert entry.signature is not None
            assert len(entry.signature) == 64


if __name__ == "__main__":
    # Run all tests
    print("Running HMAC Signature Tests...")
    hmac_tests = TestHMACSignature()
    hmac_tests.test_entry_has_hmac_signature()
    hmac_tests.test_signature_verifies_correctly()
    hmac_tests.test_tampered_signature_detected()
    print("  ✓ All HMAC signature tests passed")

    print("\nRunning Hash Chain Tests...")
    chain_tests = TestHashChain()
    chain_tests.test_first_entry_has_genesis_previous_hash()
    chain_tests.test_subsequent_entries_link_to_previous()
    chain_tests.test_chain_verification_passes_for_valid_chain()
    chain_tests.test_broken_chain_detected()
    print("  ✓ All hash chain tests passed")

    print("\nRunning Entry Hash Tests...")
    hash_tests = TestEntryHashIntegrity()
    hash_tests.test_entry_hash_computed_correctly()
    hash_tests.test_tampered_entry_data_detected()
    print("  ✓ All entry hash tests passed")

    print("\nRunning GateAudit Integration Tests...")
    gate_tests = TestGateAuditIntegration()
    gate_tests.test_gate_pass_logged_with_integrity()
    gate_tests.test_multiple_events_form_chain()
    gate_tests.test_cross_sprint_isolation()
    print("  ✓ All GateAudit integration tests passed")

    print("\nRunning JSON Export Tests...")
    export_tests = TestJSONExportIntegrity()
    export_tests.test_export_includes_all_integrity_fields()
    print("  ✓ All JSON export tests passed")

    print("\nRunning Key Management Tests...")
    key_tests = TestKeyManagement()
    key_tests.test_key_from_environment()
    key_tests.test_key_auto_generation()
    print("  ✓ All key management tests passed")

    print("\n" + "=" * 50)
    print("All audit log integrity tests passed!")
    print("=" * 50)
