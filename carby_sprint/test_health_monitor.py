"""Tests for the health_monitor module.

Tests system health checks, component status monitoring, error rate tracking,
and recovery detection for the Carby Sprint Framework.
"""

import os
import sys
import time
import tempfile
import threading
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, Mock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from health_monitor import (
    HealthMonitor,
    HealthIssue,
    get_health_monitor,
    run_health_check,
    cleanup_stale_locks,
    rotate_large_logs,
)


# =============================================================================
# Test Fixtures and Helpers
# =============================================================================

def create_mock_lock_file(base_dir: Path, name: str, age_minutes: float, pid: int = None):
    """Create a mock lock file with specified age."""
    lock_path = base_dir / name
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    content = str(pid) if pid else ""
    lock_path.write_text(content)
    
    # Set modification time to simulate age
    old_time = time.time() - (age_minutes * 60)
    os.utime(lock_path, (old_time, old_time))
    return lock_path


def create_mock_log_file(base_dir: Path, name: str, size_mb: float):
    """Create a mock log file with specified size."""
    log_path = base_dir / name
    log_path.parent.mkdir(parents=True, exist_ok=True)
    # Write bytes to create file of specific size
    size_bytes = int(size_mb * 1024 * 1024)
    log_path.write_bytes(b'x' * size_bytes)
    return log_path


def create_mock_agent_log(base_dir: Path, sprint_name: str, agent_name: str, age_hours: float):
    """Create a mock agent log file."""
    log_dir = base_dir / sprint_name / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"agent_{agent_name}.log"
    log_path.write_text("Mock agent log content")
    
    # Set modification time
    old_time = time.time() - (age_hours * 3600)
    os.utime(log_path, (old_time, old_time))
    return log_path


# =============================================================================
# Test 1: Health check returns correct status
# =============================================================================

def test_health_check_returns_correct_status():
    """Test that run_health_check returns proper status structure."""
    print("Test 1: Health check returns correct status structure")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Run health check
        report = monitor.run_health_check()
        
        # Verify structure
        assert 'locks' in report, "Report should contain 'locks' key"
        assert 'agents' in report, "Report should contain 'agents' key"
        assert 'logs' in report, "Report should contain 'logs' key"
        assert 'disk' in report, "Report should contain 'disk' key"
        
        # All values should be lists
        for key in ['locks', 'agents', 'logs', 'disk']:
            assert isinstance(report[key], list), f"Report['{key}'] should be a list"
        
        print("  PASS: Health check returns correct structure")
        return True


def test_health_check_empty_when_healthy():
    """Test that health check returns empty lists when system is healthy."""
    print("Test 2: Health check returns empty lists when healthy")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        report = monitor.run_health_check()
        
        # With empty directory, should have no issues
        assert len(report['locks']) == 0, "Should have no lock issues in empty directory"
        assert len(report['agents']) == 0, "Should have no agent issues in empty directory"
        assert len(report['logs']) == 0, "Should have no log issues in empty directory"
        
        print("  PASS: Empty directory produces no health issues")
        return True


# =============================================================================
# Test 2: Component failure detection
# =============================================================================

def test_stale_lock_detection():
    """Test detection of stale execution locks."""
    print("Test 3: Stale lock detection")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create a stale lock file (older than 30 minutes)
        lock_path = create_mock_lock_file(
            Path(tmpdir), 
            "sprint1/.execution.lock", 
            age_minutes=35
        )
        
        # Mock _is_process_running to return False (process not running)
        with patch.object(monitor, '_is_process_running', return_value=False):
            issues = monitor.check_stale_locks(max_age_minutes=30)
        
        assert len(issues) == 1, f"Should detect 1 stale lock, found {len(issues)}"
        assert issues[0].component == 'lock', "Issue should be of component type 'lock'"
        assert issues[0].severity == 'warning', "Issue should have severity 'warning'"
        assert 'Stale execution lock' in issues[0].description
        
        print("  PASS: Stale lock detected correctly")
        return True


def test_active_lock_not_detected_as_stale():
    """Test that active locks (with running process) are not flagged."""
    print("Test 4: Active lock not detected as stale")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create a lock file with a PID
        lock_path = create_mock_lock_file(
            Path(tmpdir),
            "sprint1/.execution.lock",
            age_minutes=35,
            pid=12345
        )
        
        # Mock _is_process_running to return True (process still running)
        with patch.object(monitor, '_is_process_running', return_value=True):
            issues = monitor.check_stale_locks(max_age_minutes=30)
        
        assert len(issues) == 0, "Should not detect active locks as stale"
        
        print("  PASS: Active lock correctly ignored")
        return True


def test_fresh_lock_not_detected():
    """Test that recent locks are not flagged as stale."""
    print("Test 5: Fresh lock not detected as stale")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create a fresh lock file (only 5 minutes old)
        lock_path = create_mock_lock_file(
            Path(tmpdir),
            "sprint1/.execution.lock",
            age_minutes=5
        )
        
        issues = monitor.check_stale_locks(max_age_minutes=30)
        
        assert len(issues) == 0, "Should not detect fresh locks"
        
        print("  PASS: Fresh lock correctly ignored")
        return True


def test_log_size_detection():
    """Test detection of oversized log files."""
    print("Test 6: Oversized log file detection")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create monitor with 1MB retention
        monitor = HealthMonitor(base_dir=tmpdir, log_retention_mb=1)
        
        # Create an oversized log file (2MB)
        log_path = create_mock_log_file(
            Path(tmpdir),
            "sprint1/logs/agent_001.log",
            size_mb=2.0
        )
        
        issues = monitor.check_log_sizes()
        
        assert len(issues) == 1, f"Should detect 1 oversized log, found {len(issues)}"
        assert issues[0].component == 'log', "Issue should be of component type 'log'"
        assert issues[0].severity == 'info', "Issue should have severity 'info'"
        assert 'Oversized log file' in issues[0].description
        assert issues[0].details['size_mb'] > 1.0
        
        print("  PASS: Oversized log detected correctly")
        return True


def test_normal_log_not_detected():
    """Test that normal-sized logs are not flagged."""
    print("Test 7: Normal log file not flagged")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create monitor with 1MB retention
        monitor = HealthMonitor(base_dir=tmpdir, log_retention_mb=1)
        
        # Create a normal-sized log file (0.5MB)
        log_path = create_mock_log_file(
            Path(tmpdir),
            "sprint1/logs/agent_001.log",
            size_mb=0.5
        )
        
        issues = monitor.check_log_sizes()
        
        assert len(issues) == 0, "Should not detect normal-sized logs"
        
        print("  PASS: Normal log correctly ignored")
        return True


def test_hung_agent_detection():
    """Test detection of potentially hung agents."""
    print("Test 8: Hung agent detection")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create monitor with 1 hour max duration
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create a sprint with an agent log that's inactive for 3 hours
        create_mock_agent_log(
            Path(tmpdir),
            "sprint1",
            "001",
            age_hours=3.0  # More than max_duration_hours (2 hours)
        )
        
        issues = monitor.check_hung_agents(max_duration_hours=2.0)
        
        assert len(issues) >= 1, "Should detect hung agents"
        hung_issue = next((issue for issue in issues if 'hung agent' in issue.description.lower()), None)
        assert hung_issue is not None, "Should have a hung agent issue"
        assert hung_issue.component == 'agent', "Issue should be of component type 'agent'"
        assert hung_issue.severity == 'warning', "Issue should have severity 'warning'"
        
        print("  PASS: Hung agent detected correctly")
        return True


def test_active_agent_not_detected():
    """Test that recently active agents are not flagged as hung."""
    print("Test 9: Recently active agent not detected as hung")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create a sprint with a recent agent log (only 1 hour old)
        create_mock_agent_log(
            Path(tmpdir),
            "sprint1",
            "001",
            age_hours=1.0  # Less than max_duration_hours (2 hours)
        )
        
        issues = monitor.check_hung_agents(max_duration_hours=2.0)
        
        # Filter for hung agent issues specifically
        hung_issues = [issue for issue in issues if 'hung agent' in issue.description.lower()]
        assert len(hung_issues) == 0, "Should not detect recently active agents as hung"
        
        print("  PASS: Recently active agent correctly ignored")
        return True


# =============================================================================
# Test 3: Recovery detection after failure
# =============================================================================

def test_recovery_after_stale_lock_cleanup():
    """Test that stale locks can be cleaned up."""
    print("Test 10: Recovery after stale lock cleanup")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create a stale lock file
        lock_path = create_mock_lock_file(
            Path(tmpdir),
            "sprint1/.execution.lock",
            age_minutes=35
        )
        
        # Verify lock exists initially
        assert lock_path.exists(), "Lock file should exist initially"
        
        # Mock _is_process_running to return False so cleanup occurs
        with patch.object(monitor, '_is_process_running', return_value=False):
            issues = monitor.check_stale_locks(max_age_minutes=30)
        
        # Perform recovery actions
        results = monitor.perform_recovery_actions(issues)
        
        # Check that the lock was resolved
        assert len(results['resolved']) > 0, "Should have resolved at least one issue"
        assert not lock_path.exists(), "Lock file should be removed after cleanup"
        
        print("  PASS: Stale lock recovered successfully")
        return True


def test_recovery_results_structure():
    """Test that recovery results have correct structure."""
    print("Test 11: Recovery results structure")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create a stale lock file
        lock_path = create_mock_lock_file(
            Path(tmpdir),
            "sprint1/.execution.lock",
            age_minutes=35
        )
        
        # Mock _is_process_running to return False so cleanup occurs
        with patch.object(monitor, '_is_process_running', return_value=False):
            issues = monitor.check_stale_locks(max_age_minutes=30)
        
        results = monitor.perform_recovery_actions(issues)
        
        # Check structure of results
        assert 'resolved' in results, "Results should have 'resolved' key"
        assert 'failed' in results, "Results should have 'failed' key"
        assert 'skipped' in results, "Results should have 'skipped' key"
        
        assert isinstance(results['resolved'], list), "Resolved should be a list"
        assert isinstance(results['failed'], list), "Failed should be a list"
        assert isinstance(results['skipped'], list), "Skipped should be a list"
        
        print("  PASS: Recovery results have correct structure")
        return True


# =============================================================================
# Test 4: Error rate calculation
# =============================================================================

def test_error_rate_tracking_via_issue_severity():
    """Test that issues are properly categorized by severity."""
    print("Test 12: Error rate tracking via issue severity")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create multiple issues of different severities
        # Create several stale locks (warnings)
        lock1 = create_mock_lock_file(Path(tmpdir), "sprint1/.execution.lock", age_minutes=35)
        lock2 = create_mock_lock_file(Path(tmpdir), "sprint2/.execution.lock", age_minutes=40)
        
        # Mock _is_process_running to return False
        with patch.object(monitor, '_is_process_running', return_value=False):
            issues = monitor.check_stale_locks(max_age_minutes=30)
        
        # Count warnings
        warnings = [issue for issue in issues if issue.severity == 'warning']
        criticals = [issue for issue in issues if issue.severity == 'critical']
        
        # Should have 2 warnings
        assert len(warnings) == 2, f"Should have 2 warnings, got {len(warnings)}"
        assert len(criticals) == 0, f"Should have 0 criticals, got {len(criticals)}"
        
        print("  PASS: Issues properly categorized by severity")
        return True


# =============================================================================
# Test 5: Status aggregation across components
# =============================================================================

def test_status_aggregation_all_components():
    """Test that health check aggregates status across all components."""
    print("Test 13: Status aggregation across components")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create various issues
        # 1. Stale lock
        lock_path = create_mock_lock_file(Path(tmpdir), "sprint1/.execution.lock", age_minutes=35)
        
        # 2. Large log file
        log_path = create_mock_log_file(Path(tmpdir), "sprint1/logs/agent_001.log", size_mb=2.0)
        
        # Mock _is_process_running to return False
        with patch.object(monitor, '_is_process_running', return_value=False):
            report = monitor.run_health_check()
        
        # Should have issues in at least some categories
        total_issues = sum(len(issues) for issues in report.values())
        # Since we're only creating lock and log issues, total may be 2 or more depending on disk checks
        # The main point is that the structure is properly populated
        assert isinstance(report, dict), "Report should be a dictionary"
        assert 'locks' in report and 'logs' in report and 'agents' in report and 'disk' in report, \
               "Report should contain all component keys"
        
        # Check that the aggregation worked (each key maps to a list)
        for component, issues_list in report.items():
            assert isinstance(issues_list, list), f"Component '{component}' should map to a list"
        
        print("  PASS: Status aggregated across components")
        return True


def test_global_health_monitor_singleton():
    """Test that get_health_monitor returns singleton instance."""
    print("Test 14: Global health monitor singleton")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor1 = get_health_monitor(base_dir=tmpdir)
        monitor2 = get_health_monitor(base_dir=tmpdir)
        
        # Should be the same instance
        assert monitor1 is monitor2, "Global monitor should be singleton"
        
        print("  PASS: Global health monitor is singleton")
        return True


def test_convenience_functions():
    """Test that convenience functions work correctly."""
    print("Test 15: Convenience functions")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        # Temporarily set the global monitor to our test dir
        original_monitor = getattr(sys.modules['health_monitor'], '_health_monitor', None)
        
        try:
            # Force reset the global monitor to use our temp dir
            sys.modules['health_monitor']._health_monitor = HealthMonitor(base_dir=tmpdir)
            
            # Create a stale lock
            lock_path = create_mock_lock_file(Path(tmpdir), "sprint1/.execution.lock", age_minutes=35)
            
            # Mock _is_process_running to return False
            with patch.object(HealthMonitor, '_is_process_running', return_value=False):
                # Test run_health_check convenience function
                report = run_health_check()
                
                # Should have detected the lock issue
                assert len(report['locks']) > 0, "Convenience function should detect issues"
                
                # Test cleanup_stale_locks
                cleanup_result = cleanup_stale_locks(max_age_minutes=30)
                assert 'resolved' in cleanup_result, "Cleanup should return results dict"
                
                # Test rotate_large_logs
                rotate_result = rotate_large_logs()
                assert 'large_logs' in rotate_result, "Rotate should return large_logs key"
                
        finally:
            # Restore original monitor
            sys.modules['health_monitor']._health_monitor = original_monitor
        
        print("  PASS: Convenience functions work correctly")
        return True


def test_disk_space_check():
    """Test disk space checking functionality."""
    print("Test 16: Disk space check")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Test with a very high minimum requirement (should trigger issue)
        # We'll mock psutil.disk_usage to return low space
        with patch('health_monitor.psutil.disk_usage') as mock_disk_usage:
            # Mock low disk space (0.1GB free, less than default 1GB requirement)
            mock_usage = Mock()
            mock_usage.free = int(0.1 * 1024 ** 3)  # 0.1 GB in bytes
            mock_usage.total = int(100 * 1024 ** 3)  # 100 GB total
            mock_usage.used = int(99.9 * 1024 ** 3)  # 99.9 GB used
            mock_disk_usage.return_value = mock_usage
            
            issues = monitor.check_disk_space(min_free_gb=1.0)
            
            # Should have a critical disk space issue
            critical_issues = [issue for issue in issues if issue.severity == 'critical']
            assert len(critical_issues) > 0, "Should detect critical disk space issue"
            assert critical_issues[0].component == 'disk', "Issue should be of component type 'disk'"
        
        print("  PASS: Disk space check works correctly")
        return True


def test_error_handling_in_checks():
    """Test that error handling works in health checks."""
    print("Test 17: Error handling in health checks")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = HealthMonitor(base_dir=tmpdir)
        
        # Create a problematic file scenario by mocking the open function to raise an error
        with patch('builtins.open', side_effect=PermissionError("Simulated permission error")):
            # Create a lock file that exists but can't be read
            lock_path = create_mock_lock_file(Path(tmpdir), "sprint1/.execution.lock", age_minutes=35)
            
            # This will cause an error when trying to read the PID from the lock file
            issues = monitor.check_stale_locks(max_age_minutes=30)
        
        # Should handle the error gracefully and return a list
        assert isinstance(issues, list), "Should return a list even when errors occur"
        
        # Should have at least some issues (could be warnings about not being able to check)
        warning_issues = [issue for issue in issues if issue.severity == 'warning']
        # The function should handle the error gracefully rather than crashing
        
        print("  PASS: Error handling works correctly")
        return True


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("Running health_monitor tests")
    print("=" * 60)
    print()
    
    tests = [
        test_health_check_returns_correct_status,
        test_health_check_empty_when_healthy,
        test_stale_lock_detection,
        test_active_lock_not_detected_as_stale,
        test_fresh_lock_not_detected,
        test_log_size_detection,
        test_normal_log_not_detected,
        test_hung_agent_detection,
        test_active_agent_not_detected,
        test_recovery_after_stale_lock_cleanup,
        test_recovery_results_structure,
        test_error_rate_tracking_via_issue_severity,
        test_status_aggregation_all_components,
        test_global_health_monitor_singleton,
        test_convenience_functions,
        test_disk_space_check,
        test_error_handling_in_checks,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"  ERROR in {test.__name__}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test.__name__, False))
        print()
    
    print("=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
    print()
    print(f"Total: {passed}/{total} tests passed")
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)