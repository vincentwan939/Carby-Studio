# Carby Studio

AI-native software development studio with spec-driven multi-agent workflows.

## Overview

Carby Studio orchestrates a 5-stage software development lifecycle using specialized AI agents:

```
Discover → Design → Build → Verify → Deliver
   ↓         ↓        ↓        ↓        ↓
 options   specs   tasks   review   deploy
```

Each stage validates the previous (maker-checker pattern), ensuring quality and alignment with requirements.

## The 5 Agents

| Agent | Purpose | Model | Verifies |
|-------|---------|-------|----------|
| **Discover** | Problem understanding, option generation | Kimi K2.5 | — |
| **Design** | Architecture, API contracts, data models | GLM-5 | Discover |
| **Build** | Implementation to spec | Qwen Coder | Design |
| **Verify** | Testing, review, security checks | Claude Opus | Build |
| **Deliver** | Deployment, documentation, handoff | Kimi K2.5 | Verify |

## Quick Start

### 1. Install the Skill

```bash
# Clone the skill into your OpenClaw workspace
git clone https://github.com/vincentwan939/Carby-Studio.git ~/.openclaw/workspace/skills/carby-studio
```

### 2. Create a New Project

```bash
cd ~/.openclaw/workspace
mkdir -p projects/my-app
cd projects/my-app

# Initialize task manager
python ../../skills/carby-studio/scripts/task_manager.py init --mode linear
```

### 3. Start the Pipeline

```bash
# Run discover agent
python ../../skills/carby-studio/scripts/carby-bridge.py --stage discover
```

Or use watch mode to auto-advance:

```bash
python ../../skills/carby-studio/scripts/carby-bridge.py --watch
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
│   ├── task_manager.py
│   └── carby-bridge.py
├── docs/                # Generated artifacts
│   ├── requirements.md
│   ├── design.md
│   ├── verify-report.md
│   └── delivery-summary.md
├── tasks/               # Task tracking
│   └── build-tasks.json
└── state/               # Pipeline state
    └── tasks.json
```

## Workflow Modes

### Linear Mode (Default)
Sequential pipeline: Discover → Design → Build → Verify → Deliver

```bash
python task_manager.py init --mode linear
```

### DAG Mode
Dependency-based task execution for parallel workstreams.

```bash
python task_manager.py init --mode dag
python task_manager.py add "Task A"
python task_manager.py add "Task B" --deps TASK-001
```

### Debate Mode
Multiple agents propose solutions, human selects winner.

## Task Manager Commands

```bash
# Initialize project
python task_manager.py init --mode linear

# Add tasks
python task_manager.py add "Implement API" --description "Create REST endpoints"

# Create GitHub issues
python task_manager.py issue TASK-001 --repo owner/repo

# Create feature branches
python task_manager.py branch TASK-001 --repo owner/repo

# Update status
python task_manager.py update TASK-001 in-progress

# Show status
python task_manager.py status

# Get next task (linear mode)
python task_manager.py next

# Get ready tasks (dag mode)
python task_manager.py ready
```

## Bridge Commands

```bash
# Show pipeline status
python carby-bridge.py --status

# Run current stage
python carby-bridge.py

# Run specific stage
python carby-bridge.py --stage design

# Watch mode (auto-advance)
python carby-bridge.py --watch
```

## GitHub Integration

Carby Studio uses GitHub as the source of truth:

- **Issues** track implementation tasks
- **Branches** isolate feature work
- **Pull Requests** enable human review
- **Releases** mark delivery milestones

Configure GitHub CLI:

```bash
gh auth login
gh repo create my-app --public
```

## Architecture

### Component Stack

| Layer | Technology |
|-------|-----------|
| Workflow Engine | team-tasks (adapted) |
| Agent Runtime | OpenClaw `sessions_spawn` |
| Source of Truth | GitHub |
| UI Layer | Mission Control (optional) |
| Bridge | carby-bridge.py |
| Task Manager | task_manager.py |

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

## Configuration

### Model Assignment

Edit agent prompts to change models:

```markdown
## Model Configuration
- **Model**: bailian/glm-5
- **Thinking**: on
```

### Custom Templates

Modify `templates/requirements.md` and `templates/design.md` to match your organization's standards.

## Development

### Running Tests

```bash
cd ~/.openclaw/workspace/skills/carby-studio
python -m pytest tests/
```

### Adding New Agents

1. Create `agents/{name}.md`
2. Follow the prompt structure in existing agents
3. Update `carby-bridge.py` STAGES list

## License

MIT

## Credits

- Workflow engine adapted from [team-tasks](https://github.com/win4r/team-tasks)
- Architecture inspired by Microsoft Azure AI-led SDLC, GitHub Spec Kit, and AWS AI-Driven SDLC patterns
