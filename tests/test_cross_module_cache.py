"""
Test for Cross-Module State issue - JSON cache inconsistency.

This test demonstrates the issue where gate_state.py and transaction.py
have separate JSON caches that can become inconsistent when one module
writes to a file and the other reads from its stale cache.
"""

import json
import tempfile
import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from carby_sprint.gate_state import load_json_cached as gate_state_load_cached
from carby_sprint.transaction import load_json_cached as transaction_load_cached
from carby_sprint.gate_state import _invalidate_json_cache as gate_state_invalidate_cache
from carby_sprint.transaction import _invalidate_json_cache as transaction_invalidate_cache


def test_cross_module_cache_inconsistency():
    """
    Demonstrate the cross-module cache inconsistency issue.
    
    When gate_state.py writes to a file and invalidates its cache,
    transaction.py's cache still has stale data.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_state.json"
        
        # Initial write
        initial_data = {"version": 1, "status": "initial"}
        test_file.write_text(json.dumps(initial_data))
        
        # Load via gate_state module (populates its cache)
        data_from_gate = gate_state_load_cached(test_file)
        assert data_from_gate["version"] == 1, f"Expected version 1, got {data_from_gate['version']}"
        
        # Load via transaction module (populates its cache)
        data_from_tx = transaction_load_cached(test_file)
        assert data_from_tx["version"] == 1, f"Expected version 1, got {data_from_tx['version']}"
        
        # Now simulate a write via gate_state (e.g., GateStateManager saving state)
        updated_data = {"version": 2, "status": "updated"}
        test_file.write_text(json.dumps(updated_data))
        
        # gate_state invalidates its own cache
        gate_state_invalidate_cache(test_file)
        
        # gate_state sees the new data
        data_from_gate_after = gate_state_load_cached(test_file)
        assert data_from_gate_after["version"] == 2, f"gate_state should see version 2, got {data_from_gate_after['version']}"
        
        # BUT: transaction module still has stale cached data!
        # This is the cross-module state inconsistency bug
        data_from_tx_after = transaction_load_cached(test_file)
        
        # This assertion will FAIL due to the bug - transaction sees old version
        print(f"gate_state sees version: {data_from_gate_after['version']}")
        print(f"transaction sees version: {data_from_tx_after['version']}")
        
        if data_from_tx_after["version"] != 2:
            print("BUG CONFIRMED: Cross-module cache inconsistency detected!")
            print(f"  Expected version 2, but transaction module sees version {data_from_tx_after['version']}")
            return False
        return True


def test_cross_module_cache_consistency_after_fix():
    """
    Test that cross-module cache is consistent after the fix.
    
    After implementing a shared cache, both modules should see the same data.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_state.json"
        
        # Initial write
        initial_data = {"version": 1, "status": "initial"}
        test_file.write_text(json.dumps(initial_data))
        
        # Load via both modules
        gate_state_load_cached(test_file)
        transaction_load_cached(test_file)
        
        # Update the file
        updated_data = {"version": 2, "status": "updated"}
        test_file.write_text(json.dumps(updated_data))
        
        # After the fix, invalidating in one module should affect both
        # (they share the same cache)
        gate_state_invalidate_cache(test_file)
        
        # Both should see the new data
        data_from_gate = gate_state_load_cached(test_file)
        data_from_tx = transaction_load_cached(test_file)
        
        assert data_from_gate["version"] == 2, f"gate_state should see version 2"
        assert data_from_tx["version"] == 2, f"transaction should see version 2"
        
        print("PASS: Cross-module cache is consistent!")
        return True


if __name__ == "__main__":
    print("Testing cross-module cache inconsistency...")
    result1 = test_cross_module_cache_inconsistency()
    
    print("\nTesting cross-module cache consistency after fix...")
    result2 = test_cross_module_cache_consistency_after_fix()
    
    if result1 and result2:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Tests failed - cross-module state issue detected")
        sys.exit(1)
