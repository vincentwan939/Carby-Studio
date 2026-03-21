"""
Carby Studio Telegram Bot - Fixed Version

This module fixes the race condition and type mismatch issues in the original carby_bot.py.
- Uses StateManager for consistent file locking
- Properly handles StageStatus enum/string conversions
- Includes health checks and automatic reconnection
"""

import os
import sys
import logging
import warnings
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum

from state_manager import StateManager, StageStatus, ProjectStatus, StageState, ProjectState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class Stage:
    """Stage data class with proper status handling."""
    name: str
    status: str  # Using string instead of Enum for consistency
    agent: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    
    @classmethod
    def from_stage_state(cls, stage_state: StageState) -> "Stage":
        """Create Stage from StageState."""
        return cls(
            name=stage_state.name,
            status=stage_state.status,
            agent=stage_state.agent,
            started_at=stage_state.started_at,
            completed_at=stage_state.completed_at,
            output=stage_state.output,
            error=stage_state.error,
            retry_count=stage_state.retry_count
        )
    
    def to_stage_state(self) -> StageState:
        """Convert Stage to StageState."""
        return StageState(
            name=self.name,
            status=self.status,
            agent=self.agent,
            started_at=self.started_at,
            completed_at=self.completed_at,
            output=self.output,
            error=self.error,
            retry_count=self.retry_count
        )


@dataclass
class Project:
    """Project data class."""
    id: str
    goal: str
    status: str  # Using string instead of Enum for consistency
    current_stage: str
    stages: Dict[str, Stage]
    credentials_used: List[str]
    created_at: str
    updated_at: str
    
    @classmethod
    def from_project_state(cls, project_state: ProjectState) -> "Project":
        """Create Project from ProjectState."""
        stages = {
            name: Stage.from_stage_state(stage_state)
            for name, stage_state in project_state.stages.items()
        }
        
        return cls(
            id=project_state.id,
            goal=project_state.goal,
            status=project_state.status,
            current_stage=project_state.current_stage,
            stages=stages,
            credentials_used=[],
            created_at=project_state.created_at or project_state.updated_at,
            updated_at=project_state.updated_at
        )
    
    def to_project_state(self) -> ProjectState:
        """Convert Project to ProjectState."""
        stages = {
            name: stage.to_stage_state()
            for name, stage in self.stages.items()
        }
        
        return ProjectState(
            id=self.id,
            goal=self.goal,
            status=self.status,
            mode="linear",  # Default mode
            current_stage=self.current_stage,
            stages=stages,
            updated_at=self.updated_at,
            created_at=self.created_at,
            pipeline=list(self.stages.keys())
        )


class CarbyBot:
    """
    Fixed bot class handling all Telegram interactions with proper state management.
    """
    
    STAGE_ORDER = ["discover", "design", "build", "verify", "deliver"]
    
    def __init__(self, data_dir: str = None):
        """Initialize bot with StateManager for consistent state management."""
        logger.info("Initializing fixed CarbyBot with proper state management")
        
        self.state_manager = StateManager()
        self.data_dir = data_dir or os.path.expanduser("~/.openclaw/carby-bot")
        self.projects_dir = self.state_manager.projects_dir  # Use StateManager's directory
        
        # Register reconnection callback for health checks
        self.state_manager.connection_monitor.register_reconnect_callback(self._handle_reconnection)
        
    def _handle_reconnection(self):
        """Handle reconnection when connection monitor detects hang."""
        logger.info("Handling reconnection...")
        # Restart the state manager's polling if needed
        if hasattr(self, '_poll_thread') and self._poll_thread:
            try:
                self._poll_thread.join(timeout=2)
            except:
                pass
    
    def load_project(self, project_id: str) -> Optional[Project]:
        """Load project from disk using StateManager."""
        project_state = self.state_manager.read_project_state(project_id)
        if project_state is None:
            return None
        
        return Project.from_project_state(project_state)
        
    def save_project(self, project: Project):
        """Save project to disk using StateManager."""
        project_state = project.to_project_state()
        success = self.state_manager.write_project_state(project_state)
        if not success:
            logger.error(f"Failed to save project {project.id}")
        else:
            logger.debug(f"Successfully saved project {project.id}")
            
    def list_projects(self, status: str = None) -> List[Project]:
        """List all projects, optionally filtered by status."""
        project_ids = self.state_manager.list_projects()
        projects = []
        
        for project_id in project_ids:
            project = self.load_project(project_id)
            if project and (status is None or project.status == status):
                projects.append(project)
        
        return sorted(projects, key=lambda p: p.updated_at, reverse=True)
        
    def create_project(self, project_id: str, goal: str) -> Project:
        """Create a new project using StateManager."""
        now = datetime.now().isoformat()
        
        # Create initial stages
        stages = {}
        for stage_name in self.STAGE_ORDER:
            stage = Stage(
                name=stage_name,
                status=StageStatus.PENDING.value if stage_name == "discover" else StageStatus.PENDING.value
            )
            stages[stage_name] = stage
        
        project = Project(
            id=project_id,
            goal=goal,
            status=ProjectStatus.ACTIVE.value,
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
            StageStatus.PENDING.value: "⬜",
            StageStatus.IN_PROGRESS.value: "🔄",
            StageStatus.DONE.value: "✅",
            StageStatus.APPROVED.value: "✅",
            StageStatus.FAILED.value: "❌",
            StageStatus.SKIPPED.value: "⏭️"
        }
        return icons.get(stage.status, "⬜")
        
    def get_project_status_icon(self, project: Project) -> str:
        """Get icon for project status."""
        current = project.stages.get(project.current_stage)
        if not current:
            return "⚪"
        if current.status == StageStatus.IN_PROGRESS.value:
            return "🟢"
        elif current.status == StageStatus.DONE.value:
            return "🟡"  # Waiting for approval
        elif current.status == StageStatus.FAILED.value:
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
            
            current_status = current.status if isinstance(current.status, str) else current.status.value
            
            if current_status == StageStatus.IN_PROGRESS.value:
                status_text = f"{p.current_stage}: in-progress"
                if current.agent:
                    status_text += f" • 🤖 {current.agent}"
            elif current_status == StageStatus.DONE.value:
                status_text = f"{p.current_stage}: done • ⏸️ waiting for approval"
            elif current_status == StageStatus.FAILED.value:
                status_text = f"{p.current_stage}: failed • needs action"
            else:
                status_text = f"{p.current_stage}: {current_status}"
                
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
            if stage:
                icon = self.get_stage_icon(stage)
                stage_icons.append(f"{icon} {stage_name.capitalize()}")
        lines.append(" → ".join(stage_icons))
        lines.append("")
        
        # Current stage details
        current = project.stages.get(project.current_stage)
        lines.append(f"*Current: {project.current_stage.capitalize()}*")
        current_status = current.status if isinstance(current.status, str) else current.status.value
        lines.append(f"Status: {current_status}")
        
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
        if current.status != StageStatus.DONE.value:
            return None
            
        # Mark current stage approved
        current.status = StageStatus.APPROVED.value
        current.approved_at = datetime.now().isoformat()
        current.approved_by = "user"
        
        # Find next stage
        current_idx = self.STAGE_ORDER.index(project.current_stage)
        if current_idx < len(self.STAGE_ORDER) - 1:
            next_stage_name = self.STAGE_ORDER[current_idx + 1]
            project.current_stage = next_stage_name
            project.stages[next_stage_name].status = StageStatus.PENDING.value
        
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def reject_stage(self, project_id: str, feedback: str = None) -> Optional[Project]:
        """Reject current stage and send back for revision."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        current = project.stages.get(project.current_stage)
        if current.status != StageStatus.DONE.value:
            return None
            
        # Reset to pending for retry
        current.status = StageStatus.PENDING.value
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
        if current.status != StageStatus.PENDING.value:
            return None
            
        current.status = StageStatus.IN_PROGRESS.value
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
        if current.status != StageStatus.IN_PROGRESS.value:
            return None
            
        current.status = StageStatus.DONE.value
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
        current.status = StageStatus.FAILED.value
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
        if current.status != StageStatus.FAILED.value:
            return None
            
        current.status = StageStatus.PENDING.value
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
        current.status = StageStatus.SKIPPED.value
        
        # Find next stage
        current_idx = self.STAGE_ORDER.index(project.current_stage)
        if current_idx < len(self.STAGE_ORDER) - 1:
            next_stage_name = self.STAGE_ORDER[current_idx + 1]
            project.current_stage = next_stage_name
            project.stages[next_stage_name].status = StageStatus.PENDING.value
        
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
        
    def archive_project(self, project_id: str) -> Optional[Project]:
        """Archive a project."""
        project = self.load_project(project_id)
        if not project:
            return None
            
        project.status = ProjectStatus.ARCHIVED.value
        project.updated_at = datetime.now().isoformat()
        self.save_project(project)
        return project
    
    def start_connection_monitor(self):
        """Start the connection monitor for health checks."""
        self.state_manager.connection_monitor.start()
        logger.info("Connection monitor started for health checks")
    
    def stop_connection_monitor(self):
        """Stop the connection monitor."""
        self.state_manager.connection_monitor.stop()
        logger.info("Connection monitor stopped")


# Singleton instance
_bot_instance = None

def get_bot() -> CarbyBot:
    """Get or create bot instance."""
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