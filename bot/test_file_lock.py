"""Tests for file locking."""

import os
import time
import tempfile
import threading
from pathlib import Path
import unittest

from file_lock import FileLock, ProjectLockManager


class TestFileLock(unittest.TestCase):
    """Test file locking functionality."""
    
    def setUp(self):
        """Create temp directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.lock_file = Path(self.temp_dir) / "test.lock"
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_lock_acquire_release(self):
        """Test basic lock acquire and release."""
        lock = FileLock(self.lock_file)
        
        # Acquire lock
        self.assertTrue(lock.acquire())
        self.assertTrue(self.lock_file.exists())
        
        # Release lock
        self.assertTrue(lock.release())
        self.assertFalse(self.lock_file.exists())
    
    def test_lock_context_manager(self):
        """Test lock as context manager."""
        lock = FileLock(self.lock_file)
        
        with lock:
            self.assertTrue(self.lock_file.exists())
        
        self.assertFalse(self.lock_file.exists())
    
    def test_lock_blocking(self):
        """Test that lock blocks concurrent access."""
        lock1 = FileLock(self.lock_file)
        lock2 = FileLock(self.lock_file)
        
        # First lock acquires
        self.assertTrue(lock1.acquire(blocking=False))
        
        # Second lock should fail (non-blocking)
        self.assertFalse(lock2.acquire(blocking=False))
        
        # Release first
        lock1.release()
        
        # Now second can acquire
        self.assertTrue(lock2.acquire(blocking=False))
        lock2.release()
    
    def test_lock_timeout(self):
        """Test lock timeout."""
        lock1 = FileLock(self.lock_file, timeout=0.1)
        lock2 = FileLock(self.lock_file, timeout=0.1)
        
        # First lock acquires
        lock1.acquire()
        
        # Second lock should timeout
        start = time.time()
        result = lock2.acquire(blocking=True)
        elapsed = time.time() - start
        
        self.assertFalse(result)
        self.assertGreaterEqual(elapsed, 0.1)
        
        lock1.release()
    
    def test_concurrent_locks(self):
        """Test concurrent lock access."""
        results = []
        
        def try_lock(thread_id):
            lock = FileLock(self.lock_file, timeout=1.0)
            start = time.time()
            success = lock.acquire(blocking=True)
            elapsed = time.time() - start
            
            if success:
                time.sleep(0.05)  # Hold lock briefly
                lock.release()
            
            results.append((thread_id, success, elapsed))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=try_lock, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # All should succeed (sequentially)
        self.assertEqual(len(results), 5)
        for thread_id, success, elapsed in results:
            self.assertTrue(success, f"Thread {thread_id} failed to acquire lock")
    
    def test_stale_lock_detection(self):
        """Test detection of stale locks."""
        lock = FileLock(self.lock_file)
        
        # Create a lock file with non-existent PID
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text("99999:1234567890")  # Non-existent PID
        
        # Lock should be detected as stale and removed
        self.assertTrue(lock.acquire())
        self.assertTrue(self.lock_file.exists())
        
        # Verify content was updated
        content = self.lock_file.read_text()
        pid = int(content.split(":")[0])
        self.assertEqual(pid, os.getpid())
        
        lock.release()


class TestProjectLockManager(unittest.TestCase):
    """Test project lock manager."""
    
    def setUp(self):
        """Create temp directory."""
        self.temp_dir = tempfile.mkdtemp()
        self.projects_dir = Path(self.temp_dir) / "projects"
        self.projects_dir.mkdir()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_get_lock(self):
        """Test getting/creating locks."""
        manager = ProjectLockManager(self.projects_dir)
        
        lock1 = manager.get_lock("project-a")
        lock2 = manager.get_lock("project-a")
        lock3 = manager.get_lock("project-b")
        
        # Same project should return same lock instance
        self.assertIs(lock1, lock2)
        
        # Different project should return different lock
        self.assertIsNot(lock1, lock3)
    
    def test_lock_project_context(self):
        """Test lock_project context manager."""
        manager = ProjectLockManager(self.projects_dir)
        
        with manager.lock_project("test-project"):
            # Lock should be held
            lock_file = self.projects_dir / "test-project.lock"
            self.assertTrue(lock_file.exists())
        
        # Lock should be released
        self.assertFalse(lock_file.exists())
    
    def test_concurrent_project_access(self):
        """Test concurrent access to same project."""
        manager = ProjectLockManager(self.projects_dir)
        results = []
        
        def access_project(thread_id):
            try:
                with manager.lock_project("shared-project", timeout=2.0):
                    results.append((thread_id, "success"))
                    time.sleep(0.05)
            except TimeoutError:
                results.append((thread_id, "timeout"))
        
        # Start multiple threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=access_project, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All should succeed
        self.assertEqual(len(results), 3)
        for thread_id, status in results:
            self.assertEqual(status, "success", f"Thread {thread_id} failed")
    
    def test_is_locked(self):
        """Test is_locked check."""
        manager = ProjectLockManager(self.projects_dir)
        
        # Initially not locked
        self.assertFalse(manager.is_locked("test-project"))
        
        # Acquire lock
        with manager.lock_project("test-project"):
            # Should be locked (by us, but is_locked checks for OTHER processes)
            # Since we're same process, it returns False
            pass
        
        # Not locked anymore
        self.assertFalse(manager.is_locked("test-project"))
    
    def test_cleanup_stale_locks(self):
        """Test cleanup of stale locks."""
        manager = ProjectLockManager(self.projects_dir)
        
        # Create some lock files
        (self.projects_dir / "stale.lock").write_text("99999:1234567890")
        (self.projects_dir / "also-stale.lock").write_text("88888:1234567890")
        
        # Create a valid lock (our PID)
        (self.projects_dir / "valid.lock").write_text(f"{os.getpid()}:1234567890")
        
        # Cleanup
        removed = manager.cleanup_stale_locks()
        
        self.assertEqual(removed, 2)
        self.assertFalse((self.projects_dir / "stale.lock").exists())
        self.assertFalse((self.projects_dir / "also-stale.lock").exists())
        self.assertTrue((self.projects_dir / "valid.lock").exists())


class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.projects_dir = Path(self.temp_dir) / "projects"
        self.projects_dir.mkdir()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_read_with_lock(self):
        """Test reading project with lock."""
        from atomic_file import locked_json_read, locked_json_write
        
        project_file = self.projects_dir / "test.json"
        
        # Write test data
        with locked_json_write(project_file, "test", self.projects_dir) as data:
            data["key"] = "value"
        
        # Read with lock
        with locked_json_read(project_file, "test", self.projects_dir) as data:
            self.assertEqual(data["key"], "value")
    
    def test_concurrent_reads_writes(self):
        """Test concurrent read/write operations."""
        from atomic_file import locked_json_write
        
        project_file = self.projects_dir / "concurrent.json"
        results = []
        
        def writer(thread_id):
            for i in range(5):
                try:
                    with locked_json_write(project_file, "concurrent", self.projects_dir) as data:
                        data[f"thread_{thread_id}"] = i
                        time.sleep(0.01)
                    results.append((thread_id, i, "success"))
                except Exception as e:
                    results.append((thread_id, i, f"error: {e}"))
        
        # Start multiple writers
        threads = []
        for i in range(3):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # All should succeed
        errors = [r for r in results if "error" in str(r[2])]
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        
        # Verify final data
        from atomic_file import safe_read_json
        final_data = safe_read_json(project_file)
        self.assertIsNotNone(final_data)


if __name__ == "__main__":
    unittest.main()
