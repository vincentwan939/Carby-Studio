"""
Test for Token Registry Bypass vulnerability fix.

This test verifies that the atomic check-and-mark operation prevents
the race condition where two concurrent threads could both pass the
"is token used" check before either marks it as used.

Vulnerability: Token Registry Bypass (N1)
Fix: Added check_and_mark_token_used() atomic operation
"""
import tempfile
import threading
import time
from pathlib import Path
import pytest

from carby_sprint.gate_state import GateStateManager
from carby_sprint.gate_token import GateToken
from carby_sprint.exceptions import TokenReplayError


class TestTokenRegistryBypassFix:
    """Tests for the Token Registry Bypass vulnerability fix."""
    
    def test_check_and_mark_token_used_atomic(self):
        """
        Test that check_and_mark_token_used is truly atomic.
        
        The method should:
        1. Return (True, _) if token was not used and is now marked
        2. Return (False, _) if token was already used
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GateStateManager(temp_dir)
            token = GateToken(gate_id="test", sprint_id="test-sprint")
            
            # First call should succeed (token not used)
            claimed, _ = manager.check_and_mark_token_used(
                token.token, "test-sprint", "test", "user-1"
            )
            assert claimed is True, "First claim should succeed"
            
            # Second call should fail (token already used)
            claimed2, _ = manager.check_and_mark_token_used(
                token.token, "test-sprint", "test", "user-2"
            )
            assert claimed2 is False, "Second claim should fail (replay detected)"
    
    def test_concurrent_check_and_mark_only_one_succeeds(self):
        """
        Test that concurrent check_and_mark_token_used calls result in
        only one success.
        
        This is the core test for the Token Registry Bypass fix.
        Without atomic check-and-mark, both threads could succeed.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GateStateManager(temp_dir)
            token = GateToken(gate_id="test", sprint_id="test-sprint")
            
            results = []
            
            def attempt_claim():
                claimed, _ = manager.check_and_mark_token_used(
                    token.token, "test-sprint", "test", "user"
                )
                results.append(claimed)
            
            # Start multiple threads trying to claim the same token
            threads = []
            for _ in range(10):
                t = threading.Thread(target=attempt_claim)
                threads.append(t)
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            # Exactly one should succeed
            success_count = sum(1 for r in results if r is True)
            failure_count = sum(1 for r in results if r is False)
            
            assert success_count == 1, f"Expected exactly 1 success, got {success_count}"
            assert failure_count == 9, f"Expected exactly 9 failures, got {failure_count}"
    
    def test_is_token_used_still_works_after_fix(self):
        """
        Test that the is_token_used method still works correctly
        after the bypass fix.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GateStateManager(temp_dir)
            token = GateToken(gate_id="test", sprint_id="test-sprint")
            
            # Token should not be used initially
            assert manager.is_token_used(token.token) is False
            
            # Mark token as used via check_and_mark
            claimed, _ = manager.check_and_mark_token_used(
                token.token, "test-sprint", "test", "user"
            )
            assert claimed is True
            
            # Token should now be marked as used
            assert manager.is_token_used(token.token) is True
    
    def test_mark_token_used_still_works_after_fix(self):
        """
        Test that the mark_token_used method still works correctly
        after the bypass fix.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GateStateManager(temp_dir)
            token = GateToken(gate_id="test", sprint_id="test-sprint")
            
            # Mark token as used via mark_token_used
            manager.mark_token_used(token.token, "test-sprint", "test", "user")
            
            # Token should be marked as used
            assert manager.is_token_used(token.token) is True
            
            # check_and_mark should now return False
            claimed, _ = manager.check_and_mark_token_used(
                token.token, "test-sprint", "test", "user-2"
            )
            assert claimed is False
    
    def test_check_and_mark_preserves_token_info(self):
        """
        Test that check_and_mark_token_used preserves the token info
        correctly in the registry.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GateStateManager(temp_dir)
            token = GateToken(gate_id="design", sprint_id="sprint-123")
            
            claimed, _ = manager.check_and_mark_token_used(
                token.token, "sprint-123", "design", "user-456"
            )
            assert claimed is True
            
            # Verify the token info is stored correctly
            token_hash = manager._hash_token(token.token)
            with manager._token_lock():
                registry = manager._load_token_registry()
                assert token_hash in registry
                info = registry[token_hash]
                assert info["sprint_id"] == "sprint-123"
                assert info["gate"] == "design"
                assert info["user_id"] == "user-456"
                assert "used_at" in info


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
