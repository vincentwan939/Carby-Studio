# Carby Studio Telegram Bot — Final Design V1.0

## Design Philosophy

**Minimal interface. Maximum clarity. Zero duplication.**

The bot is a thin Telegram layer over Carby Studio. It does not replace, replicate, or compete with Carby Studio. It only exposes Carby Studio's functionality through Telegram's interface.

---

## Scope Definition

### Bot Does ✅

| Function | Method |
|----------|--------|
| Read project state | Poll `~/.openclaw/workspace/projects/*.json` |
| Send notifications | Telegram messages on state change |
| Display status | Format JSON for Telegram |
| Trigger actions | Call `carby-studio` CLI commands |

### Bot Does NOT ❌

| Function | Reason |
|----------|--------|
| Spawn agents | `carby-studio dispatch` handles this |
| Manage retries | Carby Studio handles retry logic |
| Store state | team-tasks JSON files are source of truth |
| Handle credentials | carby-credentials skill handles this |
| Approval gates | Not required per user |

---

## Architecture

```
┌─────────────────┐      read       ┌──────────────────┐
│   Telegram      │ ◄────────────── │  Carby Studio    │
│     Bot         │                 │  (JSON files)    │
│                 │ ──CLI commands──►│                  │
└─────────────────┘                 └──────────────────┘
        │                                    │
        │         notifications              │
        └───────────────(poll)───────────────┘
```

### Data Flow

1. **Polling Loop** (30s interval)
   - Read all project JSON files
   - Compare with cached state
   - Detect changes
   - Send notifications

2. **User Actions**
   - Button tap → Parse callback
   - Execute CLI command
   - Show result

3. **State Cache**
   - In-memory for performance
   - Persist to disk for recovery
   - Reload on startup

---

## Menu Structure

### Level 1: Main Menu (Persistent Keyboard)

```
┌─────────────┬─────────────┬─────────────┐
│  📋 Projects │  ➕ New     │  ⚙️ More   │
└─────────────┴─────────────┴─────────────┘
```

### Level 2: Projects List

```
📋 Your Projects (4)

🟢 family-photo-hub
   Build: in-progress • 12m
   [View Details]

⏸️ karina-photo-pipeline
   Design: done • Awaiting dispatch
   [View Details]

🔴 time-fetcher
   Verify: failed • 2h ago
   [View Details]

✅ photo-archive
   Deliver: done • Yesterday
   [View Details]

[← Back]
```

**Status Icons:**
- 🟢 = in-progress
- ⏸️ = done (awaiting dispatch)
- 🔴 = failed
- ✅ = completed/archived

### Level 3: Project Detail View

```
family-photo-hub
🎯 Photo management for Sony a7c2 & iPhone

Pipeline:
✅ Discover → ✅ Design → 🔄 Build → ⬜ Verify → ⬜ Deliver
   (done)      (done)    (in-progress)

Current Stage: Build
Status: in-progress
🤖 Agent: code-agent
⏱️ Started: 12 minutes ago
📄 Task: Implement photo ingestion module

Stage Actions:
[🛑 Stop Agent] [📋 View Logs]

Project Management:
[🗄️ Archive] [✏️ Rename] [🗑️ Delete]

Files:
📁 src/ 📖 docs/
[Open in Finder]

 [← Back to Projects]
```

### Level 3a: Awaiting Dispatch State

```
karina-photo-pipeline
🎯 AI photo processing pipeline

Previous: Design ✅ (completed 5m ago)
Next: Build ⏸️ (ready to start)

[▶️ Dispatch Build]  ← Start next stage
[⏭️ Skip Build]      ← Skip to Verify
[📖 Review Design]   ← View docs/design.md

 [← Back]
```

### Level 3b: Failed State

```
time-fetcher
🎯 World time API service

Failed: Verify ❌
Error: Tests failed (3/10 passed)
Time: 2 hours ago

[🔄 Retry Verify]    ← Retry same stage
[⏭️ Skip Verify]     ← Skip to Deliver
[📋 View Logs]       ← See error details

 [← Back]
```

### Level 2: New Project

```
➕ New Project

What are you building?
[________________]

Choose approach:
[🏃 Quick]      → Single agent
[📐 Pipeline]   → Full SDLC

Project created: my-project
[▶️ Dispatch Discover]
```

### Level 2: Notifications

```
🔔 Notifications (Today)

5m ago  ✅ karina-pipeline: Design complete
1h ago  🚀 family-photo-hub: Build started
3h ago  ❌ time-fetcher: Verify failed

[Clear History]
```

### Level 2: More Menu

```
⚙️ More

[📊 System Status]  → Show all projects summary
[🗄️ Archived]       → View archived projects
[❓ Help]            → Command reference

 [← Back to Main]
```

---

## Button to Command Mapping

| Button | CLI Command | Notes |
|--------|-------------|-------|
| [▶️ Dispatch] | `carby-studio dispatch {project} {stage}` | Start next stage |
| [⏭️ Skip] | `carby-studio skip {project} {stage}` | Skip current stage |
| [🔄 Retry] | `carby-studio retry {project} {stage}` | Retry failed stage |
| [🛑 Stop] | Signal to agent process | Emergency stop |
| [🗄️ Archive] | `carby-studio update {project} archived` | Mark archived |
| [✏️ Rename] | `carby-studio rename {old} {new}` | Change project name |
| [🗑️ Delete] | `carby-studio delete {project}` | Remove project |
| [📋 View Logs] | `cat {project}/logs/{stage}.log` | Show logs |
| [📖 Review] | `cat {project}/docs/{artifact}` | Show artifact |

---

## Notification System

### Polling Configuration

```python
POLL_INTERVAL = 30  # seconds
ACTIVE_PROJECT_INTERVAL = 10  # seconds for in-progress projects
```

### Notification Triggers

| State Change | Notification | Buttons |
|--------------|--------------|---------|
| pending → in-progress | "🚀 {project}: {stage} started" | None (info only) |
| in-progress → done | "✅ {project}: {stage} complete" | [Dispatch] [Skip] [Review] |
| in-progress → failed | "❌ {project}: {stage} failed" | [Retry] [Skip] [Logs] |
| done → skipped | "⏭️ {project}: {stage} skipped" | [Dispatch Next] |
| Any → archived | "🗄️ {project}: archived" | None |

### Deduplication

- Track sent notification IDs
- Don't resend within 5 minutes
- Clear history after 24 hours

---

## Project Management Features

### Rename Project

```
User: Tap [✏️ Rename]
Bot:  "New name for karina-pipeline?"
User: "karina-ai-pipeline"
Bot:  Validate → Check exists → Check chars
      → Run: carby-studio rename karina-pipeline karina-ai-pipeline
      → "Renamed to karina-ai-pipeline"
```

**Validation:**
- Unique name (not existing)
- Valid chars: a-z, 0-9, hyphen
- Max 50 chars

### Delete Project

```
User: Tap [🗑️ Delete]
Bot:  "⚠️ Delete karina-pipeline?\n"
      "This removes all files and cannot be undone.\n"
      "Type 'DELETE' to confirm:"
User: "DELETE"
Bot:  Check: No running agent?
      → Run: carby-studio delete karina-pipeline
      → "Deleted karina-pipeline"
```

**Safety:**
- Require typed "DELETE" confirmation
- Block if stage is "in-progress"
- Suggest archive as alternative
- Show what will be deleted:
  - `projects/karina-pipeline/` (dir)
  - `projects/karina-pipeline.json` (state)

---

## Error Handling

### CLI Command Fails

```
User: Tap [▶️ Dispatch]
Bot:  Run: carby-studio dispatch family-photo-hub build
      Exit code: 1
      Error: "Agent already running"
Bot:  Show in Telegram:
      "❌ Dispatch failed\n"
      "Agent already running for family-photo-hub/build\n"
      "[Check Status] [Force Stop]"
```

### File Access Error

```
Bot: Read: ~/.openclaw/workspace/projects/missing.json
     FileNotFoundError
Bot: Skip project, log warning
     Don't crash entire poll loop
```

### Telegram API Error

```
Bot: Send message → Rate limited
     Retry with exponential backoff
     Max 3 retries
     Log failure if persistent
```

---

## Technical Implementation

### File Structure

```
bot/
├── carby_bot.py          # Core logic
├── telegram_handler.py   # Telegram integration
├── config.py             # Settings
├── cache.json            # State cache (auto-generated)
└── requirements.txt      # Dependencies
```

### Key Classes

```python
class CarbyBot:
    """Core bot logic."""
    
    def poll_projects(self) -> List[Notification]:
        """Poll all projects, return notifications."""
        pass
    
    def dispatch_stage(self, project: str, stage: str) -> Result:
        """Trigger dispatch via CLI."""
        pass
    
    def rename_project(self, old: str, new: str) -> Result:
        """Rename project via CLI."""
        pass
    
    def delete_project(self, project: str) -> Result:
        """Delete project via CLI."""
        pass

class TelegramHandler:
    """Telegram bot interface."""
    
    def send_notification(self, notification: Notification):
        """Send notification to user."""
        pass
    
    def handle_callback(self, callback: CallbackQuery):
        """Handle button tap."""
        pass
```

### Dependencies

```
python-telegram-bot>=20.0
```

---

## Configuration

### Environment Variables

```bash
CARBY_BOT_TOKEN="123456:ABC-DEF..."  # Telegram bot token
CARBY_WORKSPACE="~/.openclaw/workspace/projects"  # Project directory
CARBY_POLL_INTERVAL="30"  # Seconds
CARBY_DEBUG="false"  # Verbose logging
```

### Runtime Config

```python
# config.py
PROJECTS_DIR = os.path.expanduser("~/.openclaw/workspace/projects")
CACHE_FILE = os.path.expanduser("~/.openclaw/carby-bot/cache.json")
POLL_INTERVAL = 30  # seconds
ACTIVE_POLL_INTERVAL = 10  # seconds when projects in-progress
```

---

## Security Considerations

| Risk | Mitigation |
|------|------------|
| Telegram token leak | Store in env var, not code |
| Unauthorized access | Bot is private (no public username) |
| Command injection | Validate all inputs, use subprocess safely |
| File traversal | Validate project names, no `../` |
| Accidental delete | Require typed confirmation |

---

## Testing Strategy

### Unit Tests

```python
def test_poll_detects_change():
    """Test state change detection."""
    pass

def test_dispatch_button_calls_cli():
    """Test button triggers CLI."""
    pass

def test_rename_validates_name():
    """Test rename validation."""
    pass
```

### Integration Tests

```python
def test_full_flow():
    """Test: notification → button → CLI → result."""
    pass
```

---

## Deployment

### Local Development

```bash
export CARBY_BOT_TOKEN="your-token"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 telegram_handler.py
```

### Production

```bash
# Option 1: Systemd service
sudo systemctl enable carby-bot
sudo systemctl start carby-bot

# Option 2: LaunchAgent (macOS)
launchctl load ~/Library/LaunchAgents/com.carby.bot.plist

# Option 3: Docker
docker run -d --name carby-bot \
  -e CARBY_BOT_TOKEN=$TOKEN \
  -v ~/.openclaw:/data \
  carby-bot:latest
```

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Notification latency | < 60s | Time from stage done to Telegram |
| Button response time | < 3s | Time from tap to CLI execution |
| Uptime | > 99% | Bot process availability |
| User actions | > 50% | % of stage transitions via bot vs CLI |

---

## Future Enhancements (V2)

| Feature | Priority | Notes |
|---------|----------|-------|
| Artifact preview | Medium | Send design.md content in Telegram |
| Log streaming | Low | Real-time log tail |
| Metrics dashboard | Low | Show carby-studio metrics |
| Multi-user | Low | Support multiple Telegram users |
| Voice commands | Low | "Dispatch family-photo-hub" |

---

## Final Checklist

- [x] All user requirements addressed
- [x] No duplication of Carby Studio functionality
- [x] Clear button → command mapping
- [x] Safety measures for destructive actions
- [x] Error handling defined
- [x] Security considerations documented
- [x] Deployment options provided
- [x] Success metrics defined

---

**Status: READY FOR IMPLEMENTATION**

Estimated effort: 3 days
Confidence: 95%
