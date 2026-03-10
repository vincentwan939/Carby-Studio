"""File locking for concurrent access protection."""

import logging
import os
import time
import threading
from pathlib import Path
from typing import Optional, Dict
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class FileLock:
    """
    Cross-platform file locking using lock files.
    
    Implements advisory locking - cooperating processes must check the lock.
    Uses a simple lock file with PID + timestamp for deadlock detection.
    """
    
    def __init__(self, lock_path: Path, timeout: float = 30.0, check_interval: float = 0.1):
        """
        Initialize file lock.
        
        Args:
            lock_path: Path to the lock file (typically {file}.lock)
            timeout: Maximum time to wait for lock (seconds)
            check_interval: How often to check if lock is released (seconds)
        """
        self.lock_path = Path(lock_path)
        self.timeout = timeout
        self.check_interval = check_interval
        self._held = False
        self._local_lock = threading.Lock()
    
    def _is_lock_stale(self) -> bool:
        """Check if lock file is stale (process died without cleanup)."""
        try:
            if not self.lock_path.exists():
                return False
            
            # Read lock file content
            content = self.lock_path.read_text().strip()
            if not content:
                return True  # Empty lock file is stale
            
            # Parse PID and timestamp
            parts = content.split(":")
            if len(parts) >= 2:
                pid = int(parts[0])
                timestamp = float(parts[1])
                
                # Check if process still exists
                try:
                    os.kill(pid, 0)  # Signal 0 checks if process exists
                    # Process exists, check if lock is too old (5 minutes)
                    if time.time() - timestamp > 300:
                        logger.warning(f"Lock file is old ({time.time() - timestamp:.0f}s), considering stale")
                        return True
                    return False
                except OSError:
                    # Process doesn't exist, lock is stale
                    logger.info(f"Lock owner process {pid} no longer exists, lock is stale")
                    return True
            
            return True  # Malformed lock file
            
        except (ValueError, OSError) as e:
            logger.warning(f"Error checking lock staleness: {e}")
            return True
    
    def acquire(self, blocking: bool = True) -> bool:
        """
        Acquire the lock.
        
        Args:
            blocking: If True, wait until lock is acquired or timeout.
                     If False, return immediately.
        
        Returns:
            True if lock acquired, False otherwise.
        """
        with self._local_lock:
            if self._held:
                return True
            
            start_time = time.time()
            
            while True:
                try:
                    # Try to create lock file exclusively
                    # Use O_EXCL flag for atomic creation
                    fd = os.open(
                        str(self.lock_path),
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY
                    )
                    
                    # Write our PID and timestamp
                    content = f"{os.getpid()}:{time.time()}"
                    os.write(fd, content.encode())
                    os.close(fd)
                    
                    self._held = True
                    logger.debug(f"Lock acquired: {self.lock_path}")
                    return True
                    
                except FileExistsError:
                    # Lock file exists, check if it's stale
                    if self._is_lock_stale():
                        logger.info(f"Removing stale lock: {self.lock_path}")
                        try:
                            self.lock_path.unlink()
                        except OSError:
                            pass
                        continue  # Try again
                    
                    if not blocking:
                        return False
                    
                    # Check timeout
                    if time.time() - start_time > self.timeout:
                        logger.warning(f"Lock timeout: {self.lock_path}")
                        return False
                    
                    # Wait and retry
                    time.sleep(self.check_interval)
                    
                except OSError as e:
                    logger.error(f"Error acquiring lock: {e}")
                    return False
    
    def release(self) -> bool:
        """
        Release the lock.
        
        Returns:
            True if lock was held and released, False otherwise.
        """
        with self._local_lock:
            if not self._held:
                return False
            
            try:
                if self.lock_path.exists():
                    self.lock_path.unlink()
                self._held = False
                logger.debug(f"Lock released: {self.lock_path}")
                return True
                
            except OSError as e:
                logger.error(f"Error releasing lock: {e}")
                self._held = False  # Mark as released even if cleanup failed
                return False
    
    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.release()
        return False
    
    def __del__(self):
        """Cleanup on garbage collection."""
        if self._held:
            try:
                self.release()
            except (OSError, IOError, PermissionError):
                pass


class ProjectLockManager:
    """
    Manages file locks for project files.
    
    Provides per-project locking to prevent concurrent modifications
    from bot, CLI, and other processes.
    """
    
    def __init__(self, projects_dir: Path, timeout: float = 30.0):
        """
        Initialize lock manager.
        
        Args:
            projects_dir: Directory containing project files
            timeout: Default lock timeout in seconds
        """
        self.projects_dir = Path(projects_dir)
        self.timeout = timeout
        self._locks: Dict[str, FileLock] = {}
        self._lock_cache_lock = threading.Lock()
    
    def _get_lock_path(self, project_id: str) -> Path:
        """Get lock file path for a project."""
        # Ensure projects directory exists
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        return self.projects_dir / f"{project_id}.lock"
    
    def get_lock(self, project_id: str) -> FileLock:
        """
        Get or create a lock for a project.
        
        Args:
            project_id: Project identifier
        
        Returns:
            FileLock instance for the project
        """
        with self._lock_cache_lock:
            if project_id not in self._locks:
                lock_path = self._get_lock_path(project_id)
                self._locks[project_id] = FileLock(lock_path, timeout=self.timeout)
            return self._locks[project_id]
    
    @contextmanager
    def lock_project(self, project_id: str, timeout: Optional[float] = None):
        """
        Context manager for project locking.
        
        Usage:
            with lock_manager.lock_project("my-project"):
                # Do work with exclusive access
                pass
        
        Args:
            project_id: Project identifier
            timeout: Override default timeout
        
        Yields:
            True if lock acquired
        
        Raises:
            TimeoutError: If lock cannot be acquired within timeout
        """
        lock = self.get_lock(project_id)
        
        # Temporarily override timeout if specified
        old_timeout = lock.timeout
        if timeout is not None:
            lock.timeout = timeout
        
        try:
            if lock.acquire(blocking=True):
                try:
                    yield True
                finally:
                    lock.release()
            else:
                raise TimeoutError(f"Could not acquire lock for project '{project_id}'")
        finally:
            lock.timeout = old_timeout
    
    def is_locked(self, project_id: str) -> bool:
        """
        Check if a project is currently locked.
        
        Args:
            project_id: Project identifier
        
        Returns:
            True if locked by another process
        """
        lock_path = self._get_lock_path(project_id)
        
        if not lock_path.exists():
            return False
        
        # Check if it's our lock
        try:
            content = lock_path.read_text().strip()
            parts = content.split(":")
            if len(parts) >= 1:
                pid = int(parts[0])
                if pid == os.getpid():
                    return False  # It's our lock
        except (ValueError, OSError):
            pass
        
        return True
    
    def cleanup_stale_locks(self) -> int:
        """
        Remove all stale lock files in the projects directory.
        
        Returns:
            Number of stale locks removed
        """
        removed = 0
        
        try:
            for lock_file in self.projects_dir.glob("*.lock"):
                try:
                    # Check if stale
                    content = lock_file.read_text().strip()
                    if content:
                        parts = content.split(":")
                        if len(parts) >= 1:
                            pid = int(parts[0])
                            try:
                                os.kill(pid, 0)
                                # Process exists, not stale
                                continue
                            except OSError:
                                # Process dead, stale lock
                                pass
                    
                    # Remove stale lock
                    lock_file.unlink()
                    removed += 1
                    logger.info(f"Cleaned up stale lock: {lock_file}")
                    
                except (ValueError, OSError) as e:
                    logger.warning(f"Error checking lock {lock_file}: {e}")
                    
        except OSError as e:
            logger.error(f"Error cleaning up locks: {e}")
        
        return removed


# Global lock manager instance
_lock_manager: Optional[ProjectLockManager] = None


def get_lock_manager(projects_dir: Optional[Path] = None, timeout: float = 30.0) -> ProjectLockManager:
    """
    Get or create the global lock manager.
    
    Args:
        projects_dir: Directory containing project files
        timeout: Default lock timeout
    
    Returns:
        ProjectLockManager instance
    """
    global _lock_manager
    
    if _lock_manager is None:
        if projects_dir is None:
            from config import Config
            projects_dir = Config.PROJECTS_DIR
        _lock_manager = ProjectLockManager(projects_dir, timeout)
    
    return _lock_manager


def reset_lock_manager():
    """Reset the global lock manager (useful for testing)."""
    global _lock_manager
    _lock_manager = None
