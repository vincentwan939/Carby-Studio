"""
Two-Phase Commit (2PC) Coordinator for Distributed Transactions.

Implements the two-phase commit pattern to ensure atomic updates across
multiple state files (phase_lock.json, metadata.json, gate-status.json, etc.)

Phase 1 (Prepare): All participants prepare and vote
Phase 2 (Commit/Rollback): Based on votes, either commit all or rollback all

This ensures data consistency during distributed transactions where
multiple state files must be updated atomically.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Generator

from .lock_manager import DistributedLock


class TwoPhaseCommitError(Exception):
    """Raised when a two-phase commit operation fails."""
    pass


class PrepareError(Exception):
    """Raised during Phase 1 (Prepare) when a participant cannot prepare."""
    pass


class CommitError(Exception):
    """Raised during Phase 2 (Commit) when a participant fails to commit."""
    pass


class RollbackError(Exception):
    """Raised during Phase 2 (Rollback) when rollback fails."""
    pass


class ParticipantStatus(Enum):
    """Status of a participant in the 2PC protocol."""
    PENDING = "pending"
    PREPARED = "prepared"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class Participant:
    """
    A participant in the two-phase commit.
    
    Each participant represents a state file that needs to be updated.
    """
    name: str
    file_path: Path
    prepare_fn: Callable[[], Tuple[bool, Any, Optional[Path]]]
    commit_fn: Callable[[Any], bool]
    rollback_fn: Callable[[Any], bool]
    status: ParticipantStatus = ParticipantStatus.PENDING
    vote: bool = False
    vote_data: Any = None
    backup_path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class TransactionRecord:
    """Record of a transaction for recovery purposes."""
    transaction_id: str
    started_at: str
    coordinator_id: str
    participants: List[str]
    status: str  # "preparing", "committed", "rolled_back", "failed"
    completed_at: Optional[str] = None
    error: Optional[str] = None


class TwoPhaseCommitCoordinator:
    """
    Coordinator for two-phase commit transactions.
    
    Ensures atomic updates across multiple state files by:
    1. Phase 1 (Prepare): All participants prepare and vote
    2. Phase 2 (Commit/Rollback): Based on votes, either commit all or rollback all
    
    Thread-safe: Uses distributed locks and unique transaction IDs.
    """
    
    def __init__(self, project_dir: Path, coordinator_id: Optional[str] = None):
        """
        Initialize the 2PC coordinator.
        
        Args:
            project_dir: Project directory for storing transaction logs
            coordinator_id: Unique identifier for this coordinator instance
        """
        self.project_dir = Path(project_dir)
        self.coordinator_id = coordinator_id or f"coordinator_{threading.current_thread().ident}_{uuid.uuid4().hex[:8]}"
        self.tx_log_dir = self.project_dir / ".carby-sprints" / "tx-logs"
        self.tx_log_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._active_transactions: Dict[str, TransactionRecord] = {}
    
    def _get_lock_path_for_participants(self, participants: List[Participant]) -> Path:
        """Get the distributed lock file path based on participants.
        
        Uses the first participant's file path to determine the lock location.
        This ensures that transactions modifying the same files use the same lock.
        """
        if not participants:
            return self.tx_log_dir / ".tx_default.lock"
        
        # Use the directory of the first participant's file as the lock location
        # This ensures all transactions for the same sprint use the same lock
        first_file = participants[0].file_path
        return first_file.parent / ".two_phase_commit.lock"
    
    def _generate_tx_id(self) -> str:
        """Generate a unique transaction ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        unique = uuid.uuid4().hex[:8]
        return f"tx_{timestamp}_{unique}"
    
    def _log_transaction(self, record: TransactionRecord) -> None:
        """Log transaction state for recovery."""
        log_file = self.tx_log_dir / f"{record.transaction_id}.json"
        with open(log_file, 'w') as f:
            json.dump({
                "transaction_id": record.transaction_id,
                "started_at": record.started_at,
                "coordinator_id": record.coordinator_id,
                "participants": record.participants,
                "status": record.status,
                "completed_at": record.completed_at,
                "error": record.error,
            }, f, indent=2)
    
    def _update_tx_status(self, tx_id: str, status: str, error: Optional[str] = None) -> None:
        """Update transaction status in log."""
        log_file = self.tx_log_dir / f"{tx_id}.json"
        if log_file.exists():
            with open(log_file) as f:
                record = json.load(f)
            record["status"] = status
            record["completed_at"] = datetime.utcnow().isoformat()
            if error:
                record["error"] = error
            with open(log_file, 'w') as f:
                json.dump(record, f, indent=2)
    
    def _cleanup_tx_log(self, tx_id: str) -> None:
        """Clean up transaction log after successful completion."""
        log_file = self.tx_log_dir / f"{tx_id}.json"
        if log_file.exists():
            log_file.unlink()
    
    def _phase1_prepare(self, participants: List[Participant], tx_id: str) -> Tuple[bool, List[Participant]]:
        """
        Phase 1: Prepare all participants.
        
        Each participant prepares their changes and votes.
        All participants must vote YES for the transaction to proceed.
        
        Args:
            participants: List of participants to prepare
            tx_id: Transaction ID
            
        Returns:
            Tuple of (all_prepared, prepared_participants)
        """
        prepared_participants = []
        all_prepared = True
        
        for participant in participants:
            try:
                # Call prepare function - should return (vote, data, backup_path)
                vote, vote_data, backup_path = participant.prepare_fn()
                participant.vote = vote
                participant.vote_data = vote_data
                participant.backup_path = backup_path
                
                if vote:
                    participant.status = ParticipantStatus.PREPARED
                    prepared_participants.append(participant)
                else:
                    participant.status = ParticipantStatus.FAILED
                    participant.error = "Participant voted NO"
                    all_prepared = False
                    
            except Exception as e:
                participant.vote = False
                participant.status = ParticipantStatus.FAILED
                participant.error = str(e)
                all_prepared = False
        
        return all_prepared, prepared_participants
    
    def _phase2_commit(self, participants: List[Participant], tx_id: str) -> Tuple[bool, List[str]]:
        """
        Phase 2a: Commit all prepared participants.
        
        All participants that voted YES in Phase 1 are committed.
        If any commit fails, we attempt to rollback others.
        
        Args:
            participants: List of participants to commit
            tx_id: Transaction ID
            
        Returns:
            Tuple of (all_committed, failed_participants)
        """
        committed = []
        failed = []
        
        for participant in participants:
            if participant.status != ParticipantStatus.PREPARED:
                continue
                
            try:
                success = participant.commit_fn(participant.vote_data)
                if success:
                    participant.status = ParticipantStatus.COMMITTED
                    committed.append(participant.name)
                else:
                    participant.status = ParticipantStatus.FAILED
                    participant.error = "Commit returned False"
                    failed.append(participant.name)
            except Exception as e:
                participant.status = ParticipantStatus.FAILED
                participant.error = str(e)
                failed.append(participant.name)
        
        return len(failed) == 0, failed
    
    def _phase2_rollback(self, participants: List[Participant], tx_id: str) -> Tuple[bool, List[str]]:
        """
        Phase 2b: Rollback all prepared participants.
        
        Called when Phase 1 fails or when a commit fails.
        Attempts to rollback all participants that were prepared.
        
        Args:
            participants: List of participants to rollback
            tx_id: Transaction ID
            
        Returns:
            Tuple of (all_rolled_back, failed_participants)
        """
        rolled_back = []
        failed = []
        
        for participant in participants:
            if participant.status != ParticipantStatus.PREPARED:
                continue
                
            try:
                success = participant.rollback_fn(participant.vote_data)
                if success:
                    participant.status = ParticipantStatus.ROLLED_BACK
                    rolled_back.append(participant.name)
                else:
                    failed.append(participant.name)
            except Exception as e:
                failed.append(participant.name)
        
        return len(failed) == 0, failed
    
    def execute_transaction(
        self,
        participants: List[Participant],
        timeout_seconds: float = 30.0
    ) -> Dict[str, Any]:
        """
        Execute a two-phase commit transaction.
        
        Args:
            participants: List of participants in the transaction
            timeout_seconds: Maximum time to wait for the transaction
            
        Returns:
            Dictionary with transaction results:
            - success: True if transaction succeeded
            - transaction_id: Unique transaction ID
            - phase1_result: Result of Phase 1 (prepare)
            - phase2_result: Result of Phase 2 (commit/rollback)
            - participants: Final status of all participants
            - error: Error message if transaction failed
        """
        tx_id = self._generate_tx_id()
        started_at = datetime.utcnow().isoformat()
        
        # Log transaction start
        record = TransactionRecord(
            transaction_id=tx_id,
            started_at=started_at,
            coordinator_id=self.coordinator_id,
            participants=[p.name for p in participants],
            status="preparing"
        )
        self._log_transaction(record)
        self._active_transactions[tx_id] = record
        
        # Acquire distributed lock for the entire transaction to prevent race conditions
        # Use a lock based on participants' files to ensure consistent ordering
        lock_path = self._get_lock_path_for_participants(participants)
        
        try:
            with DistributedLock(lock_path, timeout=timeout_seconds):
                return self._execute_transaction_locked(participants, tx_id, started_at, timeout_seconds)
        except Exception as e:
            # Lock acquisition failed or other error
            return {
                "success": False,
                "transaction_id": tx_id,
                "phase1_result": "error",
                "phase2_result": "error",
                "participants": [
                    {
                        "name": p.name,
                        "status": p.status.value,
                        "error": p.error
                    }
                    for p in participants
                ],
                "error": f"Transaction failed: {str(e)}"
            }
    
    def _execute_transaction_locked(
        self,
        participants: List[Participant],
        tx_id: str,
        started_at: str,
        timeout_seconds: float
    ) -> Dict[str, Any]:
        """
        Execute transaction while holding the distributed lock.
        
        This internal method assumes the distributed lock is already held.
        """
        try:
            # Phase 1: Prepare
            all_prepared, prepared_participants = self._phase1_prepare(participants, tx_id)
            
            if not all_prepared:
                # Phase 1 failed - rollback any prepared participants
                self._update_tx_status(tx_id, "rolling_back")
                all_rolled_back, failed_rollback = self._phase2_rollback(prepared_participants, tx_id)
                
                failed_participants = [p.name for p in participants if p.status == ParticipantStatus.FAILED]
                
                # Build comprehensive error message
                if not all_rolled_back:
                    # CRITICAL: Rollback failed - data integrity may be compromised
                    error_msg = f"CRITICAL: Phase 1 failed for: {failed_participants}. "
                    error_msg += f"Rollback also failed for: {failed_rollback}. "
                    error_msg += "Data integrity may be compromised. Manual recovery may be needed."
                    
                    self._update_tx_status(
                        tx_id, 
                        "rollback_failed",
                        error=error_msg
                    )
                    
                    return {
                        "success": False,
                        "transaction_id": tx_id,
                        "phase1_result": "failed",
                        "phase2_result": "rollback_failed",
                        "rollback_failed_participants": failed_rollback,
                        "participants": [
                            {
                                "name": p.name,
                                "status": p.status.value,
                                "error": p.error
                            }
                            for p in participants
                        ],
                        "error": error_msg,
                        "critical": True
                    }
                
                self._update_tx_status(
                    tx_id, 
                    "rolled_back",
                    error=f"Phase 1 failed for: {failed_participants}"
                )
                
                return {
                    "success": False,
                    "transaction_id": tx_id,
                    "phase1_result": "failed",
                    "phase2_result": "rolled_back",
                    "participants": [
                        {
                            "name": p.name,
                            "status": p.status.value,
                            "error": p.error
                        }
                        for p in participants
                    ],
                    "error": f"Phase 1 prepare failed for: {failed_participants}"
                }
            
            # Phase 2: Commit
            self._update_tx_status(tx_id, "committing")
            all_committed, failed_commit = self._phase2_commit(prepared_participants, tx_id)
            
            if not all_committed:
                # Commit failed - attempt rollback
                self._update_tx_status(tx_id, "rolling_back_after_commit_failure")
                all_rolled_back, failed_rollback = self._phase2_rollback(prepared_participants, tx_id)
                
                # Build comprehensive error message
                if not all_rolled_back:
                    # CRITICAL: Commit failed AND rollback failed - data integrity compromised
                    error_msg = f"CRITICAL: Commit failed for: {failed_commit}. "
                    error_msg += f"Rollback also failed for: {failed_rollback}. "
                    error_msg += "Data integrity may be compromised. Manual recovery may be needed."
                    
                    self._update_tx_status(
                        tx_id,
                        "rollback_failed",
                        error=error_msg
                    )
                    
                    return {
                        "success": False,
                        "transaction_id": tx_id,
                        "phase1_result": "success",
                        "phase2_result": "rollback_failed",
                        "commit_failed_participants": failed_commit,
                        "rollback_failed_participants": failed_rollback,
                        "participants": [
                            {
                                "name": p.name,
                                "status": p.status.value,
                                "error": p.error
                            }
                            for p in participants
                        ],
                        "error": error_msg,
                        "critical": True
                    }
                
                self._update_tx_status(
                    tx_id,
                    "rolled_back",
                    error=f"Commit failed for: {failed_commit}"
                )
                
                return {
                    "success": False,
                    "transaction_id": tx_id,
                    "phase1_result": "success",
                    "phase2_result": "rolled_back",
                    "commit_failed_participants": failed_commit,
                    "participants": [
                        {
                            "name": p.name,
                            "status": p.status.value,
                            "error": p.error
                        }
                        for p in participants
                    ],
                    "error": f"Phase 2 commit failed for: {failed_commit}"
                }
            
            # Success - clean up transaction log
            self._update_tx_status(tx_id, "committed")
            self._cleanup_tx_log(tx_id)
            del self._active_transactions[tx_id]
            
            return {
                "success": True,
                "transaction_id": tx_id,
                "phase1_result": "success",
                "phase2_result": "committed",
                "participants": [
                    {
                        "name": p.name,
                        "status": p.status.value
                    }
                    for p in participants
                ]
            }
            
        except Exception as e:
            # Unexpected error - attempt rollback
            rollback_failed = False
            failed_rollback = []
            
            try:
                # Only rollback participants that were prepared
                prepared = [p for p in participants if p.status == ParticipantStatus.PREPARED]
                if prepared:
                    all_rolled_back, failed_rollback = self._phase2_rollback(prepared, tx_id)
                    rollback_failed = not all_rolled_back
            except Exception:
                rollback_failed = True
                pass  # Best effort rollback
            
            # Build comprehensive error message
            if rollback_failed:
                error_msg = f"Unexpected error: {str(e)}. "
                error_msg += f"Rollback also failed for: {failed_rollback}. "
                error_msg += "Data integrity may be compromised."
                
                self._update_tx_status(tx_id, "rollback_failed", error=error_msg)
                
                return {
                    "success": False,
                    "transaction_id": tx_id,
                    "phase1_result": "error",
                    "phase2_result": "rollback_failed",
                    "rollback_failed_participants": failed_rollback,
                    "participants": [
                        {
                            "name": p.name,
                            "status": p.status.value,
                            "error": p.error
                        }
                        for p in participants
                    ],
                    "error": error_msg,
                    "critical": True
                }
            
            self._update_tx_status(tx_id, "failed", error=str(e))
            
            return {
                "success": False,
                "transaction_id": tx_id,
                "phase1_result": "error",
                "phase2_result": "rolled_back",
                "participants": [
                    {
                        "name": p.name,
                        "status": p.status.value,
                        "error": p.error
                    }
                    for p in participants
                ],
                "error": str(e)
            }
    
    def recover_incomplete_transactions(self) -> List[Dict[str, Any]]:
        """
        Recover from incomplete transactions after a crash.
        
        Scans transaction logs and completes any incomplete transactions.
        This should be called on system startup.
        
        Returns:
            List of recovery results for each incomplete transaction
        """
        results = []
        
        if not self.tx_log_dir.exists():
            return results
        
        for log_file in self.tx_log_dir.glob("tx_*.json"):
            try:
                with open(log_file) as f:
                    record = json.load(f)
                
                tx_id = record["transaction_id"]
                status = record["status"]
                
                if status in ["preparing", "committing"]:
                    # Transaction was interrupted - need to rollback
                    # In a real implementation, we would check participant state
                    # For now, mark as failed and require manual intervention
                    record["status"] = "failed"
                    record["error"] = "Transaction interrupted - manual recovery may be needed"
                    record["completed_at"] = datetime.utcnow().isoformat()
                    
                    with open(log_file, 'w') as f:
                        json.dump(record, f, indent=2)
                    
                    results.append({
                        "transaction_id": tx_id,
                        "action": "marked_for_recovery",
                        "previous_status": status
                    })
                    
            except Exception as e:
                results.append({
                    "transaction_id": log_file.stem,
                    "action": "error",
                    "error": str(e)
                })
        
        return results


class StateFileParticipant:
    """
    Helper class to create a participant for a JSON state file.
    
    This simplifies creating participants for common state file updates.
    """
    
    def __init__(
        self,
        name: str,
        file_path: Path,
        update_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        validate_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    ):
        """
        Initialize a state file participant.
        
        Args:
            name: Participant name
            file_path: Path to the state file
            update_fn: Function that takes current data and returns updated data
            validate_fn: Optional validation function
        """
        self.name = name
        self.file_path = Path(file_path)
        self.update_fn = update_fn
        self.validate_fn = validate_fn
        self._backup_path: Optional[Path] = None
        self._new_data: Optional[Dict[str, Any]] = None
    
    def prepare(self) -> Tuple[bool, Any, Optional[Path]]:
        """
        Prepare phase: load data, validate, create backup.
        
        Returns:
            Tuple of (vote, data, backup_path)
        """
        try:
            # Load current data
            if self.file_path.exists():
                with open(self.file_path) as f:
                    current_data = json.load(f)
            else:
                current_data = {}
            
            # Apply update
            self._new_data = self.update_fn(current_data.copy())
            
            # Validate if validator provided
            if self.validate_fn and not self.validate_fn(self._new_data):
                return False, None, None
            
            # Create backup
            if self.file_path.exists():
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
                self._backup_path = self.file_path.parent / f"{self.file_path.name}.backup_{timestamp}"
                shutil.copy2(self.file_path, self._backup_path)
            
            return True, self._new_data, self._backup_path
            
        except Exception as e:
            return False, None, None
    
    def commit(self, data: Dict[str, Any]) -> bool:
        """
        Commit phase: write data to file.
        
        Args:
            data: Data to write
            
        Returns:
            True if successful
        """
        try:
            # Write to temp file first
            temp_path = self.file_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            # Atomic rename
            temp_path.replace(self.file_path)
            
            # Clean up backup
            if self._backup_path and self._backup_path.exists():
                self._backup_path.unlink()
            
            return True
            
        except Exception:
            return False
    
    def rollback(self, data: Any) -> bool:
        """
        Rollback phase: restore from backup.
        
        Args:
            data: Ignored (backup path is stored in instance)
            
        Returns:
            True if successful
        """
        try:
            if self._backup_path and self._backup_path.exists():
                shutil.copy2(self._backup_path, self.file_path)
                self._backup_path.unlink()
            return True
        except Exception:
            return False
    
    def to_participant(self) -> Participant:
        """Convert to Participant instance for use with coordinator."""
        return Participant(
            name=self.name,
            file_path=self.file_path,
            prepare_fn=self.prepare,
            commit_fn=self.commit,
            rollback_fn=self.rollback
        )


@contextmanager
def two_phase_transaction(
    project_dir: Path,
    participants: List[Participant],
    timeout_seconds: float = 30.0
) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager for two-phase commit transactions.
    
    Args:
        project_dir: Project directory
        participants: List of participants
        timeout_seconds: Transaction timeout
        
    Yields:
        Transaction result dictionary
        
    Raises:
        TwoPhaseCommitError: If transaction fails
        
    Example:
        with two_phase_transaction(project_dir, [participant1, participant2]) as result:
            if result["success"]:
                print("Transaction committed!")
            else:
                print(f"Transaction failed: {result['error']}")
    """
    coordinator = TwoPhaseCommitCoordinator(project_dir)
    result = coordinator.execute_transaction(participants, timeout_seconds)
    
    try:
        yield result
    finally:
        if not result.get("success"):
            raise TwoPhaseCommitError(
                f"Two-phase commit failed: {result.get('error', 'Unknown error')}"
            )


def create_state_participants(
    updates: Dict[str, Tuple[Path, Callable[[Dict[str, Any]], Dict[str, Any]]]],
    validators: Optional[Dict[str, Callable[[Dict[str, Any]], bool]]] = None
) -> List[Participant]:
    """
    Create participants for multiple state file updates.
    
    Args:
        updates: Dict mapping participant name to (file_path, update_fn)
        validators: Optional dict mapping participant name to validation function
        
    Returns:
        List of Participant instances
        
    Example:
        participants = create_state_participants({
            "phase_lock": (phase_lock_path, lambda d: update_phase(d)),
            "metadata": (metadata_path, lambda d: update_metadata(d)),
        })
    """
    participants = []
    validators = validators or {}
    
    for name, (file_path, update_fn) in updates.items():
        participant = StateFileParticipant(
            name=name,
            file_path=file_path,
            update_fn=update_fn,
            validate_fn=validators.get(name)
        )
        participants.append(participant.to_participant())
    
    return participants
