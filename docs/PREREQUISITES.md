# Carby Studio Prerequisites

This document lists all required and optional dependencies for Carby Studio.

## Quick Check

Run the prerequisites check script:

```bash
carby-studio check-prerequisites
```

Or manually:

```bash
./scripts/check-prerequisites.sh
```

---

## Required Dependencies

These must be installed for Carby Studio to function.

### Python 3.11+

**Purpose:** Core runtime for task manager and scripts

**Check:**
```bash
python3 --version  # Should be 3.11 or higher
```

**Install:**

macOS (Homebrew):
```bash
brew install python@3.11
```

macOS (if you have Python 3.12):
```bash
# Already installed at /opt/homebrew/bin/python3.12
# The check script will auto-detect it
```

Ubuntu/Debian:
```bash
sudo apt update
sudo apt install python3.11 python3.11-pip
```

### fcntl Module (Unix-only)

**Purpose:** File locking for concurrent access protection

**Check:**
```bash
python3 -c "import fcntl; print('OK')"
```

**Note:** The `fcntl` module is built into Python on Unix-like systems (macOS, Linux). Windows is not supported.

### OpenClaw CLI

**Purpose:** Agent runtime and session management

**Check:**
```bash
openclaw --version
```

**Install:**
```bash
# See https://docs.openclaw.ai/installation
npm install -g openclaw
```

### Git

**Purpose:** Version control for projects

**Check:**
```bash
git --version
```

**Install:**
```bash
# macOS
brew install git

# Ubuntu/Debian
sudo apt install git
```

---

## Optional Dependencies

These enable additional features but are not required for basic operation.

### GitHub CLI (gh)

**Purpose:** Create issues, branches, and pull requests

**Features enabled:**
- `carby-studio issue <project> <stage> <title>`
- `carby-studio branch <project> <stage>`
- `carby-studio pr <project> <stage>`

**Check:**
```bash
gh --version
gh auth status
```

**Install:**
```bash
# macOS
brew install gh

# Ubuntu/Debian
sudo apt install gh

# Or download from https://cli.github.com/
```

**Authenticate:**
```bash
gh auth login
```

### Docker

**Purpose:** Local deployment of containerized applications

**Features enabled:**
- `carby-studio deploy <project>` (for local-docker target)
- Docker Compose support

**Check:**
```bash
docker --version
docker info  # Must show "Server" section (daemon running)
```

**Install:**

macOS:
- Install Docker Desktop: https://docs.docker.com/desktop/mac/install/

Ubuntu/Debian:
```bash
sudo apt install docker.io docker-compose
sudo systemctl enable --now docker
sudo usermod -aG docker $USER  # Log out and back in
```

### Fly.io CLI (flyctl)

**Purpose:** Deploy to Fly.io platform

**Features enabled:**
- `carby-studio deploy <project>` (for fly-io target)

**Check:**
```bash
flyctl version
```

**Install:**
```bash
curl -L https://fly.io/install.sh | sh
```

**Add to PATH:**
```bash
export PATH="$HOME/.fly/bin:$PATH"
```

**Authenticate:**
```bash
flyctl auth login
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CARBY_WORKSPACE` | `~/.openclaw/workspace/projects` | Where projects are stored |
| `CARBY_MODEL_DISCOVER` | `bailian/kimi-k2.5` | Model for Discover agent |
| `CARBY_MODEL_DESIGN` | `bailian/glm-5` | Model for Design agent |
| `CARBY_MODEL_BUILD` | `bailian/qwen3-coder-plus` | Model for Build agent |
| `CARBY_MODEL_VERIFY` | `bailian/qwen3-coder-plus` | Model for Verify agent |
| `CARBY_MODEL_DELIVER` | `bailian/kimi-k2.5` | Model for Deliver agent |
| `CARBY_AGENT_TIMEOUT` | `600` | Agent timeout in seconds |

**Example `.zshrc` or `.bashrc`:**

```bash
# Carby Studio Configuration
export CARBY_WORKSPACE="$HOME/.openclaw/workspace/projects"
export CARBY_MODEL_BUILD="bailian/qwen3-coder-plus"
export CARBY_AGENT_TIMEOUT="900"  # 15 minutes
```

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS (Apple Silicon) | ✅ Fully supported | Primary development platform |
| macOS (Intel) | ✅ Supported | Same as Apple Silicon |
| Linux (x86_64) | ✅ Supported | Tested on Ubuntu 22.04 |
| Linux (ARM64) | ⚠️ Should work | Not explicitly tested |
| Windows | ❌ Not supported | fcntl module unavailable |
| WSL2 | ⚠️ May work | Not tested |

---

## Troubleshooting

### "Python 3.11+ not found" but I have Python 3.12

The check script auto-detects Python in common locations. If it fails:

```bash
# Find your Python 3.12
which python3.12

# Create an alias
alias python3="/opt/homebrew/bin/python3.12"

# Or update PATH
export PATH="/opt/homebrew/bin:$PATH"
```

### "fcntl module not available"

This means you're on Windows or a non-Unix system. Carby Studio requires:
- macOS
- Linux
- WSL2 (untested)

### "OpenClaw CLI not found"

Make sure `openclaw` is in your PATH:

```bash
which openclaw

# If not found, add to PATH
export PATH="$HOME/.npm-global/bin:$PATH"
```

### GitHub CLI "not authenticated"

Some features will be unavailable. To authenticate:

```bash
gh auth login
# Follow the prompts to authenticate via browser
```

---

## Verification

After installing dependencies, verify with:

```bash
# Check all prerequisites
./scripts/check-prerequisites.sh

# Run smoke tests
./tests/test_smoke.sh

# Create a test project
carby-studio init test-project -g "Test project"
carby-studio status test-project
```

---

## Getting Help

If you encounter issues:

1. Check the [TROUBLESHOOTING.md](TROUBLESHOOTING.md) guide
2. Run `carby-studio check-prerequisites` for diagnostics
3. Check the logs in `~/.openclaw/workspace/metrics/`
