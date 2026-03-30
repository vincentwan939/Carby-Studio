"""
Transaction Boundary Definitions for Carby Studio Workflow System.

This module provides clear transaction boundary definitions and demarcation
helpers to ensure proper transaction management with the two-phase commit system.

Transaction Types:
1. SINGLE_FILE_TRANSACTION: Atomic updates to a single file (metadata.json, work_item.json)
2. DISTRIBUTED_TRANSACTION: Updates across multiple state files using Two-Phase Commit
3. NESTED_TRANSACTION: Composition of transactions (avoided via save_work_item_direct)

Transaction Boundaries:
- Each transaction has a clear BEGIN and COMMIT/ROLLBACK point
- Transactions cannot overlap (no nested transactions)
- Distributed transactions use 2PC coordinator for atomicity across files
"""

from __future__ import annotations

import functools
import json
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Set, Tuple, Union

from .transaction import atomic_sprint_update, atomic_work_item_update, TransactionError
from .two_phase_commit import (
    TwoPhaseCommitCoordinator,
    StateFileParticipant,
    TwoPhaseCommitError,
    create_state_participants,
    Participant
)


class TransactionType(Enum):
    """Types of transactions supported by the system."""
    SINGLE_FILE = auto()      # Atomic update to a single file
    DISTRIBUTED = auto()      # Two-phase commit across multiple files
    READ_ONLY = auto()        # No transaction, just reading


class TransactionBoundaryError(Exception):
    """Raised when transaction boundaries are violated."""
    pass


class NestedTransactionError(TransactionBoundaryError):
    """Raised when a nested transaction is attempted."""
    pass


class TransactionScopeError(TransactionBoundaryError):
    """Raised when operations are performed outside transaction boundaries."""
    pass


@dataclass
class TransactionResult:
    """Result of a distributed transaction.
    
    Attributes:
        success: Whether transaction succeeded
        transaction_id: Unique transaction ID
        phase1_result: Result of Phase 1 (prepare)
        phase2_result: Result of Phase 2 (commit/rollback)
        error: Error message if transaction failed
        participants: List of participant names
    """
    success: bool
    transaction_id: Optional[str] = None
    phase1_result: Optional[str] = None
    phase2_result: Optional[str] = None
    error: Optional[str] = None
    participants: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.participants is None:
            self.participants = []


@dataclass
class TransactionBoundary:
    """Defines the boundaries of a transaction.
    
    Attributes:
        tx_type: Type of transaction
        participant_files: Files participating in this transaction
        coordinator: 2PC coordinator for distributed transactions
        parent_tx_id: ID of parent transaction (for tracking, not nesting)
    """
    tx_type: TransactionType
    participant_files: Set[Path]
    coordinator: Optional[TwoPhaseCommitCoordinator] = None
    tx_id: Optional[str] = None
    _active: bool = False
    
    def begin(self) -> None:
        """Mark transaction as active."""
        if self._active:
            raise TransactionBoundaryError(f"Transaction {self.tx_id} already active")
        self._active = True
    
    def commit(self) -> None:
        """Mark transaction as committed."""
        self._active = False
    
    def rollback(self) -> None:
        """Mark transaction as rolled back."""
        self._active = False
    
    @property
    def is_active(self) -> bool:
        """Check if transaction is currently active."""
        return self._active


class TransactionBoundaryManager:
    """Manages transaction boundaries and prevents nesting violations.
    
    This class ensures:
    1. Clear transaction demarcation (BEGIN -> COMMIT/ROLLBACK)
    2. No nested transactions (enforced at runtime)
    3. Proper cleanup on exit (success or failure)
    4. Transaction boundary validation
    
    Usage:
        with TransactionBoundaryManager() as mgr:
            # Begin a distributed transaction
            with mgr.distributed_transaction(project_dir, [file1, file2]) as boundary:
                # Perform operations within clear boundaries
                boundary.update_file(file1, new_data1)
                boundary.update_file(file2, new_data2)
            # Transaction automatically commits or rolls back
    """
    
    def __init__(self):
        self._active_boundaries: List[TransactionBoundary] = []
        self._tx_stack: List[str] = []
    
    def _check_no_active_transaction(self) -> None:
        """Ensure no transaction is currently active."""
        if self._active_boundaries:
            active = self._active_boundaries[-1]
            raise NestedTransactionError(
                f"Cannot start new transaction while {active.tx_type.name} "
                f"transaction is active (tx_id: {active.tx_id})"
            )
    
    def _register_boundary(self, boundary: TransactionBoundary) -> None:
        """Register a new transaction boundary."""
        self._check_no_active_transaction()
        self._active_boundaries.append(boundary)
        boundary.begin()
    
    def _unregister_boundary(self, boundary: TransactionBoundary) -> None:
        """Unregister a transaction boundary."""
        if self._active_boundaries and self._active_boundaries[-1] == boundary:
            self._active_boundaries.pop()
    
    @contextmanager
    def single_file_transaction(
        self,
        sprint_path: Path,
        backup_on_failure: bool = True
    ) -> Generator[Dict[str, Any], None, None]:
        """Context manager for single-file atomic transactions.
        
        Uses atomic_sprint_update for atomic updates to metadata.json.
        
        Args:
            sprint_path: Path to sprint directory
            backup_on_failure: Whether to create backup on failure
            
        Yields:
            Sprint data dictionary for modification
            
        Raises:
            NestedTransactionError: If another transaction is active
            TransactionError: If transaction fails
        """
        self._check_no_active_transaction()
        
        boundary = TransactionBoundary(
            tx_type=TransactionType.SINGLE_FILE,
            participant_files={sprint_path / "metadata.json"},
            tx_id=f"single_{id(self)}"
        )
        
        try:
            self._register_boundary(boundary)
            with atomic_sprint_update(sprint_path, backup_on_failure) as data:
                yield data
            boundary.commit()
        except Exception as e:
            boundary.rollback()
            raise TransactionError(f"Single-file transaction failed: {e}") from e
        finally:
            self._unregister_boundary(boundary)
    
    @contextmanager
    def work_item_transaction(
        self,
        work_items_dir: Path,
        work_item_id: str
    ) -> Generator[Dict[str, Any], None, None]:
        """Context manager for work item atomic transactions.
        
        Uses atomic_work_item_update for atomic updates to work item files.
        
        Args:
            work_items_dir: Directory containing work item files
            work_item_id: ID of work item to update
            
        Yields:
            Work item data dictionary for modification
            
        Raises:
            NestedTransactionError: If another transaction is active
            TransactionError: If transaction fails
        """
        self._check_no_active_transaction()
        
        wi_path = work_items_dir / f"{work_item_id}.json"
        boundary = TransactionBoundary(
            tx_type=TransactionType.SINGLE_FILE,
            participant_files={wi_path},
            tx_id=f"wi_{work_item_id}_{id(self)}"
        )
        
        try:
            self._register_boundary(boundary)
            with atomic_work_item_update(work_items_dir, work_item_id) as data:
                yield data
            boundary.commit()
        except Exception as e:
            boundary.rollback()
            raise TransactionError(f"Work item transaction failed: {e}") from e
        finally:
            self._unregister_boundary(boundary)
    
    @contextmanager
    def distributed_transaction(
        self,
        project_dir: Path,
        participant_configs: List[Tuple[str, Path, Callable[[Dict[str, Any]], Dict[str, Any]]]],
        timeout_seconds: float = 30.0
    ) -> Generator[TransactionResult, None, None]:
        """Context manager for distributed transactions using Two-Phase Commit.
        
        Uses TwoPhaseCommitCoordinator for atomic updates across multiple state files.
        
        Args:
            project_dir: Project directory for transaction logs
            participant_configs: List of (name, file_path, update_fn) tuples
            timeout_seconds: Maximum time to wait for transaction
            
        Yields:
            TransactionResult with success status and details
            
        Raises:
            NestedTransactionError: If another transaction is active
            TwoPhaseCommitError: If 2PC fails
        """
        self._check_no_active_transaction()
        
        participant_files = {cfg[1] for cfg in participant_configs}
        coordinator = TwoPhaseCommitCoordinator(project_dir)
        
        boundary = TransactionBoundary(
            tx_type=TransactionType.DISTRIBUTED,
            participant_files=participant_files,
            coordinator=coordinator,
            tx_id=f"dist_{id(self)}"
        )
        
        # Create participants
        participants = []
        for name, file_path, update_fn in participant_configs:
            participant = StateFileParticipant(
                name=name,
                file_path=file_path,
                update_fn=update_fn
            )
            participants.append(participant.to_participant())
        
        try:
            self._register_boundary(boundary)
            result = coordinator.execute_transaction(participants, timeout_seconds)
            
            tx_result = TransactionResult(
                success=result["success"],
                transaction_id=result.get("transaction_id"),
                phase1_result=result.get("phase1_result"),
                phase2_result=result.get("phase2_result"),
                error=result.get("error"),
                participants=[p["name"] for p in result.get("participants", [])]
            )
            
            if result["success"]:
                boundary.commit()
            else:
                boundary.rollback()
                raise TwoPhaseCommitError(
                    f"Distributed transaction failed: {result.get('error')}"
                )
            
            yield tx_result
            
        except Exception as e:
            boundary.rollback()
            if isinstance(e, TwoPhaseCommitError):
                raise
            raise TwoPhaseCommitError(f"Distributed transaction error: {e}") from e
        finally:
            self._unregister_boundary(boundary)
    
    @property
    def has_active_transaction(self) -> bool:
        """Check if any transaction is currently active."""
        return len(self._active_boundaries) > 0
    
    @property
    def active_transaction_type(self) -> Optional[TransactionType]:
        """Get the type of currently active transaction, if any."""
        if self._active_boundaries:
            return self._active_boundaries[-1].tx_type
        return None
    
    def assert_within_transaction(self) -> None:
        """Assert that code is executing within a transaction boundary.
        
        Raises:
            TransactionScopeError: If not within a transaction
        """
        if not self._active_boundaries:
            raise TransactionScopeError(
                "Operation must be performed within a transaction boundary"
            )
    
    def assert_no_transaction(self) -> None:
        """Assert that no transaction is currently active.
        
        Raises:
            NestedTransactionError: If a transaction is active
        """
        if self._active_boundaries:
            raise NestedTransactionError(
                f"Expected no active transaction but found {self.active_transaction_type.name}"
            )


# Global transaction boundary manager instance
_boundary_manager: Optional[TransactionBoundaryManager] = None


def get_boundary_manager() -> TransactionBoundaryManager:
    """Get the global transaction boundary manager instance."""
    global _boundary_manager
    if _boundary_manager is None:
        _boundary_manager = TransactionBoundaryManager()
    return _boundary_manager


def reset_boundary_manager() -> None:
    """Reset the global boundary manager (useful for testing)."""
    global _boundary_manager
    _boundary_manager = None


# Decorators for transaction boundary enforcement

def requires_transaction(func: Callable) -> Callable:
    """Decorator that requires function to be called within a transaction.
    
    Example:
        @requires_transaction
        def update_work_item(work_item_id: str, data: dict):
            # This will raise TransactionScopeError if called outside transaction
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        mgr = get_boundary_manager()
        mgr.assert_within_transaction()
        return func(*args, **kwargs)
    return wrapper


def requires_no_transaction(func: Callable) -> Callable:
    """Decorator that requires function to be called outside any transaction.
    
    Example:
        @requires_no_transaction
        def begin_new_operation():
            # This will raise NestedTransactionError if called within transaction
            pass
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        mgr = get_boundary_manager()
        mgr.assert_no_transaction()
        return func(*args, **kwargs)
    return wrapper


# Helper functions for common transaction patterns

def with_single_file_transaction(
    sprint_path: Path,
    operation: Callable[[Dict[str, Any]], Dict[str, Any]],
    backup_on_failure: bool = True
) -> Dict[str, Any]:
    """Execute an operation within a single-file transaction.
    
    Args:
        sprint_path: Path to sprint directory
        operation: Function that takes and returns sprint data
        backup_on_failure: Whether to create backup on failure
        
    Returns:
        Updated sprint data
        
    Raises:
        TransactionError: If transaction fails
    """
    mgr = get_boundary_manager()
    with mgr.single_file_transaction(sprint_path, backup_on_failure) as data:
        result = operation(data)
        data.clear()
        data.update(result)
        return dict(data)


def with_distributed_transaction(
    project_dir: Path,
    participant_configs: List[Tuple[str, Path, Callable[[Dict[str, Any]], Dict[str, Any]]]],
    timeout_seconds: float = 30.0
) -> TransactionResult:
    """Execute a distributed transaction with Two-Phase Commit.
    
    Args:
        project_dir: Project directory for transaction logs
        participant_configs: List of (name, file_path, update_fn) tuples
        timeout_seconds: Maximum time to wait for transaction
        
    Returns:
        TransactionResult with success status and details
        
    Raises:
        TwoPhaseCommitError: If transaction fails
    """
    mgr = get_boundary_manager()
    with mgr.distributed_transaction(project_dir, participant_configs, timeout_seconds) as result:
        return result


# Transaction boundary documentation helpers

class TransactionBoundaryDocs:
    """Documentation for transaction boundaries in Carby Studio.
    
    This class provides clear documentation of where transaction boundaries
    should be defined in the codebase.
    
    Transaction Boundaries:
    
    1. SPRINT LEVEL (metadata.json)
       - BEGIN: atomic_sprint_update() or mgr.single_file_transaction()
       - OPERATIONS: Update sprint metadata
       - COMMIT/ROLLBACK: Automatic on context exit
       
    2. WORK ITEM LEVEL (work_items/{id}.json)
       - BEGIN: atomic_work_item_update() or mgr.work_item_transaction()
       - OPERATIONS: Update work item data
       - COMMIT/ROLLBACK: Automatic on context exit
       - NOTE: When inside sprint transaction, use save_work_item_direct()
       
    3. DISTRIBUTED (Multiple files)
       - BEGIN: mgr.distributed_transaction() or TwoPhaseCommitCoordinator
       - OPERATIONS: Updates across phase_lock.json, metadata.json, gate-status.json
       - COMMIT/ROLLBACK: Two-phase commit (prepare -> commit/rollback)
       
    4. AGENT CALLBACKS
       - BEGIN: atomic_sprint_update() in report_agent_result()
       - OPERATIONS: Update work items via save_work_item_direct()
       - COMMIT/ROLLBACK: Automatic on context exit
       - ENFORCEMENT: Nested transactions prevented by design
    
    Anti-patterns to avoid:
    - NEVER: Start a transaction inside another transaction
    - NEVER: Call save_work_item() inside atomic_sprint_update()
    - NEVER: Mix transaction types without clear boundaries
    - ALWAYS: Use save_work_item_direct() when already in a transaction
    """
    pass


# Export all public classes and functions
__all__ = [
    # Enums and Exceptions
    'TransactionType',
    'TransactionBoundaryError',
    'NestedTransactionError',
    'TransactionScopeError',
    # Classes
    'TransactionBoundary',
    'TransactionBoundaryManager',
    'TransactionResult',
    'TransactionBoundaryDocs',
    # Functions
    'get_boundary_manager',
    'reset_boundary_manager',
    'with_single_file_transaction',
    'with_distributed_transaction',
    # Decorators
    'requires_transaction',
    'requires_no_transaction',
]

