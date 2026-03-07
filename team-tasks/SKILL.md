---
name: team-tasks
description: "Coordinate multi-agent development pipelines using shared JSON task files. Use when dispatching work across dev team agents (code-agent, test-agent, docs-agent, monitor-bot), tracking pipeline progress, or running sequential/parallel workflows. Covers project init, task assignment, status tracking, agent dispatch via sessions_send, and result collection. Supports two modes: linear (sequential pipeline) and dag (dependency graph with parallel execution)."
---

# Team Tasks — Multi-Agent Pipeline Coordination

## Overview

Coordinate dev team agents through shared JSON task files + AGI dispatch.
AGI is the command center — agents never talk to each other directly.

**Two modes:**
- **Mode A (linear):** Fixed pipeline order `code → test → docs → monitor`
- **Mode B (dag):** Tasks declare dependencies, parallel dispatch when deps are met

## Task Manager CLI

All commands use: `python3 <skill-dir>/scripts/task_manager.py <command> [args]`

Where `<skill-dir>` is the directory containing this SKILL.md.

### Quick Reference

| Command | Mode | Usage | Description |
|---------|------|-------|-------------|
| `init` | both | `init <project> -g "goal" [-m linear\|dag]` | Create project |
| `add` | dag | `add <project> <task-id> -a <agent> -d <deps>` | Add task with deps |
| `status` | both | `status <project> [--json]` | Show progress |
| `assign` | both | `assign <project> <task> "desc"` | Set task description |
| `update` | both | `update <project> <task> <status>` | Change status |
| `next` | linear | `next <project> [--json]` | Get next stage |
| `ready` | dag | `ready <project> [--json]` | Get all dispatchable tasks |
| `graph` | dag | `graph <project>` | Show dependency tree |
| `log` | both | `log <project> <task> "msg"` | Add log entry |
| `result` | both | `result <project> <task> "output"` | Save output |
| `reset` | both | `reset <project> [task] [--all]` | Reset to pending |
| `list` | both | `list` | List all projects |

### Status Values

- `pending` — waiting for dispatch
- `in-progress` — agent is working
- `done` — stage completed
- `failed` — stage failed (pipeline blocks)
- `skipped` — intentionally skipped

## Pipeline Workflow (Mode A: Linear)

### Step 1: Initialize Project

```bash
python3 scripts/task_manager.py init my-project \
  -g "Build a REST API with tests and docs" \
  -p "code-agent,test-agent,docs-agent,monitor-bot"
```

Default pipeline order: `code-agent → test-agent → docs-agent → monitor-bot`

### Step 2: Assign Tasks to All Stages

```bash
python3 scripts/task_manager.py assign my-project code-agent "Implement REST API with Flask: GET/POST/DELETE /items"
python3 scripts/task_manager.py assign my-project test-agent "Write pytest tests for all endpoints, target 90%+ coverage"
python3 scripts/task_manager.py assign my-project docs-agent "Write README.md with API docs, setup guide, examples"
python3 scripts/task_manager.py assign my-project monitor-bot "Verify code quality, check for security issues, validate deployment readiness"
```

### Step 3: Dispatch Agents Sequentially

For each stage, AGI follows this loop:

```
1. Check next stage:   task_manager.py next <project> --json
2. Mark in-progress:   task_manager.py update <project> <agent> in-progress
3. Dispatch agent:     sessions_spawn(runtime="subagent", mode="run", task=<task>)
4. Wait for completion (subagent auto-announces when done)
5. Save result:        task_manager.py result <project> <agent> "<summary>"
6. Mark done:          task_manager.py update <project> <agent> done
7. Repeat from 1       (currentStage auto-advances)
```

**Note**: We use `sessions_spawn` with `mode: "run"` instead of `sessions_send` because persistent subagent sessions require thread binding support that is not available in most channel configurations.

### Step 4: Handle Failures

If an agent fails:
```bash
python3 scripts/task_manager.py update my-project code-agent failed
python3 scripts/task_manager.py log my-project code-agent "Failed: syntax error in main.py"
```

To retry:
```bash
python3 scripts/task_manager.py reset my-project code-agent
python3 scripts/task_manager.py update my-project code-agent in-progress
# Re-dispatch...
```

### Step 5: Check Progress Anytime

```bash
python3 scripts/task_manager.py status my-project
```

Output:
```
📋 Project: my-project
🎯 Goal: Build a REST API with tests and docs
📊 Status: active
▶️  Current: test-agent

  ✅ code-agent: done
     Task: Implement REST API with Flask
     Output: Created /home/ubuntu/projects/my-project/app.py
  🔄 test-agent: in-progress
     Task: Write pytest tests for all endpoints
  ⬜ docs-agent: pending
  ⬜ monitor-bot: pending

  Progress: [██░░] 2/4
```

## Agent Dispatch Details

### ⚠️ Important: Subagent Spawning Limitation

**Current OpenClaw limitation**: `sessions_spawn` with `mode: "session"` requires `thread: true`, but thread binding requires channel plugin support for `subagent_spawning` hooks. Most channel plugins (including Telegram) do not implement these hooks.

**Result**: Persistent subagent sessions (`mode: "session"`) are **not available** in most configurations. Use `mode: "run"` instead.

### Recommended Dispatch Pattern

Use `sessions_spawn` with `mode: "run"` for each task:

```python
sessions_spawn(
  runtime="subagent",
  agentId="main",
  label="code-agent-myproject",
  mode="run",
  runTimeoutSeconds=300,
  task="""
Project: my-project
Goal: Build a REST API with tests and docs
Your task: Implement REST API with Flask: GET/POST/DELETE /items
Working directory: /home/ubuntu/projects/my-project/
"""
)
```

The agent will:
1. Spawn fresh for this task
2. Execute the task
3. Return results via completion event
4. Auto-announce when done

### Legacy Session Key Pattern (Not Recommended)

The following pattern assumes persistent agents that can be messaged via `sessions_send`. This **does not work** without thread binding support:

| Agent | Session Key (Legacy) |
|-------|---------------------|
| code-agent | `agent:code-agent:telegram:group:-5189558203` |
| test-agent | `agent:test-agent:telegram:group:-5218382533` |
| docs-agent | `agent:docs-agent:telegram:group:-5253138320` |
| monitor-bot | `agent:monitor-bot:telegram:group:-5193935559` |

**Why it fails**: `sessions_send` requires the target session to be in the same session tree. Subagents spawned without thread binding are not visible to `sessions_send` from the parent.

### Dispatch Template

When dispatching to an agent via `sessions_spawn`, include:
1. **Project context** — what the project is about
2. **Specific task** — what this agent should do
3. **Working directory** — where to create/find files
4. **Previous stage output** — if relevant (e.g., test-agent needs to know what code-agent built)

Example task message:
```
Project: my-project
Goal: Build a REST API with tests and docs
Your task: Write pytest tests for all endpoints in /home/ubuntu/projects/my-project/app.py
Target: 90%+ coverage, test GET/POST/DELETE /items
Working directory: /home/ubuntu/projects/my-project/
Previous stage (code-agent) output: Created app.py with Flask REST API, 3 endpoints
```

### Monitoring Subagent Progress

Use `subagents` tool to check status:
```bash
subagents(action="list", recentMinutes=10)
```

Or poll via exec:
```bash
ls -la /path/to/project/workspace/
```

## Mode B: DAG Workflow (Parallel Dependencies)

### Step 1: Initialize DAG Project

```bash
python3 scripts/task_manager.py init my-project -m dag -g "Build REST API with parallel workstreams"
```

### Step 2: Add Tasks with Dependencies

```bash
TM="python3 scripts/task_manager.py"
# Root tasks (no deps — can run in parallel)
$TM add my-project design     -a docs-agent  --desc "Write API spec"
$TM add my-project scaffold   -a code-agent  --desc "Create project skeleton"

# Tasks with dependencies (blocked until deps are done)
$TM add my-project implement  -a code-agent  -d "design,scaffold" --desc "Implement API"
$TM add my-project write-tests -a test-agent -d "design"          --desc "Write test cases from spec"

# Fan-in: depends on multiple tasks
$TM add my-project run-tests  -a test-agent  -d "implement,write-tests" --desc "Run all tests"
$TM add my-project write-docs -a docs-agent  -d "implement"             --desc "Write final docs"

# Final gate
$TM add my-project review     -a monitor-bot -d "run-tests,write-docs"  --desc "Final review"
```

### Step 3: View DAG Graph

```bash
$TM graph my-project
```
```
├─ ⬜ design [docs-agent]
│  ├─ ⬜ implement [code-agent]
│  │  ├─ ⬜ run-tests [test-agent]
│  │  │  └─ ⬜ review [monitor-bot]
│  │  └─ ⬜ write-docs [docs-agent]
│  └─ ⬜ write-tests [test-agent]
└─ ⬜ scaffold [code-agent]
   └─ ⬜ implement (↑ see above)
```

### Step 4: Dispatch Ready Tasks

```bash
$TM ready my-project    # Shows all tasks whose deps are met
```

For each ready task, AGI follows this loop:
```
1. Get ready tasks:     task_manager.py ready <project> --json
2. For each ready task (can dispatch in parallel):
   a. Mark in-progress: task_manager.py update <project> <task> in-progress
   b. Dispatch agent:   sessions_spawn(runtime="subagent", mode="run", task=<task + dep outputs>)
3. When agent completes (auto-announced):
   a. Save result:      task_manager.py result <project> <task> "<summary>"
   b. Mark done:        task_manager.py update <project> <task> done
   c. Check newly unblocked tasks (printed automatically)
4. Repeat until all done
```

**Note**: We use `sessions_spawn` with `mode: "run"` instead of `sessions_send` because persistent subagent sessions require thread binding support that is not available in most channel configurations.

### Key DAG Features

- **Parallel dispatch**: `ready` returns ALL tasks whose deps are satisfied — dispatch them simultaneously
- **Dep outputs forwarding**: `ready --json` includes `depOutputs` — previous stage results to pass to agents
- **Auto-unblock notification**: When a task completes, shows which tasks are newly unblocked
- **Cycle detection**: `add` rejects tasks that would create circular dependencies
- **Partial failure**: If one task fails, unrelated branches continue; only downstream tasks block
- **Graph visualization**: `graph` shows tree view with status icons and dedup markers

## Custom Pipelines

### Linear (Mode A)
```bash
# Code + test only
python3 scripts/task_manager.py init quick-fix -g "Hotfix" -p "code-agent,test-agent"

# Docs first, then code
python3 scripts/task_manager.py init spec-driven -g "Spec-driven dev" -p "docs-agent,code-agent,test-agent"
```

### DAG (Mode B)
```bash
# Diamond pattern: 2 parallel branches merge for review
$TM init diamond -m dag -g "Parallel dev"
$TM add diamond code -a code-agent --desc "Write code"
$TM add diamond test -a test-agent --desc "Write tests"
$TM add diamond integrate -a code-agent -d "code,test" --desc "Integration"
$TM add diamond review -a monitor-bot -d "integrate" --desc "Final review"
```

## Choosing Between Modes

| | Mode A (linear) | Mode B (dag) |
|---|---|---|
| **When** | Sequential tasks, simple flows | Parallel workstreams, complex deps |
| **Dispatch** | One at a time, auto-advance | Multiple simultaneous, dep-driven |
| **Setup** | `init -p agents` (one command) | `init -m dag` + `add` per task |
| **Best for** | Bug fixes, simple features | Large features, spec-driven dev |

## Data Location

Task files: `~/.openclaw/workspace/projects/<project>.json` (macOS) or `/home/ubuntu/clawd/data/team-tasks/<project>.json` (Linux)

The task manager auto-detects the platform and uses the appropriate directory.

## ⚠️ Common Pitfalls

### Mode A: Stage ID is agent name, NOT a number
In linear mode, the stage ID is the **agent name** (e.g., `code-agent`), not a numeric index like `1`, `2`, `3`.

```bash
# ❌ WRONG — will error "stage '1' not found"
python3 scripts/task_manager.py assign my-project 1 "Build API"
python3 scripts/task_manager.py update my-project 1 done

# ✅ CORRECT — use agent name as stage ID
python3 scripts/task_manager.py assign my-project code-agent "Build API"
python3 scripts/task_manager.py update my-project code-agent done
python3 scripts/task_manager.py result my-project code-agent "Created main.py"
```

This applies to all stage-referencing commands: `assign`, `update`, `result`, `log`, `reset`.

The pipeline order is defined by `-p` at `init` time (e.g., `-p "code-agent,test-agent,docs-agent"`), and `next` automatically advances through them in order — but you always reference stages by agent name.

### Subagent Session Mode Not Available
**Problem**: `sessions_spawn` with `mode: "session"` fails with "thread=true is unavailable because no channel plugin registered subagent_spawning hooks."

**Root cause**: Persistent subagent sessions require thread binding, which requires channel plugin support (e.g., Telegram plugin implementing `subagent_spawning` hooks).

**Solution**: Use `mode: "run"` instead. This spawns a fresh subagent for each task that executes and exits. The pipeline still works — just without persistent agent sessions.

```python
# ❌ Does not work without thread binding support
sessions_spawn(runtime="subagent", mode="session", thread=true)

# ✅ Use this instead
sessions_spawn(runtime="subagent", mode="run", runTimeoutSeconds=300)
```

### Sessions Send Visibility
**Problem**: `sessions_send` to subagent session keys fails with "visibility is restricted to the current session tree."

**Root cause**: Subagents spawned without thread binding are not in the same session tree as the parent.

**Solution**: Use `sessions_spawn` with `mode: "run"` and wait for completion events instead of trying to message persistent sessions.

## Tips

- **One project per task** — keep scope focused; create multiple projects for parallel work
- **Meaningful project slugs** — `rest-api-v2`, `bug-fix-auth`, `refactor-db` (not `project1`)
- **Save results** — always `result` before `update done`; this is the inter-agent context
- **Log liberally** — `log` is cheap; helps debug failed pipelines
- **Reset and retry** — `reset --all` for clean reruns; `reset <stage>` for targeted retry
- **DAG fan-out** — one root task can unblock many parallel tasks
- **DAG fan-in** — a task can depend on multiple predecessors (all must complete)
