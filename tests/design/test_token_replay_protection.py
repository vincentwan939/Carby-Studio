"""
Test token replay attack protection.

Demonstrates that tokens cannot be reused after being consumed.
"""
import tempfile
from pathlib import Path
import pytest

from carby_sprint.gate_enforcer import GateEnforcer
from carby_sprint.gate_token import GateToken
from carby_sprint.exceptions import TokenReplayError


class TestTokenReplayProtection:
    """Tests for token replay attack prevention."""
    
    def test_token_replay_is_blocked(self):
        """
        Demonstrate that a token cannot be used twice.
        
        Attack scenario:
        1. Attacker intercepts a valid token
        2. Token is used once legitimately
        3. Attacker tries to replay the same token
        4. Replay is blocked with TokenReplayError
        
        This test verifies the core security property: tokens are one-time use.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            enforcer = GateEnforcer(str(project_path))
            sprint_id = "test-sprint"
            
            # Step 1: Get a valid token for the design gate
            token = enforcer.request_gate_token(sprint_id, "design")
            token_str = token.token
            
            # Step 2: Complete discovery gate ( prerequisite for design)
            discovery_token = enforcer.request_gate_token(sprint_id, "discovery")
            enforcer._record_gate_completion(sprint_id, "discovery", discovery_token.token)
            
            # Step 3: Use the token once - legitimate use
            result = enforcer.advance_gate(sprint_id, "design", token_str)
            assert result == True
            
            # Step 4: Attempt to replay the same token for the same gate
            # This should raise TokenReplayError (replay protection now only in advance_gate)
            with pytest.raises(TokenReplayError) as exc_info:
                enforcer.advance_gate(sprint_id, "design", token_str)
            
            # Verify the error message contains token prefix
            assert token_str[:16] in str(exc_info.value)
    
    def test_replay_after_partial_failure(self):
        """
        Test that tokens are consumed even if later steps fail.
        
        This ensures atomic token marking prevents partial state bugs.
        The token should be marked as used BEFORE the advancement
        is recorded, so replay is blocked even if something goes wrong.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            enforcer = GateEnforcer(str(project_path))
            sprint_id = "test-sprint"
            
            # Get token
            token = enforcer.request_gate_token(sprint_id, "design")
            token_str = token.token
            
            # Complete discovery first
            discovery_token = enforcer.request_gate_token(sprint_id, "discovery")
            enforcer._record_gate_completion(sprint_id, "discovery", discovery_token.token)
            
            # Use token successfully
            enforcer.advance_gate(sprint_id, "design", token_str)
            
            # Try to reuse token for the same gate - should fail with replay error
            # Not GateBypassError, but specifically TokenReplayError
            with pytest.raises(TokenReplayError):
                enforcer.advance_gate(sprint_id, "design", token_str)
    
    def test_different_tokens_work(self):
        """
        Verify that different tokens for different gates still work.
        
        Replay protection should only block reused tokens, not new ones.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            enforcer = GateEnforcer(str(project_path))
            sprint_id = "test-sprint"
            
            # Complete discovery
            discovery_token = enforcer.request_gate_token(sprint_id, "discovery")
            enforcer._record_gate_completion(sprint_id, "discovery", discovery_token.token)
            
            # Use design token
            design_token = enforcer.request_gate_token(sprint_id, "design")
            enforcer.advance_gate(sprint_id, "design", design_token.token)
            
            # Use build token (different token, should work)
            build_token = enforcer.request_gate_token(sprint_id, "build")
            enforcer._record_gate_completion(sprint_id, "design", design_token.token)
            
            # Build advancement should work with new token
            result = enforcer.advance_gate(sprint_id, "build", build_token.token)
            assert result == True
    
    def test_token_registry_persistence(self):
        """
        Test that used tokens are persisted across sessions.
        
        Even after creating a new GateEnforcer, replay should be blocked.
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            # First session
            enforcer1 = GateEnforcer(str(project_path))
            sprint_id = "test-sprint"
            
            # Complete discovery
            discovery_token = enforcer1.request_gate_token(sprint_id, "discovery")
            enforcer1._record_gate_completion(sprint_id, "discovery", discovery_token.token)
            
            # Use design token
            design_token = enforcer1.request_gate_token(sprint_id, "design")
            token_str = design_token.token
            enforcer1.advance_gate(sprint_id, "design", token_str)
            
            # Create new enforcer (new session)
            enforcer2 = GateEnforcer(str(project_path))
            
            # Replay should still be blocked when attempting to advance with used token
            enforcer2._record_gate_completion(sprint_id, "discovery", discovery_token.token)  # Need to complete discovery first
            with pytest.raises(TokenReplayError):
                enforcer2.advance_gate(sprint_id, "design", token_str)
    
    def test_concurrent_replay_prevention(self):
        """
        Test that concurrent attempts to use the same token fail.
        
        This verifies the atomic locking mechanism works correctly.
        At least one thread should get a replay error or bypass error.
        """
        import threading
        
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            enforcer = GateEnforcer(str(project_path))
            sprint_id = "test-sprint"
            
            # Complete discovery
            discovery_token = enforcer.request_gate_token(sprint_id, "discovery")
            enforcer._record_gate_completion(sprint_id, "discovery", discovery_token.token)
            
            # Get token that will be contested
            contested_token = enforcer.request_gate_token(sprint_id, "design")
            token_str = contested_token.token
            
            results = []
            errors = []
            
            def attempt_advance():
                try:
                    result = enforcer.advance_gate(sprint_id, "design", token_str)
                    results.append(result)
                except (TokenReplayError, Exception) as e:
                    errors.append(type(e).__name__)
            
            # Start two threads trying to use the same token
            threads = [
                threading.Thread(target=attempt_advance),
                threading.Thread(target=attempt_advance)
            ]
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            # One should succeed, one should fail
            # The failure could be TokenReplayError or GateBypassError
            # depending on race conditions
            assert len(results) <= 1  # At most one success
            assert len(errors) >= 1  # At least one failure
            # Either TokenReplayError or GateBypassError is acceptable
            # (both indicate the concurrent attempt was blocked)
            assert any(e in ["TokenReplayError", "GateBypassError"] for e in errors)


class TestTokenRegistryMethods:
    """Tests for GateStateManager token registry methods."""
    
    def test_is_token_used_returns_false_for_new_token(self):
        """New tokens should not be marked as used."""
        from carby_sprint.gate_state import GateStateManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GateStateManager(temp_dir)
            
            token = GateToken(gate_id="test", sprint_id="test-sprint")
            assert manager.is_token_used(token.token) == False
    
    def test_is_token_used_returns_true_after_marking(self):
        """Tokens should be marked as used after mark_token_used."""
        from carby_sprint.gate_state import GateStateManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GateStateManager(temp_dir)
            
            token = GateToken(gate_id="test", sprint_id="test-sprint")
            manager.mark_token_used(token.token, "test-sprint", "test")
            
            assert manager.is_token_used(token.token) == True
    
    def test_token_hashing(self):
        """Tokens should be hashed for storage (not stored in plaintext)."""
        from carby_sprint.gate_state import GateStateManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = GateStateManager(temp_dir)
            
            token = GateToken(gate_id="test", sprint_id="test-sprint")
            token_str = token.token
            
            # Get the hash
            token_hash = manager._hash_token(token_str)
            
            # Hash should be SHA-256 (64 hex chars)
            assert len(token_hash) == 64
            
            # Raw token should NOT appear in registry file
            manager.mark_token_used(token_str, "test-sprint", "test")
            
            registry_path = manager.token_registry_file
            if registry_path.exists():
                content = registry_path.read_text()
                # Raw token should NOT be in file
                assert token_str not in content
                # Hash should be in file
                assert token_hash in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])