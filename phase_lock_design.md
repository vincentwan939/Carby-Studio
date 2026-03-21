# Minimal Phase Lock Enforcement Design
## Carby Studio v3.0 - Property Hunter Parallel Execution Fix

---

## Executive Summary

**The Single Change with Biggest Impact:** Add a `PhaseLock` file-based blocking mechanism that prevents Phase N from starting until Phase N-1 writes an explicit "APPROVED" marker.

**Lines of Code:** ~80 lines
**Files Modified:** 2 (new: `phase_lock.py`, modify: `gate_enforcer.py`)
**Breaking Changes:** None (opt-in via `--sequential` flag)

---

## 1. The Core Problem

```
Current Flow (Broken):
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

**Root Cause:** No mechanism exists to block agent spawning until previous phase is explicitly approved.

---

## 2. The Minimal Solution: Phase Lock

```
Fixed Flow (Sequential):
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

---

## 3. Implementation

### 3.1 New File: `carby_sprint/phase_lock.py` (45 lines)

```python
"""
Phase Lock - Minimal sequential execution enforcement.

Prevents Phase N from starting until Phase N-1 is explicitly approved.
Uses simple file-based locking with state markers.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from enum import Enum


class PhaseLockState(str, Enum):
    """Phase lock states."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"      # Waiting for approval
    APPROVED = "approved"         # Can proceed to next phase
    REJECTED = "rejected"


class PhaseLock:
    """
    Minimal phase lock enforcement.
    
    Usage:
        lock = PhaseLock("/path/to/project", "my-sprint")
        
        # Before spawning Phase 2:
        if not lock.can_start_phase("phase_2"):
            raise RuntimeError("Phase 1 not approved yet")
        
        # When Phase 1 completes:
        lock.complete_phase("phase_1", summary="Discover done")
        
        # User approves:
        lock.approve_phase("phase_1")
    """
    
    PHASE_SEQUENCE = [
        "phase_1_discover",
        "phase_2_design", 
        "phase_3_build",
        "phase_4_verify",
        "phase_5_deliver",
    ]
    
    def __init__(self, project_dir: str, sprint_id: str):
        self.project_dir = Path(project_dir)
        self.sprint_id = sprint_id
        self.lock_file = self.project_dir / ".carby-sprints" / f"{sprint_id}.phase-lock.json"
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
    
    def _load(self) -> Dict:
        if self.lock_file.exists():
            return json.loads(self.lock_file.read_text())
        return {p: PhaseLockState.NOT_STARTED for p in self.PHASE_SEQUENCE}
    
    def _save(self, state: Dict) -> None:
        self.lock_file.write_text(json.dumps(state, indent=2))
    
    def can_start_phase(self, phase_id: str) -> bool:
        """Check if phase can start (previous phase approved)."""
        state = self._load()
        
        idx = self.PHASE_SEQUENCE.index(phase_id)
        if idx == 0:
            return True  # First phase always allowed
        
        prev_phase = self.PHASE_SEQUENCE[idx - 1]
        return state.get(prev_phase) == PhaseLockState.APPROVED
    
    def start_phase(self, phase_id: str) -> None:
        """Mark phase as in progress."""
        state = self._load()
        state[phase_id] = PhaseLockState.IN_PROGRESS
        state[f"{phase_id}_started_at"] = datetime.utcnow().isoformat()
        self._save(state)
    
    def complete_phase(self, phase_id: str, summary: str = "") -> None:
        """Mark phase as completed (waiting for approval)."""
        state = self._load()
        state[phase_id] = PhaseLockState.COMPLETED
        state[f"{phase_id}_completed_at"] = datetime.utcnow().isoformat()
        state[f"{phase_id}_summary"] = summary
        self._save(state)
    
    def approve_phase(self, phase_id: str) -> None:
        """Mark phase as approved (unblocks next phase)."""
        state = self._load()
        state[phase_id] = PhaseLockState.APPROVED
        state[f"{phase_id}_approved_at"] = datetime.utcnow().isoformat()
        self._save(state)
    
    def get_current_phase(self) -> Optional[str]:
        """Get the current phase that should be running."""
        state = self._load()
        for phase in self.PHASE_SEQUENCE:
            if state.get(phase) in (PhaseLockState.NOT_STARTED, PhaseLockState.IN_PROGRESS):
                return phase
        return None
    
    def get_status(self) -> Dict:
        """Get full phase lock status."""
        return self._load()
```

### 3.2 Modified: `carby_sprint/gate_enforcer.py` (+35 lines)

Add to the `GateEnforcer` class:

```python
# Add to imports at top
from .phase_lock import PhaseLock

# Add to __init__ method:
def __init__(self, project_dir: str):
    # ... existing code ...
    self.phase_lock = PhaseLock(project_dir, "default")  # Will be set per-sprint

# Add new methods to GateEnforcer class:

def enforce_sequential(self, sprint_id: str, phase_id: str) -> bool:
    """
    Enforce sequential phase execution.
    
    Called before spawning any agent. Blocks until previous phase approved.
    
    Args:
        sprint_id: Sprint identifier
        phase_id: Phase attempting to start
        
    Returns:
        True if phase can start
        
    Raises:
        GateBypassError: If previous phase not approved
    """
    lock = PhaseLock(self.project_dir, sprint_id)
    
    if not lock.can_start_phase(phase_id):
        current = lock.get_current_phase()
        raise GateBypassError(
            f"Cannot start {phase_id}: {current} not approved. "
            f"Run: carby-sprint approve {sprint_id} {current}"
        )
    
    lock.start_phase(phase_id)
    return True

def complete_phase_for_approval(self, sprint_id: str, phase_id: str, summary: str) -> None:
    """
    Mark phase complete and wait for user approval.
    
    Called when an agent finishes its work.
    """
    lock = PhaseLock(self.project_dir, sprint_id)
    lock.complete_phase(phase_id, summary)
    
    # Log to user
    print(f"\n{'='*60}")
    print(f"PHASE COMPLETE: {phase_id}")
    print(f"{'='*60}")
    print(f"Summary: {summary}")
    print(f"\nTo approve and continue:")
    print(f"  carby-sprint approve {sprint_id} {phase_id}")
    print(f"{'='*60}\n")
```

### 3.3 New CLI Command: `carby_sprint/commands/approve.py` (35 lines)

```python
"""CLI command to approve phases."""

import click
from pathlib import Path
from ..phase_lock import PhaseLock


@click.command()
@click.argument("sprint_id")
@click.argument("phase_id")
def approve(sprint_id: str, phase_id: str):
    """Approve a phase completion and unblock next phase."""
    project_dir = Path(".")
    lock = PhaseLock(project_dir, sprint_id)
    lock.approve_phase(phase_id)
    click.echo(f"✓ Phase {phase_id} approved")
    
    # Show next phase
    current = lock.get_current_phase()
    if current:
        click.echo(f"Next phase ready: {current}")
```

---

## 4. Integration Points (Where to Hook)

### 4.1 Before Agent Spawn (Critical Hook)

In the agent spawning code (wherever `sessions_spawn` is called):

```python
from carby_sprint.gate_enforcer import GateEnforcer

def spawn_phase_agent(sprint_id: str, phase_id: str, agent_config: dict):
    """Spawn agent with sequential enforcement."""
    
    # ENFORCEMENT: Check if we can start this phase
    enforcer = GateEnforcer(".")
    enforcer.enforce_sequential(sprint_id, phase_id)  # ← BLOCKS HERE
    
    # Only proceeds if previous phase approved
    return sessions_spawn(
        task=agent_config["task"],
        runtime="subagent",
        # ...
    )
```

### 4.2 On Agent Completion

In the agent callback when work is done:

```python
def on_agent_complete(sprint_id: str, phase_id: str, result: dict):
    """Handle agent completion."""
    
    enforcer = GateEnforcer(".")
    enforcer.complete_phase_for_approval(
        sprint_id, 
        phase_id,
        summary=result.get("message", "")
    )
    # Phase now shows as COMPLETED, waiting for approval
```

---

## 5. What This Prevents

### Before (Broken):
```python
# All these spawn simultaneously - NO CHECKS
sessions_spawn(task="discover...")   # Phase 1
sessions_spawn(task="design...")     # Phase 2 - NO WAIT
sessions_spawn(task="build...")      # Phase 3 - NO WAIT
```

### After (Fixed):
```python
# Phase 2 blocked until Phase 1 approved
spawn_phase_agent(sprint_id, "phase_1_discover", config)  # Starts
# → completes, shows "waiting for approval"
# User runs: carby-sprint approve my-sprint phase_1_discover
spawn_phase_agent(sprint_id, "phase_2_design", config)    # NOW starts
```

---

## 6. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **File-based state** | Simple, debuggable, survives process restarts |
| **Explicit `approve` command** | User must consciously approve (no auto-advance) |
| **Opt-in via flag** | Doesn't break existing parallel sprints |
| **Leverage existing GateEnforcer** | Uses same project_dir pattern, familiar API |
| **No tokens needed** | File state is sufficient (simpler than HMAC for this use case) |

---

## 7. Usage Flow

```bash
# 1. Initialize sprint with sequential mode
carby-sprint init my-project --sequential

# 2. Start sprint (Phase 1 runs)
carby-sprint start my-project
# → Discover agent spawns
# → Discover completes, shows "waiting for approval"

# 3. User reviews deliverables, then approves
carby-sprint approve my-project phase_1_discover

# 4. Phase 2 automatically starts (or user runs start again)
# → Design agent spawns
# → Design completes, shows "waiting for approval"

# 5. Repeat...
carby-sprint approve my-project phase_2_design
```

---

## 8. Summary

**The Minimal Fix:**

1. **PhaseLock class** (45 lines) - File-based state machine
2. **GateEnforcer hooks** (35 lines) - Enforcement integration  
3. **CLI approve command** (35 lines) - User approval interface

**Total: ~115 lines of new code**

**Single Point of Enforcement:**
- `enforce_sequential()` called before every agent spawn
- Blocks with clear error message if previous phase not approved
- No way to bypass without user running `approve` command

This would have prevented Property Hunter's parallel execution with minimal changes to the existing framework.