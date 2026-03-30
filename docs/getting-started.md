# Getting Started with Carby Studio

Welcome to Carby Studio — an AI-native software development framework with sequential phase enforcement.

## Installation

```bash
# Clone the repository
git clone https://github.com/vincentwan939/Carby-Studio.git
cd Carby-Studio

# Install dependencies
pip install -e .

# Verify installation
carby-sprint doctor
```

## Quick Start

### 1. Initialize a Sprint

```bash
carby-sprint init my-project --goal "Build a REST API for user management"
```

This creates a new sprint with:
- Sprint configuration in `.carby-sprints/my-project/`
- Initial state: `initialized`

### 2. Start the Sprint

```bash
# Start with sequential phase enforcement (default)
carby-sprint start my-project

# Or explicitly use sequential mode
carby-sprint start my-project --mode sequential

# Use parallel mode for concurrent execution (legacy behavior)
carby-sprint start my-project --mode parallel
```

### 3. Monitor Progress

```bash
# Check sprint status
carby-sprint status my-project

# Check phase status
carby-sprint phase-status my-project
```

### 4. Approve Phases

With sequential mode (default), each phase requires explicit approval:

```bash
# After discover phase completes, approve it:
carby-sprint approve my-project discover

# Then the design phase can start
carby-sprint start my-project

# After design completes, approve it:
carby-sprint approve my-project design

# Continue through all phases...
```

## Phase Sequence

Carby Studio enforces this phase order:

```
discover → design → build → verify → deliver
```

| Phase | Purpose | Agent |
|-------|---------|-------|
| **discover** | Requirements gathering and analysis | Discover Agent |
| **design** | Architecture and technical design | Design Agent |
| **build** | Implementation and coding | Build Agent |
| **verify** | Testing and quality assurance | Verify Agent |
| **deliver** | Deployment and handoff | Deliver Agent |

## Phase States

Each phase progresses through these states:

```
pending → in_progress → awaiting_approval → approved
```

- **pending**: Phase not yet started
- **in_progress**: Phase currently running
- **awaiting_approval**: Phase complete, waiting for user approval
- **approved**: Phase approved, next phase can proceed

## Troubleshooting

### Phase Enforcement

By default, Carby Studio now enforces sequential phases:
```
discover → design → build → verify → deliver
```

Each phase requires explicit approval:

```bash
$ carby-sprint start my-project
# Discover phase runs...
# Phase complete, awaiting approval

$ carby-sprint approve my-project discover
# Design phase can now start
```

### "Phase blocked awaiting approval" Error

If you see:
```
PhaseBlockedError: Previous phase 'discover' complete, awaiting approval
Resolution: Run: carby-sprint approve my-project discover
```

**Solution**: Approve the previous phase:
```bash
carby-sprint approve my-project discover
```

### Phase Won't Start

Check phase status to see which phases are approved:
```bash
carby-sprint phase-status my-project
```

All previous phases must be `approved` (not just `completed`) before the next phase can start.

### Sprint Commands

| Command | Description |
|---------|-------------|
| `carby-sprint init <name> --goal "..."` | Initialize new sprint |
| `carby-sprint start <name>` | Start/resume sprint (sequential mode default) |
| `carby-sprint start <name> --mode sequential` | Start with sequential phases |
| `carby-sprint start <name> --mode parallel` | Start with parallel phases (legacy) |
| `carby-sprint status <name>` | Check sprint status |
| `carby-sprint phase-status <name>` | Check phase lock status |
| `carby-sprint approve <name> <phase>` | Approve a completed phase |
| `carby-sprint pause <name>` | Pause sprint |
| `carby-sprint resume <name>` | Resume paused sprint |
| `carby-sprint cancel <name>` | Cancel sprint |
| `carby-sprint archive <name>` | Archive completed sprint |
| `carby-sprint doctor` | Diagnose setup issues |

## Migration from v3.0.x

If upgrading from Carby Studio v3.0.x or earlier:

1. **Default mode changed**: `parallel` → `sequential`
   - Old: Phases ran concurrently
   - New: Phases run sequentially with approval gates

2. **Approval required**: You must now approve each phase before the next begins:
   ```bash
   carby-sprint approve my-project discover
   carby-sprint approve my-project design
   # etc.
   ```

3. **Legacy behavior**: To retain parallel execution (not recommended):
   ```bash
   carby-sprint start my-project --mode parallel
   ```

4. **PhaseLock API changes**:
   - Old: `PhaseLock(output_dir, sprint_id)`
   - New: `PhaseLock(output_dir)` — sprint_id now passed to methods

## Next Steps

- Read the [Phase Lock Documentation](PHASE_LOCK.md) for detailed API reference
- Check [TROUBLESHOOTING.md](../TROUBLESHOOTING.md) for common issues
- Review [API Reference](api.md) for Python API documentation

---
*Carby Studio v3.2.1 — Sequential phase enforcement with human approval*
