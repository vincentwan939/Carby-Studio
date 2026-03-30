"""
Carby Sprint - CLI for sprint management with validation gates.

A production-ready CLI tool for managing sprints with integrated
validation gates, documentation compliance, and parallel execution.
"""

from __future__ import annotations

__version__ = "2.0.2"
__author__ = "Carby Studio"
__license__ = "MIT"

from .cli import cli
from .sprint_repository import SprintRepository, SprintPaths
from .agent_callback import report_agent_result
from .lock_manager import with_sprint_lock, DistributedLock, LockTimeoutError
from .validators import (
    validate_sprint, validate_work_item, SprintModel, WorkItemModel,
    validate_work_item_state_transition, get_valid_work_item_transitions,
    WORK_ITEM_VALID_TRANSITIONS
)
from .path_utils import validate_sprint_id, validate_work_item_id, generate_work_item_id
from .gate_state import GateStateManager, StateIntegrityManager, StateTamperError
from .transaction_boundary import (
    TransactionBoundaryManager,
    TransactionBoundary,
    TransactionType,
    TransactionResult,
    TransactionBoundaryError,
    NestedTransactionError,
    TransactionScopeError,
    get_boundary_manager,
    requires_transaction,
    requires_no_transaction,
)

__all__ = [
    "cli",
    "SprintRepository",
    "SprintPaths",
    "report_agent_result",
    "with_sprint_lock",
    "DistributedLock",
    "LockTimeoutError",
    "validate_sprint",
    "validate_work_item",
    "SprintModel",
    "WorkItemModel",
    "validate_work_item_state_transition",
    "get_valid_work_item_transitions",
    "WORK_ITEM_VALID_TRANSITIONS",
    "validate_sprint_id",
    "validate_work_item_id",
    "generate_work_item_id",
    "phase_lock",
    "design_gate",
    "gate_state",
    "gate_token",
    "gate_enforcer",
    "GateStateManager",
    "StateIntegrityManager",
    "StateTamperError",
    # Transaction Boundary
    "TransactionBoundaryManager",
    "TransactionBoundary",
    "TransactionType",
    "TransactionResult",
    "TransactionBoundaryError",
    "NestedTransactionError",
    "TransactionScopeError",
    "get_boundary_manager",
    "requires_transaction",
    "requires_no_transaction",
]
