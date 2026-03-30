# INT-N1: Cross-Module State Fix

## Issue Summary

**Problem:** Cross-Module State issue - state inconsistencies between different modules accessing shared state.

**Root Cause:** `gate_state.py` and `transaction.py` each had their own independent JSON cache (`_json_cache`). When one module wrote to a file and invalidated its cache, the other module's cache still held stale data, leading to potential state inconsistencies.

**Impact:** 
- Stale data reads across module boundaries
- Potential race conditions in concurrent access
- State inconsistency between gate state and transaction operations

## Solution

Created a new shared module `json_cache.py` that provides a centralized, thread-safe JSON caching mechanism. Both `gate_state.py` and `transaction.py` now import cache functions from this shared module, ensuring:

1. **Single source of truth**: All modules share the same cache dictionary
2. **Consistent invalidation**: Invalidating cache in one module affects all modules
3. **Thread safety**: Uses `threading.RLock()` for concurrent access protection
4. **Mtime-based freshness**: Cache entries are validated against file modification time

## Files Changed

### New Files
- `carby_sprint/json_cache.py` - Shared JSON cache module

### Modified Files
- `carby_sprint/gate_state.py` - Removed local cache, imports from json_cache
- `carby_sprint/transaction.py` - Removed local cache, imports from json_cache

### New Test Files
- `tests/test_cross_module_state_fix.py` - Comprehensive tests for cross-module consistency
- `tests/test_cross_module_cache_v2.py` - Verification tests

## Implementation Details

### Before Fix
```python
# gate_state.py had its own cache
_json_cache: Dict[str, Tuple[float, Any]] = {}
_cache_lock = threading.RLock()

# transaction.py had its own separate cache  
_json_cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_cache_lock = threading.RLock()
```

### After Fix
```python
# json_cache.py - single shared cache
_json_cache: Dict[str, Tuple[float, Any]] = {}
_cache_lock = threading.RLock()

# gate_state.py imports from json_cache
from .json_cache import load_json_cached, _invalidate_json_cache

# transaction.py imports from json_cache
from .json_cache import load_json_cached, _invalidate_json_cache, _set_cached_json
```

## Test Results

```
============================= test session starts ==============================
platform darwin -- Python 3.9.6

tests/test_cross_module_state_fix.py::TestCrossModuleCacheConsistency::test_shared_cache_invalidation PASSED
tests/test_cross_module_state_fix.py::TestCrossModuleCacheConsistency::test_shared_cache_population PASSED
tests/test_cross_module_state_fix.py::TestCrossModuleCacheConsistency::test_write_invalidation_propagation PASSED
tests/test_cross_module_state_fix.py::TestCrossModuleCacheConsistency::test_concurrent_access_consistency PASSED
tests/test_cross_module_state_fix.py::TestCrossModuleCacheConsistency::test_cache_stats PASSED
tests/test_cross_module_state_fix.py::TestCrossModuleStateAtomicity::test_atomic_update_visibility PASSED
tests/test_cross_module_state_fix.py::TestCrossModuleStateAtomicity::test_no_stale_reads_after_invalidation PASSED

============================== 7 passed =======================================
```

### Full Test Suite
- 59 tests passed (including existing tests)
- No regressions detected
- All security tests pass
- All race condition tests pass

## Verification

The fix was verified with:

1. **Unit tests** - 7 new tests specifically for cross-module consistency
2. **Integration tests** - Existing 52 tests still pass
3. **Concurrency tests** - Verified thread-safe operation under concurrent access
4. **Cache invalidation tests** - Verified proper invalidation propagation

## API Compatibility

The fix maintains full backward compatibility:
- All existing function signatures remain unchanged
- All existing behavior preserved
- No breaking changes to public APIs

## Related Work

This fix builds upon:
- CR-4: Two-phase commit pattern implementation
- CR-5: Nested transaction anti-pattern fix

And enables:
- Consistent state management across all modules
- Reliable atomic updates across module boundaries
- Foundation for future distributed transaction improvements
