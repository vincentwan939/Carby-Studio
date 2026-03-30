"""Test for reentrant lock support in GateStateManager.

This test verifies that GateStateManager correctly handles nested
lock acquisition without deadlocking. The fix uses thread-local storage
to track locks already held by the current thread.

Related to:
- ES-4: Double Locking fix (this fix)
- CR-5: Agent Callback Transactions (fixed nested transaction anti-pattern)
"""

import pytest
import tempfile
import os
import threading
import time
from pathlib import Path

from carby_sprint.gate_state import GateStateManager


class TestGateStateReentrantLocks:
    """Tests for reentrant lock handling in GateStateManager."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def manager(self, temp_dir):
        """Create a GateStateManager instance."""
        os.chdir(temp_dir)
        manager = GateStateManager(temp_dir)
        return manager
    
    def test_single_gate_lock_acquisition(self, manager):
        """Test that a single gate lock acquisition works."""
        with manager._gate_lock():
            # Lock acquired successfully
            pass
    
    def test_single_token_lock_acquisition(self, manager):
        """Test that a single token lock acquisition works."""
        with manager._token_lock():
            # Lock acquired successfully
            pass
    
    def test_nested_gate_lock_same_thread(self, manager):
        """Test that nested gate lock acquisition on same thread doesn't deadlock."""
        results = []
        
        def test_nested():
            try:
                # First call acquires the lock
                with manager._gate_lock():
                    # Second call should not deadlock - lock is already held
                    with manager._gate_lock():
                        # Third level of nesting
                        with manager._gate_lock():
                            results.append(('success', 'nested_locks'))
            except Exception as e:
                results.append(('error', str(e)))
        
        # Run with timeout to detect deadlock
        t = threading.Thread(target=test_nested)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Test timed out - possible deadlock!"
        assert len(results) == 1, f"Unexpected results: {results}"
        assert results[0][0] == 'success', f"Error: {results[0]}"
    
    def test_nested_token_lock_same_thread(self, manager):
        """Test that nested token lock acquisition on same thread doesn't deadlock."""
        results = []
        
        def test_nested():
            try:
                # First call acquires the lock
                with manager._token_lock():
                    # Second call should not deadlock - lock is already held
                    with manager._token_lock():
                        # Third level of nesting
                        with manager._token_lock():
                            results.append(('success', 'nested_token_locks'))
            except Exception as e:
                results.append(('error', str(e)))
        
        # Run with timeout to detect deadlock
        t = threading.Thread(target=test_nested)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Test timed out - possible deadlock!"
        assert len(results) == 1, f"Unexpected results: {results}"
        assert results[0][0] == 'success', f"Error: {results[0]}"
    
    def test_gate_lock_released_after_nested_calls(self, manager):
        """Test that gate lock is properly released after nested calls."""
        # First, acquire the lock and do some work
        with manager._gate_lock():
            with manager._gate_lock():
                pass
        
        # Lock should be released now - verify by acquiring in another thread
        lock_acquired = []
        
        def try_acquire():
            try:
                with manager._gate_lock():
                    lock_acquired.append(True)
            except Exception as e:
                lock_acquired.append(False)
        
        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=2)
        
        assert t.is_alive() is False, "Thread should have completed"
        assert len(lock_acquired) == 1 and lock_acquired[0] is True, \
            "Lock should be acquirable after nested calls complete"
    
    def test_token_lock_released_after_nested_calls(self, manager):
        """Test that token lock is properly released after nested calls."""
        # First, acquire the lock and do some work
        with manager._token_lock():
            with manager._token_lock():
                pass
        
        # Lock should be released now - verify by acquiring in another thread
        lock_acquired = []
        
        def try_acquire():
            try:
                with manager._token_lock():
                    lock_acquired.append(True)
            except Exception as e:
                lock_acquired.append(False)
        
        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=2)
        
        assert t.is_alive() is False, "Thread should have completed"
        assert len(lock_acquired) == 1 and lock_acquired[0] is True, \
            "Lock should be acquirable after nested calls complete"
    
    def test_thread_isolation_gate_lock(self, manager):
        """Test that gate lock tracking is thread-local."""
        results = []
        barrier = threading.Barrier(2)
        
        def thread1():
            # Acquire lock in thread 1
            with manager._gate_lock():
                barrier.wait()  # Signal we're holding the lock
                time.sleep(0.1)  # Hold for a bit
                results.append(('t1', 'acquired'))
        
        def thread2():
            barrier.wait()  # Wait for thread 1 to acquire
            # Try to acquire same lock - should block until thread 1 releases
            with manager._gate_lock():
                results.append(('t2', 'acquired'))
        
        t1 = threading.Thread(target=thread1)
        t2 = threading.Thread(target=thread2)
        
        t1.start()
        t2.start()
        
        t1.join(timeout=3)
        t2.join(timeout=3)
        
        assert not t1.is_alive(), "Thread 1 should have completed"
        assert not t2.is_alive(), "Thread 2 should have completed (possible deadlock!)"
        
        # Thread 1 should acquire first, then thread 2
        assert results[0] == ('t1', 'acquired')
        assert results[1] == ('t2', 'acquired')
    
    def test_concurrent_nested_gate_locks(self, manager):
        """Test concurrent operations with nested gate locks."""
        errors = []
        successes = []
        
        def worker(worker_id):
            try:
                for i in range(3):
                    # Each worker does nested operations
                    with manager._gate_lock():
                        with manager._gate_lock():
                            successes.append((worker_id, i))
                    time.sleep(0.01)
            except Exception as e:
                errors.append((worker_id, 'exception', str(e)))
        
        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join(timeout=10)
        
        # Check all threads completed
        for t in threads:
            assert not t.is_alive(), f"Thread {t.name} did not complete - possible deadlock!"
        
        # Should have 15 successes (5 workers * 3 iterations)
        assert len(successes) == 15, f"Expected 15 successes, got {len(successes)}"
        assert len(errors) == 0, f"Errors occurred: {errors}"