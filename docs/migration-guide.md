# Migration Guide: From carby-studio to Carby Sprint

This guide helps users migrate from the legacy `carby-studio` CLI to the new `carby-sprint` framework.

---

## What's Changed

### Architecture Changes

| Aspect | Old (carby-studio) | New (carby-sprint) |
|--------|-------------------|-------------------|
| **Execution Model** | Sequential pipeline | Parallel work items |
| **Validation** | Manual stage updates | Automated gate system |
| **State Management** | File-based JSON | Atomic persistence with recovery |
| **Work Tracking** | Stage-based | Work item-based |
| **Risk Assessment** | None | Built-in risk scoring |
| **Audit Trail** | Limited | Comprehensive logging |

### Command Mapping

| Old Command | New Command | Notes |
|-------------|-------------|-------|
| `carby-studio init` | `carby-sprint init` | Similar, but adds gates automatically |
| `carby-studio assign` | `carby-sprint work-item add` | Work items replace stage assignments |
| `carby-studio update <stage> done` | `carby-sprint gate <sprint> <N>` | Gates replace stage updates |
| `carby-studio status` | `carby-sprint status` | Enhanced output with work items |
| `carby-studio list` | `carby-sprint status` (per sprint) | No global list, use per-sprint status |
| `carby-studio dispatch` | Built into `start` | Automatic agent dispatch |
| `carby-studio run` | `carby-sprint start` | Similar functionality |
| `carby-studio watch` | `carby-sprint status --watch` | Watch mode in status command |
| `carby-studio reset` | `carby-sprint gate --force` | Force flag bypasses validation |
| `carby-studio skip` | `carby-sprint gate --force` | Force to skip validation |
| `carby-studio retry` | Manual work-item update | Update work item status |
| `carby-studio issue` | Not yet implemented | Use `gh issue create` directly |
| `carby-studio branch` | Not yet implemented | Use `git checkout -b` directly |
| `carby-studio pr` | Not yet implemented | Use `gh pr create` directly |
| `carby-studio deploy` | Gate 5 (Release Gate) | Deployment validation at final gate |

---

## Step-by-Step Migration

### Step 1: Backup Existing Projects

Before migrating, backup your existing Carby Studio projects:

```bash
# Backup existing projects
cp -r ~/.openclaw/workspace/projects ~/carby-studio-backup-$(date +%Y%m%d)

# Backup carby-studio configuration
cp ~/.openclaw/carby-studio.conf ~/carby-studio-backup-$(date +%Y%m%d)/ 2>/dev/null || true
```

### Step 2: Install Carby Sprint

```bash
# Navigate to skill directory
cd ~/.openclaw/workspace/skills/carby-studio

# Install carby-sprint
pip install -e .

# Verify installation
carby-sprint --version
```

### Step 3: Update Shell Configuration

Replace old carby-studio PATH with carby-sprint:

```bash
# Remove old carby-studio from PATH (if in .zshrc)
# Edit ~/.zshrc and remove or comment out old entries

# Add new PATH if needed
echo 'export PATH="$HOME/.openclaw/workspace/skills/carby-studio:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Step 4: Migrate Existing Projects

Existing projects can continue using the old `carby-studio` commands, but new projects should use `carby-sprint`.

**Option A: Keep Old Projects As-Is**
- Old projects continue to work with `carby-studio` commands
- No migration needed
- Gradual transition as projects complete

**Option B: Migrate Active Projects to Sprints**

For active projects you want to migrate:

```bash
# 1. Create a new sprint for the project
carby-sprint init migrated-api \
  --project existing-api \
  --goal "Continue development from carby-studio"

# 2. Plan work items based on remaining stages
carby-sprint plan migrated-api \
  --work-items "Complete Build stage,Run Verify stage,Execute Deliver stage"

# 3. Pass initial gates (acknowledging existing progress)
carby-sprint gate migrated-api 1 --force
carby-sprint gate migrated-api 2 --force

# 4. Start the sprint
carby-sprint start migrated-api
```

### Step 5: Update Scripts and Automation

Update any scripts that use `carby-studio` commands:

```bash
# Old script
carby-studio init my-project -g "Build API"
carby-studio assign my-project build "Implement feature"
carby-studio update my-project build done

# New script
carby-sprint init my-sprint --project my-project --goal "Build API"
carby-sprint plan my-sprint --work-items "Implement feature"
carby-sprint gate my-sprint 1
carby-sprint gate my-sprint 2
carby-sprint start my-sprint
```

### Step 6: Update Documentation

Update internal documentation to reference new commands:

| Old | New |
|-----|-----|
| `carby-studio init <project>` | `carby-sprint init <sprint> --project <name> --goal "..."` |
| `carby-studio status <project>` | `carby-sprint status <sprint>` |
| Stage completion | Gate passing with `carby-sprint gate <sprint> <1-5>` |

---

## Breaking Changes

### 1. Project Structure

**Old Structure:**
```
my-project/
├── agents/
├── templates/
├── scripts/
├── docs/
├── src/
├── tests/
├── deploy/
└── state/
    └── tasks.json
```

**New Structure:**
```
.carby-sprints/
└── sprint-001/
    ├── metadata.json
    ├── work_items/
    │   ├── WI-1.json
    │   └── WI-2.json
    ├── gates/
    │   ├── gate_1.json
    │   └── gate_2.json
    └── logs/
```

**Impact:** Sprint data is now centralized in `.carby-sprints/` rather than per-project.

### 2. Command Syntax

**Old:**
```bash
carby-studio init my-project -g "Build API"
carby-studio assign my-project build "Task"
carby-studio update my-project build done
```

**New:**
```bash
carby-sprint init sprint-001 --project my-project --goal "Build API"
carby-sprint plan sprint-001 --work-items "Task"
carby-sprint gate sprint-001 2
```

**Impact:** Commands are more explicit with required flags.

### 3. Stage vs Gates

**Old:** 5 stages (Discover, Design, Build, Verify, Deliver) with manual updates
**New:** 5 gates (Planning, Design, Implementation, Validation, Release) with validation

**Impact:** Gates enforce validation; cannot skip without `--force`.

### 4. Work Items vs Stage Assignments

**Old:** Tasks assigned to stages
**New:** Work items tracked independently with status

**Impact:** More granular tracking, parallel execution support.

### 5. Configuration

**Old:** Environment variables only
**New:** Config file + environment variables

**Impact:** New optional config file at `~/.openclaw/carby-studio.conf`.

---

## Feature Comparison Table

| Feature | Old carby-studio | New carby-sprint | Notes |
|---------|-----------------|------------------|-------|
| **Project Initialization** | ✅ | ✅ | Enhanced with gates |
| **Stage/Gate Management** | ✅ Manual | ✅ Automated | Gates with validation |
| **Work Item Tracking** | ❌ | ✅ | New feature |
| **Parallel Execution** | ❌ | ✅ | Up to 5 concurrent |
| **Risk Scoring** | ❌ | ✅ | Automatic assessment |
| **Validation Tokens** | ❌ | ✅ | Cryptographic proof |
| **Audit Logging** | ❌ | ✅ | Tamper-proof logs |
| **Pause/Resume** | ❌ | ✅ | New control commands |
| **Archive** | ❌ | ✅ | Built-in archival |
| **GitHub Integration** | ✅ | ⚠️ Partial | Direct `gh` CLI use |
| **Metrics Dashboard** | ✅ | ⚠️ Partial | Use `status` command |
| **Agent Dispatch** | ✅ | ✅ | Integrated into start |
| **Templates** | ✅ | ✅ | Same templates |
| **Multi-language Support** | ✅ | ✅ | Same support |
| **Docker Deployment** | ✅ | ✅ | Via Release Gate |

**Legend:**
- ✅ Fully supported
- ⚠️ Partially supported / Changed
- ❌ Not supported

---

## Migration Checklist

Use this checklist when migrating:

### Pre-Migration
- [ ] Backup existing projects
- [ ] Document current active projects
- [ ] Note custom configurations
- [ ] Identify automation scripts

### Installation
- [ ] Install carby-sprint
- [ ] Verify `carby-sprint --version` works
- [ ] Update shell PATH if needed

### Project Migration
- [ ] Decide on migration strategy (keep old vs migrate)
- [ ] Create new sprints for active projects (if migrating)
- [ ] Pass initial gates with `--force` for existing progress
- [ ] Archive completed old projects

### Script Updates
- [ ] Update CI/CD pipelines
- [ ] Update local automation scripts
- [ ] Update team documentation
- [ ] Test all scripts

### Post-Migration
- [ ] Verify all active projects work
- [ ] Train team on new commands
- [ ] Update runbooks and playbooks
- [ ] Monitor for issues

---

## Frequently Asked Questions

### Q: Can I use both carby-studio and carby-sprint together?

**A:** Yes, they can coexist. Old projects continue using `carby-studio`, new projects use `carby-sprint`. However, we recommend migrating to `carby-sprint` for new work.

### Q: Do I need to migrate existing projects?

**A:** No. Existing projects can continue using `carby-studio`. Only migrate if you want the new features (parallel execution, gates, risk scoring).

### Q: What happens to my existing project data?

**A:** Existing project data in `~/.openclaw/workspace/projects/` is preserved. `carby-sprint` uses a separate `.carby-sprints/` directory.

### Q: Are the 5 stages the same as the 5 gates?

**A:** Similar but not identical:
- **Old:** Discover → Design → Build → Verify → Deliver
- **New:** Planning Gate → Design Gate → Implementation Gate → Validation Gate → Release Gate

The new gates include validation and risk assessment.

### Q: Can I still use the 5-agent pipeline?

**A:** Yes! The 5 agents (Discover, Design, Build, Verify, Deliver) are still used within the sprint framework. They're dispatched automatically when you `start` a sprint.

### Q: What about GitHub integration?

**A:** Direct `carby-studio issue/branch/pr` commands are not yet in `carby-sprint`. Use the `gh` CLI directly:

```bash
# Old
carby-studio issue my-project build "Fix bug"

# New
gh issue create --title "Fix bug" --label "sprint-001"
```

### Q: How do I track the same project across multiple sprints?

**A:** Use the same `--project` name with different sprint IDs:

```bash
carby-sprint init sprint-001 --project my-api --goal "Phase 1"
carby-sprint init sprint-002 --project my-api --goal "Phase 2"
```

### Q: Is there a GUI or web interface?

**A:** Not yet. Use `carby-sprint status --watch` for live monitoring. A web dashboard is planned for v2.1.0.

---

## Troubleshooting Migration Issues

### "carby-sprint command not found" after installation

```bash
# Check if installed
which carby-sprint

# If not found, check PATH
echo $PATH | grep carby-studio

# Add to PATH
export PATH="$HOME/.openclaw/workspace/skills/carby-studio:$PATH"
```

### Old projects not working

```bash
# Old projects still use carby-studio
# Use the old command
~/.openclaw/workspace/skills/carby-studio/scripts/carby-studio status my-project
```

### Conflicting commands

If you have both `carby-studio` and `carby-sprint` in PATH:

```bash
# Use full path to avoid conflicts
~/.openclaw/workspace/skills/carby-studio/carby-sprint --version
```

---

## Getting Help

- **[Getting Started Guide](getting-started.md)** — New user tutorial
- **[CLI Reference](cli-reference.md)** — Complete command documentation
- **[TROUBLESHOOTING.md](../TROUBLESHOOTING.md)** — General troubleshooting
- **GitHub Issues:** https://github.com/vincentwan939/Carby-Studio/issues

---

*Last updated: 2026-03-19*