# Carby Studio Telegram Bot — Final Menu Design

## Scope: Notification + Dispatch ONLY

**No approval model. No state management. Pure interface layer.**

```
┌─────────────────────────────────────────────────────────────────┐
│                    CARBY STUDIO BOT                             │
│                                                                 │
│   Responsibilities:                                             │
│   1. 📊 Read project state from JSON files                      │
│   2. 🔔 Send notifications when stages change                   │
│   3. 👆 Provide buttons that call carby-studio CLI              │
│                                                                 │
│   Does NOT:                                                     │
│   ❌ Manage approvals                                           │
│   ❌ Spawn agents                                               │
│   ❌ Handle retries                                             │
│   ❌ Store state                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## Menu Tree (Final)

```
🤖 Carby Studio Bot
│
├── 📋 PROJECTS (main menu)
│   │
│   ├── 🟢 family-photo-hub
│   │   ├── Status: Build in-progress
│   │   ├── 🤖 code-agent (12m)
│   │   ├── [View Details]
│   │   └── [🛑 Stop Agent]
│   │
│   ├── ⏸️ karina-photo-pipeline
│   │   ├── Status: Design done • Awaiting dispatch
│   │   ├── ✅ Completed 5m ago
│   │   ├── [▶️ Dispatch Build]
│   │   └── [⏭️ Skip Build]
│   │
│   ├── 🔴 time-fetcher
│   │   ├── Status: Verify failed
│   │   ├── ❌ Error: Tests failed
│   │   ├── [🔄 Retry Verify]
│   │   └── [⏭️ Skip Verify]
│   │
│   └── ✅ photo-archive
│       ├── Status: Deliver done
│       ├── ✅ Completed yesterday
│       └── [View Details]
│
│   (Inside project detail view:)
│   └── [🗄️ Archive] [✏️ Rename] [🗑️ Delete]
│
├── ➕ NEW PROJECT
│   ├── "What are you building?"
│   │   └── [Type description]
│   ├── Choose approach:
│   │   ├── [🏃 Quick] → carby-studio init --mode quick
│   │   └── [📐 Full Pipeline] → carby-studio init --mode linear
│   └── Project created!
│       [▶️ Dispatch Discover]
│
├── 🔔 NOTIFICATIONS (history)
│   ├── Recent (today)
│   │   ├── 5m ago: karina-pipeline Design done
│   │   ├── 1h ago: family-photo-hub Build started
│   │   └── 3h ago: time-fetcher Verify failed
│   └── [Clear History]
│
└── ⚙️ MORE
    │
    ├── 📊 SYSTEM STATUS
    │   ├── Active projects: 3
    │   ├── In progress: 1
    │   ├── Awaiting dispatch: 1
    │   ├── Failed: 1
    │   └── [Refresh]
    │
    ├── 🗄️ ARCHIVED PROJECTS
    │   └── [View archived]
    │
    └── ❓ HELP
        └── Command reference


═══════════════════════════════════════════════════════════════
                     DETAIL VIEWS
═══════════════════════════════════════════════════════════════


📋 PROJECT DETAIL (family-photo-hub)
│
├── family-photo-hub
├── 🎯 Photo management for Sony a7c2 & iPhone
│
├── Pipeline:
│   ✅ Discover → ✅ Design → 🔄 Build → ⬜ Verify → ⬜ Deliver
│      (done)     (done)    (in-progress)
│
├── Current Stage: Build
│   ├── Status: in-progress
│   ├── 🤖 Agent: code-agent
│   ├── ⏱️ Started: 12 minutes ago
│   └── 📄 Task: Implement photo ingestion module
│
├── Actions:
│   [🛑 Stop Agent] [📋 View Logs] [💬 Message Agent]
│
├── Files:
│   📁 /projects/family-photo-hub/src/
│   📖 /projects/family-photo-hub/docs/
│   [View in Finder]
│
├── Project Management:
│   [🗄️ Archive] [✏️ Rename] [🗑️ Delete]
│
└── [← Back to Projects]


⏸️ AWAITING DISPATCH (karina-photo-pipeline)
│
├── karina-photo-pipeline
├── 🎯 AI photo processing pipeline
│
├── Previous Stage: Design
│   ├── Status: done ✅
│   ├── ⏱️ Completed: 5 minutes ago
│   └── 📄 Output: docs/design.md
│
├── Next Stage: Build
│   ├── Status: pending ⏸️
│   └── 🤖 Agent: code-agent (ready)
│
├── Actions:
│   [▶️ Dispatch Build]  ← carby-studio dispatch karina-pipeline build
│   [⏭️ Skip Build]      ← carby-studio skip karina-pipeline build
│   [📖 Review Design]    ← Show docs/design.md
│
└── [← Back to Projects]


🔴 FAILED STAGE (time-fetcher)
│
├── time-fetcher
├── 🎯 World time API service
│
├── Failed Stage: Verify
│   ├── Status: failed ❌
│   ├── ⏱️ Failed: 2 hours ago
│   ├── ❌ Error: Tests failed (3/10 passed)
│   └── 📄 Log: tests/verify-report.md
│
├── Actions:
│   [🔄 Retry Verify]     ← carby-studio retry time-fetcher verify
│   [⏭️ Skip Verify]      ← carby-studio skip time-fetcher verify
│   [📋 View Logs]        ← Show error details
│   [🛑 Stop Pipeline]    ← Pause project
│
└── [← Back to Projects]


═══════════════════════════════════════════════════════════════
                  NOTIFICATION FLOW
═══════════════════════════════════════════════════════════════


POLLING LOOP (every 30 seconds):

Bot: Read all project JSON files
  ↓
Bot: Compare with last known state
  ↓
IF stage status changed:
  ↓
  CASE "in-progress" → "done":
    Send: "✅ {project}: {stage} complete"
    Buttons: [Dispatch Next] [Skip] [View]
    
  CASE "in-progress" → "failed":
    Send: "❌ {project}: {stage} failed"
    Buttons: [Retry] [Skip] [View Logs]
    
  CASE "pending" → "in-progress":
    Send: "🚀 {project}: {stage} started"
    (no buttons, just info)
    
  CASE "done" → "skipped":
    Send: "⏭️ {project}: {stage} skipped"
    Buttons: [Dispatch Next]


═══════════════════════════════════════════════════════════════
                   COMMAND MAPPING
═══════════════════════════════════════════════════════════════


Button → CLI Command:

[▶️ Dispatch {stage}] → carby-studio dispatch {project} {stage}
[⏭️ Skip {stage}]     → carby-studio skip {project} {stage}
[🔄 Retry {stage}]     → carby-studio retry {project} {stage}
[🛑 Stop Agent]       → (signal to running agent)
[🗄️ Archive Project]  → carby-studio update {project} archived
[✏️ Rename Project]   → carby-studio rename {project} {new_name}
[🗑️ Delete Project]   → carby-studio delete {project} [--force]


═══════════════════════════════════════════════════════════════
                    STATE MACHINE
═══════════════════════════════════════════════════════════════


User sees in Telegram:

pending ──[▶️ Dispatch]──→ in-progress ──[auto]──→ done
                                              ↓
                                         [▶️ Dispatch]
                                              ↓
                                         next stage pending

pending ──[▶️ Dispatch]──→ in-progress ──[auto]──→ failed
                                              ↓
                                         [🔄 Retry]
                                              ↓
                                         back to pending


═══════════════════════════════════════════════════════════════
                   IMPLEMENTATION NOTES
═══════════════════════════════════════════════════════════════


1. POLLING INTERVAL: 30 seconds
   - Read all ~/.openclaw/workspace/projects/*.json
   - Compare with in-memory cache
   - Send notifications on changes

2. STATE CACHE:
   - Keep last known state in memory
   - Persist to ~/.openclaw/carby-bot/cache.json
   - Reload on bot restart

3. NOTIFICATION DEDUPLICATION:
   - Track sent notification IDs
   - Don't resend same notification
   - Clear after 24 hours

4. BUTTON CALLBACKS:
   - Store (project, stage, action) in callback_data
   - Execute carby-studio CLI command
   - Show result in Telegram

5. ERROR HANDLING:
   - If CLI command fails → show error in Telegram
   - If project file missing → mark as archived
   - If poll fails → retry with backoff


═══════════════════════════════════════════════════════════════
                     SUCCESS CRITERIA
═══════════════════════════════════════════════════════════════


✅ User receives notification within 30s of stage completion
✅ User can dispatch next stage with one tap
✅ User can retry failed stage with one tap
✅ User can skip stage with one tap
✅ User can view project status anytime
✅ No need to SSH to run carby-studio commands
✅ Works on iPhone (Telegram)


═══════════════════════════════════════════════════════════════
                      EXCLUDED FEATURES
═══════════════════════════════════════════════════════════════


❌ Approval gates (not needed per user)
❌ Credential management (carby-credentials handles this)
❌ Agent spawning logic (carby-studio handles this)
❌ Retry logic (carby-studio handles this)
❌ State storage (team-tasks handles this)
❌ Web dashboard (Telegram only)


═══════════════════════════════════════════════════════════════
              PROJECT MANAGEMENT FEATURES
═══════════════════════════════════════════════════════════════


## Rename Project

Flow:
1. User taps [✏️ Rename Project]
2. Bot asks: "New name for {project}?"
3. User types new name
4. Bot validates: unique, valid characters
5. Bot runs: carby-studio rename {old} {new}
6. Bot updates internal cache
7. Confirmation: "Renamed to {new}"

Error cases:
- Name exists → "Project {new} already exists"
- Invalid chars → "Use only letters, numbers, hyphens"
- CLI fails → Show error


## Delete Project

Flow:
1. User taps [🗑️ Delete Project]
2. Bot shows confirmation:
   "⚠️ Delete {project}? This cannot be undone."
   "Type 'DELETE' to confirm:"
3. User types DELETE
4. Bot runs: carby-studio delete {project}
5. Or with force: rm -rf {project_dir} + rm {project}.json
6. Confirmation: "Deleted {project}"

Safety:
- Require typed confirmation (not just button)
- Only allow delete if project not in-progress
- Archive option presented as alternative

Error cases:
- Project in-progress → "Stop agent first"
- Files locked → "Retry later"
- Partial delete → Show what succeeded/failed
