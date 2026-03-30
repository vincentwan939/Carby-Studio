"""
Tests for Work Item State validation and transitions.

This module tests:
1. State transition validation
2. Atomic state persistence
3. Integration with agent callbacks
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

from carby_sprint.sprint_repository import SprintRepository
from carby_sprint.validators import (
    validate_work_item_state_transition,
    get_valid_work_item_transitions,
    WORK_ITEM_VALID_TRANSITIONS,
    WorkItemStatus
)


class TestWorkItemStateValidation:
    """Test work item state transition validation."""
    
    def test_valid_transitions_from_planned(self):
        """Test valid transitions from planned state."""
        assert validate_work_item_state_transition("planned", "in_progress") is True
        assert validate_work_item_state_transition("planned", "cancelled") is True
        assert validate_work_item_state_transition("planned", "completed") is False
        assert validate_work_item_state_transition("planned", "failed") is False
        assert validate_work_item_state_transition("planned", "blocked") is False
    
    def test_valid_transitions_from_in_progress(self):
        """Test valid transitions from in_progress state."""
        assert validate_work_item_state_transition("in_progress", "completed") is True
        assert validate_work_item_state_transition("in_progress", "failed") is True
        assert validate_work_item_state_transition("in_progress", "blocked") is True
        assert validate_work_item_state_transition("in_progress", "cancelled") is True
        assert validate_work_item_state_transition("in_progress", "planned") is False
        assert validate_work_item_state_transition("in_progress", "in_progress") is False
    
    def test_valid_transitions_from_blocked(self):
        """Test valid transitions from blocked state."""
        assert validate_work_item_state_transition("blocked", "in_progress") is True
        assert validate_work_item_state_transition("blocked", "failed") is True
        assert validate_work_item_state_transition("blocked", "cancelled") is True
        assert validate_work_item_state_transition("blocked", "completed") is False
        assert validate_work_item_state_transition("blocked", "planned") is False
    
    def test_valid_transitions_from_failed(self):
        """Test valid transitions from failed state."""
        assert validate_work_item_state_transition("failed", "in_progress") is True
        assert validate_work_item_state_transition("failed", "cancelled") is True
        assert validate_work_item_state_transition("failed", "completed") is False
        assert validate_work_item_state_transition("failed", "planned") is False
    
    def test_terminal_states_no_transitions(self):
        """Test that terminal states have no valid transitions."""
        assert validate_work_item_state_transition("completed", "in_progress") is False
        assert validate_work_item_state_transition("completed", "failed") is False
        assert validate_work_item_state_transition("completed", "planned") is False
        assert validate_work_item_state_transition("cancelled", "in_progress") is False
        assert validate_work_item_state_transition("cancelled", "planned") is False
    
    def test_invalid_current_state(self):
        """Test validation with invalid current state."""
        assert validate_work_item_state_transition("invalid_state", "completed") is False
    
    def test_get_valid_transitions(self):
        """Test getting valid transitions for a state."""
        assert set(get_valid_work_item_transitions("planned")) == {"in_progress", "cancelled"}
        assert set(get_valid_work_item_transitions("in_progress")) == {"completed", "failed", "blocked", "cancelled"}
        assert set(get_valid_work_item_transitions("completed")) == set()
        assert set(get_valid_work_item_transitions("invalid")) == set()


class TestWorkItemStateTransitionsIntegration:
    """Test work item state transitions with SprintRepository."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SprintRepository(tmpdir)
            yield repo
    
    @pytest.fixture
    def test_sprint(self, temp_repo):
        """Create a test sprint with work items."""
        sprint_data, paths = temp_repo.create(
            sprint_id="test-sprint",
            project="Test Project",
            goal="Test state transitions"
        )
        
        # Create a work item
        work_item = {
            "id": "WI-001",
            "title": "Test Work Item",
            "description": "For testing state transitions",
            "status": "planned",
            "priority": 1,
            "created_at": datetime.now().isoformat()
        }
        
        temp_repo.save_work_item(paths, work_item)
        
        return temp_repo, paths
    
    def test_valid_state_transition_via_repository(self, test_sprint):
        """Test valid state transition using repository method."""
        repo, paths = test_sprint
        
        # Transition: planned -> in_progress
        updated = repo.update_work_item_state(paths, "WI-001", "in_progress")
        assert updated["status"] == "in_progress"
        assert "started_at" in updated
        
        # Verify persistence
        loaded = repo.load_work_item(paths, "WI-001")
        assert loaded["status"] == "in_progress"
    
    def test_invalid_state_transition_raises_error(self, test_sprint):
        """Test that invalid state transition raises ValueError."""
        repo, paths = test_sprint
        
        # First transition to completed
        repo.update_work_item_state(paths, "WI-001", "in_progress")
        repo.update_work_item_state(paths, "WI-001", "completed")
        
        # Attempt invalid transition: completed -> in_progress
        with pytest.raises(ValueError) as exc_info:
            repo.update_work_item_state(paths, "WI-001", "in_progress")
        
        assert "Invalid state transition" in str(exc_info.value)
        assert "completed" in str(exc_info.value)
        assert "in_progress" in str(exc_info.value)
    
    def test_terminal_state_no_transitions(self, test_sprint):
        """Test that terminal states cannot transition."""
        repo, paths = test_sprint
        
        # Transition to cancelled (terminal)
        repo.update_work_item_state(paths, "WI-001", "cancelled")
        
        # Attempt transition from terminal state
        with pytest.raises(ValueError) as exc_info:
            repo.update_work_item_state(paths, "WI-001", "in_progress")
        
        assert "Invalid state transition" in str(exc_info.value)
    
    def test_full_work_item_lifecycle(self, test_sprint):
        """Test complete work item lifecycle transitions."""
        import time
        repo, paths = test_sprint
        
        # planned -> in_progress
        wi = repo.update_work_item_state(paths, "WI-001", "in_progress")
        assert wi["status"] == "in_progress"
        
        # Small delay to ensure timestamps differ
        time.sleep(0.01)
        
        # in_progress -> blocked
        wi = repo.update_work_item_state(paths, "WI-001", "blocked")
        assert wi["status"] == "blocked"
        
        time.sleep(0.01)
        
        # blocked -> in_progress (retry after unblock)
        wi = repo.update_work_item_state(paths, "WI-001", "in_progress")
        assert wi["status"] == "in_progress"
        
        time.sleep(0.01)
        
        # in_progress -> completed
        wi = repo.update_work_item_state(paths, "WI-001", "completed")
        assert wi["status"] == "completed"
        
        # Verify timestamps were set correctly
        assert "started_at" in wi
        assert "completed_at" in wi
        assert "blocked_at" in wi
    
    def test_state_persistence_across_loads(self, test_sprint):
        """Test that state changes persist across repository loads."""
        repo, paths = test_sprint
        
        # Make state change
        repo.update_work_item_state(paths, "WI-001", "in_progress")
        
        # Create new repository instance (simulates new session)
        new_repo = SprintRepository(repo.output_dir)
        new_paths = new_repo.get_paths("test-sprint")
        
        # Verify state persisted
        loaded = new_repo.load_work_item(new_paths, "WI-001")
        assert loaded["status"] == "in_progress"


class TestWorkItemStateWithAgentCallback:
    """Test work item state transitions via agent callback."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SprintRepository(tmpdir)
            yield repo
    
    @pytest.fixture
    def test_sprint_with_work_item(self, temp_repo):
        """Create a test sprint with a work item in in_progress state."""
        sprint_data, paths = temp_repo.create(
            sprint_id="callback-test",
            project="Callback Test",
            goal="Test agent callbacks"
        )
        
        # Create work item already in progress
        work_item = {
            "id": "WI-BUILD-001",
            "title": "Build Task",
            "description": "For testing callbacks",
            "status": "in_progress",
            "priority": 1,
            "created_at": datetime.now().isoformat(),
            "started_at": datetime.now().isoformat()
        }
        
        temp_repo.save_work_item(paths, work_item)
        
        return temp_repo, paths
    
    def test_agent_callback_valid_transition_success(self, test_sprint_with_work_item):
        """Test agent callback with valid success transition."""
        from carby_sprint.agent_callback import _update_work_item_status
        
        repo, paths = test_sprint_with_work_item
        
        result = {
            "status": "success",
            "message": "Build completed successfully",
            "work_item_id": "WI-BUILD-001"
        }
        
        # This should work: in_progress -> completed
        _update_work_item_status(repo, paths, "WI-BUILD-001", "success", result)
        
        # Verify state change
        wi = repo.load_work_item(paths, "WI-BUILD-001")
        assert wi["status"] == "completed"
        assert wi["completed_at"] is not None
    
    def test_agent_callback_valid_transition_failure(self, test_sprint_with_work_item):
        """Test agent callback with valid failure transition."""
        from carby_sprint.agent_callback import _update_work_item_status
        
        repo, paths = test_sprint_with_work_item
        
        result = {
            "status": "failure",
            "message": "Build failed due to test errors",
            "work_item_id": "WI-BUILD-001"
        }
        
        # This should work: in_progress -> failed
        _update_work_item_status(repo, paths, "WI-BUILD-001", "failure", result)
        
        # Verify state change
        wi = repo.load_work_item(paths, "WI-BUILD-001")
        assert wi["status"] == "failed"
        assert wi["failed_at"] is not None
        assert wi["failure_reason"] == "Build failed due to test errors"
    
    def test_agent_callback_valid_transition_blocked(self, test_sprint_with_work_item):
        """Test agent callback with valid blocked transition."""
        from carby_sprint.agent_callback import _update_work_item_status
        
        repo, paths = test_sprint_with_work_item
        
        result = {
            "status": "blocked",
            "message": "Blocked by dependency",
            "work_item_id": "WI-BUILD-001"
        }
        
        # This should work: in_progress -> blocked
        _update_work_item_status(repo, paths, "WI-BUILD-001", "blocked", result)
        
        # Verify state change
        wi = repo.load_work_item(paths, "WI-BUILD-001")
        assert wi["status"] == "blocked"
        assert wi["blocked_at"] is not None
        assert wi["block_reason"] == "Blocked by dependency"
    
    def test_agent_callback_invalid_transition_raises_error(self, temp_repo):
        """Test agent callback with invalid transition raises error."""
        from carby_sprint.agent_callback import _update_work_item_status
        
        repo = temp_repo
        sprint_data, paths = repo.create(
            sprint_id="invalid-test",
            project="Invalid Test",
            goal="Test invalid transitions"
        )
        
        # Create work item already completed
        work_item = {
            "id": "WI-COMPLETED",
            "title": "Completed Task",
            "description": "Already done",
            "status": "completed",
            "priority": 1,
            "created_at": datetime.now().isoformat(),
            "completed_at": datetime.now().isoformat()
        }
        repo.save_work_item(paths, work_item)
        
        result = {
            "status": "success",
            "message": "Trying to update completed item",
            "work_item_id": "WI-COMPLETED"
        }
        
        # This should fail: completed -> completed is invalid (no transitions from terminal)
        with pytest.raises(ValueError) as exc_info:
            _update_work_item_status(repo, paths, "WI-COMPLETED", "success", result)
        
        assert "Invalid work item state transition" in str(exc_info.value)


class TestWorkItemStateAtomicity:
    """Test atomic persistence of work item state changes."""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SprintRepository(tmpdir)
            yield repo
    
    @pytest.fixture
    def test_sprint(self, temp_repo):
        """Create a test sprint with work items."""
        sprint_data, paths = temp_repo.create(
            sprint_id="atomic-test",
            project="Atomic Test",
            goal="Test atomic state changes"
        )
        
        work_item = {
            "id": "WI-ATOMIC",
            "title": "Atomic Work Item",
            "description": "For testing atomicity",
            "status": "planned",
            "priority": 1,
            "created_at": datetime.now().isoformat()
        }
        
        temp_repo.save_work_item(paths, work_item)
        
        return temp_repo, paths
    
    def test_state_change_is_atomic(self, test_sprint):
        """Test that state changes are persisted atomically."""
        repo, paths = test_sprint
        
        # Get initial file modification time
        wi_path = paths.work_items / "WI-ATOMIC.json"
        initial_mtime = wi_path.stat().st_mtime if wi_path.exists() else 0
        
        # Perform state change
        repo.update_work_item_state(paths, "WI-ATOMIC", "in_progress")
        
        # Verify file was modified
        new_mtime = wi_path.stat().st_mtime
        assert new_mtime > initial_mtime