"""Tests for atomic file operations."""

import json
import os
import tempfile
import threading
import time
from pathlib import Path
import unittest

from atomic_file import atomic_write_json, safe_read_json, safe_write_json


class TestAtomicFileOperations(unittest.TestCase):
    """Test atomic file write operations."""
    
    def setUp(self):
        """Create temp directory for tests."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.json"
    
    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_atomic_write_success(self):
        """Test successful atomic write."""
        data = {"key": "value", "number": 42}
        
        result = atomic_write_json(self.test_file, data)
        
        self.assertTrue(result)
        self.assertTrue(self.test_file.exists())
        
        # Verify content
        with open(self.test_file, 'r') as f:
            read_data = json.load(f)
        self.assertEqual(read_data, data)
    
    def test_atomic_write_creates_directories(self):
        """Test atomic write creates parent directories."""
        nested_file = Path(self.temp_dir) / "nested" / "deep" / "file.json"
        data = {"test": "data"}
        
        result = atomic_write_json(nested_file, data)
        
        self.assertTrue(result)
        self.assertTrue(nested_file.exists())
    
    def test_safe_read_existing_file(self):
        """Test reading existing file."""
        data = {"hello": "world"}
        atomic_write_json(self.test_file, data)
        
        result = safe_read_json(self.test_file)
        
        self.assertEqual(result, data)
    
    def test_safe_read_nonexistent_file(self):
        """Test reading non-existent file returns None."""
        nonexistent = Path(self.temp_dir) / "does_not_exist.json"
        
        result = safe_read_json(nonexistent)
        
        self.assertIsNone(result)
    
    def test_safe_read_invalid_json(self):
        """Test reading invalid JSON returns None."""
        # Write invalid JSON directly
        with open(self.test_file, 'w') as f:
            f.write("{invalid json")
        
        result = safe_read_json(self.test_file)
        
        self.assertIsNone(result)
    
    def test_safe_write_fallback(self):
        """Test safe write with fallback."""
        data = {"fallback": "test"}
        
        result = safe_write_json(self.test_file, data)
        
        self.assertTrue(result)
        
        read_data = safe_read_json(self.test_file)
        self.assertEqual(read_data, data)
    
    def test_concurrent_writes(self):
        """Test that concurrent writes don't corrupt data."""
        errors = []
        success_count = [0]
        
        def writer(thread_id):
            for i in range(10):
                data = {
                    "thread": thread_id,
                    "iteration": i,
                    "timestamp": time.time()
                }
                try:
                    if atomic_write_json(self.test_file, data):
                        success_count[0] += 1
                    # Small delay to increase chance of overlap
                    time.sleep(0.001)
                except Exception as e:
                    errors.append((thread_id, i, str(e)))
        
        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=writer, args=(i,))
            threads.append(t)
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # Should have no errors
        self.assertEqual(len(errors), 0, f"Errors during concurrent writes: {errors}")
        
        # File should exist and be valid JSON
        self.assertTrue(self.test_file.exists())
        result = safe_read_json(self.test_file)
        self.assertIsNotNone(result)
        self.assertIn("thread", result)
        self.assertIn("iteration", result)
    
    def test_atomicity_during_write(self):
        """Test that readers never see partial writes."""
        large_data = {"items": list(range(1000))}
        read_results = []
        
        def reader():
            for _ in range(50):
                result = safe_read_json(self.test_file)
                if result is not None:
                    read_results.append(result)
                time.sleep(0.001)
        
        def writer():
            for i in range(20):
                data = {"iteration": i, "items": list(range(i * 10, (i + 1) * 10))}
                atomic_write_json(self.test_file, data)
                time.sleep(0.002)
        
        # Start reader and writer concurrently
        reader_thread = threading.Thread(target=reader)
        writer_thread = threading.Thread(target=writer)
        
        reader_thread.start()
        writer_thread.start()
        
        reader_thread.join()
        writer_thread.join()
        
        # All reads should have valid "iteration" key
        for result in read_results:
            self.assertIn("iteration", result)
            self.assertIsInstance(result["iteration"], int)


class TestIntegrationWithBot(unittest.TestCase):
    """Integration tests with actual bot components."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.projects_dir = Path(self.temp_dir) / "projects"
        self.projects_dir.mkdir()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_project_state_write_read(self):
        """Test writing and reading project state."""
        from atomic_file import atomic_write_json, safe_read_json
        
        project_file = self.projects_dir / "test-project.json"
        project_data = {
            "id": "test-project",
            "goal": "Test goal",
            "status": "active",
            "mode": "linear",
            "stages": {
                "design": {"status": "done", "agent": "architect"},
                "implement": {"status": "in-progress", "agent": "coder"}
            }
        }
        
        # Write
        success = atomic_write_json(project_file, project_data)
        self.assertTrue(success)
        
        # Read
        read_data = safe_read_json(project_file)
        self.assertIsNotNone(read_data)
        self.assertEqual(read_data["id"], "test-project")
        self.assertEqual(read_data["stages"]["implement"]["status"], "in-progress")


if __name__ == "__main__":
    unittest.main()
