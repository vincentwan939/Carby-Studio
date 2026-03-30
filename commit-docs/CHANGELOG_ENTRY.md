# Changelog Entry - v3.1.0

## [3.1.0] - 2026-03-21

### New Features

#### Phase Lock - Sequential Phase Execution

A new execution mode that enforces sequential phase execution with explicit user approval between phases.

**Key Capabilities:**
- **Sequential Mode** — Run phases one at a time (Discover → Design → Build → Verify → Deliver)
- **Explicit Approval** — Each phase requires user approval before next phase starts
- **Visual Status Tracking** — Real-time phase status with icons (✓ approved, ⏳ pending, 🔄 in_progress, ○ not_started)
- **File-Based State** — Persistent state survives process restarts
- **Opt-In Design** — Use `--mode sequential` to enable; parallel mode remains default

**New Commands:**
- `carby-sprint start <sprint> --mode sequential` — Start sprint in sequential mode
- `carby-sprint approve <sprint> [phase]` — Approve completed phase and unblock next phase
- `carby-sprint phase-status <sprint>` — Show all phase statuses with summary
- `carby-sprint phase-list <sprint>` — List phases in table/JSON/compact formats

**Use Cases:**
- Complex projects requiring careful review between phases
- High-risk changes where each phase needs validation
- Learning scenarios where you want to understand each phase's output
- Regulatory compliance requiring documented approvals
- Debugging sprint execution issues

### Why This Feature Exists

**The Property Hunter Issue:** During the Property Hunter project, all phase agents spawned simultaneously, causing race conditions, confusion, and difficult debugging. Phase Lock solves this by ensuring each phase completes and is approved before the next begins.

### Breaking Changes

**None.** This release is fully backward compatible with v3.0.0.

- Default execution mode remains `parallel`
- Existing sprints continue to work unchanged
- New sequential mode is opt-in via `--mode sequential`

### Migration Notes

#### For Existing Projects

No migration required. Existing sprints will continue using parallel execution.

#### For New Sequential Sprints

```bash
# 1. Initialize sprint normally
carby-sprint init my-project --project my-api --goal "Build API"

# 2. Plan work items
carby-sprint plan my-project --work-items "Setup,Develop,Test"

# 3. Pass required gates
carby-sprint gate my-project 1
carby-sprint gate my-project 2

# 4. Start in sequential mode (NEW in v3.1.0)
carby-sprint start my-project --mode sequential

# 5. Approve phases as they complete
carby-sprint approve my-project phase_1_discover
carby-sprint start my-project --mode sequential
```

#### Switching from Parallel to Sequential

Sprints cannot change mode after creation. Create a new sprint:

```bash
# Create new sequential sprint
carby-sprint init my-project-v2 \
  --project my-api \
  --goal "Continue with sequential execution"

# Copy work items from old sprint
carby-sprint plan my-project-v2 --work-items "Remaining work"

# Force-pass gates if work already done
carby-sprint gate my-project-v2 1 --force
carby-sprint gate my-project-v2 2 --force

# Start in sequential mode
carby-sprint start my-project-v2 --mode sequential
```

### Technical Details

**New Modules:**
- `carby_sprint/phase_lock.py` — Core Phase Lock state machine
- `carby_sprint/commands/approve.py` — Approve command implementation
- `carby_sprint/commands/phase.py` — Phase management commands

**Modified Modules:**
- `carby_sprint/commands/start.py` — Added `--mode` flag and Phase Lock integration
- `carby_sprint/cli.py` — Registered new commands
- `carby_sprint/commands/__init__.py` — Exported new modules

**Test Coverage:**
- 65+ new test cases
- Phase Lock module tests
- CLI command tests
- Sequential mode integration tests

**Documentation:**
- `docs/PHASE_LOCK.md` — Complete user guide
- `phase_lock_design.md` — Technical design document

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

*For complete documentation, see `docs/PHASE_LOCK.md`*
