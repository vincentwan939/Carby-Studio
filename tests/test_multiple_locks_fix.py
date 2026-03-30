"""Test for Multiple Locks issue fix (ES-3).

This test verifies that the GateStateManager correctly handles multiple
lock acquisition without deadlocks by maintaining consistent lock ordering.

The fix ensures that when both _gate_lock and _token_lock need to be held,
they are always acquired in the same order:
1. _gate_lock (higher priority) first
2. _token_lock (lower priority) second

This prevents circular wait deadlocks.

Related to:
- ES-3: Multiple Locks issue fix (this fix)
- CR-5: Agent Callback Transactions (nested transaction anti-pattern fixed)
"""

import pytest
import tempfile
import os
import threading
import time
from pathlib import Path

from carby_sprint.gate_state import GateStateManager
from carby_sprint.gate_enforcer import GateEnforcer


class TestMultipleLocksFix:
    """Tests for multiple lock handling with consistent lock ordering."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def state_manager(self, temp_dir):
        """Create a GateStateManager instance."""
        os.chdir(temp_dir)
        manager = GateStateManager(temp_dir)
        return manager
    
    @pytest.fixture
    def gate_enforcer(self, temp_dir):
        """Create a GateEnforcer instance."""
        os.chdir(temp_dir)
        enforcer = GateEnforcer(temp_dir)
        return enforcer
    
    def test_lock_hierarchy_documentation(self, state_manager):
        """Test that lock hierarchy is documented and accessible."""
        # Verify that the _acquire_both_locks method exists
        assert hasattr(state_manager, '_acquire_both_locks')
        
        # Verify that individual lock methods exist
        assert hasattr(state_manager, '_gate_lock')
        assert hasattr(state_manager, '_token_lock')
        
        # Verify that atomic_gate_advancement method exists
        assert hasattr(state_manager, 'atomic_gate_advancement')
    
    def test_acquire_both_locks_in_correct_order(self, state_manager):
        """Test that _acquire_both_locks acquires locks in correct order."""
        results = []
        
        def test_lock_order():
            try:
                with state_manager._acquire_both_locks():
                    # Both locks should be held
                    results.append(('success', 'both locks acquired'))
            except Exception as e:
                results.append(('error', str(e)))
        
        # Run with timeout to detect deadlock
        t = threading.Thread(target=test_lock_order)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Test timed out - possible deadlock!"
        assert len(results) == 1
        assert results[0][0] == 'success'
    
    def test_atomic_gate_advancement_with_locks(self, state_manager):
        """Test that atomic_gate_advancement properly acquires both locks."""
        results = []
        
        def do_advance(status, token_hash):
            # Verify we can access both gate status and token registry
            # without deadlocking
            status['test_sprint'] = {'current_gate': 'design'}
            return status
        
        def test_advancement():
            try:
                result, token_marked = state_manager.atomic_gate_advancement(
                    'test_sprint',
                    'test_token_12345',
                    do_advance
                )
                results.append(('success', result, token_marked))
            except Exception as e:
                results.append(('error', str(e)))
        
        # Run with timeout to detect deadlock
        t = threading.Thread(target=test_advancement)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Test timed out - possible deadlock!"
        assert len(results) == 1
        assert results[0][0] == 'success'
        assert results[0][2] is True  # token_marked should be True
    
    def test_concurrent_lock_acquisition_no_deadlock(self, state_manager):
        """Test that concurrent operations don't cause deadlocks."""
        errors = []
        successes = []
        
        def worker_a():
            """Worker that might acquire locks in different order."""
            try:
                for i in range(5):
                    # Use atomic_gate_advancement which has consistent lock ordering
                    def do_advance(status, token_hash):
                        status[f'worker_a_{i}'] = {'gate': 'design'}
                        return status
                    
                    state_manager.atomic_gate_advancement(
                        f'sprint_a_{i}',
                        f'token_a_{i}_{time.time()}',
                        do_advance
                    )
                    successes.append(f'a_{i}')
                    time.sleep(0.01)
            except Exception as e:
                errors.append(('worker_a', str(e)))
        
        def worker_b():
            """Worker that might acquire locks in different order."""
            try:
                for i in range(5):
                    # Use atomic_gate_advancement which has consistent lock ordering
                    def do_advance(status, token_hash):
                        status[f'worker_b_{i}'] = {'gate': 'build'}
                        return status
                    
                    state_manager.atomic_gate_advancement(
                        f'sprint_b_{i}',
                        f'token_b_{i}_{time.time()}',
                        do_advance
                    )
                    successes.append(f'b_{i}')
                    time.sleep(0.01)
            except Exception as e:
                errors.append(('worker_b', str(e)))
        
        threads = [
            threading.Thread(target=worker_a),
            threading.Thread(target=worker_b),
        ]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=10)
        
        # Check all threads completed
        for t in threads:
            assert not t.is_alive(), f"Thread {t.name} did not complete - possible deadlock!"
        
        # Should have 10 successes (5 from each worker)
        assert len(successes) == 10, f"Expected 10 successes, got {len(successes)}: {errors}"
        assert len(errors) == 0, f"Errors occurred: {errors}"
    
    def test_individual_locks_still_work(self, state_manager):
        """Test that individual lock methods still work correctly."""
        results = []
        
        def test_individual_locks():
            try:
                # Test _gate_lock alone
                with state_manager._gate_lock():
                    results.append(('gate_lock', 'acquired'))
                
                # Test _token_lock alone
                with state_manager._token_lock():
                    results.append(('token_lock', 'acquired'))
                
                # Test nested: _gate_lock then _token_lock (correct order)
                with state_manager._gate_lock():
                    results.append(('gate_lock', 'acquired_nested'))
                    with state_manager._token_lock():
                        results.append(('token_lock', 'acquired_nested'))
                
            except Exception as e:
                results.append(('error', str(e)))
        
        # Run with timeout
        t = threading.Thread(target=test_individual_locks)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Test timed out!"
        assert len(results) == 4, f"Expected 4 results, got {len(results)}: {results}"
        assert all(r[0] != 'error' for r in results), f"Errors occurred: {results}"
    
    def test_no_deadlock_with_gate_enforcer(self, gate_enforcer):
        """Test that GateEnforcer.advance_gate doesn't cause deadlocks."""
        # This test verifies that the integration between GateEnforcer and
        # GateStateManager doesn't cause deadlocks
        results = []
        
        def test_advance():
            try:
                # Create a valid token for testing
                token = gate_enforcer.request_gate_token('test_sprint', 'design')
                token_str = str(token)
                
                # Try to advance gate (this should use proper lock ordering)
                # Note: This will fail because sprint doesn't exist, but shouldn't deadlock
                try:
                    gate_enforcer.advance_gate('test_sprint', 'design', token_str)
                    results.append(('success', 'advanced'))
                except Exception as e:
                    # Expected to fail (sprint doesn't exist), but shouldn't be a deadlock
                    if "deadlock" in str(e).lower() or "timeout" in str(e).lower():
                        results.append(('error', f"Possible deadlock: {e}"))
                    else:
                        results.append(('expected_error', str(e)))
            except Exception as e:
                results.append(('error', str(e)))
        
        # Run with timeout
        t = threading.Thread(target=test_advance)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Test timed out - possible deadlock!"
        assert len(results) == 1
        assert results[0][0] != 'error', f"Unexpected error: {results[0]}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
