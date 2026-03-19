# Carby Sprint CLI Reference

Complete reference for the `carby-sprint` command-line interface.

---

## Global Options

These options are available for all commands:

| Option | Short | Description |
|--------|-------|-------------|
| `--config` | `-c` | Path to configuration file |
| `--verbose` | `-v` | Enable verbose output |
| `--version` | — | Show version and exit |
| `--help` | `-h` | Show help message and exit |

### Global Option Examples

```bash
# Use custom config file
carby-sprint -c ~/.config/carby-sprint.conf init sprint-001 --project test --goal "Test"

# Enable verbose mode
carby-sprint -v status sprint-001

# Check version
carby-sprint --version
```

---

## Command Reference

### `init` — Initialize Sprint

Create a new sprint with configuration and metadata.

**Usage:**
```bash
carby-sprint init [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Unique identifier for the sprint |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--project` | `-p` | Yes | — | Project identifier |
| `--goal` | `-g` | Yes | — | Sprint goal description |
| `--description` | `-d` | No | `""` | Additional sprint description |
| `--start-date` | — | No | Today | Sprint start date (YYYY-MM-DD) |
| `--duration` | — | No | 14 | Sprint duration in days |
| `--output-dir` | `-o` | No | `.carby-sprints` | Output directory for sprint data |

**Examples:**

```bash
# Basic initialization
carby-sprint init sprint-001 --project my-api --goal "Build REST API"

# With description and custom duration
carby-sprint init sprint-002 \
  --project auth-service \
  --goal "Implement OAuth2" \
  --description "Secure authentication for all services" \
  --duration 21

# With specific start date
carby-sprint init sprint-003 \
  --project frontend \
  --goal "Redesign dashboard" \
  --start-date 2026-04-01 \
  --duration 7
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint already exists
- `2` — Invalid arguments

---

### `plan` — Plan Work Items

Associate work items with a sprint.

**Usage:**
```bash
carby-sprint plan [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--work-items` | `-w` | Yes* | — | Comma-separated list of work item IDs |
| `--from-file` | `-f` | No | — | Load work items from JSON file |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

*Required unless using `--from-file`

**Examples:**

```bash
# Plan with comma-separated items
carby-sprint plan sprint-001 --work-items "Setup,Develop,Test,Deploy"

# Plan from JSON file
carby-sprint plan sprint-001 --from-file work-items.json
```

**JSON File Format:**
```json
{
  "work_items": [
    {
      "id": "WI-001",
      "title": "Setup project",
      "description": "Initialize repository",
      "priority": "high",
      "estimated_hours": 4
    },
    {
      "id": "WI-002",
      "title": "Develop feature",
      "priority": "medium"
    }
  ]
}
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Invalid work items file format

---

### `start` — Start Sprint

Begin sprint execution after gates are passed.

**Usage:**
```bash
carby-sprint start [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--max-parallel` | `-p` | No | 3 | Maximum parallel work items |
| `--dry-run` | — | No | False | Simulate without making changes |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
# Start with default settings
carby-sprint start sprint-001

# Start with higher parallelism
carby-sprint start sprint-001 --max-parallel 5

# Dry run to preview
carby-sprint start sprint-001 --dry-run
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Required gates not passed
- `3` — Sprint already running/completed

---

### `status` — Check Sprint Status

Display current sprint status, gates, and work items.

**Usage:**
```bash
carby-sprint status [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--watch` | `-w` | No | False | Watch status continuously |
| `--refresh` | `-r` | No | 2 | Refresh interval in seconds (watch mode) |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
# Check status once
carby-sprint status sprint-001

# Watch with 5-second refresh
carby-sprint status sprint-001 --watch --refresh 5

# Watch with default 2-second refresh
carby-sprint status sprint-001 -w
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found

---

### `gate` — Pass Validation Gate

Validate and pass a sprint gate.

**Usage:**
```bash
carby-sprint gate [OPTIONS] SPRINT_ID GATE_NUMBER
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |
| `GATE_NUMBER` | Yes | Gate number (1-5) |

**Gate Numbers:**
| Number | Name | Description | Required Status |
|--------|------|-------------|-----------------|
| 1 | Planning Gate | Validate sprint planning | initialized, planned |
| 2 | Design Gate | Validate design decisions | planned |
| 3 | Implementation Gate | Validate implementation | running |
| 4 | Validation Gate | Validate completed work | running |
| 5 | Release Gate | Validate release readiness | running |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--auto-generate` | `-a` | No | False | Auto-generate assumptions document |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
# Pass planning gate
carby-sprint gate sprint-001 1

# Pass with auto-generated assumptions
carby-sprint gate sprint-001 2 --auto-generate
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Gate requirements not met
- `3` — Gate already passed

---

### `pause` — Pause Sprint

Temporarily halt sprint execution.

**Usage:**
```bash
carby-sprint pause [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
carby-sprint pause sprint-001
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Sprint not running

---

### `resume` — Resume Sprint

Continue sprint execution after pause.

**Usage:**
```bash
carby-sprint resume [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
carby-sprint resume sprint-001
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Sprint not paused

---

### `cancel` — Cancel Sprint

Permanently stop a sprint. Cannot be resumed.

**Usage:**
```bash
carby-sprint cancel [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--reason` | `-r` | No | `""` | Reason for cancellation |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
# Cancel with reason
carby-sprint cancel sprint-001 --reason "Requirements changed"

# Cancel without reason
carby-sprint cancel sprint-001
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Sprint already cancelled/archived

---

### `list` — List Sprints

Display all sprints in the output directory.

**Usage:**
```bash
carby-sprint list [OPTIONS]
```

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |
| `--format` | `-f` | No | `table` | Output format: table, json, csv |
| `--status` | `-s` | No | — | Filter by status: initialized, planned, running, paused, completed, cancelled, archived |

**Examples:**

```bash
# List all sprints
carby-sprint list

# List as JSON
carby-sprint list --format json

# Filter by status
carby-sprint list --status running
```

**Sample Output:**
```
============================================================
Sprints
============================================================

ID              Project         Status      Created     Progress
----            -------         ------      -------     --------
sprint-001      my-api          running     2026-03-19  2/4 (50%)
sprint-002      auth-service    completed   2026-03-15  5/5 (100%)
sprint-003      frontend        planned     2026-03-18  0/3 (0%)
```

**Exit Codes:**
- `0` — Success
- `1` — Output directory not found

---

### `verify-logs` — Verify Audit Logs

Verify the integrity of sprint audit logs using cryptographic validation tokens.

**Usage:**
```bash
carby-sprint verify-logs [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier (or `--all` for all sprints) |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--all` | `-a` | No | False | Verify logs for all sprints |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |
| `--verbose` | `-v` | No | False | Show detailed verification output |

**Examples:**

```bash
# Verify logs for a specific sprint
carby-sprint verify-logs sprint-001

# Verify all sprint logs
carby-sprint verify-logs --all

# Verbose output with details
carby-sprint verify-logs sprint-001 --verbose
```

**Sample Output:**
```
============================================================
Audit Log Verification: sprint-001
============================================================

✓ Gate 1 (Planning Gate)    — Token: val-tier1-a1b2c3d4    — Valid
✓ Gate 2 (Design Gate)      — Token: val-tier2-e5f6g7h8    — Valid
✓ Gate 3 (Implementation)   — Token: val-tier3-i9j0k1l2    — Valid
✓ Gate 4 (Validation Gate)  — Token: val-tier4-m3n4o5p6    — Valid
✓ Gate 5 (Release Gate)     — Token: val-tier5-q7r8s9t0    — Valid

Summary:
  Total gates: 5
  Valid: 5
  Invalid: 0
  Missing: 0

✓ All audit logs verified successfully
```

**Exit Codes:**
- `0` — All logs valid
- `1` — Sprint not found
- `2` — One or more logs invalid
- `3` — Missing log entries

---

### `archive` — Archive Sprint

Move completed or cancelled sprint to archive.

**Usage:**
```bash
carby-sprint archive [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |
| `--archive-dir` | `-a` | No | `.carby-sprints/archive` | Archive destination directory |

**Examples:**

```bash
# Archive to default location
carby-sprint archive sprint-001

# Archive to custom location
carby-sprint archive sprint-001 --archive-dir ~/archives
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Archive destination already exists

---

## Work Item Commands

### `work-item add` — Add Work Item

Add a new work item to a sprint.

**Usage:**
```bash
carby-sprint work-item add [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--title` | `-t` | Yes | — | Work item title |
| `--description` | `-d` | No | `""` | Work item description |
| `--priority` | `-p` | No | `medium` | Priority: low, medium, high, critical |
| `--estimated-hours` | `-e` | No | — | Estimated hours |
| `--assignee` | `-a` | No | — | Assigned person |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
# Add simple work item
carby-sprint work-item add sprint-001 --title "Fix bug"

# Add detailed work item
carby-sprint work-item add sprint-001 \
  --title "Implement login" \
  --description "Add OAuth2 login flow" \
  --priority high \
  --estimated-hours 8 \
  --assignee "john.doe"
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found

---

### `work-item update` — Update Work Item

Update an existing work item.

**Usage:**
```bash
carby-sprint work-item update [OPTIONS] SPRINT_ID WORK_ITEM_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |
| `WORK_ITEM_ID` | Yes | Work item identifier (e.g., WI-1) |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--status` | `-s` | No | — | Status: planned, in_progress, completed, blocked, failed |
| `--title` | `-t` | No | — | Update title |
| `--description` | `-d` | No | — | Update description |
| `--priority` | `-p` | No | — | Update priority |
| `--assignee` | `-a` | No | — | Update assignee |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
# Update status
carby-sprint work-item update sprint-001 WI-1 --status in_progress

# Update multiple fields
carby-sprint work-item update sprint-001 WI-2 \
  --status completed \
  --priority high
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Work item not found

---

### `work-item list` — List Work Items

List all work items in a sprint.

**Usage:**
```bash
carby-sprint work-item list [OPTIONS] SPRINT_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--status` | `-s` | No | — | Filter by status |
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
# List all work items
carby-sprint work-item list sprint-001

# Filter by status
carby-sprint work-item list sprint-001 --status in_progress
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found

---

### `work-item show` — Show Work Item

Display detailed information about a work item.

**Usage:**
```bash
carby-sprint work-item show [OPTIONS] SPRINT_ID WORK_ITEM_ID
```

**Arguments:**
| Argument | Required | Description |
|----------|----------|-------------|
| `SPRINT_ID` | Yes | Sprint identifier |
| `WORK_ITEM_ID` | Yes | Work item identifier |

**Options:**
| Option | Short | Required | Default | Description |
|--------|-------|----------|---------|-------------|
| `--output-dir` | `-o` | No | `.carby-sprints` | Directory containing sprint data |

**Examples:**

```bash
carby-sprint work-item show sprint-001 WI-1
```

**Exit Codes:**
- `0` — Success
- `1` — Sprint not found
- `2` — Work item not found

---

## Exit Codes Summary

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Sprint not found |
| `2` | Invalid arguments / requirements not met |
| `3` | Invalid state (already running, already passed, etc.) |
| `4` | Work item not found |
| `5` | Archive/cancellation error |
| `255` | Unexpected error |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CARBY_SPRINT_CONFIG` | Path to default config file | `~/.openclaw/carby-studio.conf` |
| `CARBY_SPRINT_OUTPUT_DIR` | Default output directory | `.carby-sprints` |
| `CARBY_SPRINT_VERBOSE` | Enable verbose mode | `false` |

---

## Configuration File Format

```ini
[defaults]
timeout = 3600
max_parallel = 5
log_level = INFO

[security]
gate_enforcement = strict
audit_logging = enabled

[paths]
output_dir = .carby-sprints
archive_dir = .carby-sprints/archive
```