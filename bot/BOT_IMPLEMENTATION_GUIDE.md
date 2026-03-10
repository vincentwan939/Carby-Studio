# Carby Studio Telegram Bot — Implementation Guide

## Architecture Understanding

### Carby Studio Stack

```
┌─────────────────────────────────────────┐
│           Carby Studio CLI              │
│         (scripts/carby-studio)          │
│         - Bash wrapper                  │
│         - Calls task_manager.py         │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────▼───────────────────────┐
│      team-tasks/scripts/task_manager.py │
│      - Python JSON state manager        │
│      - Stores: ~/.openclaw/workspace/   │
│        projects/<project>.json          │
└─────────────────────────────────────────┘
```

### State File Location

```
~/.openclaw/workspace/projects/<project>.json
```

Example state:
```json
{
  "project": "family-photo-hub",
  "goal": "Photo management system...",
  "status": "active",
  "mode": "linear",
  "pipeline": ["discover", "design", "build", "verify", "deliver"],
  "currentStage": "build",
  "stages": {
    "discover": {
      "agent": "discover",
      "status": "done",
      "task": "",
      "startedAt": "...",
      "completedAt": "...",
      "output": "",
      "logs": []
    },
    "design": {
      "status": "done",
      ...
    },
    "build": {
      "status": "in-progress",
      "agent": "code-agent",
      "startedAt": "..."
    }
  }
}
```

### Status Values

- `pending` — Waiting to start
- `in-progress` — Agent working
- `done` — Completed, needs approval
- `failed` — Error, needs retry/skip
- `skipped` — Intentionally skipped

---

## Bot Integration Points

### 1. Read State (Display)

```python
import json

PROJECTS_DIR = "~/.openclaw/workspace/projects"

def get_project_status(project_id):
    """Read project state from Carby Studio."""
    with open(f"{PROJECTS_DIR}/{project_id}.json") as f:
        return json.load(f)

def list_projects():
    """List all projects."""
    import os
    projects = []
    for f in os.listdir(PROJECTS_DIR):
        if f.endswith('.json'):
            projects.append(f[:-5])
    return projects
```

### 2. Send Approval (Trigger)

Carby Studio uses `task_manager.py update` command:

```bash
# Mark stage as done (from agent)
python3 team-tasks/scripts/task_manager.py update <project> <stage> done

# But we need: Mark stage as approved (human approval)
# This advances to next stage in linear mode
```

**Key insight:** In linear mode, when a stage is marked `done`, `currentStage` auto-advances to next.

So approval = mark current stage as `done`? No — agent marks done, then human approves.

Looking at the code: `done` auto-advances. So where is "approval" stored?

**Answer:** Carby Studio doesn't have explicit "approval" state. The flow is:
1. Agent completes → marks `done` → auto-advances `currentStage`
2. But we want: Agent completes → waits for approval → human approves → advances

**This is a gap.** Carby Studio currently auto-advances on `done`.

### Options:

**A. Modify Carby Studio** — Add `approved` field, don't auto-advance until approved
**B. Use `pending` as approval gate** — Agent marks `pending`, human approves → `in-progress`
**C. Separate approval file** — Bot tracks approvals separately

**Which approach?**

---

### 3. Receive Notifications

How does bot know when stage completes?

**Option A: File watcher** (Simplest)
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ProjectWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.json'):
            notify_telegram(event.src_path)
```

**Option B: Polling** (Robust)
```python
import time

def poll_projects():
    last_states = {}
    while True:
        for project in list_projects():
            state = get_project_status(project)
            if state != last_states.get(project):
                notify_if_changed(state)
                last_states[project] = state
        time.sleep(30)
```

**Option C: Carby Studio calls bot** (Requires Carby Studio changes)
```python
# Carby Studio would need webhook config
WEBHOOK_URL = "http://localhost:8000/notify"
```

**Recommendation: Option B (Polling)** — Simple, no dependencies, works with existing Carby Studio.

---

## Implementation (Revised)

### Core Loop

```python
class CarbyBot:
    def __init__(self):
        self.projects_dir = "~/.openclaw/workspace/projects"
        self.last_states = {}
        
    def poll_and_notify(self):
        """Main loop - poll projects, send notifications."""
        for project_id in self.list_projects():
            state = self.get_project_state(project_id)
            
            # Check for changes
            if project_id not in self.last_states:
                # New project
                self.notify_new_project(project_id, state)
            else:
                old_state = self.last_states[project_id]
                
                # Check stage completion
                old_stage = old_state.get('currentStage')
                new_stage = state.get('currentStage')
                
                if old_stage != new_stage:
                    # Stage changed - notify
                    self.notify_stage_complete(project_id, old_stage, state)
                    
                # Check for failures
                for stage_name, stage in state['stages'].items():
                    old_stage_status = old_state['stages'].get(stage_name, {}).get('status')
                    new_stage_status = stage.get('status')
                    
                    if new_stage_status == 'failed' and old_stage_status != 'failed':
                        self.notify_stage_failed(project_id, stage_name, stage)
            
            self.last_states[project_id] = state
    
    def approve_stage(self, project_id):
        """Send approval to Carby Studio."""
        # How? Depends on Q above
        pass
```

---

## Open Questions for You

### Q1: Approval Mechanism

Carby Studio auto-advances when stage is marked `done`. How should bot handle approval?

| Option | Approach | Carby Studio Change? |
|--------|----------|---------------------|
| A | Add `approved` field to stages | Yes — modify task_manager.py |
| B | Use `pending` → `in-progress` as approval gate | Yes — change agent behavior |
| C | Bot tracks approvals, calls `carby-studio skip` to advance | No — hacky |
| D | Don't change Carby Studio, just notify on `done` | No — but no approval gate |

**Default: D** (simplest, no changes) — but loses "approve every stage" requirement.

**Recommendation: A** — Add `approved` boolean to stage state.

### Q2: Notification Method

| Option | Approach | Pros | Cons |
|--------|----------|------|------|
| A | File watcher | Instant | Extra dependency |
| B | Polling (30s) | Simple, robust | 30s delay |
| C | Carby Studio webhook | Instant | Requires changes |

**Recommendation: B** — Polling is fine for 30s delay.

---

## Simplified Bot (MVP)

If we accept that Carby Studio doesn't have approval gates yet:

### What Bot Does
1. **Read state** — Display projects, stages
2. **Poll for changes** — Notify on stage complete/fail
3. **Show status** — Pipeline visualization

### What Bot Doesn't Do (Yet)
- ❌ Approval gates (requires Carby Studio changes)
- ❌ Trigger agent spawning (Carby Studio does this)
- ❌ Error retry (Carby Studio does this)

### Next Steps
1. Build read-only bot (display + notifications)
2. Modify Carby Studio to add approval gates
3. Add approval triggers to bot

---

## Your Decision Needed

**Do you want to:**

**A.** Build read-only bot now, modify Carby Studio later for approvals
**B.** Modify Carby Studio first (add `approved` field), then build full bot
**C.** Different approach?
