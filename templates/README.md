# Template Directory

This directory contains project management templates for **Carby Studio Sprint Framework**.

## Templates

| Template | Purpose | Gate |
|----------|---------|------|
| `requirements.md` | Define what to build | Gate 1: Discover |
| `design.md` | Design how to build it | Gate 2: Design |
| `task.md` | Track implementation | Gate 3+: Build |

## Workflow

```
Gate 1: Discover
  └─→ requirements.md
      • Problem statement
      • User stories
      • Risk assessment

Gate 2: Design
  └─→ design.md
      • Architecture
      • Data models
      • Work items with risk scores

Gate 3+: Build
  └─→ task.md
      • Implementation tasks
      • Code + tests
      • Acceptance criteria
```

## Quick Start

```bash
# Gate 1: Create requirements
cp templates/requirements.md projects/my-project/docs/

# Gate 2: Create design
cp templates/design.md projects/my-project/docs/

# Gate 3: Create task tracking
cp templates/task.md projects/my-project/docs/
```

## See Also

- [PROJECT_FRAMEWORK.md](../PROJECT_FRAMEWORK.md) - Complete workflow guide
- [CONSTITUTION.md](../carby-studio-repo/CONSTITUTION.md) - Core principles
