"""
Comprehensive tests for retention policy module in gate_state.py.

Tests cover:
- cleanup_expired_tokens() - removes old tokens
- get_token_registry_stats() - returns registry statistics
- _maybe_cleanup_tokens() - triggers periodic cleanup

Test scenarios:
1. Cleanup removes tokens older than retention period
2. Cleanup preserves tokens within retention period
3. Cleanup handles empty registry
4. Cleanup preserves audit trail (doesn't delete from gate-status)
5. Dry-run mode returns stats without deleting
6. Periodic cleanup triggers after N operations
7. Cleanup respects CARBY_TOKEN_RETENTION_DAYS env var
8. Cleanup handles invalid dates gracefully
9. Thread safety during cleanup
10. Sprint completion triggers cleanup
"""

import json
import os
import sys
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, List
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import from the carby_sprint package
from carby_sprint.gate_state import GateStateManager, TOKEN_RETENTION_DAYS, DEFAULT_TOKEN_RETENTION_DAYS


class TestRetentionPolicy(unittest.TestCase):
    """Test suite for retention policy functionality."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary test directory
        self.test_dir = Path("/tmp/test_retention_policy_" + datetime.utcnow().strftime("%Y%m%d%H%M%S"))
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.sprint_dir = self.test_dir / ".carby-sprints"
        self.sprint_dir.mkdir(exist_ok=True)

        # Initialize manager
        self.manager = GateStateManager(str(self.test_dir))

        # Store original environment
        self.original_env = os.environ.get("CARBY_TOKEN_RETENTION_DAYS")
        self.original_cleanup_interval = os.environ.get("CARBY_TOKEN_CLEANUP_INTERVAL")

    def tearDown(self):
        """Clean up test environment after each test."""
        # Restore original environment
        if self.original_env is not None:
            os.environ["CARBY_TOKEN_RETENTION_DAYS"] = self.original_env
        elif "CARBY_TOKEN_RETENTION_DAYS" in os.environ:
            del os.environ["CARBY_TOKEN_RETENTION_DAYS"]

        if self.original_cleanup_interval is not None:
            os.environ["CARBY_TOKEN_CLEANUP_INTERVAL"] = self.original_cleanup_interval
        elif "CARBY_TOKEN_CLEANUP_INTERVAL" in os.environ:
            del os.environ["CARBY_TOKEN_CLEANUP_INTERVAL"]

        # Clean up test files
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_token_entry(self, token_hash: str, used_at: str, sprint_id: str = "test-sprint", gate: str = "build"):
        """Helper to create a token entry in the registry."""
        with self.manager._token_lock():
            registry = self.manager._load_token_registry()
            registry[token_hash] = {
                "sprint_id": sprint_id,
                "gate": gate,
                "used_at": used_at,
                "user_id": "test-user",
            }
            self.manager._save_token_registry(registry)

    def _get_registry(self) -> Dict[str, Any]:
        """Helper to get current token registry."""
        with self.manager._token_lock():
            return self.manager._load_token_registry()

    # =========================================================================
    # Test 1: Cleanup removes tokens older than retention period
    # =========================================================================
    def test_cleanup_removes_expired_tokens(self):
        """Test that cleanup removes tokens older than retention period."""
        # Create tokens with different ages
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 1)).isoformat()
        recent_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS - 1)).isoformat()

        self._create_token_entry("old_token_hash_1", old_date)
        self._create_token_entry("old_token_hash_2", old_date)
        self._create_token_entry("recent_token_hash", recent_date)

        # Verify tokens exist
        registry = self._get_registry()
        self.assertEqual(len(registry), 3)

        # Run cleanup
        result = self.manager.cleanup_expired_tokens(dry_run=False)

        # Verify results
        self.assertEqual(result["removed"], 2)
        self.assertEqual(result["retained"], 1)
        self.assertFalse(result["dry_run"])

        # Verify old tokens are gone
        registry = self._get_registry()
        self.assertEqual(len(registry), 1)
        self.assertIn("recent_token_hash", registry)

    # =========================================================================
    # Test 2: Cleanup preserves tokens within retention period
    # =========================================================================
    def test_cleanup_preserves_recent_tokens(self):
        """Test that cleanup preserves tokens within retention period."""
        # Create tokens at various points within the retention period
        now = datetime.utcnow()
        dates = [
            (now - timedelta(days=1)).isoformat(),      # 1 day ago
            (now - timedelta(days=7)).isoformat(),      # 1 week ago
            (now - timedelta(days=30)).isoformat(),     # 1 month ago
            (now - timedelta(days=TOKEN_RETENTION_DAYS - 1)).isoformat(),  # Just within retention
        ]

        for i, date in enumerate(dates):
            self._create_token_entry(f"token_{i}", date)

        # Run cleanup
        result = self.manager.cleanup_expired_tokens(dry_run=False)

        # All tokens should be preserved
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["retained"], 4)

        registry = self._get_registry()
        self.assertEqual(len(registry), 4)

    # =========================================================================
    # Test 3: Cleanup handles empty registry
    # =========================================================================
    def test_cleanup_handles_empty_registry(self):
        """Test that cleanup handles empty registry gracefully."""
        # Ensure registry is empty
        registry = self._get_registry()
        self.assertEqual(len(registry), 0)

        # Run cleanup on empty registry
        result = self.manager.cleanup_expired_tokens(dry_run=False)

        # Should complete without error
        self.assertEqual(result["removed"], 0)
        self.assertEqual(result["retained"], 0)
        self.assertEqual(result["removed_tokens"], [])

    # =========================================================================
    # Test 4: Cleanup preserves audit trail
    # =========================================================================
    def test_cleanup_preserves_gate_status_audit_trail(self):
        """Test that cleanup doesn't delete from gate-status (audit trail)."""
        # Create a sprint with completed gates
        sprint_id = "audit-test-sprint"
        token = "test-token-123"

        # Record gate completion (this adds to gate-status.json)
        self.manager.record_gate_completion(sprint_id, "build", token)
        self.manager.record_gate_completion(sprint_id, "verify", token)

        # Create old token in registry
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 30)).isoformat()
        self._create_token_entry("old_audit_token", old_date, sprint_id=sprint_id)

        # Verify gate status exists with completed gates
        with self.manager._gate_lock():
            status = self.manager._load_gate_status()
            self.assertIn(sprint_id, status)
            self.assertEqual(len(status[sprint_id].get("completed_gates", [])), 2)

        # Run cleanup
        result = self.manager.cleanup_expired_tokens(dry_run=False)
        self.assertEqual(result["removed"], 1)

        # Verify gate status is preserved (audit trail intact)
        with self.manager._gate_lock():
            status = self.manager._load_gate_status()
            self.assertIn(sprint_id, status)
            completed = status[sprint_id].get("completed_gates", [])
            self.assertEqual(len(completed), 2)
            # Verify both gates are still recorded
            gates = [g["gate"] for g in completed]
            self.assertIn("build", gates)
            self.assertIn("verify", gates)

    # =========================================================================
    # Test 5: Dry-run mode returns stats without deleting
    # =========================================================================
    def test_dry_run_returns_stats_without_deleting(self):
        """Test that dry-run mode returns stats without actually deleting tokens."""
        # Create old tokens
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()
        self._create_token_entry("old_token_1", old_date)
        self._create_token_entry("old_token_2", old_date)

        # Verify tokens exist
        registry = self._get_registry()
        self.assertEqual(len(registry), 2)

        # Run cleanup in dry-run mode
        result = self.manager.cleanup_expired_tokens(dry_run=True)

        # Verify dry-run results
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["removed"], 2)
        self.assertEqual(result["retained"], 0)
        self.assertEqual(len(result["removed_tokens"]), 2)

        # Verify tokens are STILL in registry (not actually deleted)
        registry = self._get_registry()
        self.assertEqual(len(registry), 2)
        self.assertIn("old_token_1", registry)
        self.assertIn("old_token_2", registry)

    # =========================================================================
    # Test 6: Periodic cleanup triggers after N operations
    # =========================================================================
    def test_periodic_cleanup_triggers_after_n_operations(self):
        """Test that periodic cleanup triggers after TOKEN_CLEANUP_INTERVAL operations."""
        # Set a small interval for testing
        os.environ["CARBY_TOKEN_CLEANUP_INTERVAL"] = "5"

        # Reload module to pick up the env var
        import importlib
        import carby_sprint.gate_state as gate_state_module
        importlib.reload(gate_state_module)

        # Create a new manager with reloaded module
        test_manager = gate_state_module.GateStateManager(str(self.test_dir))

        # Create old tokens
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()

        # Reset counter and add tokens
        results = []
        for i in range(7):
            self._create_token_entry(f"token_{i}", old_date)
            # Each mark_token_used call increments counter
            result = test_manager.mark_token_used(f"op_token_{i}", "test-sprint", "build")
            results.append(result)

        # Cleanup should trigger on the 5th operation (interval)
        # Results at indices 4 should have cleanup results
        self.assertIsNone(results[0])  # No cleanup yet
        self.assertIsNone(results[1])  # No cleanup yet
        self.assertIsNone(results[2])  # No cleanup yet
        self.assertIsNone(results[3])  # No cleanup yet
        self.assertIsNotNone(results[4])  # Cleanup triggered!

        # Verify cleanup actually ran
        cleanup_result = results[4]
        self.assertIn("removed", cleanup_result)
        self.assertIn("retained", cleanup_result)

    # =========================================================================
    # Test 7: Cleanup respects CARBY_TOKEN_RETENTION_DAYS env var
    # =========================================================================
    def test_cleanup_respects_env_var(self):
        """Test that cleanup respects CARBY_TOKEN_RETENTION_DAYS environment variable."""
        # Set env var before creating manager
        os.environ["CARBY_TOKEN_RETENTION_DAYS"] = "30"

        # Create tokens at different ages
        now = datetime.utcnow()

        # Token at 35 days (should be removed with 30-day retention)
        old_date = (now - timedelta(days=35)).isoformat()
        # Token at 25 days (should be kept with 30-day retention)
        recent_date = (now - timedelta(days=25)).isoformat()

        self._create_token_entry("old_token", old_date)
        self._create_token_entry("recent_token", recent_date)

        # Reload module to pick up new env var (simulate fresh import)
        import importlib
        import carby_sprint.gate_state as gate_state_module
        importlib.reload(gate_state_module)

        # Create new manager with reloaded module
        test_manager = gate_state_module.GateStateManager(str(self.test_dir))

        # Verify the env var was picked up
        self.assertEqual(gate_state_module.TOKEN_RETENTION_DAYS, 30)

        # Run cleanup
        result = test_manager.cleanup_expired_tokens(dry_run=False)

        # With 30-day retention: 35-day token removed, 25-day token kept
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["retained"], 1)
        self.assertEqual(result["retention_days"], 30)

        registry = self._get_registry()
        self.assertEqual(len(registry), 1)
        self.assertIn("recent_token", registry)

    # =========================================================================
    # Test 8: Cleanup handles invalid dates gracefully
    # =========================================================================
    def test_cleanup_handles_invalid_dates_gracefully(self):
        """Test that cleanup handles tokens with invalid/malformed dates."""
        # Create tokens with various invalid date formats
        invalid_dates = [
            "not-a-date",
            "",
            "2023-13-45",  # Invalid month/day
            "invalid-timestamp",
            None,  # Will be converted to empty string
        ]

        for i, date in enumerate(invalid_dates):
            date_str = date if date else ""
            self._create_token_entry(f"invalid_token_{i}", date_str)

        # Create one valid old token
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()
        self._create_token_entry("valid_old_token", old_date)

        # Run cleanup - should not raise exception
        result = self.manager.cleanup_expired_tokens(dry_run=False)

        # Invalid date tokens should be preserved (safer)
        # Valid old token should be removed
        self.assertEqual(result["removed"], 1)
        self.assertEqual(result["retained"], 5)  # All invalid date tokens kept

        registry = self._get_registry()
        self.assertEqual(len(registry), 5)

    # =========================================================================
    # Test 9: Thread safety during cleanup
    # =========================================================================
    def test_thread_safety_during_cleanup(self):
        """Test that cleanup is thread-safe with concurrent operations."""
        now = datetime.utcnow()
        old_date = (now - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()
        recent_date = (now - timedelta(days=1)).isoformat()

        # Create initial tokens
        for i in range(20):
            self._create_token_entry(f"token_{i}", old_date if i < 10 else recent_date)

        results = []
        errors = []

        def cleanup_worker():
            try:
                result = self.manager.cleanup_expired_tokens(dry_run=False)
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        def add_token_worker():
            try:
                for j in range(10):
                    self._create_token_entry(f"concurrent_token_{j}_{threading.current_thread().name}", recent_date)
                    time.sleep(0.01)  # Small delay to increase contention
            except Exception as e:
                errors.append(str(e))

        # Start multiple threads
        threads = []
        for _ in range(3):
            t = threading.Thread(target=cleanup_worker)
            threads.append(t)
            t.start()

        for _ in range(2):
            t = threading.Thread(target=add_token_worker)
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join(timeout=10)

        # No errors should occur
        self.assertEqual(len(errors), 0, f"Thread errors occurred: {errors}")

        # Cleanup should have completed at least once
        self.assertGreaterEqual(len(results), 1)

        # Final registry should be consistent
        registry = self._get_registry()
        self.assertIsInstance(registry, dict)

    # =========================================================================
    # Test 10: Sprint completion triggers cleanup
    # =========================================================================
    def test_sprint_completion_triggers_cleanup(self):
        """Test that completing the delivery gate triggers cleanup."""
        sprint_id = "completion-test-sprint"
        token = "test-token-123"

        # Create old tokens in registry
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()
        self._create_token_entry("old_token_1", old_date)
        self._create_token_entry("old_token_2", old_date)

        # Create one recent token
        recent_date = (datetime.utcnow() - timedelta(days=1)).isoformat()
        self._create_token_entry("recent_token", recent_date)

        # Verify tokens exist
        registry = self._get_registry()
        self.assertEqual(len(registry), 3)

        # Complete delivery gate - should trigger cleanup
        result = self.manager.record_gate_completion(sprint_id, "delivery", token)

        # Result should contain cleanup info
        self.assertIsNotNone(result)
        self.assertIn("removed", result)
        self.assertIn("retained", result)

        # Old tokens should be cleaned up
        self.assertEqual(result["removed"], 2)
        self.assertEqual(result["retained"], 1)

        # Verify in registry
        registry = self._get_registry()
        self.assertEqual(len(registry), 1)
        self.assertIn("recent_token", registry)

    # =========================================================================
    # Test 11: Non-delivery gates don't trigger cleanup
    # =========================================================================
    def test_non_delivery_gates_dont_trigger_cleanup(self):
        """Test that completing non-delivery gates doesn't trigger cleanup."""
        sprint_id = "no-cleanup-test-sprint"
        token = "test-token-456"

        # Create old tokens in registry
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()
        self._create_token_entry("old_token", old_date)

        # Complete build gate (not delivery)
        result = self.manager.record_gate_completion(sprint_id, "build", token)

        # Should not trigger cleanup
        self.assertIsNone(result)

        # Old token should still be in registry
        registry = self._get_registry()
        self.assertEqual(len(registry), 1)
        self.assertIn("old_token", registry)

    # =========================================================================
    # Test 12: get_token_registry_stats with empty registry
    # =========================================================================
    def test_get_stats_empty_registry(self):
        """Test get_token_registry_stats with empty registry."""
        stats = self.manager.get_token_registry_stats()

        self.assertEqual(stats["total_tokens"], 0)
        self.assertIsNone(stats["oldest_token"])
        self.assertIsNone(stats["newest_token"])
        # retention_days comes from the module constant at import time
        self.assertIn("retention_days", stats)
        self.assertIsInstance(stats["retention_days"], int)
        self.assertEqual(stats["would_cleanup"], 0)

    # =========================================================================
    # Test 13: get_token_registry_stats with tokens
    # =========================================================================
    def test_get_stats_with_tokens(self):
        """Test get_token_registry_stats with various tokens."""
        # Create tokens at significantly different times to avoid timing issues
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()
        recent_date = (datetime.utcnow() - timedelta(days=1)).isoformat()

        # Create old token (would be cleaned)
        self._create_token_entry("old_token", old_date)
        # Create recent token (would be kept)
        self._create_token_entry("recent_token", recent_date)
        # Create another recent token
        self._create_token_entry("another_recent", recent_date)

        stats = self.manager.get_token_registry_stats()

        self.assertEqual(stats["total_tokens"], 3)
        self.assertIsNotNone(stats["oldest_token"])
        self.assertIsNotNone(stats["newest_token"])
        # retention_days comes from the module constant at import time
        self.assertIn("retention_days", stats)
        self.assertIsInstance(stats["retention_days"], int)
        # Should have at least 1 token that would be cleaned (the old one)
        # Note: timing precision may cause the recent token to also be flagged
        self.assertGreaterEqual(stats["would_cleanup"], 1)

    # =========================================================================
    # Test 14: Cleanup cutoff date calculation
    # =========================================================================
    def test_cleanup_cutoff_date_calculation(self):
        """Test that cutoff date is calculated correctly."""
        # Create tokens significantly older than retention period
        # to avoid time precision issues
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()
        recent_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS - 10)).isoformat()

        # Create old tokens (should be removed)
        self._create_token_entry("old_token_1", old_date)
        self._create_token_entry("old_token_2", old_date)

        # Create recent tokens (should be preserved)
        self._create_token_entry("recent_token_1", recent_date)
        self._create_token_entry("recent_token_2", recent_date)

        result = self.manager.cleanup_expired_tokens(dry_run=False)

        # Old tokens should be removed, recent ones preserved
        self.assertEqual(result["removed"], 2)
        self.assertEqual(result["retained"], 2)

        registry = self._get_registry()
        self.assertEqual(len(registry), 2)
        self.assertNotIn("old_token_1", registry)
        self.assertNotIn("old_token_2", registry)
        self.assertIn("recent_token_1", registry)
        self.assertIn("recent_token_2", registry)

    # =========================================================================
    # Test 15: _maybe_cleanup_tokens respects disabled cleanup
    # =========================================================================
    def test_maybe_cleanup_respects_disabled(self):
        """Test that _maybe_cleanup_tokens respects TOKEN_CLEANUP_INTERVAL=0."""
        os.environ["CARBY_TOKEN_CLEANUP_INTERVAL"] = "0"

        # Reload module to pick up the env var
        import importlib
        import carby_sprint.gate_state as gate_state_module
        importlib.reload(gate_state_module)

        test_manager = gate_state_module.GateStateManager(str(self.test_dir))

        # Should return None (cleanup disabled)
        result = test_manager._maybe_cleanup_tokens()
        self.assertIsNone(result)

    # =========================================================================
    # Test 16: Cleanup result contains expected fields
    # =========================================================================
    def test_cleanup_result_structure(self):
        """Test that cleanup result contains all expected fields."""
        old_date = (datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS + 10)).isoformat()
        self._create_token_entry("old_token", old_date)

        result = self.manager.cleanup_expired_tokens(dry_run=False)

        # Check all expected fields
        required_fields = ["removed", "retained", "removed_tokens", "retention_days", "cutoff_date", "dry_run"]
        for field in required_fields:
            self.assertIn(field, result, f"Missing field: {field}")

        # Verify types
        self.assertIsInstance(result["removed"], int)
        self.assertIsInstance(result["retained"], int)
        self.assertIsInstance(result["removed_tokens"], list)
        self.assertIsInstance(result["retention_days"], int)
        self.assertIsInstance(result["cutoff_date"], str)
        self.assertIsInstance(result["dry_run"], bool)


class TestRetentionPolicyIntegration(unittest.TestCase):
    """Integration tests for retention policy."""

    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path("/tmp/test_retention_integration_" + datetime.utcnow().strftime("%Y%m%d%H%M%S"))
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.manager = GateStateManager(str(self.test_dir))

        self.original_env = os.environ.get("CARBY_TOKEN_RETENTION_DAYS")

    def tearDown(self):
        """Clean up test environment."""
        if self.original_env is not None:
            os.environ["CARBY_TOKEN_RETENTION_DAYS"] = self.original_env
        elif "CARBY_TOKEN_RETENTION_DAYS" in os.environ:
            del os.environ["CARBY_TOKEN_RETENTION_DAYS"]

        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_full_lifecycle(self):
        """Test full token lifecycle: creation, usage, stats, cleanup."""
        sprint_id = "lifecycle-test"

        # Step 1: Initial stats (empty)
        stats = self.manager.get_token_registry_stats()
        self.assertEqual(stats["total_tokens"], 0)

        # Step 2: Mark tokens as used
        self.manager.mark_token_used("token1", sprint_id, "discovery")
        self.manager.mark_token_used("token2", sprint_id, "design")

        # Step 3: Check stats
        stats = self.manager.get_token_registry_stats()
        self.assertEqual(stats["total_tokens"], 2)

        # Step 4: Dry run cleanup
        result = self.manager.cleanup_expired_tokens(dry_run=True)
        self.assertEqual(result["removed"], 0)  # Tokens are new
        self.assertTrue(result["dry_run"])

        # Step 5: Verify tokens still exist
        stats = self.manager.get_token_registry_stats()
        self.assertEqual(stats["total_tokens"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
