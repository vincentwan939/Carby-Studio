"""
Test for INT-N1: Cross-Module State Fix

This test verifies that the shared JSON cache implementation correctly
prevents state inconsistencies between different modules accessing shared state.

Issue: gate_state.py and transaction.py had separate JSON caches that could
become inconsistent when one module wrote to a file and invalidated its cache,
but the other module's cache still held stale data.

Fix: Created json_cache.py module with shared cache that both modules import.
"""

import json
import tempfile
import threading
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from carby_sprint import gate_state
from carby_sprint import transaction
from carby_sprint import json_cache


class TestCrossModuleCacheConsistency:
    """Tests for cross-module JSON cache consistency."""
    
    def setup_method(self):
        """Clear cache before each test."""
        json_cache.clear_cache()
    
    def test_shared_cache_invalidation(self):
        """Test that cache invalidation is shared across modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text(json.dumps({"data": "initial"}))
            
            # Populate cache via gate_state
            gate_state.load_json_cached(test_file)
            
            # Verify cache has data
            assert json_cache._get_cached_json(test_file) is not None
            
            # Invalidate via transaction module
            transaction._invalidate_json_cache(test_file)
            
            # Cache should be cleared for both modules
            assert json_cache._get_cached_json(test_file) is None
    
    def test_shared_cache_population(self):
        """Test that cache population is shared across modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text(json.dumps({"data": "test"}))
            
            # Load via gate_state
            data1 = gate_state.load_json_cached(test_file)
            
            # Load via transaction - should get cached data
            data2 = transaction.load_json_cached(test_file)
            
            assert data1 == data2
            assert data1["data"] == "test"
    
    def test_write_invalidation_propagation(self):
        """Test that writes in one module invalidate cache for all modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            
            # Initial data
            test_file.write_text(json.dumps({"version": 1}))
            gate_state.load_json_cached(test_file)
            
            # Update file
            test_file.write_text(json.dumps({"version": 2}))
            
            # Invalidate via gate_state
            gate_state._invalidate_json_cache(test_file)
            
            # Both modules should see new data
            gate_data = gate_state.load_json_cached(test_file)
            tx_data = transaction.load_json_cached(test_file)
            
            assert gate_data["version"] == 2
            assert tx_data["version"] == 2
    
    def test_concurrent_access_consistency(self):
        """Test cache consistency under concurrent access from multiple modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text(json.dumps({"counter": 0}))
            
            results = []
            errors = []
            stop_event = threading.Event()
            
            def reader_from_gate():
                try:
                    while not stop_event.is_set():
                        data = gate_state.load_json_cached(test_file)
                        if "counter" in data:
                            results.append(("gate", data["counter"]))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(f"gate error: {e}")
            
            def reader_from_tx():
                try:
                    while not stop_event.is_set():
                        data = transaction.load_json_cached(test_file)
                        if "counter" in data:
                            results.append(("tx", data["counter"]))
                        time.sleep(0.001)
                except Exception as e:
                    errors.append(f"tx error: {e}")
            
            def writer():
                try:
                    for i in range(10):
                        test_file.write_text(json.dumps({"counter": i + 1}))
                        json_cache._invalidate_json_cache(test_file)
                        time.sleep(0.01)
                except Exception as e:
                    errors.append(f"writer error: {e}")
                finally:
                    stop_event.set()
            
            threads = [
                threading.Thread(target=reader_from_gate),
                threading.Thread(target=reader_from_tx),
                threading.Thread(target=writer),
            ]
            
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5)
            
            stop_event.set()
            
            assert len(errors) == 0, f"Errors occurred: {errors}"
            # All reads should see valid counter values
            for source, counter in results:
                assert 0 <= counter <= 10, f"Invalid counter value: {counter}"
    
    def test_cache_stats(self):
        """Test cache statistics reporting."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text(json.dumps({"data": "test"}))
            
            # Clear and load
            json_cache.clear_cache()
            gate_state.load_json_cached(test_file)
            
            stats = json_cache.get_cache_stats()
            assert stats["entry_count"] == 1
            assert str(test_file) in stats["cached_paths"]


class TestCrossModuleStateAtomicity:
    """Tests for atomic updates across module boundaries."""
    
    def setup_method(self):
        """Clear cache before each test."""
        json_cache.clear_cache()
    
    def test_atomic_update_visibility(self):
        """Test that atomic updates are visible across modules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            test_file.write_text(json.dumps({"status": "pending"}))
            
            # Module A reads
            data_a = gate_state.load_json_cached(test_file)
            assert data_a["status"] == "pending"
            
            # Module B updates the file directly
            test_file.write_text(json.dumps({"status": "completed"}))
            
            # Invalidate cache (simulating proper write protocol)
            transaction._invalidate_json_cache(test_file)
            
            # Module A reads again - should see updated data
            data_a2 = gate_state.load_json_cached(test_file)
            assert data_a2["status"] == "completed"
    
    def test_no_stale_reads_after_invalidation(self):
        """Test that no stale reads occur after cache invalidation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.json"
            
            # Write initial data
            test_file.write_text(json.dumps({"value": 1}))
            
            # Both modules read
            gate_state.load_json_cached(test_file)
            transaction.load_json_cached(test_file)
            
            # Update file
            test_file.write_text(json.dumps({"value": 2}))
            
            # Invalidate via json_cache directly
            json_cache._invalidate_json_cache(test_file)
            
            # Both should see new value
            gate_data = gate_state.load_json_cached(test_file)
            tx_data = transaction.load_json_cached(test_file)
            
            assert gate_data["value"] == 2, f"gate_state saw stale value: {gate_data['value']}"
            assert tx_data["value"] == 2, f"transaction saw stale value: {tx_data['value']}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])