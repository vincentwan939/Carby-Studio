# ES-4: Double Locking Fix

## Issue
Double Locking issue - acquiring the same lock twice in nested contexts could cause deadlocks in `GateStateManager`.

## Root Cause
The `GateStateManager` class in `gate_state.py` used `DistributedLock` directly without reentrant lock support. If a method holding a lock called another method that also needed the same lock, it would deadlock.

While `PhaseLockService` already had reentrant lock support using thread-local tracking, `GateStateManager` did not have this protection.

## Solution
Implemented reentrant lock support in `GateStateManager` similar to `PhaseLockService`:

1. **Thread-local storage** to track locks already held by the current thread
2. **Lock tracking methods** for both gate and token locks:
   - `_is_gate_lock_held()` / `_mark_gate_lock_held()` / `_mark_gate_lock_released()`
   - `_is_token_lock_held()` / `_mark_token_lock_held()` / `_mark_token_lock_released()`

3. **Updated lock context managers** to check if lock is already held before acquiring:
   - `_gate_lock()` - now reentrant
   - `_token_lock()` - now reentrant

## Files Modified

### `carby_sprint/gate_state.py`
- Added thread-local storage `self._local = threading.local()` in `__init__`
- Added reentrant lock tracking methods for gate lock
- Added reentrant lock tracking methods for token lock
- Updated `_gate_lock()` context manager to be reentrant
- Updated `_token_lock()` context manager to be reentrant
- Updated class docstring to document thread-safety guarantees

### `tests/test_gate_state_reentrant_locks.py` (New)
- 8 comprehensive tests covering:
  - Single gate/token lock acquisition
  - Nested gate/token lock acquisition (same thread)
  - Lock release after nested calls
  - Thread isolation
  - Concurrent nested locks

## Test Results

All tests pass:

```
tests/test_nested_locks.py::TestNestedLocks::test_single_lock_acquisition PASSED
tests/test_nested_locks.py::TestNestedLocks::test_nested_lock_same_thread PASSED
tests/test_nested_locks.py::TestNestedLocks::test_deeply_nested_locks PASSED
tests/test_nested_locks.py::TestNestedLocks::test_lock_released_after_nested_calls PASSED
tests/test_nested_locks.py::TestNestedLocks::test_thread_isolation PASSED
tests/test_nested_locks.py::TestNestedLocks::test_concurrent_nested_locks PASSED
tests/test_gate_state_reentrant_locks.py::TestGateStateReentrantLocks::test_single_gate_lock_acquisition PASSED
tests/test_gate_state_reentrant_locks.py::TestGateStateReentrantLocks::test_single_token_lock_acquisition PASSED
tests/test_gate_state_reentrant_locks.py::TestGateStateReentrantLocks::test_nested_gate_lock_same_thread PASSED
tests/test_gate_state_reentrant_locks.py::TestGateStateReentrantLocks::test_nested_token_lock_same_thread PASSED
tests/test_gate_state_reentrant_locks.py::TestGateStateReentrantLocks::test_gate_lock_released_after_nested_calls PASSED
tests/test_gate_state_reentrant_locks.py::TestGateStateReentrantLocks::test_token_lock_released_after_nested_calls PASSED
tests/test_gate_state_reentrant_locks.py::TestGateStateReentrantLocks::test_thread_isolation_gate_lock PASSED
tests/test_gate_state_reentrant_locks.py::TestGateStateReentrantLocks::test_concurrent_nested_gate_locks PASSED

============================== 14 passed ==============================
```

## Related Work
- **CR-5**: Fixed nested transaction anti-pattern in agent callbacks
- **HI-3**: Transaction boundaries fix
- **PhaseLockService**: Already had reentrant lock support (reference implementation)

## Backward Compatibility
The changes are fully backward compatible:
- Public API remains unchanged
- Existing code continues to work without modification
- Lock behavior is identical for non-nested cases
- Only adds protection for nested lock acquisition scenarios
