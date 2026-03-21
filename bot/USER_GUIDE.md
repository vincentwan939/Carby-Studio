# TintinBot User Guide

Complete guide for using TintinBot with the new carby-sprint migration features.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [New Features](#new-features)
3. [Commands Reference](#commands-reference)
4. [Sprint Workflow](#sprint-workflow)
5. [Troubleshooting](#troubleshooting)
6. [Migration Notes](#migration-notes)

---

## Quick Start

### Starting the Bot

```bash
# Deploy and start the bot
./deploy.sh

# Check bot status
./monitor.sh
```

### Your First Sprint

1. **Create a sprint:**
   ```
   /sprint_init my-first-sprint "Build a todo app" 14
   ```

2. **Start the sprint:**
   ```
   /start my-first-sprint
   ```

3. **Advance through gates:**
   ```
   /gate my-first-sprint 1  # Start gate 1 (Discover)
   /approve my-first-sprint # Approve current phase
   /gate my-first-sprint 2  # Move to gate 2 (Design)
   ```

---

## New Features

### 🏃 Sprint-Based Workflow

The bot now supports **sprints** - time-boxed projects with 5 gates:

| Gate | Name | Purpose |
|------|------|---------|
| 1 | Discover | Research and requirements |
| 2 | Design | Architecture and planning |
| 3 | Build | Implementation |
| 4 | Verify | Testing and validation |
| 5 | Deliver | Deployment and handoff |

### 📊 Visual Gate/Phase Display

Each sprint shows visual progress:

```
🎯 my-first-sprint
Status: 🟢 Active | Gate: 2/5 | Phase: 1/3

Gates:
Gate 1: Discover   ✅ Complete
Gate 2: Design     🔄 In Progress
Gate 3: Build      ⬜ Pending
Gate 4: Verify     ⬜ Pending
Gate 5: Deliver    ⬜ Pending

Current Phase:
Phase 1: Research    ◉ In Progress
Phase 2: Planning    ◯ Pending
Phase 3: Review      ◯ Pending
```

### 🎛️ Interactive Controls

New inline buttons for managing sprints:
- **▶️ Start Gate** - Begin work on a gate
- **⏸️ Pause** - Temporarily halt the sprint
- **✅ Approve** - Mark phase as complete
- **🔄 Retry** - Retry a failed gate
- **⏭️ Skip** - Skip current gate/phase
- **❌ Cancel** - Cancel the sprint
- **🗄️ Archive** - Archive completed sprint

### 📋 Sprint vs Project

| Feature | Legacy Projects | New Sprints |
|---------|----------------|-------------|
| Storage | `projects/*.json` | `.carby-sprints/<name>/` |
| Stages | 5 fixed stages | 5 gates with multiple phases |
| Duration | Unlimited | Configurable (days) |
| Visualization | Basic | Rich gate/phase display |
| CLI | `carby-studio` | `carby-sprint` |

---

## Commands Reference

### Sprint Management

| Command | Description | Example |
|---------|-------------|---------|
| `/sprint_init <name> <goal> [days]` | Create new sprint | `/sprint_init my-app "Build app" 14` |
| `/start <name>` | Start sprint | `/start my-app` |
| `/pause <name>` | Pause sprint | `/pause my-app` |
| `/resume <name>` | Resume sprint | `/resume my-app` |
| `/cancel <name>` | Cancel sprint | `/cancel my-app` |
| `/archive <name>` | Archive sprint | `/archive my-app` |

### Gate Operations

| Command | Description | Example |
|---------|-------------|---------|
| `/gate <name> <1-5>` | Start/retry gate | `/gate my-app 2` |
| `/gate_skip <name> <1-5>` | Skip gate | `/gate_skip my-app 3` |
| `/approve <name> [phase]` | Approve phase | `/approve my-app` |
| `/retry <name>` | Retry current gate | `/retry my-app` |

### Status & Info

| Command | Description | Example |
|---------|-------------|---------|
| `/status <name>` | Show sprint status | `/status my-app` |
| `/phase_status <name>` | Show phase details | `/phase_status my-app` |
| `/list` | List all sprints | `/list` |

### Legacy Commands (Still Supported)

| Command | Maps To | Description |
|---------|---------|-------------|
| `/dispatch <project> <stage>` | `/gate` | Start stage (auto-converts) |
| `/skip <project> <stage>` | `/gate_skip` | Skip stage |
| `/stop <project>` | `/pause` | Pause project |
| `/projects` | `/list` | List projects/sprints |

---

## Sprint Workflow

### Typical Sprint Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│  1. CREATE                                                  │
│     /sprint_init my-sprint "Goal description" 14           │
│     → Creates sprint with 5 gates, each with phases        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  2. START                                                   │
│     /start my-sprint                                        │
│     → Activates sprint, ready for Gate 1                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  3. EXECUTE GATES (repeat for gates 1-5)                   │
│     ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│     │  Gate N  │───▶│  Phases  │───▶│ Approve  │           │
│     │  Start   │    │ Execute  │    │ Complete │           │
│     └──────────┘    └──────────┘    └──────────┘           │
│          │                                    │             │
│          └────────── Retry if failed ◀────────┘             │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  4. COMPLETE                                                │
│     → All gates approved                                   │
│     → Sprint marked complete                               │
│     → Can archive with /archive                            │
└─────────────────────────────────────────────────────────────┘
```

### Gate Details

Each gate contains multiple phases:

**Gate 1: Discover**
- Phase 1: Research
- Phase 2: Requirements gathering
- Phase 3: Stakeholder alignment

**Gate 2: Design**
- Phase 1: Architecture
- Phase 2: Technical planning
- Phase 3: Review

**Gate 3: Build**
- Phase 1: Implementation
- Phase 2: Code review
- Phase 3: Integration

**Gate 4: Verify**
- Phase 1: Testing
- Phase 2: Bug fixes
- Phase 3: Validation

**Gate 5: Deliver**
- Phase 1: Deployment
- Phase 2: Documentation
- Phase 3: Handoff

---

## Troubleshooting

### Bot Won't Start

**Symptom:** `./deploy.sh` fails or bot exits immediately

**Solutions:**
1. Check Python is installed: `python3 --version`
2. Verify token is set: `echo $CARBY_BOT_TOKEN`
3. Check logs: `tail -f bot.log`
4. Run syntax check: `python3 -m py_compile bot.py`

### Commands Not Responding

**Symptom:** Bot is running but doesn't respond to commands

**Solutions:**
1. Check Telegram API connectivity: `./monitor.sh`
2. Verify bot token is valid
3. Check if bot is blocked by user
4. Look for errors in logs: `grep ERROR bot.log | tail -20`

### Sprint Creation Fails

**Symptom:** `/sprint_init` returns error

**Solutions:**
1. Sprint name must be lowercase letters, numbers, hyphens only
2. Sprint name max 50 characters
3. Check if sprint already exists: `/list`
4. Verify write permissions in `.carby-sprints/` directory

### Gate Advancement Issues

**Symptom:** Can't advance to next gate

**Solutions:**
1. Current gate must be completed first
2. Check status: `/status <sprint-name>`
3. Retry if failed: `/retry <sprint-name>`
4. Force skip if needed: `/gate_skip <sprint-name> <gate-number>`

### State Corruption

**Symptom:** Sprint shows incorrect status or errors

**Solutions:**
1. Check sprint state file: `cat .carby-sprints/<name>/state.json`
2. Look for backup: `ls backups/`
3. Restore from backup if needed
4. Contact admin if state is unrecoverable

### Performance Issues

**Symptom:** Bot is slow or unresponsive

**Solutions:**
1. Check memory usage: `./monitor.sh`
2. Review log file size: `ls -lh bot.log`
3. Rotate logs if too large: `mv bot.log bot.log.old && touch bot.log`
4. Restart bot: `./deploy.sh --force`

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid sprint name" | Name contains invalid characters | Use only a-z, 0-9, hyphens |
| "Sprint not found" | Sprint doesn't exist | Check `/list` for correct name |
| "Gate already active" | Trying to start active gate | Complete or skip current gate first |
| "Permission denied" | File system issue | Check directory permissions |
| "CLI command failed" | carby-sprint not installed | Install carby-sprint CLI |

---

## Migration Notes

### Backward Compatibility

✅ **Fully Maintained:**
- Old project JSON files still readable
- Legacy commands still work (auto-mapped to new commands)
- Mixed environment supported (projects + sprints)
- No data migration required

### What Changed

| Aspect | Before | After |
|--------|--------|-------|
| CLI Tool | `carby-studio` | `carby-sprint` |
| Storage | `projects/*.json` | `.carby-sprints/<name>/state.json` |
| Stages | 5 fixed stages | 5 gates with phases |
| UI | Simple stage list | Rich gate/phase visualization |
| Commands | Stage-based | Gate-based |

### Migration Timeline

1. **Phase 1 (Complete):** CLI executor migrated
2. **Phase 2 (Complete):** State manager migrated
3. **Phase 3 (Complete):** Telegram UI migrated
4. **Phase 4 (Complete):** Testing complete

### Rolling Back

If issues occur:
```bash
# Stop current bot
pkill -f "python.*bot.py"

# Restore from git
git checkout HEAD~1 -- bot.py carby_bot.py cli_executor.py state_manager.py telegram_interface.py

# Restart
./deploy.sh
```

---

## Support

For additional help:
1. Check logs: `tail -f bot.log`
2. Run diagnostics: `./monitor.sh --alert`
3. Review migration docs: `MIGRATION_COMPLETE.md`
4. Contact: Check with your system administrator

---

*Last updated: 2026-03-21*
*Version: carby-sprint migration v1.0*
