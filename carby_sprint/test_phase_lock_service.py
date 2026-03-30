"""Comprehensive tests for phase_lock_service module.

Tests cover:
- Distributed locking (acquire/release)
- Two-phase commit (2PC) state updates
- Build phase validation with design tokens
- Thread safety and concurrent access
- Lock expiration and cleanup
- Cross-sprint isolation
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch, mock_open

import pytest

from .phase_lock_service import (
    PhaseLockService,
    PhaseState,
    PhaseTransitionError,
    PhaseLockServiceError,
    ConcurrentUpdateError,
    _validate_state_transition,
    _get_previous_phase,
    _load_phase_lock,
    _save_phase_lock,
    _get_phase_lock_path,
    _get_design_token_path,
    PHASE_ORDER,
    VALID_TRANSITIONS,
)
from .sprint_repository import SprintRepository, SprintPaths
from .gate_enforcer import GateEnforcer, DesignGateEnforcer, GateBypassError, GateEnforcementError
from .two_phase_commit import TwoPhaseCommitCoordinator, TwoPhaseCommitError


class TestPhaseLockService:
    """Test suite for PhaseLockService class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        tmp = tempfile.mkdtemp()
        yield Path(tmp)
        shutil.rmtree(tmp, ignore_errors=True)

    @pytest.fixture
    def sprint_repo(self, temp_dir):
        """Create a SprintRepository with temp directory."""
        return SprintRepository(output_dir=str(temp_dir))

    @pytest.fixture
    def phase_service(self, sprint_repo):
        """Create a PhaseLockService instance."""
        return PhaseLockService(repository=sprint_repo)

    @pytest.fixture
    def sample_sprint(self, sprint_repo, temp_dir):
        """Create a sample sprint for testing."""
        sprint_id = "test-sprint-001"
        sprint_data, paths = sprint_repo.create(
            sprint_id=sprint_id,
            project="Test Project",
            goal="Test sprint for phase locking",
            duration_days=7
        )
        # Initialize phase_lock.json
        phase_lock = {
            "sprint_id": sprint_id,
            "phases": {
                p: {"state": PhaseState.PENDING.value, "summary": None}
                for p in PHASE_ORDER
            }
        }
        lock_path = _get_phase_lock_path(paths.sprint_dir)
        _save_phase_lock(phase_lock, paths.sprint_dir)
        return sprint_id, sprint_data, paths

    # =========================================================================
    # Test 1: Lock acquisition succeeds when available
    # =========================================================================
    def test_acquire_phase_lock_succeeds_when_available(self, phase_service, sample_sprint):
        """Test that lock acquisition succeeds when lock is available."""
        sprint_id, _, paths = sample_sprint
        
        # Acquire lock using the internal method
        with phase_service._acquire_lock(sprint_id):
            # Lock should be held
            assert phase_service._is_lock_held(sprint_id)
        
        # After context exit, lock should be released
        assert not phase_service._is_lock_held(sprint_id)

    # =========================================================================
    # Test 2: Lock acquisition fails when already held (by another process/thread)
    # =========================================================================
    def test_lock_acquisition_fails_when_already_held(self, phase_service, sample_sprint, temp_dir):
        """Test that lock acquisition fails when lock is already held."""
        sprint_id, _, _ = sample_sprint
        lock_path = phase_service._get_lock_file_path(sprint_id)
        
        # Create lock file and hold it
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Use a thread to hold the lock
        lock_held = threading.Event()
        can_release = threading.Event()
        
        def hold_lock():
            from .lock_manager import DistributedLock, LockTimeoutError
            try:
                with DistributedLock(lock_path, timeout=0.5):
                    lock_held.set()
                    can_release.wait(timeout=2)
            except LockTimeoutError:
                pass
        
        # Start thread holding the lock
        holder = threading.Thread(target=hold_lock)
        holder.start()
        lock_held.wait(timeout=1)
        
        # Try to acquire lock with short timeout
        from .lock_manager import DistributedLock, LockTimeoutError
        with pytest.raises(LockTimeoutError):
            with DistributedLock(lock_path, timeout=0.1):
                pass  # Should not reach here
        
        # Release the lock
        can_release.set()
        holder.join(timeout=2)

    # =========================================================================
    # Test 3: Lock release works correctly
    # =========================================================================
    def test_release_phase_lock_works_correctly(self, phase_service, sample_sprint):
        """Test that lock release works correctly."""
        sprint_id = sample_sprint[0]
        
        # Acquire and release lock multiple times
        for _ in range(3):
            with phase_service._acquire_lock(sprint_id):
                assert phase_service._is_lock_held(sprint_id)
            assert not phase_service._is_lock_held(sprint_id)

    # =========================================================================
    # Test 4: Lock expiration/timeout
    # =========================================================================
    def test_lock_expiration_timeout(self, phase_service, sample_sprint):
        """Test that lock acquisition respects timeout."""
        sprint_id = sample_sprint[0]
        lock_path = phase_service._get_lock_file_path(sprint_id)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        
        from .lock_manager import DistributedLock, LockTimeoutError
        
        # Acquire lock in one thread
        lock_acquired = threading.Event()
        can_release = threading.Event()
        
        def hold_lock():
            with DistributedLock(lock_path, timeout=30):
                lock_acquired.set()
                can_release.wait(timeout=2)
        
        holder = threading.Thread(target=hold_lock)
        holder.start()
        lock_acquired.wait(timeout=1)
        
        # Try to acquire with very short timeout - should fail
        start_time = time.time()
        with pytest.raises(LockTimeoutError):
            with DistributedLock(lock_path, timeout=0.1):
                pass
        elapsed = time.time() - start_time
        
        # Should have failed quickly (within timeout + small margin)
        assert elapsed < 0.5
        
        can_release.set()
        holder.join(timeout=2)

    # =========================================================================
    # Test 5: State updates with two-phase commit
    # =========================================================================
    def test_state_update_with_two_phase_commit(self, phase_service, sample_sprint):
        """Test that state updates use 2PC correctly."""
        sprint_id, _, paths = sample_sprint
        
        # Update phase state using 2PC (default)
        result = phase_service.update_phase_state(
            sprint_id=sprint_id,
            phase_id="discover",
            state=PhaseState.IN_PROGRESS.value,
            use_two_phase_commit=True
        )
        
        assert result["success"] is True
        assert result["sprint_id"] == sprint_id
        assert result["phase_id"] == "discover"
        assert result["new_state"] == PhaseState.IN_PROGRESS.value
        assert result["two_phase_commit"] is True
        
        # Verify the state was actually updated
        phase_state = phase_service.get_phase_state(sprint_id, "discover")
        assert phase_state["state"] == PhaseState.IN_PROGRESS.value

    # =========================================================================
    # Test 6: State update rollback on failure
    # =========================================================================
    @patch('carby_sprint.two_phase_commit.TwoPhaseCommitCoordinator.execute_transaction')
    def test_state_update_rollback_on_failure(self, mock_execute, phase_service, sample_sprint):
        """Test that state updates are rolled back on failure."""
        sprint_id, _, paths = sample_sprint
        
        # Mock 2PC to fail
        mock_execute.return_value = {
            "success": False,
            "error": "Simulated failure",
            "transaction_id": "mock-tx-id",
            "phase1_result": "success",
            "phase2_result": "rolled_back"
        }
        
        result = phase_service.update_phase_state(
            sprint_id=sprint_id,
            phase_id="discover",
            state=PhaseState.IN_PROGRESS.value,
            use_two_phase_commit=True
        )
        
        assert result["success"] is False
        assert "Two-phase commit failed" in result["error"]
        
        # Verify the state remains unchanged
        phase_state = phase_service.get_phase_state(sprint_id, "discover")
        assert phase_state["state"] == PhaseState.PENDING.value

    # =========================================================================
    # Test 7: Build phase validation with design token
    # =========================================================================
    def test_build_phase_validation_with_design_token(self, temp_dir):
        """Test that build phase validation works with design token."""
        sprint_repo = SprintRepository(output_dir=str(temp_dir))
        
        # Create a mock gate enforcer
        mock_gate = MagicMock(spec=GateEnforcer)
        mock_design_gate = MagicMock(spec=DesignGateEnforcer)
        
        phase_service = PhaseLockService(repository=sprint_repo, gate_enforcer=mock_gate)
        
        # Create a sample sprint
        sprint_id = "test-sprint-build"
        sprint_data, paths = sprint_repo.create(
            sprint_id=sprint_id,
            project="Test Project",
            goal="Test build phase validation",
            duration_days=7
        )
        
        # Initialize phase_lock.json
        phase_lock = {
            "sprint_id": sprint_id,
            "phases": {
                p: {"state": PhaseState.PENDING.value, "summary": None}
                for p in PHASE_ORDER
            }
        }
        lock_path = _get_phase_lock_path(paths.sprint_dir)
        _save_phase_lock(phase_lock, paths.sprint_dir)
        
        # First, approve design phase and create design token
        design_approve_path = _get_design_token_path(paths.sprint_dir)
        design_token_data = {
            "token": "design-approval-token-123",
            "sprint_id": sprint_id,
            "approved_at": datetime.utcnow().isoformat(),
            "approver": "test-user",
            "expires_at": (datetime.utcnow() + timedelta(hours=24)).isoformat()
        }
        design_approve_path.parent.mkdir(parents=True, exist_ok=True)
        with open(design_approve_path, 'w') as f:
            json.dump(design_token_data, f)
        
        # Set design phase to approved
        phase_lock["phases"]["design"]["state"] = PhaseState.APPROVED.value
        _save_phase_lock(phase_lock, paths.sprint_dir)
        
        # Now try to start build phase - should succeed
        result = phase_service.can_start_phase(sprint_id, "build")
        assert result["can_start"] is True
        assert result["sprint_id"] == sprint_id
        assert result["phase_id"] == "build"

    # =========================================================================
    # Test 8: Invalid design token rejection
    # =========================================================================
    def test_invalid_design_token_rejection(self, temp_dir):
        """Test that invalid design tokens are rejected."""
        sprint_repo = SprintRepository(output_dir=str(temp_dir))
        
        # Create a mock gate enforcer
        mock_gate = MagicMock(spec=GateEnforcer)
        mock_design_gate = MagicMock(spec=DesignGateEnforcer)
        
        phase_service = PhaseLockService(repository=sprint_repo, gate_enforcer=mock_gate)
        
        # Create a sample sprint
        sprint_id = "test-sprint-invalid-token"
        sprint_data, paths = sprint_repo.create(
            sprint_id=sprint_id,
            project="Test Project",
            goal="Test invalid token rejection",
            duration_days=7
        )
        
        # Initialize phase_lock.json
        phase_lock = {
            "sprint_id": sprint_id,
            "phases": {
                p: {"state": PhaseState.PENDING.value, "summary": None}
                for p in PHASE_ORDER
            }
        }
        lock_path = _get_phase_lock_path(paths.sprint_dir)
        _save_phase_lock(phase_lock, paths.sprint_dir)
        
        # Create invalid design token (not approved)
        design_approve_path = _get_design_token_path(paths.sprint_dir)
        design_token_data = {
            "token": "invalid-design-token-123",
            "sprint_id": sprint_id,
            "requested_at": datetime.utcnow().isoformat(),
            "status": "awaiting_approval"
        }
        design_approve_path.parent.mkdir(parents=True, exist_ok=True)
        with open(design_approve_path, 'w') as f:
            json.dump(design_token_data, f)
        
        # Try to start build phase - should fail
        result = phase_service.can_start_phase(sprint_id, "build")
        assert result["can_start"] is False
        assert "Design approval token not found" in result["error"] or "not approved" in result["error"]

    # =========================================================================
    # Test 9: Expired design token rejection
    # =========================================================================
    def test_expired_design_token_rejection(self, temp_dir):
        """Test that expired design tokens are rejected."""
        sprint_repo = SprintRepository(output_dir=str(temp_dir))
        
        # Create a mock gate enforcer
        mock_gate = MagicMock(spec=GateEnforcer)
        mock_design_gate = MagicMock(spec=DesignGateEnforcer)
        
        phase_service = PhaseLockService(repository=sprint_repo, gate_enforcer=mock_gate)
        
        # Create a sample sprint
        sprint_id = "test-sprint-expired-token"
        sprint_data, paths = sprint_repo.create(
            sprint_id=sprint_id,
            project="Test Project",
            goal="Test expired token rejection",
            duration_days=7
        )
        
        # Initialize phase_lock.json
        phase_lock = {
            "sprint_id": sprint_id,
            "phases": {
                p: {"state": PhaseState.PENDING.value, "summary": None}
                for p in PHASE_ORDER
            }
        }
        # Set design phase to approved so that build phase can be considered
        # This simulates the scenario where design was completed but the token has expired
        phase_lock["phases"]["discover"]["state"] = PhaseState.APPROVED.value
        phase_lock["phases"]["design"]["state"] = PhaseState.APPROVED.value
        lock_path = _get_phase_lock_path(paths.sprint_dir)
        _save_phase_lock(phase_lock, paths.sprint_dir)
        
        # Create expired design token
        design_approve_path = _get_design_token_path(paths.sprint_dir)
        expired_time = datetime.utcnow() - timedelta(hours=1)  # 1 hour ago
        design_token_data = {
            "token": "expired-design-token-123",
            "sprint_id": sprint_id,
            "approved_at": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "approver": "test-user",
            "expires_at": expired_time.isoformat()
        }
        design_approve_path.parent.mkdir(parents=True, exist_ok=True)
        with open(design_approve_path, 'w') as f:
            json.dump(design_token_data, f)
        
        # Try to start build phase - should fail due to expired token
        result = phase_service.can_start_phase(sprint_id, "build")
        assert result["can_start"] is False
        assert "expired" in result["error"].lower() or "invalid" in result["error"].lower()

    # =========================================================================
    # Test 10: Thread safety with concurrent lock attempts
    # =========================================================================
    def test_thread_safety_concurrent_lock_attempts(self, phase_service, sample_sprint):
        """Test thread safety with concurrent lock attempts."""
        sprint_id = sample_sprint[0]
        
        # Counter to track how many threads accessed the critical section
        counter = 0
        counter_lock = threading.Lock()
        
        def worker():
            nonlocal counter
            with phase_service._acquire_lock(sprint_id):
                # Simulate some work in critical section
                current = counter
                time.sleep(0.01)  # Small delay to increase chance of race condition
                with counter_lock:
                    counter = current + 1
        
        # Run multiple threads concurrently
        num_threads = 10
        threads = []
        for _ in range(num_threads):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        
        # Wait for all threads to complete
        for t in threads:
            t.join()
        
        # Counter should equal number of threads since only one could access at a time
        assert counter == num_threads

    # =========================================================================
    # Test 11: Lock file cleanup
    # =========================================================================
    def test_lock_file_cleanup(self, phase_service, sample_sprint):
        """Test that lock files are properly managed."""
        sprint_id = sample_sprint[0]
        lock_path = phase_service._get_lock_file_path(sprint_id)
        
        # Verify lock path is constructed correctly
        expected_path = Path(".carby-sprints") / sprint_id / ".phase_lock_service.lock"
        assert lock_path.name == expected_path.name
        assert sprint_id in str(lock_path)
        
        # The lock file itself is created and cleaned up by the DistributedLock context manager
        # We can verify that our service correctly constructs the path

    # =========================================================================
    # Test 12: Cross-sprint isolation
    # =========================================================================
    def test_cross_sprint_isolation(self, phase_service, sample_sprint, temp_dir):
        """Test that different sprints have isolated locks and states."""
        # Create a second sprint
        sprint_repo = SprintRepository(output_dir=str(temp_dir))
        sprint_id_1, _, _ = sample_sprint
        sprint_id_2 = "test-sprint-002"
        sprint_data_2, paths_2 = sprint_repo.create(
            sprint_id=sprint_id_2,
            project="Test Project 2",
            goal="Second test sprint for isolation",
            duration_days=7
        )
        
        # Initialize phase_lock.json for second sprint
        phase_lock_2 = {
            "sprint_id": sprint_id_2,
            "phases": {
                p: {"state": PhaseState.PENDING.value, "summary": None}
                for p in PHASE_ORDER
            }
        }
        lock_path_2 = _get_phase_lock_path(paths_2.sprint_dir)
        _save_phase_lock(phase_lock_2, paths_2.sprint_dir)
        
        # Update phase in first sprint
        result1 = phase_service.update_phase_state(
            sprint_id=sprint_id_1,
            phase_id="discover",
            state=PhaseState.IN_PROGRESS.value
        )
        
        # Update phase in second sprint
        result2 = phase_service.update_phase_state(
            sprint_id=sprint_id_2,
            phase_id="discover",
            state=PhaseState.IN_PROGRESS.value
        )
        
        # Both should succeed independently
        assert result1["success"] is True
        assert result2["success"] is True
        assert result1["sprint_id"] == sprint_id_1
        assert result2["sprint_id"] == sprint_id_2
        
        # Check that states are independent
        state1 = phase_service.get_phase_state(sprint_id_1, "discover")
        state2 = phase_service.get_phase_state(sprint_id_2, "discover")
        
        assert state1["sprint_id"] == sprint_id_1
        assert state2["sprint_id"] == sprint_id_2
        assert state1["state"] == PhaseState.IN_PROGRESS.value
        assert state2["state"] == PhaseState.IN_PROGRESS.value

    # =========================================================================
    # Additional helper function tests
    # =========================================================================
    def test_validate_state_transition(self):
        """Test the state transition validation function."""
        # Valid transitions
        assert _validate_state_transition(PhaseState.PENDING.value, PhaseState.IN_PROGRESS.value) is True
        assert _validate_state_transition(PhaseState.IN_PROGRESS.value, PhaseState.AWAITING_APPROVAL.value) is True
        assert _validate_state_transition(PhaseState.AWAITING_APPROVAL.value, PhaseState.APPROVED.value) is True
        assert _validate_state_transition(PhaseState.AWAITING_APPROVAL.value, PhaseState.IN_PROGRESS.value) is True
        
        # Invalid transitions
        assert _validate_state_transition(PhaseState.PENDING.value, PhaseState.APPROVED.value) is False
        assert _validate_state_transition(PhaseState.IN_PROGRESS.value, PhaseState.APPROVED.value) is False
        assert _validate_state_transition(PhaseState.APPROVED.value, PhaseState.IN_PROGRESS.value) is False  # Approved is terminal

    def test_get_previous_phase(self):
        """Test getting the previous phase."""
        assert _get_previous_phase("design") == "discover"
        assert _get_previous_phase("build") == "design"
        assert _get_previous_phase("discover") is None  # First phase has no predecessor
        assert _get_previous_phase("invalid_phase") is None  # Invalid phase


class TestHelperFunctions:
    """Test helper functions for phase lock service."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        tmp = tempfile.mkdtemp()
        yield Path(tmp)
        shutil.rmtree(tmp, ignore_errors=True)

    def test_load_save_phase_lock(self, temp_dir):
        """Test loading and saving phase lock files."""
        sprint_dir = temp_dir / "test-sprint"
        sprint_dir.mkdir()
        
        # Create initial data
        initial_data = {
            "sprint_id": "test-sprint",
            "phases": {
                "discover": {"state": PhaseState.PENDING.value, "summary": "Initial discovery"},
                "design": {"state": PhaseState.PENDING.value, "summary": None}
            }
        }
        
        # Save the data
        _save_phase_lock(initial_data, sprint_dir)
        
        # Load the data back
        loaded_data = _load_phase_lock(sprint_dir)
        
        assert loaded_data["sprint_id"] == "test-sprint"
        assert loaded_data["phases"]["discover"]["state"] == PhaseState.PENDING.value
        assert loaded_data["phases"]["discover"]["summary"] == "Initial discovery"
        assert loaded_data["phases"]["design"]["state"] == PhaseState.PENDING.value

    def test_load_phase_lock_defaults(self, temp_dir):
        """Test that loading creates default data if file doesn't exist."""
        sprint_dir = temp_dir / "new-sprint"
        sprint_dir.mkdir()
        
        # Load from non-existent file - should create defaults
        loaded_data = _load_phase_lock(sprint_dir)
        
        assert loaded_data["sprint_id"] == "new-sprint"
        for phase in PHASE_ORDER:
            assert phase in loaded_data["phases"]
            assert loaded_data["phases"][phase]["state"] == PhaseState.PENDING.value
            assert loaded_data["phases"][phase]["summary"] is None


if __name__ == "__main__":
    pytest.main([__file__])