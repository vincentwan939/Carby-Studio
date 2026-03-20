"""
Health Monitor for Carby Sprint Framework.

Monitors system health, detects stale locks, hung agents, and manages log rotation.
Provides recovery actions for common failure scenarios.
"""

import os
import psutil
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class HealthIssue:
    """Represents a detected health issue."""
    severity: str  # 'critical', 'warning', 'info'
    component: str  # 'lock', 'agent', 'log', 'disk', etc.
    description: str
    details: Dict[str, any]


class HealthMonitor:
    """Monitors sprint framework health and performs recovery actions."""
    
    def __init__(self, base_dir: str = ".carby-sprints", log_retention_mb: int = 100):
        self.base_dir = Path(base_dir)
        self.log_retention_mb = log_retention_mb
        self.logger = logging.getLogger(__name__)
        
    def check_stale_locks(self, max_age_minutes: int = 30) -> List[HealthIssue]:
        """
        Check for stale execution locks.
        
        Args:
            max_age_minutes: Maximum age in minutes before considering a lock stale
            
        Returns:
            List of detected stale locks
        """
        issues = []
        max_age_seconds = max_age_minutes * 60
        
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                if file.endswith('.execution.lock'):
                    lock_path = Path(root) / file
                    try:
                        # Get lock file modification time
                        lock_mtime = lock_path.stat().st_mtime
                        current_time = time.time()
                        
                        if current_time - lock_mtime > max_age_seconds:
                            # Check if the process that created the lock is still running
                            pid = self._read_pid_from_lock(lock_path)
                            if pid is None or not self._is_process_running(pid):
                                # This is a stale lock
                                issues.append(HealthIssue(
                                    severity='warning',
                                    component='lock',
                                    description=f'Stale execution lock detected: {lock_path}',
                                    details={'lock_path': str(lock_path), 'age_minutes': (current_time - lock_mtime) / 60}
                                ))
                    except Exception as e:
                        issues.append(HealthIssue(
                            severity='warning',
                            component='lock',
                            description=f'Could not check lock file {lock_path}: {str(e)}',
                            details={'lock_path': str(lock_path)}
                        ))
        
        return issues
    
    def _read_pid_from_lock(self, lock_path: Path) -> Optional[int]:
        """Read the PID from a lock file."""
        try:
            with open(lock_path, 'r') as f:
                content = f.read().strip()
                if content.isdigit():
                    return int(content)
        except:
            pass
        return None
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process with given PID is still running."""
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False
    
    def check_hung_agents(self, max_duration_hours: int = 2, sample_size: int = 10) -> List[HealthIssue]:
        """
        Check for hung agents that have been running too long.

        Uses sampling for performance on systems with many sprints.

        Args:
            max_duration_hours: Maximum duration in hours before considering an agent hung
            sample_size: Maximum number of sprints to check (for performance)

        Returns:
            List of detected hung agents
        """
        issues = []
        max_duration_seconds = max_duration_hours * 3600

        # Get list of sprint directories (sample for performance)
        sprint_dirs = [d for d in self.base_dir.iterdir() if d.is_dir()]
        if len(sprint_dirs) > sample_size:
            # Sample recent sprints first (by modification time)
            sprint_dirs = sorted(sprint_dirs, key=lambda d: d.stat().st_mtime, reverse=True)[:sample_size]

        # Look for active sprint executions and check their duration
        for sprint_dir in sprint_dirs:
            # Check if there's an execution log that indicates ongoing work
            logs_dir = sprint_dir / "logs"
            if not logs_dir.exists():
                continue

            # Look for agent activity logs (limit to recent ones)
            agent_logs = sorted(logs_dir.glob("agent_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]

            for log_file in agent_logs:
                try:
                    stat = log_file.stat()
                    log_age = time.time() - stat.st_mtime

                    # If log is old but execution directory suggests work is ongoing
                    if log_age > max_duration_seconds:
                        # Check if there are any ongoing work indicators
                        issues.append(HealthIssue(
                            severity='warning',
                            component='agent',
                            description=f'Potentially hung agent detected in sprint {sprint_dir.name}',
                            details={
                                'sprint_id': sprint_dir.name,
                                'log_file': str(log_file),
                                'inactive_duration_hours': log_age / 3600
                            }
                        ))
                except Exception as e:
                    issues.append(HealthIssue(
                        severity='warning',
                        component='agent',
                        description=f'Could not check agent log {log_file}: {str(e)}',
                        details={'log_file': str(log_file)}
                    ))

        return issues
    
    def check_log_sizes(self) -> List[HealthIssue]:
        """
        Check for oversized log files that need rotation.
        
        Returns:
            List of oversized log files
        """
        issues = []
        max_size_bytes = self.log_retention_mb * 1024 * 1024  # Convert MB to bytes
        
        for root, dirs, files in os.walk(self.base_dir):
            for file in files:
                if file.endswith(('.log', '.jsonl')):
                    log_path = Path(root) / file
                    try:
                        size = log_path.stat().st_size
                        if size > max_size_bytes:
                            issues.append(HealthIssue(
                                severity='info',
                                component='log',
                                description=f'Oversized log file detected: {log_path}',
                                details={
                                    'log_path': str(log_path),
                                    'size_mb': size / (1024 * 1024),
                                    'max_allowed_mb': self.log_retention_mb
                                }
                            ))
                    except Exception as e:
                        issues.append(HealthIssue(
                            severity='warning',
                            component='log',
                            description=f'Could not check log file {log_path}: {str(e)}',
                            details={'log_path': str(log_path)}
                        ))
        
        return issues
    
    def check_disk_space(self, min_free_gb: float = 1.0) -> List[HealthIssue]:
        """
        Check available disk space.
        
        Args:
            min_free_gb: Minimum free space in GB required
            
        Returns:
            List of disk space issues
        """
        issues = []
        try:
            usage = psutil.disk_usage(str(self.base_dir))
            free_gb = usage.free / (1024 ** 3)
            
            if free_gb < min_free_gb:
                issues.append(HealthIssue(
                    severity='critical',
                    component='disk',
                    description=f'Low disk space: {free_gb:.2f}GB free, minimum {min_free_gb}GB required',
                    details={
                        'free_gb': free_gb,
                        'total_gb': usage.total / (1024 ** 3),
                        'used_gb': usage.used / (1024 ** 3),
                        'min_required_gb': min_free_gb
                    }
                ))
        except Exception as e:
            issues.append(HealthIssue(
                severity='warning',
                component='disk',
                description=f'Could not check disk space: {str(e)}',
                details={}
            ))
        
        return issues
    
    def run_health_check(self) -> Dict[str, List[HealthIssue]]:
        """
        Run comprehensive health check.
        
        Returns:
            Dictionary mapping component names to lists of issues
        """
        health_report = {
            'locks': self.check_stale_locks(),
            'agents': self.check_hung_agents(),
            'logs': self.check_log_sizes(),
            'disk': self.check_disk_space()
        }
        
        return health_report
    
    def perform_recovery_actions(self, issues: List[HealthIssue]) -> Dict[str, any]:
        """
        Perform automated recovery actions for detected issues.
        
        Args:
            issues: List of health issues to address
            
        Returns:
            Dictionary with results of recovery actions
        """
        results = {
            'resolved': [],
            'failed': [],
            'skipped': []
        }
        
        for issue in issues:
            try:
                if issue.component == 'lock' and issue.severity in ['warning', 'critical']:
                    # Attempt to clean up stale locks
                    lock_path = Path(issue.details['lock_path'])
                    if self._attempt_lock_cleanup(lock_path):
                        results['resolved'].append({
                            'issue': issue.description,
                            'action': 'lock_removed',
                            'path': str(lock_path)
                        })
                    else:
                        results['failed'].append({
                            'issue': issue.description,
                            'action': 'lock_cleanup_failed',
                            'path': str(lock_path)
                        })
                elif issue.component == 'log':
                    # Log files are typically handled by external log rotation
                    # For now, just report them
                    results['skipped'].append({
                        'issue': issue.description,
                        'action': 'log_rotation_manual',
                        'path': issue.details.get('log_path', 'unknown')
                    })
                else:
                    results['skipped'].append({
                        'issue': issue.description,
                        'action': 'manual_intervention_required'
                    })
            except Exception as e:
                results['failed'].append({
                    'issue': issue.description,
                    'action': 'recovery_error',
                    'error': str(e)
                })
        
        return results
    
    def _attempt_lock_cleanup(self, lock_path: Path) -> bool:
        """
        Attempt to safely remove a stale lock file.
        
        Args:
            lock_path: Path to the lock file to remove
            
        Returns:
            True if successfully removed, False otherwise
        """
        try:
            # Atomic check-and-remove to prevent TOCTOU race condition
            # Use a temporary lock to synchronize cleanup operations
            cleanup_lock_path = lock_path.parent / ".cleanup_lock"

            import portalocker
            with open(cleanup_lock_path, 'w') as cleanup_lock:
                portalocker.lock(cleanup_lock, portalocker.LOCK_EX)

                # Now safely check and remove
                if lock_path.exists():
                    lock_mtime = lock_path.stat().st_mtime
                    current_time = time.time()

                    # Re-check that it's still stale (age > 30 min)
                    if current_time - lock_mtime > 30 * 60:
                        # Double-check that no process is using it
                        pid = self._read_pid_from_lock(lock_path)
                        if pid is None or not self._is_process_running(pid):
                            lock_path.unlink()
                            self.logger.info(f"Removed stale lock file: {lock_path}")
                            return True
            return False
        except Exception as e:
            self.logger.error(f"Failed to remove lock file {lock_path}: {str(e)}")
            return False


# Global health monitor instance
_health_monitor: Optional[HealthMonitor] = None


def get_health_monitor(base_dir: str = ".carby-sprints") -> HealthMonitor:
    """
    Get or create the global health monitor instance.
    
    Args:
        base_dir: Base directory for monitoring
        
    Returns:
        HealthMonitor instance
    """
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor(base_dir)
    return _health_monitor


def run_health_check() -> Dict[str, List[HealthIssue]]:
    """
    Convenience function to run a health check.
    
    Returns:
        Health check report
    """
    monitor = get_health_monitor()
    return monitor.run_health_check()


def cleanup_stale_locks(max_age_minutes: int = 30) -> Dict[str, any]:
    """
    Convenience function to clean up stale locks.
    
    Args:
        max_age_minutes: Maximum age in minutes before considering a lock stale
        
    Returns:
        Results of cleanup actions
    """
    monitor = get_health_monitor()
    issues = monitor.check_stale_locks(max_age_minutes=max_age_minutes)
    return monitor.perform_recovery_actions(issues)


def rotate_large_logs() -> Dict[str, any]:
    """
    Convenience function to identify large log files for rotation.
    
    Returns:
        Results of log analysis
    """
    monitor = get_health_monitor()
    issues = monitor.check_log_sizes()
    return {'large_logs': [issue.details for issue in issues]}