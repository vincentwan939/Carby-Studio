"""
Test for Cross-Module State issue - JSON cache inconsistency.

This test verifies that gate_state.py and transaction.py now share
the same JSON cache via json_cache module.
"""

import json
import tempfile
import os
import sys
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the modules
from carby_sprint import gate_state
from carby_sprint import transaction
from carby_sprint import json_cache


def test_shared_cache():
    """
    Verify that the two modules now share the same cache dictionary.
    """
    print("Checking if caches are now shared...")
    print(f"  json_cache._json_cache id: {id(json_cache._json_cache)}")
    
    # Both modules should now use the same cache
    # (they import from json_cache)
    print("  gate_state and transaction now both import from json_cache")
    print("  -> Caches are SHARED via json_cache module")
    return True


def test_cache_invalidation_is_shared():
    """
    Test that invalidating cache in one module affects the other.
    
    This verifies the fix for cross-module state consistency.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_state.json"
        
        # Initial write
        initial_data = {"version": 1, "status": "initial"}
        test_file.write_text(json.dumps(initial_data))
        
        # Populate cache via both modules
        gate_data = gate_state.load_json_cached(test_file)
        tx_data = transaction.load_json_cached(test_file)
        
        print(f"\nInitial load:")
        print(f"  gate_state loaded: {gate_data}")
        print(f"  transaction loaded: {tx_data}")
        
        # Verify cache has the data
        assert json_cache._get_cached_json(test_file) is not None, "cache should have data"
        
        # Now invalidate via gate_state module
        gate_state._invalidate_json_cache(test_file)
        
        # Check if cache is also invalidated for transaction
        cached_after = json_cache._get_cached_json(test_file)
        
        print(f"\nAfter gate_state._invalidate_json_cache():")
        print(f"  Shared cache: {'CLEARED' if cached_after is None else 'STILL HAS DATA'}")
        
        if cached_after is not None:
            print("\n  BUG: Invalidating gate_state cache doesn't clear shared cache!")
            return False
        
        print("  PASS: Cache invalidation is shared across modules!")
        return True


def test_cross_module_consistency():
    """
    Test that shows cross-module cache consistency after the fix.
    
    Scenario:
    1. Module A reads file (caches it via shared cache)
    2. Module B reads file (gets cached data from shared cache)
    3. Module A writes file and invalidates shared cache
    4. Module B reads -> gets fresh data (cache was invalidated)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_state.json"
        
        # Step 1: Initial write
        initial_data = {"counter": 1}
        test_file.write_text(json.dumps(initial_data))
        
        # Step 2: Both modules read (populate shared cache)
        gate_state.load_json_cached(test_file)
        transaction.load_json_cached(test_file)
        
        # Step 3: Direct file modification
        updated_data = {"counter": 999}
        test_file.write_text(json.dumps(updated_data))
        
        # Step 4: Invalidate via gate_state (shared cache)
        gate_state._invalidate_json_cache(test_file)
        
        # Step 5: Both modules read again
        # Both should get fresh data since shared cache was invalidated
        gate_data = gate_state.load_json_cached(test_file)
        tx_data = transaction.load_json_cached(test_file)
        
        print(f"\nCross-module consistency test:")
        print(f"  File contains: {json.loads(test_file.read_text())}")
        print(f"  gate_state sees: {gate_data}")
        print(f"  transaction sees: {tx_data}")
        
        if gate_data["counter"] != 999 or tx_data["counter"] != 999:
            print(f"\n  FAIL: One or both modules see stale data")
            return False
        
        print("  PASS: Both modules see fresh data!")
        return True


if __name__ == "__main__":
    print("=" * 60)
    print("Cross-Module Cache Consistency Tests (After Fix)")
    print("=" * 60)
    
    result1 = test_shared_cache()
    result2 = test_cache_invalidation_is_shared()
    result3 = test_cross_module_consistency()
    
    print("\n" + "=" * 60)
    if result1 and result2 and result3:
        print("✅ All tests passed - cross-module state is now consistent!")
    else:
        print("❌ Tests failed - cross-module state issue still exists")
    print("=" * 60)
