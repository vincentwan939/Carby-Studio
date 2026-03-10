"""State management for Carby Studio Bot."""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from threading import Lock
import logging

from config import Config
from atomic_file import atomic_write_json, safe_read_json, locked_json_read, locked_json_write
from file_lock import get_lock_manager

logger = logging.getLogger(__name__)


@dataclass
class StageState:
    """State of a single stage."""
    name: str
    status: str
    agent: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    task: Optional[str] = None
    output: Optional[str] = None


@dataclass
class ProjectState:
    """State of a project."""
    id: str
    goal: str
    status: str
    mode: str
    current_stage: str
    stages: Dict[str, StageState]
    updated_at: str


@dataclass
class StateChange:
    """Represents a change in project state."""
    project_id: str
    change_type: str  # "new", "stage_changed", "deleted"
    stage_name: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class StateManager:
    """Manages reading and caching project states."""
    
    def __init__(self):
        self.projects_dir = Config.PROJECTS_DIR
        self.cache_file = Config.CACHE_FILE
        self._cache: Dict[str, dict] = {}
        self._lock = Lock()
        self._load_cache()
    
    def _get_project_path(self, project_id: str) -> Path:
        """Get path to project JSON file."""
        return self.projects_dir / f"{project_id}.json"
    
    def _load_cache(self):
        """Load cached state from disk."""
        if self.cache_file.exists():
            cache_data = safe_read_json(self.cache_file)
            if cache_data is not None:
                self._cache = cache_data
                logger.info(f"Loaded cache with {len(self._cache)} projects")
            else:
                logger.warning("Failed to load cache, starting fresh")
                self._cache = {}
        else:
            self._cache = {}
    
    def _save_cache(self):
        """Save cache to disk atomically."""
        Config.ensure_directories()
        if not atomic_write_json(self.cache_file, self._cache):
            logger.error(f"Failed to save cache to {self.cache_file}")
    
    def read_project(self, project_id: str) -> Optional[dict]:
        """Read project state from JSON file with locking."""
        path = self._get_project_path(project_id)
        try:
            with locked_json_read(path, project_id, self.projects_dir) as data:
                return data
        except TimeoutError:
            logger.error(f"Timeout reading project '{project_id}' - another process has the lock")
            # Fallback to non-locked read
            return safe_read_json(path)
    
    def list_projects(self) -> List[str]:
        """List all project IDs."""
        projects = []
        try:
            for f in self.projects_dir.iterdir():
                if f.suffix == '.json':
                    projects.append(f.stem)
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Failed to list projects: {e}")
        return sorted(projects)
    
    def detect_changes(self) -> List[StateChange]:
        """Detect changes since last poll."""
        changes = []
        current_projects = set()
        
        with self._lock:
            for project_id in self.list_projects():
                current_projects.add(project_id)
                new_state = self.read_project(project_id)
                
                if new_state is None:
                    continue
                
                old_state = self._cache.get(project_id)
                
                if old_state is None:
                    # New project
                    changes.append(StateChange(
                        project_id=project_id,
                        change_type="new"
                    ))
                else:
                    # Check for stage changes
                    changes.extend(self._detect_stage_changes(
                        project_id, old_state, new_state
                    ))
                
                # Update cache
                self._cache[project_id] = new_state
            
            # Check for deleted projects
            for project_id in list(self._cache.keys()):
                if project_id not in current_projects:
                    changes.append(StateChange(
                        project_id=project_id,
                        change_type="deleted"
                    ))
                    del self._cache[project_id]
            
            # Save cache
            self._save_cache()
        
        return changes
    
    def _detect_stage_changes(self, project_id: str, old: dict, new: dict) -> List[StateChange]:
        """Detect changes in stage statuses."""
        changes = []
        
        old_stages = old.get("stages", {})
        new_stages = new.get("stages", {})
        
        for stage_name, new_stage in new_stages.items():
            old_stage = old_stages.get(stage_name, {})
            old_status = old_stage.get("status")
            new_status = new_stage.get("status")
            
            if old_status != new_status:
                changes.append(StateChange(
                    project_id=project_id,
                    change_type="stage_changed",
                    stage_name=stage_name,
                    old_status=old_status,
                    new_status=new_status
                ))
        
        return changes
    
    def get_project_summary(self, project_id: str) -> Optional[dict]:
        """Get summary of project for display."""
        state = self.read_project(project_id)
        if not state:
            return None
        
        current_stage = state.get("currentStage") or state.get("current_stage", "")
        stages = state.get("stages", {})
        current_stage_data = stages.get(current_stage, {}) if current_stage else {}
        
        # Determine current status
        current_status = current_stage_data.get("status", "unknown")
        
        # If no current stage or status is unknown, check project status
        if not current_stage or current_status == "unknown":
            project_status = state.get("status", "")
            if project_status == "completed":
                current_status = "completed"
            elif project_status == "failed":
                current_status = "failed"
            elif not current_stage:
                # No current stage set - check if any stages are in progress
                for stage_name, stage_data in stages.items():
                    if stage_data.get("status") == "in-progress":
                        current_stage = stage_name
                        current_status = "in-progress"
                        break
                else:
                    # No in-progress stages, find first pending
                    for stage_name in state.get("pipeline", []):
                        stage_data = stages.get(stage_name, {})
                        if stage_data.get("status") == "pending":
                            current_stage = stage_name
                            current_status = "pending"
                            break
        
        return {
            "id": project_id,
            "goal": state.get("goal", ""),
            "status": state.get("status", ""),
            "mode": state.get("mode", ""),
            "current_stage": current_stage,
            "current_status": current_status,
            "agent": current_stage_data.get("agent"),
            "updated_at": state.get("updated", ""),
        }
    
    def format_project_list(self) -> str:
        """Format projects list for Telegram - header only, projects shown in buttons."""
        projects = self.list_projects()
        if not projects:
            return "📋 No projects found.\n\nCreate one with ➕ New Project"
        
        # Just return the header - projects are shown in the inline keyboard buttons
        return f"📋 Your Projects ({len(projects)})\n\nTap a project to view details:"
