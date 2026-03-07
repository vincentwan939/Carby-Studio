# Carby Studio Troubleshooting Guide

## Common Issues and Solutions

### Installation & Setup

#### Issue: `carby-studio: command not found`
**Symptoms:** Command not recognized  
**Solution:**
```bash
# Add to PATH or use full path
export PATH="$PATH:$HOME/.openclaw/workspace/carby-studio-repo/scripts"
# Or use full path
~/.openclaw/workspace/carby-studio-repo/scripts/carby-studio
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
carby-studio init my-project --force
# Or delete existing
rm -rf ~/.openclaw/workspace/projects/my-project
rm ~/.openclaw/workspace/projects/my-project.json
```

#### Issue: Interactive prompts hang
**Symptoms:** Init stops at deployment selection  
**Solution:**
```bash
# Use flags to skip prompts
carby-studio init my-project -g "Goal" -d local-docker
```

---

### Validation Failures

#### Issue: `Validation failed for design`
**Symptoms:** Cannot mark design as done  
**Cause:** Template placeholders like `[e.g., Python]` still in design.md  
**Solution:**
```bash
# View errors
carby-studio validate my-project design

# Fix the file, then retry
# Or force if intentional
carby-studio update my-project design done --force
```

#### Issue: `Artifact not found`
**Symptoms:** Cannot mark stage as done  
**Cause:** Required file doesn't exist  
**Solution:**
```bash
# Check what artifact is expected
carby-studio validate my-project <stage>

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
carby-studio dispatch my-project <stage>

# Or retry
carby-studio retry my-project <stage>
```

#### Issue: `Spawn failed`
**Symptoms:** Agent doesn't start  **Solution:**
```bash
# Check OpenClaw status
openclaw status

# Check model availability
openclaw models list | grep <model>

# Retry with different model
CARBY_MODEL_BUILD=bailian/kimi-k2.5 carby-studio dispatch my-project build
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
carby-studio init my-project -d local-docker
```

---

### Stage Recovery

#### Issue: Stage stuck "in-progress"
**Symptoms:** Cannot proceed  
**Solution:**
```bash
# Reset to pending
carby-studio reset my-project <stage>

# Or skip
carby-studio skip my-project <stage>

# Or retry
carby-studio retry my-project <stage>
```

#### Issue: `Cannot mark as done: validation failed`
**Symptoms:** Stage won't complete  
**Solution:**
```bash
# Check what's wrong
carby-studio validate my-project <stage>

# Force if needed (use sparingly)
carby-studio update my-project <stage> done --force
```

---

### Pipeline Issues

#### Issue: `Next: (empty)`
**Symptoms:** No next stage shown  
**Cause:** Pipeline complete or blocked  
**Solution:**
```bash
# Check status
carby-studio status my-project

# Check all stages
carby-studio list
```

#### Issue: Wrong stage order
**Symptoms:** Stages not in expected order  
**Solution:**
```bash
# Pipeline is fixed: discover→design→build→verify→deliver
# Use DAG mode for custom ordering
carby-studio init my-project -m dag
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

---

### Debug Mode

Enable verbose output:
```bash
export CARBY_DEBUG=1
carby-studio <command>
```

---

### Getting Help

1. Check validation: `carby-studio validate <project> <stage>`
2. Check status: `carby-studio status <project>`
3. Check logs: `carby-studio list` then inspect `.json` file
4. Reset and retry: `carby-studio retry <project> <stage>`

---

## Quick Fixes

```bash
# Complete reset
rm -rf ~/.openclaw/workspace/projects/<project>
rm ~/.openclaw/workspace/projects/<project>.json

# Fresh start
carby-studio init <project> -g "Goal"

# Skip problematic stage
carby-studio skip <project> <stage>

# Force stage completion
carby-studio update <project> <stage> done --force
```
