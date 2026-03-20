"""
Distributed Lock Manager for Carby Sprint Framework.

Provides file-based distributed locking using portalocker to prevent race conditions
during concurrent sprint operations.
"""

from __future__ import annotations

import functools
import portalocker
from pathlib import Path
from typing import Callable, Any
from contextlib import contextmanager


class DistributedLock:
    """
    Distributed lock using file-based locking with portalocker.
    """
    
    def __init__(self, lock_file_path: str | Path):
        """
        Initialize the distributed lock.
        
        Args:
            lock_file_path: Path to the lock file
        """
        self.lock_file_path = Path(lock_file_path)
        self.lock_file_handle = None
        
    def __enter__(self) -> DistributedLock:
        """Acquire the lock."""
        self.lock_file_handle = open(self.lock_file_path, 'w')
        portalocker.lock(self.lock_file_handle, portalocker.LOCK_EX)
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Release the lock."""
        if self.lock_file_handle:
            portalocker.unlock(self.lock_file_handle)
            self.lock_file_handle.close()
            self.lock_file_handle = None


def with_sprint_lock(lock_path_func: Callable[[str], str]):
    """
    Decorator to wrap functions with distributed locking.
    
    Args:
        lock_path_func: Function that takes sprint_id and returns the path to the lock file
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract sprint_id from arguments - look for it in args or kwargs
            sprint_id = None
            
            # Look for sprint_id in positional arguments
            for arg in args:
                if isinstance(arg, str) and len(arg) > 0 and not arg.startswith('/'):
                    # This might be a sprint_id - basic heuristic
                    sprint_id = arg
                    break
            
            # Look for sprint_id in keyword arguments
            if 'sprint_id' in kwargs:
                sprint_id = kwargs['sprint_id']
            elif 'sprint_data' in kwargs and isinstance(kwargs['sprint_data'], dict):
                sprint_id = kwargs['sprint_data'].get('sprint_id')
            
            if not sprint_id:
                # If we can't find sprint_id, call the function without locking
                return func(*args, **kwargs)
            
            # Get the lock file path
            lock_path = lock_path_func(sprint_id)
            
            # Ensure the directory exists
            Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Acquire lock and execute the function
            with DistributedLock(lock_path):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


@contextmanager
def acquire_sprint_lock(sprint_id: str, lock_path_func: Callable[[str], str]):
    """
    Context manager to acquire a sprint lock.
    
    Args:
        sprint_id: Sprint identifier
        lock_path_func: Function that takes sprint_id and returns the path to the lock file
    """
    lock_path = lock_path_func(sprint_id)
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    
    with DistributedLock(lock_path):
        yield


# Common lock path generators
def default_sprint_lock_path(sprint_id: str) -> str:
    """Generate default lock file path for a sprint."""
    return f".carby-sprints/{sprint_id}/.lock"


def execution_lock_path(sprint_id: str) -> str:
    """Generate execution lock file path for a sprint."""
    return f".carby-sprints/{sprint_id}/.execution.lock"