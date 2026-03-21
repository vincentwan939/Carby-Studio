"""Unit tests for state_manager.py."""

import json
import os
import tempfile
import shutil
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

from state_manager import StateManager, StateChange, SprintState, GateState, PhaseState, SprintStatus, GateStatus, PhaseStatus
from config import Config


class TestStateManager:
    """Test StateManager class."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir)
    
    @pytest.fixture
    def manager(self, temp_dir):
        """Create StateManager with temp directory."""
        # Patch config
        original_projects_dir = Config.PROJECTS_DIR
        original_cache_file = Config.CACHE_FILE
        
        Config.PROJECTS_DIR = Path(temp_dir) / "projects"
        Config.CACHE_FILE = Path(temp_dir) / "cache.json"
        
        Config.PROJECTS_DIR.mkdir(exist_ok=True)
        
        manager = StateManager()
        
        yield manager
        
        # Restore config
        Config.PROJECTS_DIR = original_projects_dir
        Config.CACHE_FILE = original_cache_file
    
    def create_project(self, manager, project_id: str, data: dict):
        """Helper to create a project file."""
        path = manager._get_project_path(project_id)
        with open(path, 'w') as f:
            json.dump(data, f)
    
    def create_sprint(self, manager, sprint_id: str, data: dict):
        """Helper to create a sprint file."""
        path = manager._get_sprint_path(sprint_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f)
    
    def test_read_project_success(self, manager):
        """Test reading a valid project."""
        project_data = {
            "project": "test-project",
            "goal": "Test goal",
            "status": "active",
            "stages": {
                "discover": {"status": "done"},
                "design": {"status": "in-progress"}
            }
        }
        self.create_project(manager, "test-project", project_data)
        
        result = manager.read_project("test-project")
        
        assert result is not None
        assert result["project"] == "test-project"
        assert result["goal"] == "Test goal"
    
    def test_read_project_not_found(self, manager):
        """Test reading non-existent project."""
        result = manager.read_project("non-existent")
        assert result is None
    
    def test_read_project_invalid_json(self, manager):
        """Test reading invalid JSON."""
        path = manager._get_project_path("bad-project")
        with open(path, 'w') as f:
            f.write("not valid json")
        
        result = manager.read_project("bad-project")
        assert result is None
    
    def test_list_projects(self, manager):
        """Test listing projects."""
        self.create_project(manager, "project-a", {"project": "project-a"})
        self.create_project(manager, "project-b", {"project": "project-b"})
        
        projects = manager.list_projects()
        
        assert len(projects) == 2
        assert "project-a" in projects
        assert "project-b" in projects
    
    def test_detect_changes_new_project(self, manager):
        """Test detecting new project."""
        self.create_project(manager, "new-project", {
            "project": "new-project",
            "stages": {"discover": {"status": "pending"}}
        })
        
        changes = manager.detect_changes()
        
        assert len(changes) == 1
        assert changes[0].change_type == "new"
        assert changes[0].entity_id == "new-project"
    
    def test_detect_changes_stage_changed(self, manager):
        """Test detecting stage status change."""
        # First, create project and detect (adds to cache)
        self.create_project(manager, "test-project", {
            "project": "test-project",
            "stages": {"discover": {"status": "pending"}}
        })
        manager.detect_changes()
        
        # Now update the project
        self.create_project(manager, "test-project", {
            "project": "test-project",
            "stages": {"discover": {"status": "in-progress"}}
        })
        
        changes = manager.detect_changes()
        
        assert len(changes) == 1
        assert changes[0].change_type == "stage_changed"
        assert changes[0].stage_name == "discover"
        assert changes[0].old_status == "pending"
        assert changes[0].new_status == "in-progress"
    
    def test_detect_changes_deleted_project(self, manager):
        """Test detecting deleted project."""
        # Create and cache
        self.create_project(manager, "deleted-project", {
            "project": "deleted-project",
            "stages": {}
        })
        manager.detect_changes()
        
        # Delete file
        path = manager._get_project_path("deleted-project")
        path.unlink()
        
        changes = manager.detect_changes()
        
        assert len(changes) == 1
        assert changes[0].change_type == "deleted"
        assert changes[0].entity_id == "deleted-project"
    
    def test_get_project_summary(self, manager):
        """Test getting project summary."""
        self.create_project(manager, "summary-project", {
            "project": "summary-project",
            "goal": "Test goal",
            "status": "active",
            "currentStage": "build",
            "stages": {
                "build": {
                    "status": "in-progress",
                    "agent": "code-agent"
                }
            }
        })
        
        summary = manager.get_project_summary("summary-project")
        
        assert summary is not None
        assert summary["id"] == "summary-project"
        assert summary["goal"] == "Test goal"
        assert summary["current_stage"] == "build"
        assert summary["current_status"] == "in-progress"
        assert summary["agent"] == "code-agent"
    
    def test_format_project_list(self, manager):
        """Test formatting project list."""
        self.create_project(manager, "project-a", {
            "project": "project-a",
            "goal": "Goal A",
            "currentStage": "discover",
            "stages": {"discover": {"status": "in-progress"}}
        })
        
        text = manager.format_project_list()
        
        assert "📋 Your Projects" in text
        assert "project-a" in text
        assert "discover" in text
    
    # NEW TESTS FOR SPRINT FUNCTIONALITY
    
    def test_read_write_sprint_dict(self, manager):
        """Test reading and writing sprint as dictionary."""
        sprint_data = {
            "sprint_id": "test-sprint",
            "project": "test-project",
            "goal": "Test sprint goal",
            "status": "in-progress",
            "current_gate": 2
        }
        
        success = manager.write_sprint("test-sprint", sprint_data)
        assert success is True
        
        read_data = manager.read_sprint("test-sprint")
        assert read_data is not None
        assert read_data["sprint_id"] == "test-sprint"
        assert read_data["goal"] == "Test sprint goal"
    
    def test_read_write_sprint_state_object(self, manager):
        """Test reading and writing SprintState object."""
        sprint_state = SprintState(
            sprint_id="obj-sprint",
            project="test-project",
            goal="Object test goal",
            status=SprintStatus.IN_PROGRESS.value,
            mode="sequential",
            current_gate=1
        )
        
        success = manager.write_sprint_state(sprint_state)
        assert success is True
        
        read_state = manager.read_sprint_state("obj-sprint")
        assert read_state is not None
        assert read_state.sprint_id == "obj-sprint"
        assert read_state.goal == "Object test goal"
        assert read_state.status == SprintStatus.IN_PROGRESS.value
    
    def test_list_sprints(self, manager):
        """Test listing sprints."""
        # Create sprint directories with state files
        self.create_sprint(manager, "sprint-1", {"sprint_id": "sprint-1", "goal": "Goal 1"})
        self.create_sprint(manager, "sprint-2", {"sprint_id": "sprint-2", "goal": "Goal 2"})
        
        sprints = manager.list_sprints()
        assert len(sprints) == 2
        assert "sprint-1" in sprints
        assert "sprint-2" in sprints
        assert sprints == ["sprint-1", "sprint-2"]  # Should be sorted
    
    def test_list_all_entities(self, manager):
        """Test listing all entities (projects and sprints)."""
        # Create a project
        self.create_project(manager, "test-project", {"project": "test-project", "goal": "Goal"})
        # Create a sprint
        self.create_sprint(manager, "test-sprint", {"sprint_id": "test-sprint", "goal": "Goal"})
        
        entities = manager.list_all_entities()
        assert len(entities) == 2
        assert ("test-project", "project") in entities
        assert ("test-sprint", "sprint") in entities
    
    def test_get_sprint_summary(self, manager):
        """Test getting sprint summary."""
        sprint_data = {
            "sprint_id": "summary-sprint",
            "project": "test-project",
            "goal": "Summary test goal",
            "status": "in-progress",
            "current_gate": 2,
            "gates": [
                {"gate_number": 1, "name": "Discover", "status": "completed"},
                {"gate_number": 2, "name": "Design", "status": "in-progress"}
            ]
        }
        self.create_sprint(manager, "summary-sprint", sprint_data)
        
        summary = manager.get_sprint_summary("summary-sprint")
        assert summary is not None
        assert summary["id"] == "summary-sprint"
        assert summary["project"] == "test-project"
        assert summary["goal"] == "Summary test goal"
        assert summary["current_gate"] == 2
        assert summary["current_gate_name"] == "Design"
        assert summary["current_status"] == "in-progress"
        assert summary["type"] == "sprint"
    
    def test_format_entity_list(self, manager):
        """Test formatting entity list with projects and sprints."""
        # Create projects
        self.create_project(manager, "project-1", {"project": "project-1", "goal": "Goal 1"})
        # Create sprints
        self.create_sprint(manager, "sprint-1", {"sprint_id": "sprint-1", "goal": "Goal 1"})
        
        formatted = manager.format_entity_list()
        assert "Projects (1)" in formatted
        assert "Sprints (1)" in formatted
        assert "project-1" in formatted
        assert "sprint-1" in formatted
    
    def test_detect_changes_new_sprint(self, manager):
        """Test detecting new sprint."""
        sprint_data = {
            "sprint_id": "new-sprint",
            "project": "test-project",
            "goal": "New sprint test",
            "status": "pending"
        }
        self.create_sprint(manager, "new-sprint", sprint_data)
        
        changes = manager.detect_changes()
        assert len(changes) == 1
        assert changes[0].entity_id == "new-sprint"
        assert changes[0].entity_type == "sprint"
        assert changes[0].change_type == "new"
    
    def test_detect_changes_sprint_status_change(self, manager):
        """Test detecting sprint status change."""
        # Create initial sprint
        sprint_data = {
            "sprint_id": "status-change-sprint",
            "project": "test-project",
            "goal": "Status change test",
            "status": "pending",
            "current_gate": 1
        }
        self.create_sprint(manager, "status-change-sprint", sprint_data)
        
        # Detect initial creation
        changes = manager.detect_changes()
        assert len(changes) == 1
        assert changes[0].change_type == "new"
        
        # Update sprint status
        sprint_data["status"] = "in-progress"
        self.create_sprint(manager, "status-change-sprint", sprint_data)
        
        # Detect status change
        changes = manager.detect_changes()
        assert len(changes) == 1
        assert changes[0].entity_id == "status-change-sprint"
        assert changes[0].change_type == "status_changed"
        assert changes[0].old_status == "pending"
        assert changes[0].new_status == "in-progress"
    
    def test_detect_changes_sprint_gate_change(self, manager):
        """Test detecting sprint gate change."""
        # Create initial sprint
        sprint_data = {
            "sprint_id": "gate-change-sprint",
            "project": "test-project",
            "goal": "Gate change test",
            "status": "in-progress",
            "current_gate": 1
        }
        self.create_sprint(manager, "gate-change-sprint", sprint_data)
        
        # Detect initial creation
        manager.detect_changes()
        
        # Update current gate
        sprint_data["current_gate"] = 2
        self.create_sprint(manager, "gate-change-sprint", sprint_data)
        
        # Detect gate change
        changes = manager.detect_changes()
        assert len(changes) == 1
        assert changes[0].entity_id == "gate-change-sprint"
        assert changes[0].change_type == "gate_changed"
        assert changes[0].old_status == "1"
        assert changes[0].new_status == "2"
    
    def test_detect_changes_sprint_gate_phase_change(self, manager):
        """Test detecting sprint gate and phase changes."""
        # Create initial sprint with gates and phases
        sprint_data = {
            "sprint_id": "phase-change-sprint",
            "project": "test-project",
            "goal": "Phase change test",
            "status": "in-progress",
            "current_gate": 1,
            "gates": [
                {
                    "gate_number": 1,
                    "name": "Discover",
                    "status": "in-progress",
                    "phases": [
                        {"phase_id": "p1", "name": "Research", "status": "pending"}
                    ]
                }
            ]
        }
        self.create_sprint(manager, "phase-change-sprint", sprint_data)
        
        # Detect initial creation
        manager.detect_changes()
        
        # Update phase status
        sprint_data["gates"][0]["phases"][0]["status"] = "completed"
        self.create_sprint(manager, "phase-change-sprint", sprint_data)
        
        # Detect phase change
        changes = manager.detect_changes()
        assert len(changes) == 1
        assert changes[0].entity_id == "phase-change-sprint"
        assert changes[0].change_type == "phase_changed"
        assert changes[0].phase_id == "p1"
        assert changes[0].gate_number == 1
        assert changes[0].old_status == "pending"
        assert changes[0].new_status == "completed"
    
    def test_detect_changes_deleted_sprint(self, manager):
        """Test detecting deleted sprint."""
        # Create and cache sprint
        sprint_data = {
            "sprint_id": "to-delete-sprint",
            "project": "test-project",
            "goal": "To delete test",
            "status": "in-progress"
        }
        self.create_sprint(manager, "to-delete-sprint", sprint_data)
        manager.detect_changes()  # Cache the sprint
        
        # Delete the sprint file
        sprint_path = manager._get_sprint_path("to-delete-sprint")
        sprint_path.unlink()
        sprint_path.parent.rmdir()  # Remove the directory too
        
        # Detect deletion
        changes = manager.detect_changes()
        assert len(changes) == 1
        assert changes[0].entity_id == "to-delete-sprint"
        assert changes[0].entity_type == "sprint"
        assert changes[0].change_type == "deleted"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])