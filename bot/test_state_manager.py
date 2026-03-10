"""Unit tests for state_manager.py."""

import json
import os
import tempfile
import shutil
from pathlib import Path
import pytest

from state_manager import StateManager, StateChange
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
        assert changes[0].project_id == "new-project"
    
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
        assert changes[0].project_id == "deleted-project"
    
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
