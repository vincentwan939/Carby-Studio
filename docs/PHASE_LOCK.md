# Phase Lock Documentation

Phase Lock enforces sequential phase execution with explicit user approval between phases.

## Phase Sequence

```
discover → design → build → verify → deliver
```

Each phase must be explicitly approved before the next phase can begin.

## CLI Usage

### Start Sprint with Sequential Mode (Default)

```bash
# Default is now sequential mode
carby-sprint start my-project

# Explicit sequential mode
carby-sprint start my-project --mode sequential

# Legacy parallel mode (concurrent execution)
carby-sprint start my-project --mode parallel
```

### Approve Phases

After a phase completes, it awaits approval:

```bash
# Check current phase status
carby-sprint phase-status my-project

# Approve the completed phase to allow next phase
carby-sprint approve my-project discover

# Start the next phase
carby-sprint start my-project
```

## Python API

### PhaseLock Class

```python
from carby_sprint.phase_lock import PhaseLock

# Initialize PhaseLock (output_dir only)
lock = PhaseLock(output_dir=".carby-sprints")

# Check if phase can start (requires sprint_id parameter)
can_start, error = lock.can_start_phase(sprint_id="my-project", phase_id="phase_2_design")

# Mark phase as started
lock.start_phase(sprint_id="my-project", phase_id="phase_2_design")

# Mark phase as complete (awaits approval)
lock.complete_phase(sprint_id="my-project", phase_id="phase_2_design", summary="Design complete")

# Approve phase to allow next phase
lock.approve_phase(sprint_id="my-project", phase_id="phase_2_design")

# Check if phase is approved
is_approved = lock.is_phase_approved(sprint_id="my-project", phase_id="phase_2_design")

# Get current phase
current = lock.get_current_phase(sprint_id="my-project")

# Get phase waiting for approval
waiting = lock.get_waiting_phase(sprint_id="my-project")
```

### Function-Based API

```python
from carby_sprint.phase_lock import (
    get_phase_status,
    wait_for_previous_phase,
    mark_phase_complete,
    approve_phase,
)

# Get phase status
status = get_phase_status(sprint_id="my-project", phase_id="design")

# Wait for previous phase (blocks until approved)
result = wait_for_previous_phase(sprint_id="my-project", phase_id="design")

# Mark phase complete (awaits approval)
result = mark_phase_complete(
    sprint_id="my-project",
    phase_id="discover",
    summary="Requirements gathered"
)

# Approve phase
result = approve_phase(sprint_id="my-project", phase_id="discover")
```

## Phase States

| State | Description |
|-------|-------------|
| `pending` | Phase not yet started |
| `in_progress` | Phase currently running |
| `awaiting_approval` | Phase complete, waiting for user approval |
| `approved` | Phase approved, next phase can proceed |
| `rejected` | Phase rejected (rarely used) |

## Human-in-the-Loop Workflow

```
1. Start sprint:        carby-sprint start my-project
2. Discover runs...     (automatic)
3. Phase complete       "Awaiting approval"
4. User approves:       carby-sprint approve my-project discover
5. Design can start:    carby-sprint start my-project
6. Design runs...       (automatic)
7. Phase complete       "Awaiting approval"
8. User approves:       carby-sprint approve my-project design
... and so on
```

## Migration from Parallel Mode

If upgrading from v3.0.x or earlier where parallel mode was default:

1. **Update scripts**: Replace `carby-sprint start <project>` with explicit mode if needed
2. **Sequential is now default**: No `--mode` flag required for sequential behavior
3. **Add approval steps**: Insert `carby-sprint approve <project> <phase>` between phases
4. **Legacy behavior**: Use `--mode parallel` to retain concurrent execution (not recommended for production)

## Troubleshooting

### "Previous phase awaiting approval" Error

```
PhaseBlockedError: Previous phase 'discover' complete, awaiting approval
Resolution: Run: carby-sprint approve my-project discover
```

**Solution**: Approve the previous phase before starting the next.

### Phase Won't Start

Check phase status:
```bash
carby-sprint phase-status my-project
```

Ensure all previous phases are `approved` (not just `completed`).

### Lock File Location

Phase lock state is stored in:
```
.carby-sprints/<sprint_id>/phase_lock.json
```

---
*Phase Lock v3.2.1 — Sequential phase enforcement with human approval*
