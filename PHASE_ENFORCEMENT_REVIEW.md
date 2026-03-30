# Carby Studio Phase Enforcement & Workflow Analysis
## End-to-End Review Report v3.2.1

**Date:** 2026-03-23  
**Reviewer:** Subagent Analysis  
**Scope:** Phase Lock, State Management, Auto-Trigger Mechanisms

---

## Executive Summary

Carby Studio implements a **manual approval-based sequential phase system**. There is **NO automatic phase advancement**. All phase transitions require explicit user intervention via CLI commands.

### Critical Finding: 100% Manual Workflow
- **NO auto-trigger mechanism exists**
- **NO automatic phase advancement**
- User must manually run `carby-sprint approve <sprint> <phase>` after each phase completes
- User must manually run `carby-sprint start <sprint> --mode sequential` to begin each phase

---

## 1. Phase Enforcement Mechanisms

### 1.1 Phase Lock Architecture

**File:** `carby_sprint/phase_lock.py`

The Phase Lock system uses a **file-based state machine** with five states:

```python
PHASE_ORDER = ["discover", "design", "build", "verify", "deliver"]

# States per phase:
- "pending"         # Initial state
- "in_progress"     # Phase currently running
- "awaiting_approval"  # Phase complete, waiting for user
- "approved"        # Phase approved, next can start
```

### 1.2 How `wait_for_previous_phase()` Works

```python
def wait_for_previous_phase(sprint_id, phase_id, ...):
    prev = _prev(phase_id)  # Get previous phase
    
    while True:  # Blocking loop (actually raises immediately)
        data = _load(sprint_id, output_dir)
        prev_state = data["phases"][prev]["state"]
        
        if prev_state == "approved":
            return {"ready": True}  # Can proceed
        
        if prev_state == "awaiting_approval":
            raise RuntimeError(
                f"⏸️ Phase '{phase_id}' blocked.\n"
                f"   Run: carby phase approve {sprint_id} {prev}"
            )  # ← HARD BLOCK
        
        raise RuntimeError(
            f"⏸️ Phase '{phase_id}' blocked.\n"
            f"   Previous phase '{prev}' is {prev_state}."
        )  # ← HARD BLOCK
```

**Key Behavior:**
- Function **raises RuntimeError immediately** (not a polling wait)
- No retry mechanism — caller must handle the exception
- Clear error message tells user exactly what to run

### 1.3 What Happens When a Phase Completes

**In `mark_phase_complete()`:**

```python
def mark_phase_complete(sprint_id, phase_id, summary, ...):
    data["phases"][phase_id] = {
        "state": "awaiting_approval",  # ← KEY: Not "approved"
        "summary": summary,
        "completed_at": datetime.now().isoformat(),
    }
    return {
        "message": f"✅ Phase '{phase_id}' complete. Awaiting approval.",
        "approve_command": f"carby phase approve {sprint_id} {phase_id}",
    }
```

**Phase stays in `awaiting_approval` state until user explicitly approves.**

### 1.4 What Triggers the Next Phase

**Nothing automatic.** The next phase is triggered by:

1. **User runs approval command:**
   ```bash
   carby-sprint approve <sprint_id> <phase_id>
   ```

2. **User manually starts next phase:**
   ```bash
   carby-sprint start <sprint_id> --mode sequential
   ```

3. **Optional auto-advance flag (must be explicitly set):**
   ```bash
   carby-sprint approve <sprint_id> <phase_id> --auto-advance
   ```
   This only exists in the `approve.py` command and is **NOT the default**.

---

## 2. Phase Transition Analysis

### Phase Transition Matrix

| Transition | Trigger | Automatic? | Blocking Mechanism |
|------------|---------|------------|-------------------|
| **Discover → Design** | `carby-sprint approve <sprint> discover` + `carby-sprint start <sprint> --mode sequential` | ❌ NO | Phase Lock: `wait_for_previous_phase()` checks if discover is "approved" |
| **Design → Build** | `carby-sprint approve <sprint> design` + `carby-sprint start <sprint> --mode sequential` | ❌ NO | Phase Lock + Design Gate: Additional `DesignGateEnforcer.check_approval()` for build phase |
| **Build → Verify** | `carby-sprint approve <sprint> build` + `carby-sprint start <sprint> --mode sequential` | ❌ NO | Phase Lock: `wait_for_previous_phase()` checks if build is "approved" |
| **Verify → Deliver** | `carby-sprint approve <sprint> verify` + `carby-sprint start <sprint> --mode sequential` | ❌ NO | Phase Lock: `wait_for_previous_phase()` checks if verify is "approved" |

### Detailed Transition Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  DISCOVER   │────▶│    DESIGN   │────▶│    BUILD    │
│   PHASE     │     │   PHASE     │     │   PHASE     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       ▼                   ▼                   ▼
  1. Agent runs      1. User runs:       1. User runs:
     to completion       carby-sprint        carby-sprint
                        approve <sprint>    approve <sprint>
  2. State changes:     design              design
     "awaiting_approval"  2. State changes:  2. State changes:
                        "approved"          "approved"
  3. User sees:        3. User runs:       3. Design Gate
     "Run: carby         carby-sprint        check passes
      phase approve..."  start <sprint>      (token exists)
                        --mode sequential
                        4. Design agent     4. User runs:
                           spawns            carby-sprint
                        5. Design agent      start <sprint>
                           runs to           --mode sequential
                           completion     5. Build agent
                        6. State changes:      spawns
                           "awaiting_approval"
                        7. User sees:
                           "Run: carby
                            phase approve..."
```

---

## 3. Auto-Trigger Analysis

### Question: Does Carby Studio Auto-Advance Phases?

**Answer: NO.**

### Evidence from Code Review

**1. No Event Listeners for Phase Completion**
- No file watchers on `phase_lock.json`
- No callbacks registered when phase state changes
- No background daemon monitoring phase status

**2. Approval Command is Explicit User Action**

From `carby_sprint/commands/approve.py`:
```python
@click.command()
@click.argument("sprint_id")
@click.argument("phase_id", required=False)
@click.option("--auto-advance", is_flag=True, help="Automatically start the next phase after approval")
def approve(ctx, sprint_id, phase_id, output_dir, auto_advance):
    """Approve a phase completion and unblock the next phase."""
    # ... approval logic ...
    
    if auto_advance:
        # Only if --auto-advance flag explicitly provided
        ctx.invoke(start, sprint_id=sprint_id, mode="sequential")
    else:
        # DEFAULT: Just show message, don't auto-start
        click.echo(f"\nTo start the next phase, run:")
        click.echo(f"  carby-sprint start {sprint_id} --mode sequential")
```

**3. Start Command Requires Explicit Invocation**

From `carby_sprint/commands/start.py`:
```python
@click.command()
@click.argument("sprint_id")
@click.option("--mode", type=click.Choice(["parallel", "sequential"]))
def start(ctx, sprint_id, max_parallel, dry_run, output_dir, mode):
    """Start the given SPRINT_ID."""
    # Must be explicitly called by user
```

**4. Agent Completion Does Not Trigger Next Phase**

When an agent completes:
```python
def report_phase_completion(sprint_id, phase_id, summary, output_dir):
    lock = PhaseLock(output_dir, sprint_id)
    lock.complete_phase(phase_id, summary)
    
    # ONLY displays message — does NOT spawn next phase
    click.echo(f"\n{'='*60}")
    click.echo(f"PHASE COMPLETE: {phase_id}")
    click.echo(f"{'='*60}

---

## 7. Critical Questions Answered

### Q1: Does Carby Studio auto-advance phases, or is it all manual?

**A: 100% MANUAL.** No auto-advance mechanism exists. User must:
1. Run `carby-sprint approve <sprint> <phase>` after each phase completes
2. Run `carby-sprint start <sprint> --mode sequential` to begin each phase

### Q2: Are there any race conditions in phase transitions?

**A: MINOR RISK.** File-based state reduces races but doesn't eliminate them:
- Check-then-act pattern in `spawn_phase_agent()` has a race window
- No exclusive file locking on state reads/writes
- Atomic rename in `_save()` prevents file corruption but not logical races

### Q3: Can a phase get stuck waiting forever?

**A: YES.** If user never runs the `approve` command:
- Phase stays in `awaiting_approval` state indefinitely
- Next phase blocked until approval given
- No timeout or escalation mechanism

### Q4: Is the Design Gate properly integrated with phase flow?

**A: YES, with caveats:**
- Design Gate adds extra approval layer for Build phase
- Token expires after 7 days (potential for blocking)
- Requires both Phase Lock approval AND Design Gate token
- Integration is opt-in via `check_design_gate=True` parameter

### Q5: What happens if a phase fails — is there retry logic?

**A: NO RETRY LOGIC.** If a phase fails:
- State remains whatever it was (likely "in_progress")
- No automatic retry
- No failure state tracking
- User must manually diagnose and restart

---

## 8. Recommendations

### High Priority

1. **Add Auto-Advance Option**
   ```python
   # In approve command, make --auto-advance the default for sequential mode
   # OR add a sprint-level setting: "auto_advance: true"
   ```

2. **Add Phase Timeout Handling**
   ```python
   # Track phase start time, auto-fail if stuck in_progress too long
   if datetime.now() - started_at > timeout:
       mark_phase_failed(sprint_id, phase_id)
   ```

3. **Add Retry Logic for Failed Phases**
   ```python
   # Track failure count, allow N retries before requiring manual intervention
   if phase_state == "failed" and retry_count < max_retries:
       auto_restart_phase(sprint_id, phase_id)
   ```

### Medium Priority

4. **Add File Locking for State Changes**
   ```python
   # Use file locking to prevent race conditions
   with file_lock(lock_path):
       data = _load(sprint_id)
       data[phase]["state"] = new_state
       _save(data, sprint_id)
   ```

5. **Extend Design Token Expiration**
   ```python
   # Increase from 7 days to 30 days, or make configurable
   expires_in_hours=720  # 30 days
   ```

### Low Priority

6. **Add Phase Completion Notifications**
   - Webhook support
   - Slack/Discord integration
   - Desktop notifications

7. **Add Phase Status Dashboard**
   - Web UI for viewing phase status
   - Real-time updates via WebSocket

---

## 9. Summary

| Aspect | Status | Notes |
|--------|--------|-------|
| Phase enforcement | ✅ WORKING | File-based state machine correctly blocks phases |
| Sequential execution | ✅ WORKING | Phases execute in order with approval gates |
| Design Gate | ✅ WORKING | Additional approval layer for Build phase |
| Auto-trigger | ❌ NOT IMPLEMENTED | All transitions manual |
| Race conditions | ⚠️ MINOR RISK | File-based state reduces but doesn't eliminate |
| Deadlocks | ⚠️ POSSIBLE | Phases can wait forever for approval |
| Retry logic | ❌ NOT IMPLEMENTED | Failed phases require manual intervention |

### Overall Assessment

**Phase enforcement is solid and working as designed.** The system correctly implements a manual approval workflow that prevents phases from running out of order. However, the complete lack of automation means users must actively manage each phase transition, which creates friction and potential for phases to stall indefinitely.

**Recommendation:** Consider adding optional auto-advance for teams that want a more automated workflow, while keeping manual approval as the safe default.

---

*End of Report*
