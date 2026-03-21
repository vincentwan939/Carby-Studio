# Phase Lock - Sequential Phase Execution

**Carby Studio v3.x Feature Documentation**

---

## Table of Contents

1. [What is Phase Lock?](#what-is-phase-lock)
2. [Why Was It Created?](#why-was-it-created)
3. [How It Works](#how-it-works)
4. [Phase Sequence Diagram](#phase-sequence-diagram)
5. [State Machine Explanation](#state-machine-explanation)
6. [Usage Guide](#usage-guide)
7. [CLI Reference](#cli-reference)
8. [Migration Guide](#migration-guide)

---

## What is Phase Lock?

Phase Lock is a **sequential phase execution enforcement mechanism** for Carby Studio sprints. It ensures that each phase of a sprint (Discover → Design → Build → Verify → Deliver) completes and receives explicit user approval before the next phase can begin.

### Key Characteristics

| Feature | Description |
|---------|-------------|
| **Opt-in** | Disabled by default; enable with `--mode sequential` |
| **Blocking** | Prevents next phase from starting until current phase is approved |
| **Explicit Approval** | Requires user to run `approve` command to proceed |
| **State Persistence** | Stores phase state in `.carby-sprints/<sprint>/phase_lock.json` |
| **Non-Breaking** | Existing parallel sprints continue to work unchanged |

### When to Use Phase Lock

- **Complex projects** requiring careful review between phases
- **High-risk changes** where each phase needs validation
- **Learning scenarios** where you want to understand each phase's output
- **Regulatory compliance** requiring documented approvals
- **Debugging** sprint execution issues

---

## Why Was It Created?

### The Property Hunter Issue

The Phase Lock feature was created to address a critical issue discovered during the **Property Hunter** project:

```
Problem: All phase agents spawned simultaneously

Before Phase Lock:
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Discover   │   │   Design    │   │    Build    │
│   Agent     │   │   Agent     │   │   Agent     │
│   spawns    │   │   spawns    │   │   spawns    │
│   NOW       │   │   NOW       │   │   NOW       │
└─────────────┘   └─────────────┘   └─────────────┘
      │                 │                 │
      └─────────────────┼─────────────────┘
                        ▼
              ALL RUN SIMULTANEOUSLY
                        ❌
```

**Root Cause:** The sprint framework had no mechanism to block agent spawning until the previous phase was explicitly approved. All agents were spawned in parallel, causing:

- Race conditions between phases
- Design agents working before discovery completed
- Build agents starting without approved designs
- Confusion about which phase outputs were ready
- Difficult debugging and troubleshooting

### The Solution

Phase Lock adds a simple file-based state machine that enforces sequential execution:

```
After Phase Lock:
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Discover   │────▶│   [LOCK]    │────▶│   Design    │
│   Agent     │     │  WAITING    │     │   Agent     │
│  completes  │     │  FOR USER   │     │   spawns    │
│             │     │  APPROVAL   │     │   AFTER     │
└─────────────┘     └─────────────┘     └─────────────┘
      │                    │                  │
      ▼                    ▼                  ▼
  WRITES              CHECKS FILE         CHECKS FILE
  "completed"         → blocks            → "phase1_approved"
  marker              until approved      → allows spawn
```

**Lines of Code:** ~80 lines  
**Files Modified:** 2 (new: `phase_lock.py`, modify: `start.py`)  
**Breaking Changes:** None (opt-in via `--mode sequential`)

---

## How It Works

### Core Components

#### 1. Phase Lock State File

Each sprint in sequential mode has a `phase_lock.json` file:

```json
{
  "sprint_id": "my-sprint",
  "phases": {
    "discover": {
      "state": "approved",
      "summary": "Requirements gathered",
      "completed_at": "2026-03-21T08:00:00",
      "approved_at": "2026-03-21T08:05:00"
    },
    "design": {
      "state": "awaiting_approval",
      "summary": "Architecture designed",
      "completed_at": "2026-03-21T09:00:00"
    },
    "build": {
      "state": "pending"
    },
    "verify": {
      "state": "pending"
    },
    "deliver": {
      "state": "pending"
    }
  }
}
```

#### 2. Phase Lock Module (`phase_lock.py`)

The module provides:

- **`wait_for_previous_phase()`** — Blocks until previous phase is approved
- **`mark_phase_complete()`** — Marks phase complete, awaiting approval
- **`approve_phase()`** — Approves phase, unblocking next phase
- **`get_phase_status()`** — Returns current phase status

#### 3. Integration Points

**Before Agent Spawn (in `start.py`):**
```python
# Check if we can start this phase
lock = PhaseLock(output_dir, sprint_id)
if not lock.can_start_phase(phase_id):
    raise click.ClickException(
        f"Cannot start {phase_id}: waiting for approval.\n"
        f"Run: carby-sprint approve {sprint_id} {waiting_phase}"
    )

# Mark phase as in progress
lock.start_phase(phase_id)
```

**On Agent Completion:**
```python
# Mark phase complete and wait for approval
lock.complete_phase(phase_id, summary)
# Displays: "To approve and continue: carby-sprint approve <sprint> <phase>"
```

### Phase Sequence

```
Phase Order (enforced by Phase Lock):

1. discover  →  2. design  →  3. build  →  4. verify  →  5. deliver
     │              │             │             │             │
     │              │             │             │             │
     └──────────────┴─────────────┴─────────────┴─────────────┘
                    Sequential execution only
```

---

## Phase Sequence Diagram

### Complete Sequential Flow

```
┌─────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  User   │     │   Sprint    │     │  PhaseLock  │     │   Agent     │
└────┬────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
     │                 │                   │                   │
     │  start --mode   │                   │                   │
     │  sequential     │                   │                   │
     │────────────────▶│                   │                   │
     │                 │                   │                   │
     │                 │  Check: can       │                   │
     │                 │  start discover?  │                   │
     │                 │──────────────────▶│                   │
     │                 │                   │                   │
     │                 │  Yes (first phase)│                   │
     │                 │◀──────────────────│                   │
     │                 │                   │                   │
     │                 │                   │                   │  Spawn
     │                 │──────────────────────────────────────▶│
     │                 │                   │                   │
     │                 │                   │  Mark in_progress │
     │                 │◀──────────────────────────────────────│
     │                 │                   │                   │
     │                 │  Agent runs...    │                   │
     │                 │                   │                   │
     │                 │                   │  Mark completed   │
     │                 │◀──────────────────────────────────────│
     │                 │                   │                   │
     │                 │  Display:         │                   │
     │                 │  "Run: approve    │                   │
     │                 │   <sprint>        │                   │
     │                 │   discover"       │                   │
     │◀────────────────│                   │                   │
     │                 │                   │                   │
     │  approve        │                   │                   │
     │  <sprint>       │                   │                   │
     │  discover       │                   │                   │
     │────────────────▶│                   │                   │
     │                 │                   │                   │
     │                 │  Approve phase    │                   │
     │                 │──────────────────▶│                   │
     │                 │                   │                   │
     │                 │  Mark approved    │                   │
     │                 │◀──────────────────│                   │
     │                 │                   │                   │
     │  "Next phase:   │                   │                   │
     │   design"       │                   │                   │
     │◀────────────────│                   │                   │
     │                 │                   │                   │
     │  start (or      │                   │                   │
     │  auto-advance)  │                   │                   │
     │────────────────▶│                   │                   │
     │                 │                   │                   │
     │                 │  Check: can       │                   │
     │                 │  start design?    │                   │
     │                 │──────────────────▶│                   │
     │                 │                   │                   │
     │                 │  Yes (discover    │                   │
     │                 │  approved)        │                   │
     │                 │◀──────────────────│                   │
     │                 │                   │                   │
     │                 │                   │                   │  Spawn
     │                 │──────────────────────────────────────▶│
     │                 │                   │                   │
     │                 │  ... continues    │                   │
     │                 │  for phases 3-5   │                   │
```

---

## State Machine Explanation

### Phase States

```
                    ┌─────────────────┐
                    │    PENDING      │
                    │  (not started)  │
                    └────────┬────────┘
                             │
                             │ start_phase()
                             ▼
                    ┌─────────────────┐
                    │  IN_PROGRESS    │
                    │  (agent running)│
                    └────────┬────────┘
                             │
                             │ complete_phase()
                             ▼
                    ┌─────────────────┐
                    │AWAITING_APPROVAL│
                    │ (waiting for    │◀────┐
                    │  user approval) │     │
                    └────────┬────────┘     │
                             │              │
              ┌──────────────┼──────────────┘
              │              │ approve_phase()
              ▼              ▼
     ┌─────────────────┐
     │    APPROVED     │
     │ (next phase can │
     │    proceed)     │
     └─────────────────┘
```

### State Transitions

| From State | To State | Trigger | Description |
|------------|----------|---------|-------------|
| `pending` | `in_progress` | `start_phase()` | Phase agent is spawned |
| `in_progress` | `awaiting_approval` | `complete_phase()` | Agent finished work |
| `awaiting_approval` | `approved` | `approve_phase()` | User approves completion |
| `approved` | — | — | Terminal state; next phase can start |

### Blocking Behavior

```
When Phase N tries to start:

┌─────────────────────────────────────────────────────────┐
│  Check Phase N-1 state                                  │
├─────────────────────────────────────────────────────────┤
│  IF Phase N-1 == "approved":                            │
│     → ALLOW Phase N to start                            │
│                                                         │
│  IF Phase N-1 == "awaiting_approval":                   │
│     → BLOCK with message:                               │
│       "Phase N-1 complete, awaiting approval.           │
│        Run: carby-sprint approve <sprint> <phase N-1>"  │
│                                                         │
│  IF Phase N-1 == "in_progress":                         │
│     → BLOCK with message:                               │
│       "Phase N-1 still in progress"                     │
│                                                         │
│  IF Phase N-1 == "pending":                             │
│     → BLOCK with message:                               │
│       "Complete Phase N-1 before starting Phase N"      │
└─────────────────────────────────────────────────────────┘
```

---

## Usage Guide

### Starting a Sprint in Sequential Mode

Initialize and start a sprint with sequential phase execution:

```bash
# 1. Initialize the sprint
carby-sprint init my-project \
  --project my-api \
  --goal "Build REST API"

# 2. Plan work items
carby-sprint plan my-project \
  --work-items "Setup,Develop,Test"

# 3. Pass required gates
carby-sprint gate my-project 1
carby-sprint gate my-project 2

# 4. Start in sequential mode
carby-sprint start my-project --mode sequential
```

**What happens:**
1. Discover agent spawns immediately (first phase)
2. When discover completes, you'll see:
   ```
   ============================================================
   PHASE COMPLETE: phase_1_discover
   ============================================================
   Summary: Requirements gathered from stakeholders

   To approve and continue to next phase:
     carby-sprint approve my-project phase_1_discover
   ============================================================
   ```
3. Sprint pauses, waiting for your approval

### Approving Phases

When a phase completes, approve it to unblock the next phase:

```bash
# Approve a specific phase
carby-sprint approve my-project phase_1_discover

# Or approve the phase currently waiting for approval
carby-sprint approve my-project
```

**After approval:**
```
============================================================
✓ PHASE APPROVED: phase_1_discover
============================================================
Summary: Requirements gathered from stakeholders
Completed: 2026-03-21T08:00:00

Next phase ready: phase_2_design

To start the next phase, run:
  carby-sprint start my-project --mode sequential
============================================================
```

### Checking Status

Check the current phase status at any time:

```bash
# Show all phase statuses
carby-sprint phase-status my-project

# Show only phases pending approval
carby-sprint phase-status my-project --pending-only

# List phases in table format
carby-sprint phase-list my-project

# List phases in compact format
carby-sprint phase-list my-project --format compact

# Export phases as JSON
carby-sprint phase-list my-project --format json
```

**Example output:**
```
============================================================
Phase Status for Sprint: my-project
============================================================

📊 Summary
  ✓ Approved: 2
  ⏳ Pending Approval: 1
  🔄 In Progress: 0
  ○ Not Started: 2

📋 Phases
  ✓ approved Phase 1: Discovery
  ✓ approved Phase 2: Design
  ⏳ pending_approval Phase 3: Implementation
  ○ not_started Phase 4: Validation
  ○ not_started Phase 5: Deployment

============================================================
Progress: [████████████░░░░░░░░░░░░░░░░░░] 2/5 (40%)
```

### Common Workflows

#### Workflow 1: Basic Sequential Sprint

```bash
# Initialize and start sequential sprint
carby-sprint init api-sprint --project my-api --goal "Build v2 API"
carby-sprint plan api-sprint --work-items "Auth,Endpoints,Docs"
carby-sprint gate api-sprint 1
carby-sprint gate api-sprint 2

# Start sequential execution
carby-sprint start api-sprint --mode sequential

# ... discover phase runs and completes ...

# Approve and continue
carby-sprint approve api-sprint
carby-sprint start api-sprint --mode sequential

# ... design phase runs and completes ...

# Approve and continue
carby-sprint approve api-sprint
carby-sprint start api-sprint --mode sequential

# ... continue for remaining phases ...
```

#### Workflow 2: Review Before Approve

```bash
# After phase completes, review deliverables
cat .carby-sprints/my-project/deliverables/phase_1_discover.md

# Check what the agent produced
carby-sprint phase-status my-project --pending-only

# Approve only after review
carby-sprint approve my-project phase_1_discover
```

#### Workflow 3: Auto-Advance (Scripted)

```bash
# Approve and automatically start next phase
carby-sprint approve my-project --auto-advance
```

---

## CLI Reference

### `carby-sprint start --mode sequential`

Start a sprint with sequential phase execution.

**Usage:**
```bash
carby-sprint start [OPTIONS] SPRINT_ID --mode sequential
```

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--mode` | `-m` | `parallel` | Execution mode: `parallel` or `sequential` |
| `--max-parallel` | `-p` | `3` | Max parallel work items (within a phase) |
| `--dry-run` | — | `False` | Simulate without spawning agents |
| `--output-dir` | `-o` | `.carby-sprints` | Sprint data directory |

**Examples:**

```bash
# Start in sequential mode
carby-sprint start my-sprint --mode sequential

# Start with higher parallelism within phases
carby-sprint start my-sprint --mode sequential --max-parallel 5

# Dry run to preview
carby-sprint start my-sprint --mode sequential --dry-run
```

**Exit Codes:**
- `0` — Success (phase started or completed)
- `1` — Sprint not found
- `2` — Required gates not passed
- `3` — Phase blocked (previous phase not approved)

---

### `carby-sprint approve`

Approve a completed phase and unblock the next phase.

**Usage:**
```bash
carby-sprint approve [OPTIONS] SPRINT_ID [PHASE_ID]
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |
| `PHASE_ID` | No | Phase to approve (defaults to waiting phase) |

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output-dir` | `-o` | `.carby-sprints` | Sprint data directory |
| `--auto-advance` | — | `False` | Auto-start next phase after approval |

**Examples:**

```bash
# Approve the phase waiting for approval
carby-sprint approve my-sprint

# Approve a specific phase
carby-sprint approve my-sprint phase_1_discover

# Approve and auto-start next phase
carby-sprint approve my-sprint --auto-advance
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Phase not in awaiting_approval state
- `3` — No phase waiting for approval

---

### `carby-sprint phase-status`

Show all phase statuses for a sprint.

**Usage:**
```bash
carby-sprint phase-status [OPTIONS] SPRINT_ID
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output-dir` | `-o` | `.carby-sprints` | Sprint data directory |
| `--pending-only` | `-p` | `False` | Show only phases pending approval |

**Examples:**

```bash
# Show all phase statuses
carby-sprint phase-status my-sprint

# Show only pending approvals
carby-sprint phase-status my-sprint --pending-only
```

**Output:**
```
============================================================
Phase Status for Sprint: my-sprint
============================================================

📊 Summary
  ✓ Approved: 2
  ⏳ Pending Approval: 1
  🔄 In Progress: 1
  ○ Not Started: 1

📋 Phases
  ✓ approved Phase 1: Discovery
  ✓ approved Phase 2: Design
  ⏳ pending_approval Phase 3: Implementation
  🔄 in_progress Phase 4: Validation
  ○ not_started Phase 5: Deployment

============================================================
Progress: [████████████████░░░░░░░░░░░░░░] 3/5 (60%)
```

---

### `carby-sprint phase-list`

List all phases and their states.

**Usage:**
```bash
carby-sprint phase-list [OPTIONS] SPRINT_ID
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output-dir` | `-o` | `.carby-sprints` | Sprint data directory |
| `--format` | `-f` | `table` | Output format: `table`, `json`, or `compact` |

**Examples:**

```bash
# Table format (default)
carby-sprint phase-list my-sprint

# Compact format
carby-sprint phase-list my-sprint --format compact

# JSON format
carby-sprint phase-list my-sprint --format json
```

**Table Output:**
```
======================================================================
Phase    Name                 Status               Approved
----------------------------------------------------------------------
1        Discovery            ✓ approved           Yes
2        Design               ✓ approved           Yes
3        Implementation       ⏳ pending_approval   No
4        Validation           🔄 in_progress        No
5        Deployment           ○ not_started        No
======================================================================
```

---

## Migration Guide

### For Existing Projects

**Good news:** Phase Lock is **opt-in** and does not affect existing sprints.

| Aspect | Behavior |
|--------|----------|
| Default mode | `parallel` (unchanged) |
| Existing sprints | Continue using parallel execution |
| New sprints | Can use either `parallel` or `sequential` |

### Opt-in to Sequential Mode

To use Phase Lock for a new sprint:

```bash
# Initialize sprint normally
carby-sprint init my-sprint --project my-api --goal "Build API"

# Plan work items
carby-sprint plan my-sprint --work-items "Feature1,Feature2"

# Pass gates
carby-sprint gate my-sprint 1
carby-sprint gate my-sprint 2

# Start with sequential mode (NEW)
carby-sprint start my-sprint --mode sequential
```

### Migration Scenarios

#### Scenario 1: New Sprint, Want Sequential

```bash
# Use --mode sequential on start
carby-sprint start my-sprint --mode sequential
```

#### Scenario 2: Existing Parallel Sprint, Want to Switch

Sprints cannot change mode after creation. Create a new sprint:

```bash
# Create new sequential sprint
carby-sprint init my-sprint-v2 \
  --project my-api \
  --goal "Continue with sequential execution"

# Copy work items from old sprint
carby-sprint plan my-sprint-v2 --work-items "Remaining work"

# Force-pass gates if work already done
carby-sprint gate my-sprint-v2 1 --force
carby-sprint gate my-sprint-v2 2 --force

# Start in sequential mode
carby-sprint start my-sprint-v2 --mode sequential
```

#### Scenario 3: Keep Using Parallel (No Changes Needed)

```bash
# Default behavior unchanged
carby-sprint start my-sprint
# Runs in parallel mode (same as before)
```

### Comparison: Parallel vs Sequential

| Feature | Parallel Mode | Sequential Mode |
|---------|---------------|-----------------|
| Phase execution | All phases run simultaneously | One phase at a time |
| User approval | Not required | Required between phases |
| Speed | Faster | Slower (but more controlled) |
| Use case | Well-understood projects | Complex/high-risk projects |
| Debugging | Harder | Easier |
| Review points | End of sprint | Each phase |

### Recommended Usage

| Project Type | Recommended Mode |
|--------------|------------------|
| Simple/Well-understood | `parallel` (default) |
| Complex/High-risk | `sequential` |
| Learning/Training | `sequential` |
| Production systems | `sequential` |
| Prototypes/MVPs | `parallel` |

---

## Files and Locations

| File | Location | Description |
|------|----------|-------------|
| `phase_lock.py` | `carby_sprint/phase_lock.py` | Core Phase Lock module |
| `phase.py` | `carby_sprint/commands/phase.py` | Phase management commands |
| `approve.py` | `carby_sprint/commands/approve.py` | Approve command |
| `phase_lock.json` | `.carby-sprints/<sprint>/phase_lock.json` | Per-sprint state file |

---

## Troubleshooting

### "Cannot start phase: waiting for approval"

**Cause:** Previous phase completed but not approved.

**Solution:**
```bash
carby-sprint approve <sprint> <phase>
```

### "Phase not in awaiting_approval state"

**Cause:** Trying to approve a phase that hasn't completed or is already approved.

**Solution:**
```bash
# Check current status
carby-sprint phase-status <sprint>

# Only approve phases showing "pending_approval"
```

### "Sprint is not in sequential mode"

**Cause:** Running `approve` on a parallel-mode sprint.

**Solution:** Approval only needed for sequential mode. For parallel sprints, use standard `start` command.

---

## Summary

Phase Lock solves the parallel execution problem by enforcing sequential phase execution with explicit user approval. It is:

- **Opt-in** — Use `--mode sequential` to enable
- **Non-breaking** — Existing sprints continue unchanged
- **Simple** — ~115 lines of code
- **Effective** — Prevents the Property Hunter issue

For complex projects requiring careful phase-by-phase validation, Phase Lock provides the control needed to ensure quality and prevent race conditions.
