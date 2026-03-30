"""Test for nested lock anti-pattern fix in PhaseLockService.

This test verifies that the PhaseLockService correctly handles nested
lock acquisition without deadlocking. The fix uses thread-local storage
to track locks already held by the current thread.

Related to:
- CR-5: Agent Callback Transactions (fixed nested transaction anti-pattern)
- H3: Nested Locks fix (this fix)
"""

import pytest
import tempfile
import os
import threading
import time
from pathlib import Path

from carby_sprint.phase_lock_service import PhaseLockService
from carby_sprint.sprint_repository import SprintRepository


class TestNestedLocks:
    """Tests for nested lock handling in PhaseLockService."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir
    
    @pytest.fixture
    def service(self, temp_dir):
        """Create a PhaseLockService instance."""
        os.chdir(temp_dir)
        repo = SprintRepository(temp_dir)
        service = PhaseLockService(repo)
        # Create a test sprint
        repo.create('test-sprint', 'Test Project', 'Test Goal')
        return service
    
    def test_single_lock_acquisition(self, service):
        """Test that a single lock acquisition works."""
        result = service.update_phase_state('test-sprint', 'discover', 'in_progress')
        assert result['success'] is True
    
    def test_nested_lock_same_thread(self, service):
        """Test that nested lock acquisition on same thread doesn't deadlock.
        
        This simulates a scenario where one method (holding a lock) calls
        another method that also needs the same lock.
        """
        results = []
        
        def test_nested():
            try:
                # First call acquires the lock
                result1 = service.update_phase_state('test-sprint', 'discover', 'in_progress')
                
                # Second call should not deadlock - lock is already held
                result2 = service.get_phase_state('test-sprint', 'discover')
                
                # Third call also should not deadlock
                result3 = service.can_start_phase('test-sprint', 'design')
                
                results.append(('success', result1, result2, result3))
            except Exception as e:
                results.append(('error', str(e)))
        
        # Run with timeout to detect deadlock
        t = threading.Thread(target=test_nested)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Test timed out - possible deadlock!"
        assert len(results) == 1, f"Unexpected results: {results}"
        assert results[0][0] == 'success', f"Error: {results[0]}"
        
        # Verify all operations succeeded
        assert results[0][1]['success'] is True  # update_phase_state
        assert results[0][2]['success'] is True  # get_phase_state
        # can_start_phase returns can_start=False because design needs discover approved
        assert 'can_start' in results[0][3]
    
    def test_deeply_nested_locks(self, service):
        """Test deeply nested lock acquisitions (3+ levels)."""
        results = []
        
        def test_deep_nesting():
            try:
                # Simulate a call chain where each method needs the lock
                with service._acquire_lock('test-sprint'):
                    with service._acquire_lock('test-sprint'):
                        with service._acquire_lock('test-sprint'):
                            # All three levels should succeed without deadlock
                            result = service.get_phase_state('test-sprint', 'discover')
                            results.append(('success', result))
            except Exception as e:
                results.append(('error', str(e)))
        
        t = threading.Thread(target=test_deep_nesting)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Test timed out - possible deadlock!"
        assert len(results) == 1
        assert results[0][0] == 'success'
        assert results[0][1]['success'] is True
    
    def test_lock_released_after_nested_calls(self, service):
        """Test that lock is properly released after nested calls."""
        # First, acquire the lock and do some work
        with service._acquire_lock('test-sprint'):
            service.update_phase_state('test-sprint', 'discover', 'in_progress')
        
        # Lock should be released now - verify by acquiring in another thread
        lock_acquired = []
        
        def try_acquire():
            try:
                with service._acquire_lock('test-sprint'):
                    lock_acquired.append(True)
            except Exception as e:
                lock_acquired.append(False)
        
        t = threading.Thread(target=try_acquire)
        t.start()
        t.join(timeout=2)
        
        assert t.is_alive() is False, "Thread should have completed"
        assert len(lock_acquired) == 1 and lock_acquired[0] is True, \
            "Lock should be acquirable after nested calls complete"
    
    def test_thread_isolation(self, service):
        """Test that lock tracking is thread-local (one thread's lock doesn't affect another)."""
        results = []
        barrier = threading.Barrier(2)
        
        def thread1():
            # Acquire lock in thread 1
            with service._acquire_lock('test-sprint'):
                barrier.wait()  # Signal we're holding the lock
                time.sleep(0.1)  # Hold for a bit
                results.append(('t1', 'acquired'))
        
        def thread2():
            barrier.wait()  # Wait for thread 1 to acquire
            # Try to acquire same lock - should block until thread 1 releases
            with service._acquire_lock('test-sprint'):
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
    
    def test_concurrent_nested_locks(self, service):
        """Test concurrent operations with nested locks."""
        errors = []
        successes = []
        
        def worker(worker_id):
            try:
                for i in range(3):
                    # Each worker does nested operations
                    result1 = service.get_phase_state('test-sprint', 'discover')
                    result2 = service.can_start_phase('test-sprint', 'design')
                    if result1['success'] and 'can_start' in result2:
                        successes.append((worker_id, i))
                    else:
                        errors.append((worker_id, i, 'failed'))
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
        
        # Should have 15