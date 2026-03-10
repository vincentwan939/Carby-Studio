# Carby Studio Telegram Bot — Final Specification

## Scope: Reporting & Triggering ONLY

**The bot does NOT replace Carby Studio. It is a thin Telegram interface.**

Carby Studio handles:
- ✅ Agent spawning
- ✅ Error handling & retry logic
- ✅ Credential management
- ✅ Pipeline orchestration
- ✅ Notifications

Bot handles:
- 📱 Display project status (read from Carby Studio state)
- 👆 Send approval/reject triggers (write to Carby Studio state)
- 📨 Forward Carby Studio notifications to Telegram

---

## Architecture

```
┌─────────────┐     read state      ┌──────────────┐
│   Telegram  │ ←────────────────── │ Carby Studio │
│    Bot      │                     │   (existing) │
│             │ ──approval trigger──→│              │
└─────────────┘                     └──────────────┘
       ↑                                   │
       │         notifications            │
       └──────────────────────────────────┘
```

---

## Data Flow

### 1. Display Status (Read-Only)

```
User: "Projects"
  ↓
Bot: Read ~/.openclaw/workspace/projects/*.json
  ↓
Bot: Format for Telegram
  ↓
User sees: "🟢 family-photo-hub [build] in-progress"
```

### 2. Send Approval (Trigger Only)

```
User clicks: [Approve]
  ↓
Bot: Write approval to project.json
     (or call carby-studio CLI)
  ↓
Carby Studio: Detects approval → Starts next stage
  ↓
Carby Studio: Spawns agent, handles everything
```

### 3. Receive Notification (Forward Only)

```
Carby Studio: Stage complete
  ↓
Carby Studio: Sends notification (how?)
  ↓
Bot: Receives notification
  ↓
Bot: Forwards to Telegram
  ↓
User sees: "🔔 family-photo-hub: DESIGN complete [Review] [Approve]"
```

---

## Implementation (Simplified)

### Core Functions

```python
def show_projects():
    """Read project state, format for display."""
    projects = read_carby_studio_state()
    return format_for_telegram(projects)

def approve_stage(project_id):
    """Send approval trigger to Carby Studio."""
    write_approval_to_state(project_id)
    # Carby Studio handles the rest
    
def on_notification(notification):
    """Forward Carby Studio notification to Telegram."""
    send_telegram_message(notification)
```

### No Complex Logic

❌ No agent spawning  
❌ No retry logic  
❌ No error handling  
❌ No credential management  
❌ No pipeline orchestration  

✅ Just read, display, trigger, forward  

---

## Integration Points

### 1. Read State

```python
# Read from existing Carby Studio state
PROJECTS_DIR = "~/.openclaw/workspace/projects"

def get_project_status(project_id):
    with open(f"{PROJECTS_DIR}/{project_id}.json") as f:
        return json.load(f)
```

### 2. Send Approval

```python
# Option A: Write directly to state file
def approve(project_id):
    state = get_project_status(project_id)
    state["stages"][state["current_stage"]]["approved"] = True
    save_state(state)

# Option B: Call carby-studio CLI
def approve(project_id):
    subprocess.run(["carby-studio", "approve", project_id])
```

**Which does Carby Studio support?**

### 3. Receive Notifications

How does Carby Studio send notifications to the bot?

**Option A:** File watcher
```python
# Bot watches project.json for changes
watch(PROJECTS_DIR, on_change)
```

**Option B:** Webhook/HTTP
```python
# Carby Studio calls bot API
@app.post("/notify")
def notify(message: str):
    send_telegram(message)
```

**Option C:** Shared queue
```python
# Both read/write to Redis/SQLite queue
queue = SQLiteQueue("~/.openclaw/notifications.db")
```

**Which does Carby Studio support?**

---

## UI (Unchanged from Design)

```
📋 PROJECTS
├── 🟢 family-photo-hub
│   └── [View] [Approve] [Reject]
├── 🟡 karina-pipeline
│   └── [View] [Approve] [Reject]
└── 🟢 time-fetcher
    └── [Archive]

➕ NEW PROJECT → Trigger only, Carby Studio creates
⚙️ MORE → Credentials, Status, Help (all read-only)
```

---

## Questions for Carby Studio Integration

1. **State location:** Where does Carby Studio store project state?
   - `~/.openclaw/workspace/projects/*.json`?

2. **Approval mechanism:** How does Carby Studio detect approvals?
   - Write to JSON? CLI command? Other?

3. **Notification mechanism:** How does Carby Studio send notifications?
   - File change? Webhook? Queue? Other?

4. **Concurrent projects:** Carby Studio supports multiple active?
   - Yes (per your answer)

---

## Revised Implementation Plan

### Phase 1: Read-Only (Done)
- ✅ Read project state
- ✅ Format for Telegram
- ✅ Display projects list
- ✅ Display project detail

### Phase 2: Triggers (Next)
- [ ] Write approval to state
- [ ] Write reject to state
- [ ] Write retry/skip to state

### Phase 3: Notifications (Pending)
- [ ] Receive from Carby Studio
- [ ] Forward to Telegram

---

## Key Insight

**The bot is a Telegram frontend for Carby Studio.**

It doesn't do anything Carby Studio doesn't already do.
It just makes Carby Studio accessible from your phone.
