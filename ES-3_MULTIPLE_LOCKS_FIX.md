# ES-3: Multiple Locks Issue Fix

## Issue Summary

The Multiple Locks issue occurs when multiple locks are acquired in different orders, which can cause deadlocks. In the Carby Studio framework, `GateStateManager` has two separate locks:
- `_gate_lock`: For gate status operations
- `_token_lock`: For token registry operations

When these locks are acquired in inconsistent orders (e.g., Thread A: token→gate, Thread B: gate→token), a circular wait deadlock can occur.

## Solution

Implemented consistent lock ordering (hierarchy) to prevent deadlocks:

### Lock Hierarchy
1. `_gate_lock` (higher priority) - always acquire FIRST
2. `_token_lock` (lower priority) - always acquire SECOND

### Changes Made

#### 1. `carby_sprint/gate_state.py`

**Added lock hierarchy documentation:**
```python
# Lock hierarchy for deadlock prevention:
# When acquiring multiple locks, always acquire in this order:
# 1. _gate_lock (higher priority - gate status)
# 2. _token_lock (lower priority - token registry)
# This prevents circular wait deadlocks.
```

**Added `_acquire_both_locks()` method:**
- Context manager that acquires both locks in correct order
- Ensures consistent lock acquisition to prevent deadlocks

**Added `atomic_gate_advancement()` method:**
- Atomically updates both gate status and token registry
- Acquires both locks in correct order (gate first, then token)
- Prevents race conditions and deadlocks during gate advancement

#### 2. `carby_sprint/gate_enforcer.py`

**Updated `advance_gate()` method:**
- Now uses `atomic_gate_advancement()` instead of manual lock management
- Ensures consistent lock ordering throughout the gate advancement process
- Eliminates the risk of acquiring locks in different orders

### Test Coverage

Created comprehensive tests in `tests/test_multiple_locks_fix.py`:

1. **test_lock_hierarchy_documentation**: Verifies lock hierarchy is documented
2. **test_acquire_both_locks_in_correct_order**: Tests `_acquire_both_locks()` method
3. **test_atomic_gate_advancement_with_locks**: Tests atomic advancement with both locks
4. **test_concurrent_lock_acquisition_no_deadlock**: Stress test with concurrent operations
5. **test_individual_locks_still_work**: Ensures individual locks still function correctly
6. **test_no_deadlock_with_gate_enforcer**: Integration test with GateEnforcer

All 6 tests pass, confirming:
- No deadlocks occur with consistent lock ordering
- Concurrent operations complete successfully
- Individual locks still work as expected
- Integration with GateEnforcer works correctly

## Verification

Run the tests to verify the fix:

```bash
# Run multiple locks fix tests
python3 -m pytest tests/test_multiple_locks_fix.py -v

# Run nested locks tests (related)
python3 -m pytest tests/test_nested_locks.py -v

# Run all security-related tests
python3 -m pytest tests/test_hmac_verification.py tests/test_path_traversal_fix.py tests/test_gate_state_race.py tests/test_phase_lock_toctou.py -v
```

## Impact

- **Deadlock Risk**: Eliminated - consistent lock ordering prevents circular waits
- **Performance**: Maintained - no additional overhead from the fix
- **Compatibility**: Maintained - all existing tests pass
- **Maintainability**: Improved - clear lock hierarchy documented

## Related Issues

- **CR-5**: Agent Callback Transactions (nested transaction anti-pattern fixed)
- **HI-3**: Transaction Boundaries Fix

## References

- `carby_sprint/gate_state.py`: Lock hierarchy and atomic_gate_advancement implementation
- `carby_sprint/gate_enforcer.py`: Updated advance_gate() method
- `tests/test_multiple_locks_fix.py`: Comprehensive test coverage
- `tests/test_nested_locks.py`: Related nested lock tests
