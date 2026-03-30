"""
Pydantic Models for Carby Sprint Framework Validation.

Provides data validation models for sprint and work item data structures.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator


class SprintStatus(str, Enum):
    """Valid sprint statuses."""
    INITIALIZED = "initialized"
    RUNNING = "running"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class WorkItemStatus(str, Enum):
    """Valid work item statuses."""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


# Valid work item state transitions
# Defines which states can transition to which other states
WORK_ITEM_VALID_TRANSITIONS: Dict[str, List[str]] = {
    WorkItemStatus.PLANNED.value: [WorkItemStatus.IN_PROGRESS.value, WorkItemStatus.CANCELLED.value],
    WorkItemStatus.IN_PROGRESS.value: [
        WorkItemStatus.COMPLETED.value,
        WorkItemStatus.FAILED.value,
        WorkItemStatus.BLOCKED.value,
        WorkItemStatus.CANCELLED.value
    ],
    WorkItemStatus.BLOCKED.value: [
        WorkItemStatus.IN_PROGRESS.value,
        WorkItemStatus.FAILED.value,
        WorkItemStatus.CANCELLED.value
    ],
    WorkItemStatus.FAILED.value: [
        WorkItemStatus.IN_PROGRESS.value,
        WorkItemStatus.CANCELLED.value
    ],
    WorkItemStatus.COMPLETED.value: [],  # Terminal state - no transitions allowed
    WorkItemStatus.CANCELLED.value: [],  # Terminal state - no transitions allowed
}


class GateStatus(str, Enum):
    """Valid gate statuses."""
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"
    PASS_WITH_WARNINGS = "passed_with_warnings"


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
    
    @field_validator('id')
    def validate_id(cls, v):
        """Validate work item ID format."""
        if not v:
            raise ValueError('ID cannot be empty')
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('ID cannot contain path traversal characters (.., /, \\)')
        return v
    
    @field_validator('title')
    def validate_title(cls, v):
        """Validate work item title."""
        if not v.strip():
            raise ValueError('Title cannot be empty or whitespace')
        return v.strip()
    
    @model_validator(mode='after')
    def validate_timestamps(self):
        """Validate timestamp consistency."""
        status = self.status
        started_at = self.started_at
        completed_at = self.completed_at
        failed_at = self.failed_at
        blocked_at = self.blocked_at
        cancelled_at = self.cancelled_at
        
        # Validate status-specific timestamp requirements
        if status == WorkItemStatus.IN_PROGRESS and not started_at:
            raise ValueError('started_at is required for in_progress status')
        elif status == WorkItemStatus.COMPLETED and not completed_at:
            raise ValueError('completed_at is required for completed status')
        elif status == WorkItemStatus.FAILED and not failed_at:
            raise ValueError('failed_at is required for failed status')
        elif status == WorkItemStatus.BLOCKED and not blocked_at:
            raise ValueError('blocked_at is required for blocked status')
        elif status == WorkItemStatus.CANCELLED and not cancelled_at:
            raise ValueError('cancelled_at is required for cancelled status')
        
        # Validate timestamp ordering
        if completed_at and started_at and completed_at < started_at:
            raise ValueError('completed_at cannot be before started_at')
        if failed_at and started_at and failed_at < started_at:
            raise ValueError('failed_at cannot be before started_at')
        if blocked_at and started_at and blocked_at < started_at:
            raise ValueError('blocked_at cannot be before started_at')
        
        return self


class GateModel(BaseModel):
    """Pydantic model for gate validation."""
    
    status: GateStatus = Field(default=GateStatus.PENDING, description="Current status")
    name: str = Field(..., min_length=1, max_length=100, description="Gate name")
    description: Optional[str] = Field(default=None, max_length=500, description="Gate description")
    passed_at: Optional[datetime] = Field(default=None, description="Pass timestamp")
    failed_at: Optional[datetime] = Field(default=None, description="Fail timestamp")
    blocked_at: Optional[datetime] = Field(default=None, description="Block timestamp")
    
    @field_validator('name')
    def validate_name(cls, v):
        """Validate gate name."""
        if not v.strip():
            raise ValueError('Name cannot be empty or whitespace')
        return v.strip()


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
    
    @field_validator('sprint_id')
    def validate_sprint_id(cls, v):
        """Validate sprint ID format."""
        if not v:
            raise ValueError('Sprint ID cannot be empty')
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Sprint ID cannot contain path traversal characters (.., /, \\)')
        return v
    
    @field_validator('project', 'goal')
    def validate_required_fields(cls, v):
        """Validate required fields."""
        if not v.strip():
            raise ValueError('Field cannot be empty or whitespace')
        return v.strip()
    
    @field_validator('duration_days')
    def validate_duration(cls, v):
        """Validate duration."""
        if v <= 0:
            raise ValueError('Duration must be positive')
        return v
    
    @model_validator(mode='after')
    def validate_dates(self):
        """Validate date relationships."""
        start_date_str = self.start_date
        end_date_str = self.end_date
        
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
                
                if end_date < start_date:
                    raise ValueError('End date cannot be before start date')
            except ValueError:
                raise ValueError('Invalid date format or relationship')
        
        return self
    
    @model_validator(mode='after')
    def validate_status_transitions(self):
        """Validate status transitions."""
        status = self.status
        started_at = self.started_at
        completed_at = self.completed_at
        archived_at = self.archived_at
        
        # Validate status-specific requirements
        if status == SprintStatus.IN_PROGRESS and not started_at:
            raise ValueError('started_at is required for in_progress status')
        elif status == SprintStatus.COMPLETED and not completed_at:
            raise ValueError('completed_at is required for completed status')
        elif status == SprintStatus.ARCHIVED and not archived_at:
            raise ValueError('archived_at is required for archived status')
        
        return self


def validate_work_item(data: Dict[str, Any]) -> WorkItemModel:
    """
    Validate work item data using Pydantic model.
    
    Args:
        data: Work item data dictionary
        
    Returns:
        Validated WorkItemModel instance
        
    Raises:
        ValueError: If validation fails
    """
    try:
        return WorkItemModel(**data)
    except Exception as e:
        raise ValueError(f"Work item validation failed: {str(e)}")


def validate_sprint(data: Dict[str, Any]) -> SprintModel:
    """
    Validate sprint data using Pydantic model.
    
    Args:
        data: Sprint data dictionary
        
    Returns:
        Validated SprintModel instance
        
    Raises:
        ValueError: If validation fails
    """
    try:
        return SprintModel(**data)
    except Exception as e:
        raise ValueError(f"Sprint validation failed: {str(e)}")


def validate_and_clean_work_item(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate work item data and return cleaned dictionary.
    
    Args:
        data: Work item data dictionary
        
    Returns:
        Cleaned and validated work item dictionary
    """
    validated = validate_work_item(data)
    return validated.dict()


def validate_and_clean_sprint(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate sprint data and return cleaned dictionary.
    
    Args:
        data: Sprint data dictionary
        
    Returns:
        Cleaned and validated sprint dictionary
    """
    validated = validate_sprint(data)
    return validated.dict()


def validate_work_item_state_transition(
    current_state: str,
    new_state: str,
    allowed_transitions: Optional[Dict[str, List[str]]] = None
) -> bool:
    """
    Validate work item state transition according to business rules.
    
    Args:
        current_state: Current state of the work item
        new_state: Desired new state
        allowed_transitions: Custom transition rules (uses defaults if None)
        
    Returns:
        True if transition is valid, False otherwise
        
    Example:
        >>> validate_work_item_state_transition("planned", "in_progress")
        True
        >>> validate_work_item_state_transition("completed", "in_progress")
        False
    """
    if allowed_transitions is None:
        allowed_transitions = WORK_ITEM_VALID_TRANSITIONS
    
    if current_state not in allowed_transitions:
        return False
    
    return new_state in allowed_transitions[current_state]


def get_valid_work_item_transitions(current_state: str) -> List[str]:
    """
    Get list of valid states that can be transitioned to from current state.
    
    Args:
        current_state: Current state of the work item
        
    Returns:
        List of valid target states
        
    Example:
        >>> get_valid_work_item_transitions("in_progress")
        ['completed', 'failed', 'blocked', 'cancelled']
    """
    return WORK_ITEM_VALID_TRANSITIONS.get(current_state, [])