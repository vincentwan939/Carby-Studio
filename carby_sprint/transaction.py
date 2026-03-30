"""
Atomic Transaction Manager for Sprint Operations.

Implements atomic updates using copy-on-write pattern with backup and rollback
capabilities for reliability in concurrent environments.
"""

import json
import os
import shutil
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Generator, Optional, Tuple
from datetime import datetime

from .json_cache import (
    load_json_cached,
    _invalidate_json_cache,
    _set_cached_json,
)


class TransactionError(Exception):
    """Raised when a transaction operation fails."""
    pass


# NOTE: JSON cache functions are now imported from json_cache module
# to ensure cross-module state consistency. Both gate_state.py and
# transaction.py share the same cache via json_cache module.


def save_json_invalidate_cache(file_path: Path, data: Dict[str, Any]) -> None:
    """
    Save JSON data and invalidate cache.
    
    Args:
        file_path: Path to save the JSON file
        data: Data to save
    """
    with open(file_path, "w") as f:
        json.dump(data, f, indent=2)
    _invalidate_json_cache(file_path)


@contextmanager
def atomic_sprint_update(
    sprint_path: Path,
    backup_on_failure: bool = True,
    create_backup: bool = True
) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager for atomic sprint updates using copy-on-write pattern.
    Thread-safe with unique temp directories per transaction.

    Args:
        sprint_path: Path to the sprint directory containing metadata.json
        backup_on_failure: Whether to create backup on transaction failure
        create_backup: Whether to create initial backup before modification

    Yields:
        Sprint data dict for modification

    Raises:
        TransactionError: If transaction fails and rollback is needed
    """
    import uuid

    metadata_path = sprint_path / "metadata.json"
    temp_dir = None
    backup_path = None
    temp_final_path = None

    # Ensure the sprint directory exists
    sprint_path.mkdir(parents=True, exist_ok=True)

    # Create backup if requested
    if create_backup and metadata_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = sprint_path / f"metadata.json.backup_{timestamp}"
        shutil.copy2(metadata_path, backup_path)

    try:
        # Create unique temporary working directory with thread ID and UUID
        thread_id = threading.current_thread().ident
        unique_id = uuid.uuid4().hex[:8]
        temp_dir = Path(tempfile.mkdtemp(prefix=f"sprint_tx_{thread_id}_{unique_id}_"))

        # Copy current metadata to temp location for modification
        temp_metadata_path = temp_dir / "metadata.json"
        if metadata_path.exists():
            shutil.copy2(metadata_path, temp_metadata_path)

        # Load sprint data from temp location using cache
        if temp_metadata_path.exists():
            sprint_data = load_json_cached(temp_metadata_path)
        else:
            sprint_data = {}

        # Yield control back to caller for modifications
        yield sprint_data

        # Write modified data back to temp file
        save_json_invalidate_cache(temp_metadata_path, sprint_data)

        # After successful modification, atomically move temp to final location
        # Use unique temp file name to avoid conflicts
        temp_final_path = metadata_path.with_suffix(f".tmp.{unique_id}")
        shutil.copy2(temp_metadata_path, temp_final_path)
        os.rename(str(temp_final_path), str(metadata_path))
        
        # Invalidate cache for the main metadata file since we modified it
        _invalidate_json_cache(metadata_path)

    except Exception as e:
        # Transaction failed, attempt cleanup and rollback
        rollback_failed = False
        rollback_error_msg = None
        
        try:
            if backup_on_failure and backup_path and backup_path.exists():
                # Restore from backup atomically
                restore_temp = metadata_path.with_suffix(f".restore_tmp.{unique_id}")
                shutil.copy2(backup_path, restore_temp)
                os.rename(str(restore_temp), str(metadata_path))
                # Invalidate cache since we restored from backup
                _invalidate_json_cache(metadata_path)
        except Exception as rollback_error:
            rollback_failed = True
            rollback_error_msg = str(rollback_error)
            # Log rollback failure for forensic analysis
            import logging
            logging.getLogger(__name__).error(
                f"CRITICAL: Rollback failed after transaction error: {rollback_error}. "
                f"Original error: {e}. Backup at: {backup_path}"
            )
        
        # Build comprehensive error message including rollback status
        error_msg = f"Transaction failed: {str(e)}"
        if rollback_failed:
            error_msg = f"{error_msg}. CRITICAL: Rollback also failed: {rollback_error_msg}. "
            error_msg += f"Data integrity may be compromised. Manual recovery may be needed. "
            error_msg += f"Backup location: {backup_path}"
            raise TransactionError(error_msg) from e
        
        raise TransactionError(error_msg) from e

    finally:
        # Clean up temp directory if it still exists
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)

        # Clean up any partial temp files (using pattern to catch all)
        for partial_file in sprint_path.glob("*.tmp.*"):
            try:
                partial_file.unlink(missing_ok=True)
            except Exception:
                pass

        # Clean up old backups (keep last 10)
        if backup_path and backup_path.exists():
            _cleanup_old_backups(sprint_path, max_backups=10)


@contextmanager
def atomic_work_item_update(
    work_items_dir: Path,
    work_item_id: str,
    backup_on_failure: bool = True
) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager for atomic work item updates with rollback support.
    
    Args:
        work_items_dir: Directory containing work item files
        work_item_id: ID of the work item to update
        backup_on_failure: Whether to create backup and attempt rollback on failure
        
    Yields:
        Work item data dict for modification
        
    Raises:
        TransactionError: If transaction fails and rollback is needed
    """
    import uuid
    
    work_item_path = work_items_dir / f"{work_item_id}.json"
    temp_dir = None
    backup_path = None
    
    # Ensure the work items directory exists
    work_items_dir.mkdir(parents=True, exist_ok=True)
    
    # Create backup if file exists and backup is enabled
    if backup_on_failure and work_item_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = work_items_dir / f"{work_item_id}.json.backup_{timestamp}"
        shutil.copy2(work_item_path, backup_path)
    
    try:
        # Create temporary working directory with unique ID
        unique_id = uuid.uuid4().hex[:8]
        temp_dir = Path(tempfile.mkdtemp(prefix=f"wi_{work_item_id}_{unique_id}_"))
        
        # Copy current work item to temp location for modification
        temp_work_item_path = temp_dir / f"{work_item_id}.json"
        if work_item_path.exists():
            shutil.copy2(work_item_path, temp_work_item_path)
        
        # Load work item data from temp location using cache
        if temp_work_item_path.exists():
            work_item_data = load_json_cached(temp_work_item_path)
        else:
            work_item_data = {"id": work_item_id, "status": "planned"}
        
        # Yield control back to caller for modifications
        yield work_item_data
        
        # Write modified data back to temp file
        save_json_invalidate_cache(temp_work_item_path, work_item_data)
        
        # After successful modification, atomically move temp to final location
        temp_final_path = work_item_path.with_suffix(f".tmp.{unique_id}")
        shutil.copy2(temp_work_item_path, temp_final_path)
        os.rename(str(temp_final_path), str(work_item_path))
        
        # Invalidate cache for the main work item file since we modified it
        _invalidate_json_cache(work_item_path)
        
    except Exception as e:
        # Transaction failed, attempt cleanup and rollback
        rollback_failed = False
        rollback_error_msg = None
        
        try:
            if backup_on_failure and backup_path and backup_path.exists():
                # Restore from backup atomically
                restore_temp = work_item_path.with_suffix(f".restore_tmp.{unique_id}")
                shutil.copy2(backup_path, restore_temp)
                os.rename(str(restore_temp), str(work_item_path))
                # Invalidate cache since we restored from backup
                _invalidate_json_cache(work_item_path)
        except Exception as rollback_error:
            rollback_failed = True
            rollback_error_msg = str(rollback_error)
            # Log rollback failure for forensic analysis
            import logging
            logging.getLogger(__name__).error(
                f"CRITICAL: Work item rollback failed after transaction error: {rollback_error}. "
                f"Original error: {e}. Backup at: {backup_path}"
            )
        
        # Clean up temp directory
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        # Clean up any partial temp files
        for partial_file in work_items_dir.glob(f"{work_item_id}*.tmp*"):
            try:
                partial_file.unlink(missing_ok=True)
            except Exception:
                pass
        
        # Build comprehensive error message including rollback status
        error_msg = f"Work item transaction failed: {str(e)}"
        if rollback_failed:
            error_msg = f"{error_msg}. CRITICAL: Rollback also failed: {rollback_error_msg}. "
            error_msg += f"Data integrity may be compromised. Manual recovery may be needed. "
            error_msg += f"Backup location: {backup_path}"
            raise TransactionError(error_msg) from e
            
        raise TransactionError(error_msg) from e
        
    finally:
        # Clean up temp directory if it still exists
        if temp_dir and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
        
        # Clean up old backups (keep last 10)
        if backup_path and backup_path.exists():
            _cleanup_old_backups(work_items_dir, max_backups=10, pattern=f"{work_item_id}.json.backup_*")


def validate_gate_transition(
    current_gate_status: str,
    target_status: str,
    allowed_transitions: Optional[Dict[str, list]] = None
) -> bool:
    """
    Validate gate status transition according to business rules.
    
    Args:
        current_gate_status: Current status of the gate
        target_status: Desired new status
        allowed_transitions: Custom transition rules (uses defaults if None)
        
    Returns:
        True if transition is valid, False otherwise
    """
    if allowed_transitions is None:
        allowed_transitions = {
            "pending": ["in_progress", "skipped"],
            "in_progress": ["passed", "failed", "blocked"],
            "blocked": ["in_progress", "failed"],
            "failed": ["in_progress", "skipped"],
            "passed": [],
            "skipped": []
        }
    
    if current_gate_status not in allowed_transitions:
        return False
    
    allowed = allowed_transitions[current_gate_status]
    return target_status in allowed


def validate_work_item_exists(
    work_items_dir: Path,
    work_item_id: str
) -> bool:
    """
    Validate that a work item exists.
    
    Args:
        work_items_dir: Directory containing work item files
        work_item_id: ID of the work item to check
        
    Returns:
        True if work item exists, False otherwise
    """
    work_item_path = work_items_dir / f"{work_item_id}.json"
    return work_item_path.exists()


def ensure_directory_structure(sprint_path: Path) -> None:
    """
    Ensure all required sprint directories exist.

    Args:
        sprint_path: Path to the sprint directory
    """
    sprint_path.mkdir(parents=True, exist_ok=True)
    (sprint_path / "work_items").mkdir(exist_ok=True)
    (sprint_path / "gates").mkdir(exist_ok=True)
    (sprint_path / "logs").mkdir(exist_ok=True)


def _cleanup_old_backups(sprint_path: Path, max_backups: int = 10, pattern: str = "metadata.json.backup_*") -> None:
    """
    Clean up old backup files to prevent unlimited disk usage.

    Args:
        sprint_path: Path to the sprint directory
        max_backups: Maximum number of backups to keep
        pattern: Glob pattern for matching backup files
    """
    backups = sorted(sprint_path.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    # Remove excess backups
    for old_backup in backups[max_backups:]:
        try:
            old_backup.unlink()
        except Exception:
            pass  # Best effort cleanup