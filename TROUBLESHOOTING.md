# Carby Studio v3.2.1 Troubleshooting Guide

## Common Issues and Solutions

### Installation & Setup

#### Issue: `carby-sprint: command not found`
**Symptoms:** Command not recognized  
**Solution:**
```bash
# Add to PATH or use full path
export PATH="$PATH:$HOME/.openclaw/workspace/carby-studio-repo/scripts"
# Or use full path
~/.openclaw/workspace/carby-studio-repo/scripts/carby-sprint
```

#### Issue: `team-tasks not found`
**Symptoms:** Error about missing team-tasks  
**Solution:**
```bash
cd ~/.openclaw/workspace/carby-studio-repo
git submodule update --init
```

---

### Project Initialization

#### Issue: `Project already exists`
**Symptoms:** Cannot create project with same name  
**Solution:**
```bash
# Use force flag
carby-sprint init my-project --force
# Or delete existing
rm -rf ~/.openclaw/workspace/projects/my-project
rm ~/.openclaw/workspace/projects/my-project.json
```

#### Issue: Interactive prompts hang
**Symptoms:** Init stops at deployment selection  
**Solution:**
```bash
# Use flags to skip prompts
carby-sprint init my-project -g "Goal" -d local-docker
```

---

### Phase Lock Troubleshooting

#### Issue: Phase stuck in "awaiting_approval"
**Symptoms:** Pipeline won't proceed to next phase  
**Cause:** Phase requires manual approval before continuing  
**Solution:**
```bash
# Check current phase status
carby-sprint status my-project

# View pending approvals
carby-sprint phase list --pending

# Approve the phase
carby-sprint phase approve my-project <phase-name>

# Or reject if changes needed
carby-sprint phase reject my-project <phase-name> -r "Reason for rejection"
```

#### Issue: Sequential mode blocking
**Symptoms:** Phases won't run in parallel  
**Cause:** Sequential mode enforces strict phase-by-phase execution  
**Solution:**
```bash
# Check current execution mode
carby-sprint config get my-project execution_mode

# Switch to DAG mode for parallel execution
carby-sprint config set my-project execution_mode dag

# Or force sequential to continue
carby-sprint phase unlock my-project <phase-name> --force
```

---

### TDD Protocol Troubleshooting

#### Issue: Design gate failures
**Symptoms:** Cannot proceed past design validation  
**Cause:** Design document doesn't meet TDD requirements  
**Solution:**
```bash
# Check specific design gate errors
carby-sprint validate my-project design --tdd-check

# Common fixes:
# 1. Ensure test scenarios are defined
# 2. Verify acceptance criteria exist
# 3. Check interface contracts are specified

# View TDD requirements
carby-sprint tdd requirements my-project

# Force bypass (not recommended for production)
carby-sprint update my-project design done --bypass-tdd
```

#### Issue: Test coverage requirements not met
**Symptoms:** Build phase fails with coverage error  
**Cause:** Code coverage below threshold (default: 80%)  
**Solution:**
```bash
# Check current coverage
carby-sprint coverage my-project

# View uncovered files
carby-sprint coverage my-project --uncovered

# Lower threshold for this project (if justified)
carby-sprint config set my-project coverage_threshold 70

# Or skip coverage check (emergency only)
carby-sprint update my-project build done --skip-coverage
```

#### Issue: Validation token issues
**Symptoms:** "Invalid or expired validation token"  
**Cause:** Token expired or not properly issued  
**Solution:**
```bash
# Check token status
carby-sprint token status my-project

# Request new token
carby-sprint token refresh my-project

# For critical phases, re-run full validation
carby-sprint validate my-project <phase> --renew-token

# Check token in config
carby-sprint config get my-project validation_token
```

---

### Two-Stage Verify Troubleshooting

#### Issue: Stage 1 failures (spec compliance)
**Symptoms:** Verify fails at specification check  
**Cause:** Implementation doesn't match design specification  
**Solution:**
```bash
# View detailed spec compliance report
carby-sprint verify my-project --stage 1 --verbose

# Compare implementation vs spec
carby-sprint diff my-project spec implementation

# Common fixes:
# 1. Update implementation to match spec
# 2. Update spec if implementation is correct (requires design phase update)
# 3. Document deviation with justification

# Re-run Stage 1 after fixes
carby-sprint verify my-project --stage 1 --rerun
```

#### Issue: Stage 2 conditional approvals
**Symptoms:** Verify passes with warnings requiring approval  
**Cause:** Non-blocking issues found (performance, style, etc.)  
**Solution:**
```bash
# View conditional approval details
carby-sprint verify my-project --stage 2 --show-conditions

# Approve with conditions
carby-sprint verify approve my-project --conditions "acknowledged"

# Or reject and require fixes
carby-sprint verify reject my-project --stage 2 -r "Fix performance issues"

# List all conditional approvals pending
carby-sprint verify list --pending-approvals
```

#### Issue: How to re-run verification
**Symptoms:** Need to re-verify after fixes  
**Solution:**
```bash
# Re-run full two-stage verification
carby-sprint verify my-project --rerun

# Re-run specific stage only
carby-sprint verify my-project --stage 1 --rerun
carby-sprint verify my-project --stage 2 --rerun

# Force re-verification (bypass cache)
carby-sprint verify my-project --force

# Reset verify phase and start over
carby-sprint reset my-project verify
carby-sprint dispatch my-project verify
```

---

### Validation Failures

#### Issue: `Validation failed for design`
**Symptoms:** Cannot mark design as done  
**Cause:** Template placeholders like `[e.g., Python]` still in design.md  
**Solution:**
```bash
# View errors
carby-sprint validate my-project design

# Fix the file, then retry
# Or force if intentional
carby-sprint update my-project design done --force
```

#### Issue: `Artifact not found`
**Symptoms:** Cannot mark stage as done  
**Cause:** Required file doesn't exist  
**Solution:**
```bash
# Check what artifact is expected
carby-sprint validate my-project <stage>

# Create the artifact or use --force
```

---

### Agent Dispatch

#### Issue: `Agent timed out`
**Symptoms:** Dispatch fails after 10 minutes  
**Solution:**
```bash
# Increase timeout
export CARBY_AGENT_TIMEOUT=1800  # 30 minutes
carby-sprint dispatch my-project <stage>

# Or retry
carby-sprint retry my-project <stage>
```

#### Issue: `Spawn failed`
**Symptoms:** Agent doesn't start  
**Solution:**
```bash
# Check OpenClaw status
openclaw status

# Check model availability
openclaw models list | grep <model>

# Retry with different model
CARBY_MODEL_BUILD=bailian/kimi-k2.5 carby-sprint dispatch my-project build
```

---

### GitHub Integration

#### Issue: `gh: command not found`
**Symptoms:** GitHub commands fail  
**Solution:**
```bash
# Install GitHub CLI
brew install gh  # macOS
# or
apt install gh   # Ubuntu

# Authenticate
gh auth login
```

#### Issue: `could not add label`
**Symptoms:** Issue/PR created without labels  
**Cause:** Labels don't exist in repo  
**Solution:**
```bash
# Create labels in GitHub UI first
# Or ignore - issues still created
```

---

### Deployment

#### Issue: `docker-compose.yml not found`
**Symptoms:** Deploy fails  
**Cause:** Project initialized before deploy configs  
**Solution:**
```bash
# Reinitialize or create manually
mkdir -p deploy
cat > deploy/docker-compose.yml << 'EOF'
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8000:8000"
EOF
```

#### Issue: `flyctl not installed`
**Symptoms:** Fly.io deploy fails  
**Solution:**
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Or use different target
carby-sprint init my-project -d local-docker
```

---

### Stage Recovery

#### Issue: Stage stuck "in-progress"
**Symptoms:** Cannot proceed  
**Solution:**
```bash
# Reset to pending
carby-sprint reset my-project <stage>

# Or skip
carby-sprint skip my-project <stage>

# Or retry
carby-sprint retry my-project <stage>
```

#### Issue: `Cannot mark as done: validation failed`
**Symptoms:** Stage won't complete  
**Solution:**
```bash
# Check what's wrong
carby-sprint validate my-project <stage>

# Force if needed (use sparingly)
carby-sprint update my-project <stage> done --force
```

---

### Pipeline Issues

#### Issue: `Next: (empty)`
**Symptoms:** No next stage shown  
**Cause:** Pipeline complete or blocked  
**Solution:**
```bash
# Check status
carby-sprint status my-project

# Check all stages
carby-sprint list
```

#### Issue: Wrong stage order
**Symptoms:** Stages not in expected order  
**Solution:**
```bash
# Pipeline is fixed: discover→design→build→verify→deliver
# Use DAG mode for custom ordering
carby-sprint init my-project -m dag
```

---

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CARBY_WORKSPACE` | `~/.openclaw/workspace/projects` | Project storage |
| `CARBY_AGENT_TIMEOUT` | `600` | Agent timeout (seconds) |
| `CARBY_MODEL_DISCOVER` | `bailian/kimi-k2.5` | Discover model |
| `CARBY_MODEL_DESIGN` | `bailian/glm-5` | Design model |
| `CARBY_MODEL_BUILD` | `bailian/qwen3-coder-next` | Build model |
| `CARBY_MODEL_VERIFY` | `openrouter/anthropic/claude-opus-4.6` | Verify model |
| `CARBY_MODEL_DELIVER` | `bailian/kimi-k2.5` | Deliver model |
| `CARBY_PHASE_LOCK` | `true` | Enable phase locking |
| `CARBY_TDD_ENABLED` | `true` | Enable TDD protocol |
| `CARBY_VERIFY_STAGES` | `2` | Two-stage verification |

---

### Debug Mode

Enable verbose output:
```bash
export CARBY_DEBUG=1
carby-sprint <command>
```

---

### Getting Help

1. Check validation: `carby-sprint validate <project> <stage>`
2. Check status: `carby-sprint status <project>`
3. Check logs: `carby-sprint list` then inspect `.json` file
4. Reset and retry: `carby-sprint retry <project> <stage>`

---

## Quick Fixes

```bash
# Complete reset
rm -rf ~/.openclaw/workspace/projects/<project>
rm ~/.openclaw/workspace/projects/<project>.json

# Fresh start
carby-sprint init <project> -g "Goal"

# Skip problematic stage
carby-sprint skip <project> <stage>

# Force stage completion
carby-sprint update <project> <stage> done --force

# Unlock all phases
carby-sprint phase unlock-all <project>

# Re-run verification
carby-sprint verify <project> --rerun
```