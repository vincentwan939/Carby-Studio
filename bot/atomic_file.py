"""Atomic file operations for data integrity."""

import json
import os
import tempfile
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


def atomic_write_json(filepath: Path, data: Dict[str, Any]) -> bool:
    """
    Atomically write JSON data to file.
    
    Uses write-to-temp-then-rename pattern to ensure:
    - Readers always see complete, valid data
    - No partial writes if process crashes
    - No data corruption on concurrent access
    
    Args:
        filepath: Path to the JSON file
        data: Dictionary to serialize
        
    Returns:
        True if successful, False otherwise
    """
    filepath = Path(filepath)
    dir_name = filepath.parent
    
    try:
        # Ensure directory exists
        dir_name.mkdir(parents=True, exist_ok=True)
        
        # Write to temp file in same directory (for atomic rename)
        with tempfile.NamedTemporaryFile(
            mode='w',
            dir=str(dir_name),
            delete=False,
            suffix='.tmp'
        ) as f:
            temp_path = Path(f.name)
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ensure data is written to disk
        
        # Atomic rename (POSIX: atomic on same filesystem)
        os.replace(str(temp_path), str(filepath))
        
        # Sync directory to ensure rename is persisted
        dir_fd = os.open(str(dir_name), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        
        logger.debug(f"Atomic write successful: {filepath}")
        return True
        
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"Atomic write failed for {filepath}: {e}")
        # Clean up temp file if it exists
        try:
            if 'temp_path' in locals() and temp_path.exists():
                temp_path.unlink()
        except (OSError, IOError):
            pass
        return False


def safe_read_json(filepath: Path) -> Optional[Dict[str, Any]]:
    """
    Safely read JSON file with specific exception handling.
    
    Args:
        filepath: Path to the JSON file
        
    Returns:
        Parsed JSON dict or None if file doesn't exist or is invalid
    """
    filepath = Path(filepath)
    
    if not filepath.exists():
        return None
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {filepath}: {e}")
        return None
        
    except FileNotFoundError:
        logger.debug(f"File not found: {filepath}")
        return None
        
    except PermissionError as e:
        logger.error(f"Permission denied reading {filepath}: {e}")
        return None
        
    except IsADirectoryError:
        logger.error(f"Path is a directory, not a file: {filepath}")
        return None
        
    except OSError as e:
        logger.error(f"OS error reading {filepath}: {e}")
        return None


def safe_write_json(filepath: Path, data: Dict[str, Any]) -> bool:
    """
    Safe wrapper for atomic JSON write with fallback.
    
    Args:
        filepath: Path to the JSON file
        data: Dictionary to serialize
        
    Returns:
        True if successful, False otherwise
    """
    # Try atomic write first
    if atomic_write_json(filepath, data):
        return True
    
    # Fallback to direct write (for recovery scenarios)
    logger.warning(f"Atomic write failed, attempting direct write to {filepath}")
    try:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        return True
    except (OSError, IOError, PermissionError) as e:
        logger.error(f"Direct write also failed for {filepath}: {e}")
        return False


@contextmanager
def locked_json_write(filepath: Path, project_id: Optional[str] = None, 
                      projects_dir: Optional[Path] = None):
    """
    Context manager for locked atomic JSON write.
    
    Combines file locking with atomic writes for full protection.
    
    Usage:
        with locked_json_write(path, "my-project") as data:
            data["key"] = "value"  # Modify the dict
            # Lock released and data written automatically
    
    Args:
        filepath: Path to the JSON file
        project_id: Project ID for locking (derived from filename if None)
        projects_dir: Projects directory (uses Config default if None)
    
    Yields:
        Dictionary containing current file data (or empty dict if new)
    """
    from file_lock import get_lock_manager
    
    # Derive project_id from filename if not provided
    if project_id is None:
        project_id = Path(filepath).stem
    
    # Get lock manager
    lock_manager = get_lock_manager(projects_dir)
    
    # Acquire lock
    with lock_manager.lock_project(project_id):
        # Read current data
        data = safe_read_json(filepath) or {}
        
        # Yield for modification
        yield data
        
        # Write atomically
        if not atomic_write_json(filepath, data):
            raise IOError(f"Failed to write {filepath}")


@contextmanager  
def locked_json_read(filepath: Path, project_id: Optional[str] = None,
                     projects_dir: Optional[Path] = None):
    """
    Context manager for locked JSON read.
    
    Args:
        filepath: Path to the JSON file
        project_id: Project ID for locking
        projects_dir: Projects directory
    
    Yields:
        Dictionary containing file data (or None if not exists)
    """
    from file_lock import get_lock_manager
    
    if project_id is None:
        project_id = Path(filepath).stem
    
    lock_manager = get_lock_manager(projects_dir)
    
    with lock_manager.lock_project(project_id):
        yield safe_read_json(filepath)
