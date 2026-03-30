"""
Distributed Lock Manager for Carby Sprint Framework.

Provides file-based distributed locking using portalocker to prevent race conditions
during concurrent sprint operations.
"""

from __future__ import annotations

import functools
import os
import portalocker
from pathlib import Path
from typing import Callable, Any
from contextlib import contextmanager


class LockTimeoutError(Exception):
    """Raised when a lock cannot be acquired within the specified timeout."""
    pass


class DistributedLock:
    """
    Distributed lock using file-based locking with portalocker.
    
    Supports timeout-based lock acquisition to prevent indefinite blocking.
    """
    
    # Default timeout from environment variable or 30 seconds
    DEFAULT_TIMEOUT = float(os.environ.get('CARBY_LOCK_TIMEOUT', 30))
    
    def __init__(self, lock_file_path: str | Path, timeout: float | None = None):
        """
        Initialize the distributed lock.
        
        Args:
            lock_file_path: Path to the lock file
            timeout: Maximum time to wait for lock acquisition in seconds.
                    Defaults to CARBY_LOCK_TIMEOUT env var or 30 seconds.
                    Use None for blocking indefinitely (backward compatible).
        """
        self.lock_file_path = Path(lock_file_path)
        self.lock_file_handle = None
        self.timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        
    def __enter__(self) -> DistributedLock:
        """Acquire the lock with timeout support."""
        self.lock_file_handle = open(self.lock_file_path, 'w')
        try:
            # Use LOCK_NB (non-blocking) with timeout for controlled waiting
            if self.timeout is not None and self.timeout > 0:
                import time
                start_time = time.time()
                acquired = False
                while time.time() - start_time < self.timeout:
                    try:
                        portalocker.lock(self.lock_file_handle, portalocker.LOCK_EX | portalocker.LOCK_NB)
                        acquired = True
                        break
                    except portalocker.LockException:
                        # Lock is held by another process, wait briefly and retry
                        time.sleep(0.1)
                
                if not acquired:
                    self.lock_file_handle.close()
                    self.lock_file_handle = None
                    raise LockTimeoutError(
                        f"Could not acquire lock on {self.lock_file_path} within {self.timeout}s timeout"
                    )
            else:
                # Blocking mode (backward compatible)
                portalocker.lock(self.lock_file_handle, portalocker.LOCK_EX)
        except Exception:
            # Clean up on any error
            if self.lock_file_handle:
                self.lock_file_handle.close()
                self.lock_file_handle = None
            raise
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Release the lock."""
        if self.lock_file_handle:
            try:
                portalocker.unlock(self.lock_file_handle)
            except Exception:
                # Ignore unlock errors (file may already be unlocked)
                pass
            self.lock_file_handle.close()
            self.lock_file_handle = None


def with_sprint_lock(lock_path_func: Callable[[str], str], timeout: float | None = None):
    """
    Decorator to wrap functions with distributed locking.
    
    Args:
        lock_path_func: Function that takes sprint_id and returns the path to the lock file
        timeout: Maximum time to wait for lock acquisition in seconds.
                Defaults to CARBY_LOCK_TIMEOUT env var or 30 seconds.
                Use None for blocking indefinitely (backward compatible).
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
            with DistributedLock(lock_path, timeout=timeout):
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


@contextmanager
def acquire_sprint_lock(sprint_id: str, lock_path_func: Callable[[str], str], timeout: float | None = None):
    """
    Context manager to acquire a sprint lock.
    
    Args:
        sprint_id: Sprint identifier
        lock_path_func: Function that takes sprint_id and returns the path to the lock file
        timeout: Maximum time to wait for lock acquisition in seconds.
                Defaults to CARBY_LOCK_TIMEOUT env var or 30 seconds.
                Use None for blocking indefinitely (backward compatible).
    """
    lock_path = lock_path_func(sprint_id)
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    
    with DistributedLock(lock_path, timeout=timeout):
        yield


# Common lock path generators
def default_sprint_lock_path(sprint_id: str) -> str:
    """Generate default lock file path for a sprint."""
    return f".carby-sprints/{sprint_id}/.lock"


def execution_lock_path(sprint_id: str) -> str:
    """Generate execution lock file path for a sprint."""
    return f".carby-sprints/{sprint_id}/.execution.lock"