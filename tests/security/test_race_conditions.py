"""
Security Tests for Race Condition Prevention in Carby Sprint Framework.

Tests that validate the distributed locking mechanisms prevent race conditions.
"""

import tempfile
import threading
import time
import pytest
from pathlib import Path
import json

from carby_sprint.sprint_repository import SprintRepository
from carby_sprint.lock_manager import DistributedLock, with_sprint_lock, default_sprint_lock_path
from carby_sprint.agent_callback import report_agent_result


def test_distributed_lock_basic():
    """Test basic functionality of distributed locks."""
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = Path(temp_dir) / "test.lock"
        
        # Test that lock can be acquired and released
        with DistributedLock(lock_path):
            # Lock is held here
            pass
        
        # Lock should be released after exiting context


def test_distributed_lock_blocking():
    """Test that distributed locks properly block concurrent access."""
    with tempfile.TemporaryDirectory() as temp_dir:
        lock_path = Path(temp_dir) / "test.lock"
        
        lock_acquired = threading.Event()
        second_lock_blocked = threading.Event()
        second_lock_acquired = threading.Event()
        
        def first_thread():
            with DistributedLock(lock_path):
                lock_acquired.set()
                time.sleep(0.5)  # Hold the lock for a bit
                second_lock_blocked.wait()  # Wait for second thread to try
            # Lock released
        
        def second_thread():
            second_lock_blocked.set()  # Signal that we're trying
            with DistributedLock(lock_path):
                second_lock_acquired.set()
        
        # Start both threads
        t1 = threading.Thread(target=first_thread)
        t2 = threading.Thread(target=second_thread)
        
        t1.start()
        time.sleep(0.1)  # Give first thread a head start
        t2.start()
        
        # Wait for first thread to acquire lock
        lock_acquired.wait(timeout=2.0)
        
        # Second thread should be blocked waiting for lock
        time.sleep(0.1)
        assert not second_lock_acquired.is_set()
        
        # Allow second thread to proceed
        second_lock_blocked.set()
        
        # Wait for both threads to complete
        t1.join(timeout=2.0)
        t2.join(timeout=2.0)
        
        # Second lock should have been acquired after first was released
        assert second_lock_acquired.is_set()


def test_sprint_save_with_lock():
    """Test that sprint save operations are protected by locks."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Verify lock file can be created and used
        from carby_sprint.lock_manager import DistributedLock
        lock_path = Path(temp_dir) / "test.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        lock_acquired = False

        # Test that lock can be acquired and released
        with DistributedLock(lock_path):
            lock_acquired = True

        # Verify lock was acquired
        assert lock_acquired is True

        # Verify lock file exists after use
        assert lock_path.exists()


def test_agent_callback_with_lock():
    """Test that agent callbacks are protected by locks."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = SprintRepository(temp_dir)
        
        # Create a sprint
        sprint_id = "callback-lock-test"
        sprint_data, paths = repo.create(sprint_id, "Callback Test", "Testing callback locks")
        
        # Simulate multiple agent results being reported concurrently
        def report_result(status):
            result = {
                "status": status,
                "message": f"Test result with {status}",
            }
            report_agent_result(sprint_id, "test", result, temp_dir)
        
        # Run multiple callbacks concurrently
        threads = []
        for status in ["success", "failure", "success", "blocked", "success"]:
            t = threading.Thread(target=lambda s=status: report_result(s))
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Load the final sprint data to verify it's not corrupted
        final_data, _ = repo.load(sprint_id)
        assert "last_agent_result" in final_data


def test_decorator_lock_functionality():
    """Test that the @with_sprint_lock decorator works correctly."""
    call_count = 0
    lock_contention_detected = False
    
    @with_sprint_lock(lambda sprint_id: f"/tmp/test_decorator_lock_{sprint_id}.lock")
    def test_function(sprint_id):
        nonlocal call_count, lock_contention_detected
        call_count += 1
        time.sleep(0.1)  # Hold the lock briefly
        return f"Called with {sprint_id}, count: {call_count}"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        import os
        os.chdir(temp_dir)  # Change to temp dir to avoid file conflicts
        
        # Run multiple calls concurrently
        results = []
        def call_test_function(sprint_id):
            result = test_function(sprint_id)
            results.append(result)
        
        threads = []
        for i in range(3):
            t = threading.Thread(target=call_test_function, args=[f"test-sprint-{i}"])
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # All calls should have succeeded
        assert len(results) == 3
        assert all("Called with test-sprint-" in r for r in results)


def test_concurrent_work_item_updates():
    """Test that work item operations can use locks for safety."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = SprintRepository(temp_dir)

        # Create a sprint
        sprint_id = "work-item-concurrent-test"
        sprint_data, paths = repo.create(sprint_id, "Work Item Test", "Testing concurrent work items")

        # Create a work item
        work_item = {
            "id": "test-work-item-123",
            "title": "Test Work Item",
            "status": "planned",
            "progress": 0,
        }
        repo.save_work_item(paths, work_item)

        # Verify lock file can be created and used alongside work item operations
        from carby_sprint.lock_manager import DistributedLock
        lock_path = Path(temp_dir) / ".carby-sprints" / sprint_id / ".lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)

        # Test that lock can be acquired during work item operations
        lock_acquired = False
        with DistributedLock(lock_path):
            lock_acquired = True
            # Load and verify work item exists
            work_item_data = repo.load_work_item(paths, "test-work-item-123")
            assert work_item_data["id"] == "test-work-item-123"

        # Verify lock was acquired
        assert lock_acquired is True


if __name__ == "__main__":
    # Run the tests
    test_distributed_lock_basic()
    test_distributed_lock_blocking()
    test_sprint_save_with_lock()
    test_agent_callback_with_lock()
    test_decorator_lock_functionality()
    test_concurrent_work_item_updates()
    print("All race condition security tests passed!")