#!/usr/bin/env python3
"""
Carby Studio Telegram Bot - DEPRECATED

This module is DEPRECATED. Use bot.py::CarbyBot instead.

This file is kept for backward compatibility but will be removed in a future version.
All functionality has been migrated to the main bot.py module which integrates with:
- StateManager for state management
- CLIExecutor for CLI operations
- SafetyManager for safety checks
- NotificationService for notifications
"""

import os
import sys
import json
import logging
import warnings
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "carby_bot.py is deprecated. Use bot.py::CarbyBot instead. "
    "This module will be removed in a future version.",
    DeprecationWarning,
    stacklevel=2
)


class StageStatus(Enum):
    """DEPRECATED: Use state_manager.StageState instead."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    APPROVED = "approved"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProjectStatus(Enum):
    """DEPRECATED: Use state from project JSON directly."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    PAUSED = "paused"


@dataclass
class Stage:
    """DEPRECATED: Use state_manager.StageState instead."""
    name: str
    status: StageStatus
    agent: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0


@dataclass
class Project:
    """DEPRECATED: Project data is now stored as dict in JSON files."""
    id: str
    goal: str
    status: ProjectStatus
    current_stage: str
    stages: Dict[str, Stage]
    credentials_used: List[str]
    created_at: str
    updated_at: str


class CarbyBot:
    """
    DEPRECATED: Main bot class handling all Telegram interactions.
    
    This class is kept for backward compatibility but delegates to bot.py::CarbyBot.
    Please migrate to using bot.py directly.
    """
    
    STAGE_ORDER = ["discover", "design", "build", "verify", "deliver"]
    
    def __init__(self, data_dir: str = None):
        """Initialize deprecated bot."""
        logger.warning("CarbyBot from carby_bot.py is deprecated. Use bot.py::CarbyBot instead.")
        
        self.data_dir = data_dir or os.path.expanduser("~/.openclaw/carby-bot")
        self.projects_dir = os.path.join(self.data_dir, "projects")
        self.ensure_directories()
        
    def ensure_directories(self):
        """Create necessary directories."""
        os.makedirs(self.projects_dir, exist_ok=True)
        
    def get_project_path(self, project_id: str) -> str:
        """Get path to project JSON file."""
        return os.path.join(self.projects_dir, f"{project_id}.json")
        
    def load_project(self, project_id: str) -> Optional[Project]:
        """Load project from disk."""
        path = self.get_project_path(project_id)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            # Convert stage dicts to Stage objects
            stages = {
                k: Stage(**v) if isinstance(v, dict) else v
                for k, v in data.get('stages', {}).items()
            }
            data['stages'] = stages
            data['status'] = ProjectStatus(data['status'])
            return Project(**data)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.error(f"Failed to load project {project_id}: {e}")
            return None
            
    def save_project(self, project: Project):
        """Save project to disk."""
        path = self.get_project_path(project.id)
        data = asdict(project)
        data['status'] = project.status.value
        data['stages'] = {
            k: {**asdict(v), 'status': v.status.value} if isinstance(v, Stage) else v
            for k, v in project.stages.items()
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
            
    def list_projects(self, status: ProjectStatus = None) -> List[Project]:
        """List all projects, optionally filtered by status."""
        projects = []
        for filename in os.listdir(self.projects_dir):
            if filename.endswith('.json'):
                project_id = filename[:-5]
                project = self.load_project(project_id)
                if project and (status is None or project.status == status):
                    projects.append(project)
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)
        
    def create_project(self, project_id: str, goal: str) -> Project:
        """Create a new project."""
        now = datetime.now().isoformat()
        stages = {
            stage: Stage(
                name=stage,
                status=StageStatus.PENDING if stage == "discover" else StageStatus.PENDING
            )
            for stage in self.STAGE_ORDER
        }
        # First stage is ready to start
        stages["discover"].status = StageStatus.PENDING
        
        project = Project(
            id=project_id,
            goal=goal,
            status=ProjectStatus.ACTIVE,
            current_stage="discover",
            stages=stages,
            credentials_used=[],
            created_at=now,
            updated_at=now
        )
        self.save_project(project)
        return project
        
    def get_stage_icon(self, stage: Stage) -> str:
        """Get icon for stage status."""
        icons = {
            StageStatus.PENDING: "⬜",
            StageStatus.IN_PROGRESS: "🔄",
            StageStatus.DONE: "✅",
            StageStatus.APPROVED: "✅",
            StageStatus.FAILED: "❌",
            StageStatus.SKIPPED: "⏭️"
        }
        return icons.get(stage.status, "⬜")
        
    def get_project_status_icon(self, project: Project) -> str:
        """Get icon for project status."""
        current = project.stages.get(project.current_stage)
        if not current:
            return "⚪"
        if current.status == StageStatus.IN_PROGRESS:
            return "🟢"
        elif current.status == StageStatus.DONE:
            return "🟡"  # Waiting for approval
        elif current.status == StageStatus.FAILED:
            return "🔴"
        return "⚪"
        
    def format_projects_list(self, projects: List[Project]) -> str:
        """Format projects list for display."""
        if not projects:
            return "📋 No active projects.\n\nStart one with ➕ New Project"
            
        lines = ["📋 Your Projects"]
        lines.append("")
        
        for p in projects:
            icon = self.get_project_status_icon(p)
            current = p.stages.get(p.current_stage)
            status_text = ""
            
            current_status = StageStatus(current.status) if isinstance(current.status, str) else current.status
            
            if current_status == StageStatus.IN_PROGRESS:
                status_text = f"{p.current_stage}: in-progress"
                if current.agent:
                    status_text += f" • 🤖 {current.agent}"
            elif current_status == StageStatus.DONE:
                status_text = f"{p.current_stage}: done • ⏸️ waiting for approval"
            elif current_status == StageStatus.FAILED:
                status_text = f"{p.current_stage}: failed • needs action"
            else:
                status_text = f"{p.current_stage}: {current_status.value}"
                
            lines.append(f"{icon} {p.id}")
            lines.append(f"   {status_text}")
            lines.append("")
            
        return "\n".join(lines)
        
    def format_project_detail(self, project: Project) -> str:
        """Format project detail view."""
        lines = [
            f"*{project.id}*",
            f"🎯 {project.goal}",
            "",
            "*Pipeline:*"
        ]
        
        # Pipeline visualization
        stage_icons = []
        for stage_name in self.STAGE_ORDER:
            stage = project.stages.get(stage_name)
            icon = self.get_stage_icon(stage)
            stage_icons.append(f"{icon} {stage_name.capitalize()}")
        lines.append(" → ".join(stage_icons))
        lines.append("")
        
        # Current stage details
        current = project.stages.get(project.current_stage)
        lines.append(f"*Current: {project.current_stage.capitalize()}*")
        current_status = StageStatus(current.status) if isinstance(current.status, str) else current.status
        lines.append(f"Status: {current_status.value}")
        
        if current.agent:
            lines.append(f"🤖 Agent: {current.agent}")
        if current.started_at:
            lines.append(f"⏱️ Started: {current.started_at}")
        if current.output:
            lines.append(f"📄 Output: {current.output}")
        if current.error:
            lines.append(f"❌ Error: {current.error}")
            
        lines.append("")
        lines.append(f"📁 Files: `projects/{project.id}/`")
        lines.append(f"🔐 Credentials: {len(project.credentials_used)} configured")
        
        return "\n".join(lines)
        
    def format_approval_screen(self, project: Project) -> str:
        """Format approval screen for completed stage."""
        current = project.stages.get(project.current_stage)
        
        lines = [
            f"🔔 *{project.id}*",
            f"{project.current_stage.capitalize()} stage complete",
            "",
            "*Deliverables:*"
        ]
        
        # List artifacts based on stage
        artifacts = self.get_stage_artifacts(project.current_stage)
        for artifact in artifacts:
            lines.append(f"✅ {artifact}")
            
        lines.append("")
        lines.append("Your decision:")
        
        return "\n".join(lines)
        
    def get_stage_artifacts(self, stage_name: str) -> List[str]:
        """Get expected artifacts for a stage."""
        artifacts = {
            "discover": ["requirements.md", "user-stories.md"],
            "design": ["design.md", "api-spec.md", "credentials-required.md"],
            "build": ["src/", "tests/", "README.md"],
            "verify": ["test-report.md", "coverage-report.md"],
            "deliver": ["deployment.md", "runbook.md"]
        }
        return artifacts.get(stage_name, [])
        
    def approve_stage(self, project_id: str) -> Optional[Project]:
        """Approve current stage and advance to next."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        current = project.stages.get(project.current_stage)
        if current.status != StageStatus.DONE:
            return None
            
        # Mark current stage approved
        current.status = StageStatus.APPROVED
        current.approved_at = datetime.now().isoformat()
        current.approved_by = "user"
        
        # Find next stage
        current_idx = self.STAGE_ORDER.index(project.current_stage)
        if current_idx < len(self.STAGE_ORDER) - 1:
            next_stage_name = self.STAGE_ORDER[current_idx + 1]
            project.current_stage = next_stage_name
            project.stages[next_stage_name].status = StageStatus.PENDING
        
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def reject_stage(self, project_id: str, feedback: str = None) -> Optional[Project]:
        """Reject current stage and send back for revision."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        current = project.stages.get(project.current_stage)
        if current.status != StageStatus.DONE:
            return None
            
        # Reset to pending for retry
        current.status = StageStatus.PENDING
        current.error = feedback
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def start_stage(self, project_id: str, agent: str = None) -> Optional[Project]:
        """Start the current stage (spawn agent)."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        current = project.stages.get(project.current_stage)
        if current.status != StageStatus.PENDING:
            return None
            
        current.status = StageStatus.IN_PROGRESS
        current.agent = agent or f"{project.current_stage}-agent"
        current.started_at = datetime.now().isoformat()
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def complete_stage(self, project_id: str, output: str = None) -> Optional[Project]:
        """Mark current stage as done (called by agent)."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        current = project.stages.get(project.current_stage)
        if current.status != StageStatus.IN_PROGRESS:
            return None
            
        current.status = StageStatus.DONE
        current.completed_at = datetime.now().isoformat()
        current.output = output
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def fail_stage(self, project_id: str, error: str) -> Optional[Project]:
        """Mark current stage as failed."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        current = project.stages.get(project.current_stage)
        current.status = StageStatus.FAILED
        current.error = error
        current.retry_count += 1
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def retry_stage(self, project_id: str) -> Optional[Project]:
        """Retry failed stage."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        current = project.stages.get(project.current_stage)
        if current.status != StageStatus.FAILED:
            return None
            
        current.status = StageStatus.PENDING
        current.error = None
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def skip_stage(self, project_id: str) -> Optional[Project]:
        """Skip current stage and advance."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        current = project.stages.get(project.current_stage)
        current.status = StageStatus.SKIPPED
        
        # Find next stage
        current_idx = self.STAGE_ORDER.index(project.current_stage)
        if current_idx < len(self.STAGE_ORDER) - 1:
            next_stage_name = self.STAGE_ORDER[current_idx + 1]
            project.current_stage = next_stage_name
            project.stages[next_stage_name].status = StageStatus.PENDING
        
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def archive_project(self, project_id: str) -> Optional[Project]:
        """Archive a project."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        project.status = ProjectStatus.ARCHIVED
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project


# Singleton instance - DEPRECATED
_bot_instance = None

def get_bot() -> CarbyBot:
    """DEPRECATED: Get or create bot instance."""
    warnings.warn(
        "get_bot() is deprecated. Import CarbyBot from bot.py instead.",
        DeprecationWarning,
        stacklevel=2
    )
    global _bot_instance
    if _bot_instance is None:
        _bot_instance = CarbyBot()
    return _bot_instance


if __name__ == "__main__":
    # Test the bot
    bot = get_bot()
    
    # Create test project
    project = bot.create_project("test-project", "A test project for the bot")
    print(f"Created project: {project.id}")
    
    # List projects
    projects = bot.list_projects()
    print(bot.format_projects_list(projects))
    
    # Start stage
    bot.start_stage("test-project")
    project = bot.load_project("test-project")
    print("\nAfter starting:")
    print(bot.format_project_detail(project))
    
    # Complete stage
    bot.complete_stage("test-project", "Requirements document created")
    project = bot.load_project("test-project")
    print("\nAfter completing:")
    print(bot.format_approval_screen(project))
