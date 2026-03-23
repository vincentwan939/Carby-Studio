# Carby Studio

[![Version](https://img.shields.io/badge/version-3.2.2-blue.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/tests-227%2F227%20passing-brightgreen.svg)](TEST_PLAN.md)
[![Security](https://img.shields.io/badge/security-hardened-success.svg)]()
[![Docs](https://img.shields.io/badge/docs-available-green.svg)](docs/)

AI-native software development studio with spec-driven multi-agent workflows.

> ✅ **Production Ready:** Carby Studio v3.2.2 — Security hardened with timing attack fixes, race condition protection, and 93 new tests. Phase Lock, Two-Stage Verify, atomic transactions, distributed locking. [Learn more →](docs/getting-started.md)

## Overview

Carby Studio v3.2.2 orchestrates a 5-stage software development lifecycle using specialized AI agents with enterprise-grade security and reliability. **New in v3.2.2:** Security hardening with timing attack fixes, race condition protection, and 93 new tests. **New in v3.2.1:** Two-Stage Verify for enhanced quality assurance. **New in v3.1.0:** Phase Lock sequential enforcement for controlled phase-by-phase execution with user approval workflow.

### Security & Reliability Features

- 🔒 **Security Hardened** — Timing attack protection, race condition fixes, permission controls *(New in v3.2.2)*
- 🔒 **Two-Stage Verify** — Enhanced verification with pre-check and final validation *(New in v3.2.1)*
- 🔒 **Phase Lock** — Sequential phase enforcement with user approval *(New in v3.1.0)*
- 🔒 **Atomic Transactions** — Thread-safe with rollback capability
- 🔒 **Distributed Locking** — Prevents race conditions
- 🔒 **Server-Side Gates** — HMAC-signed tokens prevent bypass
- 🔒 **Path Validation** — Prevents directory traversal
- 🔒 **Health Monitoring** — Automatic stale lock detection
- 🔒 **Backup Management** — Auto-cleanup prevents disk exhaustion

```
Discover → Design → Build → Verify → Deliver
   ↓         ↓        ↓        ↓        ↓
 options   specs   tasks   review   deploy
   ↓         ↓        ↓        ↓        ↓
   [Parallel Execution]  or  [Sequential (Phase Lock)]
```

**Execution Modes:**
- **Parallel** (default): All agents spawn simultaneously for speed
- **Sequential** (`--mode sequential`): Phases execute one at a time with user approval between each

Each stage validates the previous (maker-checker pattern), ensuring quality and alignment with requirements.

### Agent Dispatch & Parallel Execution

The Sprint Framework automatically dispatches the 5 agents (Discover, Design, Build, Verify, Deliver) when you start a sprint. Work items execute in parallel (up to 5 concurrent) with intelligent orchestration:

```
┌─────────────────────────────────────────┐
│           Sprint Execution              │
├─────────────────────────────────────────┤
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Work    │ │ Work    │ │ Work    │   │
│  │ Item 1  │ │ Item 2  │ │ Item 3  │   │
│  │ (Build) │ │ (Build) │ │ (Verify)│   │
│  └────┬────┘ └────┬────┘ └────┬────┘   │
│       └───────────┴───────────┘         │
│              Agent Dispatch             │
│       ┌─────────┬─────────┐             │
│       ▼         ▼         ▼             │
│    [Build]  [Build]   [Verify]          │
│    Agent    Agent     Agent             │
└─────────────────────────────────────────┘
```

Agents are spawned automatically using OpenClaw's `sessions_spawn` for isolated, secure execution.

## The 5 Agents

| Agent | Purpose | Model | Verifies |
|-------|---------|-------|----------|
| **Discover** | Problem understanding, option generation | Kimi K2.5 | — |
| **Design** | Architecture, API contracts, data models | GLM-5 | Discover |
| **Build** | Implementation to spec | Qwen Coder Plus | Design |
| **Verify** | Testing, review, security checks | Qwen Coder Plus | Build |
| **Deliver** | Deployment, documentation, handoff | Kimi K2.5 | Verify |

## Quick Start

### New: Carby Sprint Framework with Phase Lock (v3.2.1)

The Sprint Framework enables parallel or sequential work item execution with validation gates:

**Sequential Mode (Phase Lock):**
```bash
# 1. Initialize a sprint
carby-sprint init sprint-001 --project my-api --goal "Build REST API"

# 2. Start in sequential mode
carby-sprint start sprint-001 --mode sequential

# 3. Phase completes, approve to continue
carby-sprint approve sprint-001 discover

# 4. Next phase starts automatically
carby-sprint phase-status sprint-001
```

**Parallel Mode (Default):**
```bash

```bash
# 1. Initialize a sprint
carby-sprint init sprint-001 --project my-api --goal "Build REST API"

# 2. Plan work items
carby-sprint plan sprint-001 --work-items "Setup,Develop,Test,Deploy"

# 3. Pass planning gates
carby-sprint gate sprint-001 1
carby-sprint gate sprint-001 2

# 4. Start execution
carby-sprint start sprint-001

# 5. Monitor progress
carby-sprint status sprint-001 --watch
```

[Learn more in the Getting Started Guide →](docs/getting-started.md)

### Classic: Carby Studio Pipeline

The original 5-stage sequential pipeline:

```bash
# 1. Prerequisites Check
carby-studio check-prerequisites

# 2. Create a New Project
carby-studio init my-app -g "Build a REST API for user management"

# 3. Run the Pipeline
carby-studio run my-app
```

See [Migration Guide](docs/migration-guide.md) for differences between approaches.

### 4. Monitor Progress

```bash
# View execution metrics
carby-studio metrics --days 7

# List all projects
carby-studio list
```

## Project Structure

```
my-app/
├── agents/              # Agent prompts (copied from skill)
│   ├── discover.md
│   ├── design.md
│   ├── build.md
│   ├── verify.md
│   └── deliver.md
├── templates/           # Document templates
│   ├── requirements.md
│   └── design.md
├── scripts/             # Utility scripts
│   └── validator.py
├── docs/                # Generated artifacts
│   ├── requirements.md
│   ├── design.md
│   ├── verify-report.md
│   └── delivery-summary.md
├── src/                 # Source code (generated by Build)
├── tests/               # Test files (generated by Build/Verify)
├── deploy/              # Deployment configs
│   ├── Dockerfile
│   └── docker-compose.yml
└── state/               # Pipeline state
    └── tasks.json
```

## CLI Commands

### Project Management

```bash
# Initialize a new project
carby-studio init <project-name> -g "Project goal description"

# Check project status
carby-studio status <project>

# List all projects
carby-studio list

# Get next stage to run
carby-studio next <project>
```

### Stage Management

```bash
# Assign a task to a stage
carby-studio assign <project> <stage> "Task description"

# Update stage status
carby-studio update <project> <stage> done
carby-studio update <project> <stage> in-progress
carby-studio update <project> <stage> failed

# Validate stage output before marking done
carby-studio validate <project> <stage>

# Dispatch agent for a stage
carby-studio dispatch <project> <stage>

# Run complete pipeline interactively
carby-studio run <project>

# Watch for artifacts and auto-advance
carby-studio watch <project>
```

### Recovery Commands

```bash
# Reset a stage to pending
carby-studio reset <project> <stage>

# Skip a stage
carby-studio skip <project> <stage>

# Retry a failed stage
carby-studio retry <project> <stage>
```

### GitHub Integration

```bash
# Create GitHub issue for a stage
carby-studio issue <project> <stage> "Issue title"

# Create feature branch
carby-studio branch <project> <stage>

# Create pull request
carby-studio pr <project> <stage>
```

### Deployment

```bash
# Deploy to configured target
carby-studio deploy <project>
```

## Workflow Modes

### Linear Mode (Default)
Sequential pipeline: Discover → Design → Build → Verify → Deliver

```bash
carby-studio init my-app -g "Build a REST API" --mode linear
```

### DAG Mode
Dependency-based task execution for parallel workstreams.

```bash
carby-studio init my-app -g "Build a REST API" --mode dag
```

### Debate Mode
Multiple agents propose solutions, human selects winner.

```bash
carby-studio init my-app -g "Build a REST API" --mode debate
```

## Golden Path Templates

Carby Studio includes **Golden Path templates** for the Build phase:

| Language | Framework | Features |
|----------|-----------|----------|
| Python | FastAPI | SQLAlchemy 2.0, Pydantic, pytest |
| Node.js | Express | TypeScript, Jest, Docker |
| Go | Gin | Standard layout, structured logging |
| Rust | Axum | Tokio, SQLx, tracing |

Templates provide:
- ✅ Production-ready project structure
- ✅ Working code with health checks
- ✅ Multi-stage Dockerfiles
- ✅ Test examples
- ✅ Documentation (STRUCTURE.md)

[Learn more about templates →](TEMPLATES_README.md)

## Configuration

### Model Assignment

Set models via environment variables:

```bash
export CARBY_MODEL_DISCOVER="bailian/kimi-k2.5"
export CARBY_MODEL_DESIGN="bailian/glm-5"
export CARBY_MODEL_BUILD="bailian/qwen3-coder-plus"
export CARBY_MODEL_VERIFY="bailian/qwen3-coder-plus"
export CARBY_MODEL_DELIVER="bailian/kimi-k2.5"
```

Or edit `scripts/carby-studio` to change defaults.

### Custom Templates

Modify `templates/requirements.md` and `templates/design.md` to match your organization's standards.

### Deployment Targets

Supported targets (set during init or in `.carby-config.json`):

- `local-docker` — Local Docker Compose (default)
- `github-pages` — Static site deployment
- `fly-io` — Fly.io platform
- `custom` — Custom deployment script

## Architecture

### Component Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Workflow Engine | team-tasks (adapted) | Multi-agent orchestration |
| Agent Runtime | OpenClaw `sessions_spawn` | Isolated agent execution |
| CLI Interface | `carby-studio` (bash) | User-facing commands |
| Source of Truth | Local JSON + GitHub | State + code storage |
| Validator | `validator.py` | Output quality checks |

### Handoff Protocol

Each agent produces:

1. **Artifacts** — Files for the next agent
2. **Verification Checklist** — Explicit validation criteria
3. **Escalation Path** — When to involve humans

Example Design→Build handoff:

```yaml
artifacts:
  - design.md
  - api-contracts.yaml
  - data-models.sql
verification_checklist:
  - "All endpoints specified have implementations"
  - "Data models match schema definitions"
  - "Error handling covers all documented cases"
escalation_path: "/discuss if coverage < 80%"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CARBY_WORKSPACE` | `~/.openclaw/workspace/projects` | Project storage directory |
| `CARBY_BACKEND` | `file` | Storage backend: `file` or `sqlite` |
| `CARBY_MODEL_DISCOVER` | `bailian/kimi-k2.5` | Discover agent model |
| `CARBY_MODEL_DESIGN` | `bailian/glm-5` | Design agent model |
| `CARBY_MODEL_BUILD` | `bailian/qwen3-coder-plus` | Build agent model |
| `CARBY_MODEL_VERIFY` | `bailian/qwen3-coder-plus` | Verify agent model |
| `CARBY_MODEL_DELIVER` | `bailian/kimi-k2.5` | Deliver agent model |
| `CARBY_AGENT_TIMEOUT` | `600` | Agent timeout (seconds) |
| `CARBY_DEBUG` | — | Enable verbose output |
| `TEAM_TASKS_DIR` | `~/.openclaw/workspace/projects` | Task storage directory |

## Documentation

### Sprint Framework (New in v2.0)
- **[docs/getting-started.md](docs/getting-started.md)** - Sprint Framework quick start guide
- **[docs/cli-reference.md](docs/cli-reference.md)** - Complete carby-sprint CLI reference (includes `list` and `verify-logs` commands)
- **[docs/migration-guide.md](docs/migration-guide.md)** - Migrating from carby-studio to carby-sprint

### Classic Pipeline
- **[TEMPLATES_README.md](TEMPLATES_README.md)** - Golden Path templates guide
- **[docs/PREREQUISITES.md](docs/PREREQUISITES.md)** - Installation requirements
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions

### Project Reports
- **[PHASE1_COMPLETION_REPORT.md](PHASE1_COMPLETION_REPORT.md)** - Phase 1 completion details
- **[PHASE2_COMPLETION_REPORT.md](PHASE2_COMPLETION_REPORT.md)** - Phase 2 completion details
- **[PHASE3_COMPLETION_REPORT.md](PHASE3_COMPLETION_REPORT.md)** - Phase 3 completion details
- **[FINAL_EVALUATION_REPORT.md](FINAL_EVALUATION_REPORT.md)** - Final evaluation

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for common issues and solutions.

Quick fixes:

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

## Development

### Project Structure

```
Carby-Studio/
├── agents/           # 5 SDLC agent prompts
├── templates/        # requirements.md, design.md
├── scripts/          # carby-studio CLI, validator.py
├── team-tasks/       # Forked workflow engine
├── README.md         # This file
├── SKILL.md          # OpenClaw skill definition
└── TROUBLESHOOTING.md # Common issues & fixes
```

### Adding New Agents

1. Create `agents/{name}.md`
2. Follow the prompt structure in existing agents
3. Update `CARBY_PIPELINE` in `scripts/carby-studio` if needed

## License

MIT

## Credits

- Workflow engine adapted from [team-tasks](https://github.com/win4r/team-tasks)
- Architecture inspired by Microsoft Azure AI-led SDLC, GitHub Spec Kit, and AWS AI-Driven SDLC patterns
ven SDLC patterns
ven SDLC patterns
d by Microsoft Azure AI-led SDLC, GitHub Spec Kit, and AWS AI-Driven SDLC patterns
ven SDLC patterns
ven SDLC patterns
y Microsoft Azure AI-led SDLC, GitHub Spec Kit, and AWS AI-Driven SDLC patterns
ven SDLC patterns
ven SDLC patterns
