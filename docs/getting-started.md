# Getting Started with Carby Sprint

Welcome to Carby Sprint — the parallel execution framework for Carby Studio. This guide will walk you through installation, setup, and your first sprint.

---

## Prerequisites Check

Before installing Carby Sprint, ensure your system meets these requirements:

### System Requirements

| Component | Minimum Version | Recommended |
|-----------|-----------------|-------------|
| Python | 3.9+ | 3.11+ |
| OpenClaw | Latest | Latest |
| Git | 2.30+ | 2.40+ |
| GitHub CLI (optional) | 2.0+ | Latest |
| 1Password CLI (optional) | 2.0+ | Latest |

### Verify Prerequisites

```bash
# Check Python version
python3 --version

# Check OpenClaw
openclaw --version

# Check Git
git --version

# Check GitHub CLI (optional)
gh --version

# Check 1Password CLI (optional)
op --version
```

### Required Python Packages

Carby Sprint requires these packages (installed automatically):

- `click` >= 8.0 — CLI framework
- `typing-extensions` — Type hints support

---

## Installation Steps

### Step 1: Install Carby Sprint

```bash
# Navigate to the Carby Studio skill directory
cd ~/.openclaw/workspace/skills/carby-studio

# Install the carby-sprint package
pip install -e .

# Or install from requirements
pip install -r requirements.txt
```

### Step 2: Configure Your Shell

Add Carby Sprint to your PATH:

```bash
# For zsh (macOS default)
echo 'export PATH="$HOME/.openclaw/workspace/skills/carby-studio:$PATH"' >> ~/.zshrc
source ~/.zshrc

# For bash
echo 'export PATH="$HOME/.openclaw/workspace/skills/carby-studio:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Step 3: Verify Installation

```bash
# Check version
carby-sprint --version

# Expected output:
# carby-sprint, version 0.1.0

# View help
carby-sprint --help
```

### Step 4: Optional Configuration

Create a configuration file at `~/.openclaw/carby-studio.conf`:

```ini
[defaults]
timeout = 3600
max_parallel = 5
log_level = INFO

[security]
gate_enforcement = strict
audit_logging = enabled
```

---

## First Sprint Walkthrough

Let's create and run your first sprint!

### Step 1: Initialize a Sprint

```bash
# Create a new sprint
carby-sprint init sprint-001 \
  --project my-first-project \
  --goal "Build a REST API for user management"
```

**Output:**
```
✓ Sprint 'sprint-001' initialized successfully
  Project: my-first-project
  Goal: Build a REST API for user management
  Duration: 14 days (2026-03-19 to 2026-04-02)
  Status: initialized

Next steps:
  carby-sprint plan sprint-001 --work-items <items>
```

### Step 2: Plan Work Items

```bash
# Add work items to your sprint
carby-sprint plan sprint-001 \
  --work-items "Setup project structure,Create user model,Implement auth endpoints,Write tests"
```

**Output:**
```
✓ Sprint 'sprint-001' planned successfully
  Work items: 4
    - WI-1: Setup project structure
    - WI-2: Create user model
    - WI-3: Implement auth endpoints
    - WI-4: Write tests

Next steps:
  carby-sprint gate sprint-001 1  # Pass planning gate
```

### Step 3: Pass the Planning Gate

```bash
# Pass gate 1 (Planning Gate)
carby-sprint gate sprint-001 1
```

**Output:**
```
✓ Gate 1 passed for sprint 'sprint-001'
  Token: val-tier1-a1b2c3d4
  Tier: 1
  Risk Score: 0.5/5.0

Next: carby-sprint gate sprint-001 2
```

### Step 4: Pass the Design Gate

```bash
# Pass gate 2 (Design Gate)
carby-sprint gate sprint-001 2
```

### Step 5: Start the Sprint

```bash
# Start execution
carby-sprint start sprint-001 --max-parallel 3
```

**Output:**
```
✓ Sprint 'sprint-001' started successfully
  Status: running
  Max parallel: 3
  Work items: 4
  Started at: 2026-03-19T10:30:00

Monitor with:
  carby-sprint status sprint-001 --watch
```

### Step 6: Monitor Progress

```bash
# Check status
carby-sprint status sprint-001

# Watch live updates
carby-sprint status sprint-001 --watch
```

**Sample Output:**
```
============================================================
Sprint: sprint-001
============================================================

📋 General
  Project: my-first-project
  Goal: Build a REST API for user management
  Status: RUNNING
  Created: 2026-03-19

📅 Timeline
  Start: 2026-03-19
  End: 2026-04-02
  Duration: 14 days
  Elapsed: 2h 15m

🚪 Gates
  ✅ Gate 1: Planning Gate [passed]
  ✅ Gate 2: Design Gate [passed]
  ⏳ Gate 3: Implementation Gate [pending]
  ⏳ Gate 4: Validation Gate [pending]
  ⏳ Gate 5: Release Gate [pending]

📦 Work Items
  Total: 4
    📋 planned: 2
    🔄 in_progress: 1
    ✅ completed: 1

⚙️  Execution
  Max parallel: 3
  In progress: 1
  Completed: 1
  Failed: 0
```

### Step 7: Update Work Items

```bash
# Mark a work item as in-progress
carby-sprint work-item update sprint-001 WI-1 --status in_progress

# Mark as completed
carby-sprint work-item update sprint-001 WI-1 --status completed
```

### Step 8: Pass Remaining Gates

```bash
# Pass implementation gate
carby-sprint gate sprint-001 3

# Pass validation gate
carby-sprint gate sprint-001 4

# Pass release gate (completes the sprint)
carby-sprint gate sprint-001 5
```

### Step 9: Archive the Sprint

```bash
# Archive completed sprint
carby-sprint archive sprint-001
```

**Output:**
```
✓ Sprint 'sprint-001' archived
  Archived at: 2026-03-19T14:30:00
  Location: .carby-sprints/archive/sprint-001
```

---

## Common Commands Reference

### Sprint Management

| Command | Description | Example |
|---------|-------------|---------|
| `init` | Create a new sprint | `carby-sprint init <sprint-id> --project <name> --goal "Goal"` |
| `plan` | Plan work items | `carby-sprint plan <sprint-id> --work-items "Item1,Item2"` |
| `start` | Start sprint execution | `carby-sprint start <sprint-id> --max-parallel 3` |
| `status` | Check sprint status | `carby-sprint status <sprint-id> --watch` |
| `pause` | Pause a running sprint | `carby-sprint pause <sprint-id>` |
| `resume` | Resume a paused sprint | `carby-sprint resume <sprint-id>` |
| `cancel` | Cancel a sprint | `carby-sprint cancel <sprint-id> --reason "Blocked"` |
| `archive` | Archive completed sprint | `carby-sprint archive <sprint-id>` |

### Gate Management

| Command | Description | Example |
|---------|-------------|---------|
| `gate` | Pass a validation gate | `carby-sprint gate <sprint-id> <1-5>` |

**Gate Numbers:**
- `1` — Planning Gate
- `2` — Design Gate
- `3` — Implementation Gate
- `4` — Validation Gate
- `5` — Release Gate

### Work Item Management

| Command | Description | Example |
|---------|-------------|---------|
| `work-item add` | Add a work item | `carby-sprint work-item add <sprint-id> --title "Title"` |
| `work-item update` | Update work item | `carby-sprint work-item update <sprint-id> <wi-id> --status completed` |
| `work-item list` | List work items | `carby-sprint work-item list <sprint-id> --status in_progress` |
| `work-item show` | Show work item details | `carby-sprint work-item show <sprint-id> <wi-id>` |

### Global Options

| Option | Description | Example |
|--------|-------------|---------|
| `--verbose, -v` | Enable verbose output | `carby-sprint -v init ...` |
| `--config, -c` | Use custom config file | `carby-sprint -c /path/to/config ...` |
| `--output-dir, -o` | Custom sprint directory | `carby-sprint init ... -o ./sprints` |

---

## Troubleshooting Section

### Installation Issues

#### "command not found: carby-sprint"

**Cause:** The CLI is not in your PATH.

**Solution:**
```bash
# Add to PATH
export PATH="$HOME/.openclaw/workspace/skills/carby-studio:$PATH"

# Or use the full path
~/.openclaw/workspace/skills/carby-studio/carby-sprint --version
```

#### ImportError: No module named 'click'

**Cause:** Dependencies not installed.

**Solution:**
```bash
# Install dependencies
pip install click typing-extensions

# Or install from requirements
cd ~/.openclaw/workspace/skills/carby-studio
pip install -r requirements.txt
```

---

### Sprint Issues

#### "Sprint 'xxx' not found"

**Cause:** Sprint doesn't exist or wrong output directory.

**Solution:**
```bash
# Check available sprints
ls -la .carby-sprints/

# Use correct output directory
carby-sprint status sprint-001 --output-dir ./my-sprints
```

#### "Cannot start sprint. Required gates not passed"

**Cause:** Gates 1 and 2 must be passed before starting.

**Solution:**
```bash
# Pass required gates
carby-sprint gate sprint-001 1
carby-sprint gate sprint-001 2

# Then start
carby-sprint start sprint-001
```

#### "Sprint 'xxx' already exists"

**Cause:** Sprint ID must be unique.

**Solution:**
```bash
# Use a different sprint ID
carby-sprint init sprint-002 --project my-project --goal "Goal"

# Or delete existing sprint
rm -rf .carby-sprints/sprint-001
```

---

### Gate Issues

#### "Cannot pass gate X: Sprint status is 'yyy'"

**Cause:** Sprint must be in correct status for the gate.

**Gate Requirements:**
| Gate | Required Status |
|------|-----------------|
| 1 | initialized, planned |
| 2 | planned |
| 3 | running |
| 4 | running |
| 5 | running |

**Solution:** Check current status and advance to required state:
```bash
carby-sprint status sprint-001
```

#### "Gate X already passed"

**Cause:** Gate has already been validated.

**Solution:** No action needed, or use `--force` to re-pass (not recommended):
```bash
carby-sprint gate sprint-001 2 --force
```

---

### Work Item Issues

#### "Work item 'WI-X' not found"

**Cause:** Work item ID doesn't exist.

**Solution:**
```bash
# List all work items
carby-sprint work-item list sprint-001

# Use correct ID format (WI-1, WI-2, etc.)
carby-sprint work-item update sprint-001 WI-1 --status completed
```

---

### Performance Issues

#### Sprint status updates slowly

**Cause:** Too many work items or slow disk I/O.

**Solution:**
```bash
# Reduce refresh interval in watch mode
carby-sprint status sprint-001 --watch --refresh 5

# Check disk space
df -h

# Archive old sprints to improve performance
carby-sprint archive sprint-old-001
```

---

## Quick Reference Card

```bash
# Initialize → Plan → Gate 1 → Gate 2 → Start → Monitor → Gates 3-5 → Archive
carby-sprint init sprint-001 --project X --goal "Y"
carby-sprint plan sprint-001 --work-items "A,B,C"
carby-sprint gate sprint-001 1
carby-sprint gate sprint-001 2
carby-sprint start sprint-001
carby-sprint status sprint-001 --watch
carby-sprint gate sprint-001 3
carby-sprint gate sprint-001 4
carby-sprint gate sprint-001 5
carby-sprint archive sprint-001
```

---

## Next Steps

- **[CLI Reference](cli-reference.md)** — Complete command documentation
- **[Migration Guide](migration-guide.md)** — Moving from old carby-studio
- **[TROUBLESHOOTING.md](../TROUBLESHOOTING.md)** — Additional troubleshooting

---

*Last updated: 2026-03-19*

