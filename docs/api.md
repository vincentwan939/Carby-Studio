# Carby Studio API Documentation

Complete API reference for the Carby Sprint Framework public modules.

---

## Table of Contents

- [phase_lock](#phase_lock) — Phase state management and sequential enforcement
- [gate_enforcer](#gate_enforcer) — Gate enforcement and token validation
- [validators](#validators) — Pydantic models and input validation
- [transaction](#transaction) — Atomic transactions with rollback
- [lock_manager](#lock_manager) — Distributed locking
- [sprint_repository](#sprint_repository) — Sprint data management

---

## phase_lock

**Module Path:** `carby_sprint.phase_lock`

Phase Lock Module for Carby Studio Sequential Phase Enforcement. Enforces sequential phase execution: **discover → design → build → verify → deliver**.

### Overview

The phase_lock module provides both functional and class-based interfaces for managing sprint phases. It ensures that phases execute in the correct order and cannot be skipped or started before their prerequisites are met.

### Constants

```python
PHASE_ORDER = ["discover", "design", "build", "verify", "deliver"]
DEFAULT_OUTPUT_DIR = ".carby-sprints"
```

### PhaseLockState Enum

```python
class PhaseLockState(str, Enum):
    """Phase lock states."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"
```

### PhaseLock Class

```python
class PhaseLock:
    """Class-based Phase Lock interface."""
    
    PHASE_SEQUENCE = [
        "phase_1_discover", 
        "phase_2_design", 
        "phase_3_build", 
        "phase_4_verify", 
        "phase_5_deliver"
    ]
    
    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR)
```

#### Methods

##### can_start_phase

```python
def can_start_phase(
    self, 
    sprint_id: str, 
    phase_id: str
) -> tuple[bool, str | None]
```

Check if a phase can be started.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `phase_id` (str): Phase identifier (e.g., "phase_1_discover" or "discover")

**Returns:**
- `tuple[bool, str | None]`: (can_start, error_message_if_blocked)

**Example:**
```python
from carby_sprint.phase_lock import PhaseLock

lock = PhaseLock()
can_start, error = lock.can_start_phase("my-sprint", "phase_2_design")
if not can_start:
    print(f"Cannot start: {error}")
```

---

##### start_phase

```python
def start_phase(
    self, 
    sprint_id: str, 
    phase_id: str
) -> None
```

Mark phase as started.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `phase_id` (str): Phase identifier

**Raises:**
- `PhaseBlockedError`: If previous phase is not approved

---

##### complete_phase

```python
def complete_phase(
    self, 
    sprint_id: str, 
    phase_id: str, 
    summary: str = ""
) -> None
```

Mark phase as completed, awaiting approval.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `phase_id` (str): Phase identifier
- `summary` (str): Completion summary

---

##### approve_phase

```python
def approve_phase(
    self, 
    sprint_id: str, 
    phase_id: str
) -> None
```

Approve a phase, allowing the next phase to proceed.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `phase_id` (str): Phase identifier

---

##### get_current_phase

```python
def get_current_phase(
    self, 
    sprint_id: str
) -> str | None
```

Get the currently active phase.

**Parameters:**
- `sprint_id` (str): Sprint identifier

**Returns:**
- `str | None`: Current phase name or None if no phase is active

---

##### get_waiting_phase

```python
def get_waiting_phase(
    self, 
    sprint_id: str
) -> str | None
```

Get the phase waiting for approval.

**Parameters:**
- `sprint_id` (str): Sprint identifier

**Returns:**
- `str | None`: Phase name awaiting approval or None

---

##### is_phase_approved

```python
def is_phase_approved(
    self, 
    sprint_id: str, 
    phase_id: str
) -> bool
```

Check if a phase is approved.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `phase_id` (str): Phase identifier (can be simple name like 'discover' or full like 'phase_1_discover')

**Returns:**
- `bool`: True if phase is approved, False otherwise

---

### Functional API

#### get_phase_status

```python
def get_phase_status(
    sprint_id: str, 
    phase_id: str,
    output_dir: str = DEFAULT_OUTPUT_DIR
) -> Dict[str, Any]
```

Get current status of a phase.

**Returns:**
```python
{
    "phase": str,           # Phase identifier
    "state": str,           # Current state (pending, awaiting_approval, approved)
    "summary": str | None,  # Completion summary
    "previous_phase": str | None  # Previous phase in sequence
}
```

---

#### wait_for_previous_phase

```python
def wait_for_previous_phase(
    sprint_id: str, 
    phase_id: str,
    output_dir: str = DEFAULT_OUTPUT_DIR,
    poll_interval: float = 1.0,
    check_design_gate: bool = False
) -> Dict[str, Any]
```

Block until previous phase is approved. Raises `PhaseBlockedError` if blocked.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `phase_id` (str): Phase to wait for
- `output_dir` (str): Directory containing sprint data
- `poll_interval` (float): Polling interval (unused, kept for compatibility)
- `check_design_gate` (bool): If True, also check design approval gate for build phase

**Returns:**
```python
{
    "ready": True,
    "phase": str,
    "previous_phase": str
}
```

**Raises:**
- `PhaseBlockedError`: If previous phase is not ready

---

#### mark_phase_complete

```python
def mark_phase_complete(
    sprint_id: str, 
    phase_id: str, 
    summary: str,
    output_dir: str = DEFAULT_OUTPUT_DIR
) -> Dict[str, Any]
```

Mark phase complete, awaiting approval.

**Returns:**
```python
{
    "phase": str,
    "state": "awaiting_approval",
    "message": str,
    "approve_command": str  # CLI command to approve
}
```

---

#### approve_phase

```python
def approve_phase(
    sprint_id: str, 
    phase_id: str,
    output_dir: str = DEFAULT_OUTPUT_DIR
) -> Dict[str, Any]
```

Approve phase, allowing next to proceed.

**Returns:**
```python
{
    "phase": str,
    "state": "approved",
    "message": str,
    "next_phase": str | None,      # Next phase in sequence
    "next_command": str | None     # Command to start next phase
}
```

---

### Exceptions

```python
from carby_sprint.exceptions import PhaseBlockedError

class PhaseBlockedError(Exception):
    """Raised when a phase cannot proceed due to unmet prerequisites."""
    
    def __init__(
        self, 
        phase_id: str, 
        reason: str, 
        resolution: str
    )
```

---

## gate_enforcer

**Module Path:** `carby_sprint.gate_enforcer`

Server-Side Gate Enforcement System. Implements cryptographic gate enforcement with HMAC-signed tokens, expiration validation, and server-side `can_advance()` checks to prevent agents from bypassing gates.

### Overview

The gate_enforcer module provides:
- HMAC-SHA256 signed tokens with 24-hour expiration
- Server-side gate advancement validation
- Tamper-evident gate logs
- No client-side bypass capability
- Design Approval Gate for design-first workflow

### Re-exports

This module re-exports from split modules:
- `gate_token.py`: `GateToken`, `DesignApprovalToken`
- `gate_state.py`: `GateStateManager`
- `design_gate.py`: `DesignGateEnforcer`

### GateEnforcer Class

```python
class GateEnforcer:
    """
    Server-side gate enforcement system that controls advancement 
    through sprint phases.
    """
    
    def __init__(self, project_dir: str)
```

**Parameters:**
- `project_dir`: Path to the project directory

### DesignGateEnforcer Class

```python
class DesignGateEnforcer:
    """Enforces design approval before build phase."""
    
    def __init__(self, sprint_id: str, output_dir: str = ".carby-sprints")
    def request_approval(self, design_summary: str, approver: str = "user") -> dict
    def check_approval(self) -> dict
    def approve(self, approver: str = "user") -> DesignApprovalToken
```

### GateToken

```python
@dataclass
class GateToken:
    """HMAC-signed token for gate validation."""
    token: str
    gate: int
    sprint_id: str
    created_at: datetime
    expires_at: datetime
    
    def is_valid(self) -> bool
    def to_dict() -> dict
```

---

## validators

**Module Path:** `carby_sprint.validators`

Pydantic models for input validation and data serialization.

### SprintCreate

```python
class SprintCreate(BaseModel):
    """Validation model for sprint creation."""
    sprint_id: str
    project_name: str
    goal: str
    
    @field_validator("sprint_id")
    def validate_sprint_id(cls, v: str) -> str
```

### GateInfo

```python
class GateInfo(BaseModel):
    """Gate information model."""
    gate_number: int
    name: str
    status: str  # "pending", "in_progress", "passed", "failed"
    validation_token: Optional[str]
    completed_at: Optional[datetime]
```

---

## transaction

**Module Path:** `carby_sprint.transaction`

Atomic transactions with rollback support.

### TransactionManager

```python
class TransactionManager:
    """
    Manages atomic transactions for sprint data updates.
    Uses copy-on-write pattern with automatic rollback.
    """
    
    def __init__(self, output_dir: str = ".carby-sprints")
    def begin(self, sprint_id: str) -> TransactionContext
    def commit(self, tx_id: str) -> bool
    def rollback(self, tx_id: str) -> bool
```

### TransactionContext

```python
class TransactionContext:
    """Context manager for transactions."""
    
    def __enter__(self) -> TransactionContext
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool
    def update(self, data: dict) -> None
```

---

## lock_manager

**Module Path:** `carby_sprint.lock_manager`

Distributed file locking for concurrent access.

### DistributedLock

```python
class DistributedLock:
    """
    File-based distributed lock using portalocker.
    """
    
    def __init__(self, lock_file: Union[str, Path], timeout: float = 30.0)
    def acquire(self) -> bool
    def release(self) -> None
    def __enter__(self) -> DistributedLock
    def __exit__(self, exc_type, exc_val, exc_tb) -> None
```

### with_lock Decorator

```python
def with_lock(lock_file: Union[str, Path], timeout: float = 30.0) -> Callable
    """Decorator for function-level locking."""
```

---

## sprint_repository

**Module Path:** `carby_sprint.sprint_repository`

Sprint data persistence and retrieval.

### SprintRepository

```python
class SprintRepository:
    """
    Repository for sprint data operations.
    Provides CRUD operations for sprints, gates, and work items.
    """
    
    def __init__(self, output_dir: str = ".carby-sprints")
    def create(self, sprint_id: str, project_name: str, goal: str) -> SprintPaths
    def get(self, sprint_id: str) -> Optional[dict]
    def update(self, sprint_id: str, data: dict) -> bool
    def delete(self, sprint_id: str) -> bool
    def list_all(self) -> list[str]
```

### SprintPaths

```python
@dataclass
class SprintPaths:
    """Paths for sprint artifacts."""
    root: Path
    metadata: Path
    gates: Path
    work_items: Path
    logs: Path
```

---

## Usage Examples

### Complete Sprint Workflow

```python
from carby_sprint import phase_lock, gate_enforcer, validators

# Create a sprint
sprint_data = validators.SprintCreate(
    sprint_id="my-project",
    project_name="My Project",
    goal="Build an API"
)

# Start discover phase
lock = phase_lock.PhaseLock()
lock.start_phase("my-project", "phase_1_discover")

# Complete and approve
lock.complete_phase("my-project", "phase_1_discover", "Requirements gathered")
lock.approve_phase("my-project", "phase_1_discover")

# Check if design can start
can_start, error = lock.can_start_phase("my-project", "phase_2_design")
```

---

*API Documentation for Carby Studio v3.2.2*
project_dir` (str): Project directory path

---

#### Methods

##### can_advance

```python
def can_advance(
    self, 
    sprint_id: str, 
    current_gate: str, 
    next_gate: str
) -> bool
```

Server-side check to determine if advancement is allowed.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `current_gate` (str): Current gate
- `next_gate` (str): Next gate to advance to

**Returns:**
- `bool`: True if advancement is allowed, False otherwise

---

##### request_gate_token

```python
def request_gate_token(
    self, 
    sprint_id: str, 
    gate: str
) -> GateToken
```

Request a signed token for a specific gate.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `gate` (str): Gate identifier

**Returns:**
- `GateToken`: Signed GateToken

---

##### validate_gate_token

```python
def validate_gate_token(
    self, 
    token_str: str
) -> Tuple[bool, Optional[str], Optional[str]]
```

Validate a gate token and return validation result.

**Parameters:**
- `token_str` (str): Token string to validate

**Returns:**
- `Tuple[bool, Optional[str], Optional[str]]`: (is_valid, gate_id, sprint_id)

---

##### advance_gate

```python
def advance_gate(
    self, 
    sprint_id: str, 
    gate: str, 
    token_str: str
) -> bool
```

Advance to the next gate using a valid token.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `gate` (str): Gate to advance to
- `token_str` (str): Valid gate token

**Returns:**
- `bool`: True if advancement successful, False otherwise

**Raises:**
- `GateBypassError`: If token is invalid or advancement not allowed

---

##### get_gate_status

```python
def get_gate_status(
    self, 
    sprint_id: str
) -> Dict[str, Any]
```

Get the current status of gates for a sprint.

**Parameters:**
- `sprint_id` (str): Sprint identifier

**Returns:**
- `Dict[str, Any]`: Gate status information

---

### Exceptions

```python
from carby_sprint.exceptions import (
    CarbyStudioError,
    InvalidTokenError,
    ExpiredTokenError,
    GateEnforcementError,
    GateBypassError
)
```

---

## validators

**Module Path:** `carby_sprint.validators`

Pydantic Models for Carby Sprint Framework Validation. Provides data validation models for sprint and work item data structures.

### Overview

The validators module defines Pydantic models for validating sprint and work item data. These models ensure data integrity and consistency across the framework.

### Enums

#### SprintStatus

```python
class SprintStatus(str, Enum):
    """Valid sprint statuses."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"
```

#### WorkItemStatus

```python
class WorkItemStatus(str, Enum):
    """Valid work item statuses."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
```

#### GateStatus

```python
class GateStatus(str, Enum):
    """Valid gate statuses."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    PASS_WITH_WARNINGS = "passed_with_warnings"
```

### Models

#### WorkItemModel

```python
class WorkItemModel(BaseModel):
    """Pydantic model for work item validation."""
    
    id: str = Field(..., pattern=r'^[a-zA-Z0-9_-]+$', description="Work item ID (alphanumeric, underscore, hyphen)")
    title: str = Field(..., min_length=1, max_length=200, description="Work item title")
    description: str = Field(default="", max_length=2000, description="Work item description")
    status: WorkItemStatus = Field(default=WorkItemStatus.PLANNED, description="Current status")
    priority: int = Field(default=1, ge=1, le=5, description="Priority (1-5, 1=highest)")
    assigned_to: Optional[str] = Field(default=None, max_length=100, description="Assignee")
    created_at: Optional[datetime] = Field(default=None, description="Creation timestamp")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    failed_at: Optional[datetime] = Field(default=None, description="Failure timestamp")
    blocked_at: Optional[datetime] = Field(default=None, description="Block timestamp")
    cancelled_at: Optional[datetime] = Field(default=None, description="Cancellation timestamp")
    artifacts: List[str] = Field(default_factory=list, description="Generated artifacts")
    github_issues: List[str] = Field(default_factory=list, description="Related GitHub issues")
    validation_token: Optional[str] = Field(default=None, max_length=100, description="Validation token")
    failure_reason: Optional[str] = Field(default=None, max_length=500, description="Failure reason")
    block_reason: Optional[str] = Field(default=None, max_length=500, description="Block reason")
```

**Validation Rules:**
- ID must be alphanumeric with underscores/hyphens only
- Title must be 1-200 characters
- Priority must be between 1-5
- Timestamps must follow logical ordering

---

#### GateModel

```python
class GateModel(BaseModel):
    """Pydantic model for gate validation."""
    
    status: GateStatus = Field(default=GateStatus.PENDING, description="Current status")
    name: str = Field(..., min_length=1, max_length=100, description="Gate name")
    description: Optional[str] = Field(default=None, max_length=500, description="Gate description")
    passed_at: Optional[datetime] = Field(default=None, description="Pass timestamp")
    failed_at: Optional[datetime] = Field(default=None, description="Fail timestamp")
    blocked_at: Optional[datetime] = Field(default=None, description="Block timestamp")
```

---

#### SprintModel

```python
class SprintModel(BaseModel):
    """Pydantic model for sprint validation."""
    
    sprint_id: str = Field(..., pattern=r'^[a-zA-Z0-9_-]+$', description="Sprint ID (alphanumeric, underscore, hyphen)")
    project: str = Field(..., min_length=1, max_length=100, description="Project name")
    goal: str = Field(..., min_length=1, max_length=500, description="Sprint goal")
    description: str = Field(default="", max_length=2000, description="Sprint description")
    status: SprintStatus = Field(default=SprintStatus.INITIALIZED, description="Current status")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    start_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="Start date (YYYY-MM-DD)")
    end_date: str = Field(..., pattern=r'^\d{4}-\d{2}-\d{2}$', description="End date (YYYY-MM-DD)")
    duration_days: int = Field(..., ge=1, le=999, description="Duration in days")
    work_items: List[str] = Field(default_factory=list, description="List of work item IDs")
    gates: Dict[str, GateModel] = Field(default_factory=dict, description="Gate configurations")
    validation_token: Optional[str] = Field(default=None, max_length=100, description="Validation token")
    risk_score: Optional[float] = Field(default=None, ge=0.0, le=5.0, description="Risk score (0.0-5.0)")
    current_gate: int = Field(default=1, ge=1, le=5, description="Current gate number")
    max_parallel: Optional[int] = Field(default=None, ge=1, le=10, description="Max parallel work items")
    started_at: Optional[datetime] = Field(default=None, description="Start timestamp")
    completed_at: Optional[datetime] = Field(default=None, description="Completion timestamp")
    archived_at: Optional[datetime] = Field(default=None, description="Archive timestamp")
    last_agent_result: Optional[Dict[str, Any]] = Field(default=None, description="Last agent result")
```

**Validation Rules:**
- Sprint ID must be alphanumeric with underscores/hyphens only
- Dates must follow YYYY-MM-DD format
- Duration must be 1-999 days
- Risk score must be 0.0-5.0
- End date must be after start date

---

### Validation Functions

#### validate_work_item

```python
def validate_work_item(data: Dict[str, Any]) -> WorkItemModel
```

Validate work item data using Pydantic model.

**Parameters:**
- `data` (Dict[str, Any]): Work item data dictionary

**Returns:**
- `WorkItemModel`: Validated WorkItemModel instance

**Raises:**
- `ValueError`: If validation fails

---

#### validate_sprint

```python
def validate_sprint(data: Dict[str, Any]) -> SprintModel
```

Validate sprint data using Pydantic model.

**Parameters:**
- `data` (Dict[str, Any]): Sprint data dictionary

**Returns:**
- `SprintModel`: Validated SprintModel instance

**Raises:**
- `ValueError`: If validation fails

---

#### validate_and_clean_work_item

```python
def validate_and_clean_work_item(data: Dict[str, Any]) -> Dict[str, Any]
```

Validate work item data and return cleaned dictionary.

**Parameters:**
- `data` (Dict[str, Any]): Work item data dictionary

**Returns:**
- `Dict[str, Any]`: Cleaned and validated work item dictionary

---

#### validate_and_clean_sprint

```python
def validate_and_clean_sprint(data: Dict[str, Any]) -> Dict[str, Any]
```

Validate sprint data and return cleaned dictionary.

**Parameters:**
- `data` (Dict[str, Any]): Sprint data dictionary

**Returns:**
- `Dict[str, Any]`: Cleaned and validated sprint dictionary

---

## transaction

**Module Path:** `carby_sprint.transaction`

Atomic Transaction Manager for Sprint Operations. Implements atomic updates using copy-on-write pattern with backup and rollback capabilities for reliability in concurrent environments.

### Overview

The transaction module provides atomic update capabilities for sprint operations using a copy-on-write pattern. It ensures data integrity during concurrent operations with backup and rollback capabilities.

### Exceptions

```python
class TransactionError(Exception):
    """Raised when a transaction operation fails."""
```

### Context Managers

#### atomic_sprint_update

```python
@contextmanager
def atomic_sprint_update(
    sprint_path: Path,
    backup_on_failure: bool = True,
    create_backup: bool = True
) -> Generator[Dict[str, Any], None, None]
```

Context manager for atomic sprint updates using copy-on-write pattern. Thread-safe with unique temp directories per transaction.

**Parameters:**
- `sprint_path` (Path): Path to the sprint directory containing metadata.json
- `backup_on_failure` (bool): Whether to create backup on transaction failure
- `create_backup` (bool): Whether to create initial backup before modification

**Yields:**
- `Dict[str, Any]`: Sprint data dict for modification

**Raises:**
- `TransactionError`: If transaction fails and rollback is needed

**Example:**
```python
from carby_sprint.transaction import atomic_sprint_update
from pathlib import Path

sprint_path = Path(".carby-sprints/my-sprint")
with atomic_sprint_update(sprint_path) as sprint_data:
    sprint_data["status"] = "completed"
    sprint_data["completed_at"] = "2026-03-30T10:30:00Z"
```

---

#### atomic_work_item_update

```python
@contextmanager
def atomic_work_item_update(
    work_items_dir: Path,
    work_item_id: str
) -> Generator[Dict[str, Any], None, None]
```

Context manager for atomic work item updates.

**Parameters:**
- `work_items_dir` (Path): Directory containing work item files
- `work_item_id` (str): ID of the work item to update

**Yields:**
- `Dict[str, Any]`: Work item data dict for modification

---

### Utility Functions

#### validate_gate_transition

```python
def validate_gate_transition(
    current_gate_status: str,
    target_status: str,
    allowed_transitions: Optional[Dict[str, list]] = None
) -> bool
```

Validate gate status transition according to business rules.

**Parameters:**
- `current_gate_status` (str): Current status of the gate
- `target_status` (str): Desired new status
- `allowed_transitions` (Optional[Dict[str, list]]): Custom transition rules (uses defaults if None)

**Returns:**
- `bool`: True if transition is valid, False otherwise

**Default Transitions:**
```python
{
    "pending": ["in_progress", "skipped"],
    "in_progress": ["passed", "failed", "blocked"],
    "blocked": ["in_progress", "failed"],
    "failed": ["in_progress", "skipped"],
    "passed": [],
    "skipped": []
}
```

---

#### validate_work_item_exists

```python
def validate_work_item_exists(
    work_items_dir: Path,
    work_item_id: str
) -> bool
```

Validate that a work item exists.

**Parameters:**
- `work_items_dir` (Path): Directory containing work item files
- `work_item_id` (str): ID of the work item to check

**Returns:**
- `bool`: True if work item exists, False otherwise

---

#### ensure_directory_structure

```python
def ensure_directory_structure(sprint_path: Path) -> None
```

Ensure all required sprint directories exist.

**Parameters:**
- `sprint_path` (Path): Path to the sprint directory

---

## lock_manager

**Module Path:** `carby_sprint.lock_manager`

Distributed Lock Manager for Carby Sprint Framework. Provides file-based distributed locking using portalocker to prevent race conditions during concurrent sprint operations.

### Overview

The lock_manager module implements distributed locking using file-based locks with portalocker. This prevents race conditions during concurrent sprint operations.

### Classes

#### DistributedLock

```python
class DistributedLock:
    """
    Distributed lock using file-based locking with portalocker.
    """
    
    def __init__(self, lock_file_path: str | Path)
```

**Parameters:**
- `lock_file_path` (str | Path): Path to the lock file

**Usage:**
```python
from carby_sprint.lock_manager import DistributedLock

with DistributedLock("/path/to/lockfile") as lock:
    # Critical section code here
    pass
```

---

### Decorators

#### with_sprint_lock

```python
def with_sprint_lock(lock_path_func: Callable[[str], str])
```

Decorator to wrap functions with distributed locking.

**Parameters:**
- `lock_path_func` (Callable[[str], str]): Function that takes sprint_id and returns the path to the lock file

**Example:**
```python
from carby_sprint.lock_manager import with_sprint_lock

def my_lock_path_func(sprint_id: str) -> str:
    return f".carby-sprints/{sprint_id}/.lock"

@with_sprint_lock(my_lock_path_func)
def update_sprint(sprint_id: str, data: dict):
    # This function will be executed with a distributed lock
    pass
```

---

### Context Managers

#### acquire_sprint_lock

```python
@contextmanager
def acquire_sprint_lock(sprint_id: str, lock_path_func: Callable[[str], str])
```

Context manager to acquire a sprint lock.

**Parameters:**
- `sprint_id` (str): Sprint identifier
- `lock_path_func` (Callable[[str], str]): Function that takes sprint_id and returns the path to the lock file

---

### Lock Path Generators

#### default_sprint_lock_path

```python
def default_sprint_lock_path(sprint_id: str) -> str
```

Generate default lock file path for a sprint.

**Parameters:**
- `sprint_id` (str): Sprint identifier

**Returns:**
- `str`: Default lock file path

---

#### execution_lock_path

```python
def execution_lock_path(sprint_id: str) -> str
```

Generate execution lock file path for a sprint.

**Parameters:**
- `sprint_id` (str): Sprint identifier

**Returns:**
- `str`: Execution lock file path

---

## sprint_repository

**Module Path:** `carby_sprint.sprint_repository`

Sprint Repository - Centralized sprint data access layer. Provides a unified interface for loading, saving, and managing sprint data. Eliminates code duplication across CLI commands and maintains backward compatibility with existing function-based API.

### Overview

The sprint_repository module provides a centralized data access layer for sprint operations. It handles all file operations for loading, saving, and managing sprint data with validation and atomic transactions.

### Classes

#### SprintPaths

```python
@dataclass
class SprintPaths:
    """Container for sprint-related file paths."""
    sprint_dir: Path
    metadata: Path
    work_items: Path
    gates: Path
    logs: Path

    @property
    def execution_lock(self) -> Path:
        """Path to execution lock file."""
        return self.sprint_dir / ".execution.lock"
```

---

#### SprintRepository

```python
class SprintRepository:
    """
    Repository for sprint data access and manipulation.
    """
    
    DEFAULT_OUTPUT_DIR = ".carby-sprints"

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR)
```

**Parameters:**
- `output_dir` (str): Base directory for sprint data storage

---

#### Methods

##### get_sprint_path

```python
def get_sprint_path(self, sprint_id: str) -> Path
```

Get the path to a sprint directory with validation.

**Parameters:**
- `sprint_id` (str): Sprint identifier

**Returns:**
- `Path`: Path to sprint directory

---

##### get_paths

```python
def get_paths(self, sprint_id: str) -> SprintPaths
```

Get all relevant paths for a sprint.

**Parameters:**
- `sprint_id` (str): Sprint identifier

**Returns:**
- `SprintPaths`: Container with all sprint-related paths

---

##### exists

```python
def exists(self, sprint_id: str) -> bool
```

Check if a sprint exists with validation.

**Parameters:**
- `sprint_id` (str): Sprint identifier

**Returns:**
- `bool`: True if sprint exists, False otherwise

---

##### load

```python
def load(self, sprint_id: str) -> Tuple[Dict[str, Any], SprintPaths]
```

Load sprint metadata.

**Parameters:**
- `sprint_id` (str): The sprint identifier

**Returns:**
- `Tuple[Dict[str, Any], SprintPaths]`: (sprint_data, paths)

**Raises:**
- `FileNotFoundError`: If sprint not found

---

##### load_or_raise

```python
def load_or_raise(
    self, 
    sprint_id: str, 
    exception_class: type | None = None, 
    message: str | None = None
) -> tuple[dict[str, Any], SprintPaths]
```

Load sprint with custom exception handling.

**Parameters:**
- `sprint_id` (str): The sprint identifier
- `exception_class` (type | None): Exception class to raise (default: FileNotFoundError)
- `message` (str | None): Custom error message

**Returns:**
- `tuple[dict[str, Any], SprintPaths]`: (sprint_data, paths)

---

##### save

```python
def save(self, sprint_data: Dict[str, Any], paths: SprintPaths) -> None
```

Save sprint metadata with validation and atomic transaction.

**Parameters:**
- `sprint_data` (Dict[str, Any]): Sprint data dictionary
- `paths` (SprintPaths): SprintPaths object

---

##### save_by_id

```python
def save_by_id(self, sprint_id: str, sprint_data: Dict[str, Any]) -> None
```

Save sprint metadata by sprint ID with locking and atomic transaction.

**Parameters:**
- `sprint_id` (str): The sprint identifier
- `sprint_data` (Dict[str, Any]): Sprint data dictionary

---

##### create

```python
def create(
    self,
    sprint_id: str,
    project: str,
    goal: str,
    description: str = "",
    duration_days: int = 14,
    start_date: Optional[datetime] = None,
) -> Tuple[Dict[str, Any], SprintPaths]
```

Create a new sprint.

**Parameters:**
- `sprint_id` (str): Unique sprint identifier
- `project` (str): Project name
- `goal` (str): Sprint goal
- `description` (str): Optional description
- `duration_days` (int): Sprint duration in days
- `start_date` (Optional[datetime]): Optional start date (defaults to now)

**Returns:**
- `Tuple[Dict[str, Any], SprintPaths]`: (sprint_data, paths)

---

##### delete

```python
def delete(self, sprint_id: str) -> None
```

Delete a sprint directory.

**Parameters:**
- `sprint_id` (str): Sprint to delete

---

##### archive

```python
def archive(
    self,
    sprint_id: str,
    archive_dir: Path,
    update_status: bool = True,
) -> Path
```

Archive a sprint.

**Parameters:**
- `sprint_id` (str): Sprint to archive
- `archive_dir` (Path): Destination directory
- `update_status` (bool): Whether to update status to 'archived'

**Returns:**
- `Path`: Path to archived sprint

---

##### load_work_item

```python
def load_work_item(self, paths: SprintPaths, work_item_id: str) -> Dict[str, Any]
```

Load a work item with path validation.

**Parameters:**
- `paths` (SprintPaths): Sprint paths container
- `work_item_id` (str): Work item ID to load

**Returns:**
- `Dict[str, Any]`: Work item data

---

##### save_work_item

```python
def save_work_item(self, paths: SprintPaths, work_item: Dict[str, Any]) -> None
```

Save a work item with validation and atomic transaction.

**Parameters:**
- `paths` (SprintPaths): Sprint paths container
- `work_item` (Dict[str, Any]): Work item data to save

---

##### list_work_items

```python
def list_work_items(self, paths: SprintPaths) -> list[str]
```

List all work item IDs.

**Parameters:**
- `paths` (SprintPaths): Sprint paths container

**Returns:**
- `list[str]`: List of work item IDs

---

##### delete_work_item

```python
def delete_work_item(self, paths: SprintPaths, work_item_id: str) -> None
```

Delete a work item with path validation.

**Parameters:**
- `paths` (SprintPaths): Sprint paths container
- `work_item_id` (str): Work item ID to delete

---

### Backward Compatibility Functions

#### get_sprint_path (deprecated)

```python
def get_sprint_path(sprint_id: str, output_dir: str = SprintRepository.DEFAULT_OUTPUT_DIR) -> Path
```

Get the path to a sprint directory.

**DEPRECATED:** Use `SprintRepository.get_sprint_path()` instead.

---

#### load_sprint (deprecated)

```python
def load_sprint(sprint_id: str, output_dir: str = SprintRepository.DEFAULT_OUTPUT_DIR) -> Tuple[Dict[str, Any], Path]
```

Load sprint metadata.

**DEPRECATED:** Use `SprintRepository.load()` instead.
Returns tuple of (sprint_data, sprint_path) for backward compatibility.

---

#### save_sprint (deprecated)

```python
def save_sprint(sprint_data: Dict[str, Any], sprint_path: Path) -> None
```

Save sprint metadata.

**DEPRECATED:** Use `SprintRepository.save()` instead.