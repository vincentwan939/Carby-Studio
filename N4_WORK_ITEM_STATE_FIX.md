# N4: Work Item State Fix

## Issue Summary

Work Item State issue - state transitions were not properly validated or persisted atomically.

## Root Cause

The `_update_work_item_status()` function in `agent_callback.py` was updating work item states without:
1. Validating if the state transition is valid (e.g., can you go from "completed" back to "in_progress"?)
2. Checking the current state before transitioning
3. Ensuring state changes follow a valid lifecycle

## Solution

Implemented proper state validation and atomic transitions for work items.

### Changes Made

#### 1. `carby_sprint/validators.py`
- Added `WORK_ITEM_VALID_TRANSITIONS` dictionary defining valid state transitions:
  - `planned` -> `in_progress`, `cancelled`
  - `in_progress` -> `completed`, `failed`, `blocked`, `cancelled`
  - `blocked` -> `in_progress`, `failed`, `cancelled`
  - `failed` -> `in_progress`, `cancelled`
  - `completed` -> (terminal, no transitions)
  - `cancelled` -> (terminal, no transitions)
- Added `validate_work_item_state_transition()` function
- Added `get_valid_work_item_transitions()` function

#### 2. `carby_sprint/agent_callback.py`
- Updated imports to include `validate_work_item_state_transition`
- Modified `_update_work_item_status()` to:
  - Get current state before transitioning
  - Validate state transition before updating
  - Raise `ValueError` for invalid transitions
  - Document valid transitions in docstring

#### 3. `carby_sprint/sprint_repository.py`
- Added import for `validate_work_item_state_transition`
- Added `update_work_item_state()` method that:
  - Validates state transitions
  - Sets appropriate timestamps (started_at, completed_at, failed_at, blocked_at, cancelled_at)
  - Preserves original started_at when retrying from blocked/failed states
  - Persists changes atomically within transaction
  - Returns updated work item data

#### 4. `carby_sprint/__init__.py`
- Exported new functions: `validate_work_item_state_transition`, `get_valid_work_item_transitions`, `WORK_ITEM_VALID_TRANSITIONS`

#### 5. `tests/test_work_item_state.py` (New)
- Added 17 comprehensive tests covering:
  - State transition validation from all states
  - Terminal state enforcement
  - Integration with SprintRepository
  - Integration with agent callbacks
  - Atomic persistence verification

## Test Results

All 17 new tests pass:

```
tests/test_work_item_state.py::TestWorkItemStateValidation::test_valid_transitions_from_planned PASSED
tests/test_work_item_state.py::TestWorkItemStateValidation::test_valid_transitions_from_in_progress PASSED
tests/test_work_item_state.py::TestWorkItemStateValidation::test_valid_transitions_from_blocked PASSED
tests/test_work_item_state.py::TestWorkItemStateValidation::test_valid_transitions_from_failed PASSED
tests/test_work_item_state.py::TestWorkItemStateValidation::test_terminal_states_no_transitions PASSED
tests/test_work_item_state.py::TestWorkItemStateValidation::test_invalid_current_state PASSED
tests/test_work_item_state.py::TestWorkItemStateValidation::test_get_valid_transitions PASSED
tests/test_work_item_state.py::TestWorkItemStateTransitionsIntegration::test_valid_state_transition_via_repository PASSED
tests/test_work_item_state.py::TestWorkItemStateTransitionsIntegration::test_invalid_state_transition_raises_error PASSED
tests/test_work_item_state.py::TestWorkItemStateTransitionsIntegration::test_terminal_state_no_transitions PASSED
tests/test_work_item_state.py::TestWorkItemStateTransitionsIntegration::test_full_work_item_lifecycle PASSED
tests/test_work_item_state.py::TestWorkItemStateTransitionsIntegration::test_state_persistence_across_loads PASSED
tests/test_work_item_state.py::TestWorkItemStateWithAgentCallback::test_agent_callback_valid_transition_success PASSED
tests/test_work_item_state.py::TestWorkItemStateWithAgentCallback::test_agent_callback_valid_transition_failure PASSED
tests/test_work_item_state.py::TestWorkItemStateWithAgentCallback::test_agent_callback_valid_transition_blocked PASSED
tests/test_work_item_state.py::TestWorkItemStateWithAgentCallback::test_agent_callback_invalid_transition_raises_error PASSED
tests/test_work_item_state.py::TestWorkItemStateAtomicity::test_state_change_is_atomic PASSED
```

Existing tests also pass:
- `tests/test_transaction_boundary.py` - 23 tests passed
- `tests/test_commands_plan.py` - 6 tests passed
- `tests/test_e2e_sprint_lifecycle.py` - 9 tests passed

## Impact

- **Data Consistency:** Work items now follow a valid lifecycle
- **Error Prevention:** Invalid state transitions are rejected with clear error messages
- **Atomicity:** State changes are persisted atomically within transaction boundaries
- **Backward Compatibility:** Existing valid operations continue to work

## Dependencies

This fix depends on:
- **CR-5 (Nested Transaction Fix)**: Fixed nested transaction anti-pattern in agent callbacks
- **HI-3 (Transaction Boundaries)**: Clear transaction demarcation for atomic persistence

## Usage Examples

### Validating State Transitions
```python
from carby_sprint import validate_work_item_state_transition

# Check if transition is valid
is_valid = validate_work_item_state_transition("planned", "in_progress")
# Returns: True

is_valid = validate_work_item_state_transition("completed", "in_progress")
# Returns: False (completed is terminal)
```

### Updating Work Item State
```python
from carby_sprint.sprint_repository import SprintRepository

repo = SprintRepository()
paths = repo.get_paths("my-sprint")

# Update with validation
updated = repo.update_work_item_state(paths, "WI-001", "completed")
# Raises ValueError if transition is invalid
```

### Agent Callback Integration
```python
from carby_sprint.agent_callback import _update_work_item_status

# This now validates transitions automatically
_update_work_item_status(repo, paths, "WI-001", "success", result)
# Will raise ValueError if current state doesn't allow transition to completed
```
