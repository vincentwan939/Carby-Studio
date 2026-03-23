# Carby Sprint Python API Reference

Complete API reference for the Carby Sprint Python modules.

---

## Table of Contents

- [SprintRepository](#sprintrepository)
- [SprintPaths](#sprintpaths)
- [WorkItemModel](#workitemmodel)
- [SprintModel](#sprintmodel)
- [PhaseLock](#phaselock)
- [GateToken](#gatetoken)
- [Utility Functions](#utility-functions)
- [Configuration Options](#configuration-options)

---

## SprintRepository

Centralized sprint data access layer.

```python
from carby_sprint.sprint_repository import SprintRepository

repo = SprintRepository(output_dir=".carby-sprints")
```

### Constructor

#### `SprintRepository(output_dir: str = ".carby-sprints")`

Initialize the repository.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `output_dir` | str | `.carby-sprints` | Base directory for sprint data |

### Methods

#### `get_sprint_path(sprint_id: str) -> Path`

Get the path to a sprint directory with validation.

```python
path = repo.get_sprint_path("sprint-001")
# Returns: Path(".carby-sprints/sprint-001")
```

#### `get_paths(sprint_id: str) -> SprintPaths`

Get all relevant paths for a sprint.

```python
paths = repo.get_paths("sprint-001")
print(paths.metadata)      # .carby-sprints/sprint-001/metadata.json
print(paths.work_items)    # .carby-sprints/sprint-001/work_items
print(paths.gates)         # .carby-sprints/sprint-001/gates
print(paths.logs)          # .carby-sprints/sprint-001/logs
```

#### `exists(sprint_id: str) -> bool`

Check if a sprint exists.

```python
if repo.exists("sprint-001"):
    print("Sprint exists")
```

#### `load(sprint_id: str) -> Tuple[Dict[str, Any], SprintPaths]`

Load sprint metadata.

```python
data, paths = repo.load("sprint-001")
print(data["project"])     # Project name
print(data["status"])      # Sprint status
```

**Raises:** `FileNotFoundError` if sprint not found.

#### `save(sprint_data: Dict[str, Any], paths: SprintPaths) -> None`

Save sprint metadata with validation and atomic transaction.

```python
repo.save(sprint_data, paths)
```

#### `create(sprint_id: str, project: str, goal: str, description: str = "", duration_days: int = 14, start_date: Optional[datetime] = None) -> Tuple[Dict[str, Any], SprintPaths]`

Create a new sprint.

```python
data, paths = repo.create(
    sprint_id="sprint-001",
    project="my-api",
    goal="Build REST API",
    description="User management API",
    duration_days=14
)
```

#### `delete(sprint_id: str) -> None`

Delete a sprint directory.

```python
repo.delete("sprint-001")
```

#### `archive(sprint_id: str, archive_dir: Path, update_status: bool = True) -> Path`

Archive a sprint.

```python
from pathlib import Path
archive_path = repo.archive(
    sprint_id="sprint-001",
    archive_dir=Path(".carby-sprints/archive")
)
```

#### `load_work_item(paths: SprintPaths, work_item_id: str) -> Dict[str, Any]`

Load a work item.

```python
work_item = repo.load_work_item(paths, "WI-1")
```

#### `save_work_item(paths: SprintPaths, work_item: Dict[str, Any]) -> None`

Save a work item with validation.

```python
repo.save_work_item(paths, work_item)
```

#### `list_work_items(paths: SprintPaths) -> List[str]`

List all work item IDs.

```python
items = repo.list_work_items(paths)
# Returns: ["WI-1", "WI-2", "WI-3"]
```

---

## SprintPaths

Container for sprint-related file paths.

```python
from carby_sprint.sprint_repository import SprintPaths

paths = SprintPaths(
    sprint_dir=Path(".carby-sprints/sprint-001"),
    metadata=Path(".carby-sprints/sprint-001/metadata.json"),
    work_items=Path(".carby-sprints/sprint-001/work_items"),
    gates=Path(".carby-sprints/sprint-001/gates"),
    logs=Path(".carby-sprints/sprint-001/logs")
)
```

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `sprint_dir` | Path | Sprint directory |
| `metadata` | Path | metadata.json file |
| `work_items` | Path | Work items directory |
| `gates` | Path | Gates directory |
| `logs` | Path | Logs directory |
| `execution_lock` | Path | Execution lock file (computed) |

---

## WorkItemModel

Pydantic model for work item validation.

```python
from carby_sprint.validators import WorkItemModel, WorkItemStatus

work_item = WorkItemModel(
    id="WI-1",
    title="Implement auth",
    description="Add OAuth2 authentication",
    status=WorkItemStatus.PLANNED,
    priority=1
)
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | str | required | Work item ID (alphanumeric, underscore, hyphen) |
| `title` | str | required | Work item title (1-200 chars) |
| `description` | str | `""` | Description (max 2000 chars) |
| `status` | WorkItemStatus | `PLANNED` | Current status |
| `priority` | int | `1` | Priority (1-5, 1=highest) |
| `assigned_to` | Optional[str] | `None` | Assignee name |
| `created_at` | Optional[datetime] | `None` | Creation timestamp |
| `started_at` | Optional[datetime] | `None` | Start timestamp |
| `completed_at` | Optional[datetime] | `None` | Completion timestamp |
| `artifacts` | List[str] | `[]` | Generated artifacts |
| `github_issues` | List[str] | `[]` | Related GitHub issues |
| `validation_token` | Optional[str] | `None` | Validation token |

### Status Enum

```python
from carby_sprint.validators import WorkItemStatus

WorkItemStatus.PLANNED      # Not started
WorkItemStatus.IN_PROGRESS  # Currently working
WorkItemStatus.COMPLETED    # Done
WorkItemStatus.FAILED       # Failed
WorkItemStatus.BLOCKED      # Blocked
WorkItemStatus.CANCELLED    # Cancelled
```

---

## SprintModel

Pydantic model for sprint validation.

```python
from carby_sprint.validators import SprintModel, SprintStatus

sprint = SprintModel(
    sprint_id="sprint-001",
    project="my-api",
    goal="Build REST API",
    start_date="2026-03-23",
    end_date="2026-04-06",
    duration_days=14
)
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `sprint_id` | str | required | Sprint ID (alphanumeric, underscore, hyphen) |
| `project` | str | required | Project name (1-100 chars) |
| `goal` | str | required | Sprint goal (1-500 chars) |
| `description` | str | `""` | Additional description |
| `status` | SprintStatus | `INITIALIZED` | Current status |
| `start_date` | str | required | Start date (YYYY-MM-DD) |
| `end_date` | str | required | End date (YYYY-MM-DD) |
| `duration_days` | int | required | Duration (1-999 days) |
| `work_items` | List[str] | `[]` | List of work item IDs |
| `gates` | Dict[str, GateModel] | `{}` | Gate configurations |
| `risk_score` | Optional[float] | `None` | Risk score (0.0-5.0) |
| `current_gate` | int | `1` | Current gate number (1-5) |
| `max_parallel` | Optional[int] | `None` | Max parallel work items (1-10) |

### Status Enum

```python
from carby_sprint.validators import SprintStatus

SprintStatus.INITIALIZED  # Created, not started
SprintStatus.RUNNING      # In progress
SprintStatus.COMPLETED    # All work done
SprintStatus.CANCELLED    # Cancelled
SprintStatus.ARCHIVED     # Archived
```

---

## PhaseLock

Sequential phase execution enforcement.

```python
from carby_sprint.phase_lock import PhaseLock

lock = PhaseLock(output_dir=".carby-sprints")
```

### Phase Sequence

```
discover → design → build → verify → deliver
```

### Methods

#### `can_start_phase(sprint_id: str, phase_id: str) -> Tuple[bool, Optional[str]]`

Check if a phase can be started.

```python
can_start, error = lock.can_start_phase("sprint-001", "phase_2_design")
if not can_start:
    print(error)  # "Previous phase 'discover' not approved"
```

#### `start_phase(sprint_id: str, phase_id: str) -> None`

Mark phase as started.

```python
lock.start_phase("sprint-001", "phase_2_design")
```

#### `complete_phase(sprint_id: str, phase_id: str, summary: str = "") -> None`

Mark phase as completed.

```python
lock.complete_phase(
    "sprint-001",
    "phase_2_design",
    summary="Architecture complete"
)
```

#### `approve_phase(sprint_id: str, phase_id: str) -> None`

Approve a phase to unblock the next.

```python
lock.approve_phase("sprint-001", "phase_2_design")
```

#### `get_current_phase(sprint_id: str) -> Optional[str]`

Get the currently running phase.

```python
current = lock.get_current_phase("sprint-001")
# Returns: "design" or None
```

#### `get_waiting_phase(sprint_id: str) -> Optional[str]`

Get phase waiting for approval.

```python
waiting = lock.get_waiting_phase("sprint-001")
# Returns: "design" or None
```

### Function-Based API

```python
from carby_sprint.phase_lock import (
    get_phase_status,
    wait_for_previous_phase,
    mark_phase_complete,
    approve_phase
)

# Get phase status
status = get_phase_status("sprint-001", "design")
# Returns: {"phase": "design", "state": "in_progress", ...}

# Wait for previous phase (blocks)
result = wait_for_previous_phase("sprint-001", "build")

# Mark complete
result = mark_phase_complete("sprint-001", "design", "Architecture done")

# Approve
result = approve_phase("sprint-001", "design")
```

---

## GateToken

Cryptographically signed gate token with expiration.

```python
from carby_sprint.gate_enforcer import GateToken

# Create token
token = GateToken(
    gate_id="gate-1",
    sprint_id="sprint-001",
    expires_in_hours=24
)

print(token.token)  # Serialized token string
```

### Constructor

#### `GateToken(gate_id: str, sprint_id: str, expires_in_hours: int = 24, secret_key: Optional[bytes] = None)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `gate_id` | str | required | Unique gate identifier |
| `sprint_id` | str | required | Associated sprint ID |
| `expires_in_hours` | int | `24` | Token lifetime |
| `secret_key` | Optional[bytes] | `None` | HMAC secret (auto-generated if None) |

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `token` | str | Serialized token string |
| `created_at` | datetime | Creation timestamp |
| `expires_at` | datetime | Expiration timestamp |
| `nonce` | str | Cryptographic nonce |

### Class Methods

#### `from_string(token_str: str, secret_key: Optional[bytes] = None) -> GateToken`

Deserialize token from string.

```python
token = GateToken.from_string(token_string)
```

#### `validate(token_str: str, gate_id: str, sprint_id: str, secret_key: Optional[bytes] = None) -> bool`

Validate a token.

```python
is_valid = GateToken.validate(token_str, "gate-1", "sprint-001")
```

---

## Utility Functions

### Validation Functions

```python
from carby_sprint.validators import validate_sprint, validate_work_item

# Validate sprint data
validated = validate_sprint({"sprint_id": "sprint-001", ...})

# Validate work item data
validated = validate_work_item({"id": "WI-1", ...})
```

### Path Utilities

```python
from carby_sprint.path_utils import (
    validate_sprint_id,
    validate_work_item_id,
    generate_work_item_id,
    safe_join_path
)

# Validate IDs
validate_sprint_id("sprint-001")      # OK
validate_sprint_id("../etc")          # Raises ValueError

# Generate work item ID
wi_id = generate_work_item_id(1)      # Returns: "WI-1"

# Safe path joining
path = safe_join_path(".carby-sprints", "sprint-001")
```

### Lock Manager

```python
from carby_sprint.lock_manager import with_sprint_lock, DistributedLock

# Context manager for sprint locking
with with_sprint_lock(".carby-sprints/sprint-001/.lock"):
    # Critical section
    pass

# Distributed lock
lock = DistributedLock(".carby-sprints/sprint-001/.lock")
lock.acquire()
lock.release()
```

### Transaction Support

```python
from carby_sprint.transaction import atomic_sprint_update

# Atomic sprint update
with atomic_sprint_update(sprint_dir) as data:
    data["status"] = "running"
    # Changes applied atomically on exit
```

---

## Configuration Options

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CARBY_WORKSPACE` | Project storage directory | `~/.openclaw/workspace/projects` |
| `CARBY_BACKEND` | Storage backend | `file` |
| `CARBY_MODEL_DISCOVER` | Discover agent model | `bailian/kimi-k2.5` |
| `CARBY_MODEL_DESIGN` | Design agent model | `bailian/glm-5` |
| `CARBY_MODEL_BUILD` | Build agent model | `bailian/qwen3-coder-plus` |
| `CARBY_MODEL_VERIFY` | Verify agent model | `bailian/qwen3-coder-plus` |
| `CARBY_MODEL_DELIVER` | Deliver agent model | `bailian/kimi-k2.5` |
| `CARBY_AGENT_TIMEOUT` | Agent timeout (seconds) | `600` |
| `CARBY_DEBUG` | Enable verbose output | — |

### Configuration File

Create `~/.openclaw/carby-studio.conf`:

```ini
[defaults]
timeout = 3600
max_parallel = 5
log_level = INFO

[security]
gate_enforcement = strict
audit_logging = enabled

[paths]
output_dir = .carby-sprints
archive_dir = .carby-sprints/archive

[phase_lock]
enabled = true
default_mode = parallel
phase_order = discover,design,build,verify,deliver
approval_required = true
```

---

## Exceptions

```python
from carby_sprint.gate_enforcer import (
    GateEnforcementError,
    InvalidTokenError,
    ExpiredTokenError,
    GateBypassError
)

try:
    token.validate()
except InvalidTokenError:
    print("Token is invalid or tampered")
except ExpiredTokenError:
    print("Token has expired")
except GateBypassError:
    print("Gate bypass attempt detected")
```

---

*Carby Studio v3.2.1 — API Reference*
