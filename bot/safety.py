"""Safety features for destructive operations."""

import logging
from typing import Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

from config import Config
from state_manager import StateManager

logger = logging.getLogger(__name__)


@dataclass
class SafetyCheck:
    """Result of a safety check."""
    allowed: bool
    reason: str
    details: Optional[dict] = None


class SafetyManager:
    """Manages safety checks for destructive operations."""
    
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager
        self._delete_confirmations = {}  # project -> expected confirmation
    
    def check_rename(self, old_name: str, new_name: str) -> SafetyCheck:
        """Check if rename is safe."""
        from cli_executor import CLIExecutor
        
        executor = CLIExecutor()
        
        # Validate new name format
        valid, error = executor.validate_project_name(new_name)
        if not valid:
            return SafetyCheck(allowed=False, reason=error)
        
        # Check old project exists
        if not executor.project_exists(old_name):
            return SafetyCheck(allowed=False, reason=f"Project '{old_name}' not found")
        
        # Check new name doesn't exist
        if executor.project_exists(new_name):
            return SafetyCheck(
                allowed=False,
                reason=f"Project '{new_name}' already exists",
                details={"existing_project": new_name}
            )
        
        # Check not in-progress
        summary = self.state_manager.get_project_summary(old_name)
        if summary and summary.get("current_status") == "in-progress":
            return SafetyCheck(
                allowed=False,
                reason=f"Cannot rename while '{old_name}' has running agent",
                details={"status": "in-progress"}
            )
        
        return SafetyCheck(allowed=True, reason="Rename is safe")
    
    def check_delete(self, project: str) -> SafetyCheck:
        """Check if delete is safe."""
        from cli_executor import CLIExecutor
        
        executor = CLIExecutor()
        
        # Check project exists
        if not executor.project_exists(project):
            return SafetyCheck(allowed=False, reason=f"Project '{project}' not found")
        
        # Get what will be deleted
        projects_dir = Config.PROJECTS_DIR
        json_file = projects_dir / f"{project}.json"
        project_dir = projects_dir / project
        
        # Check if in-progress (warn but allow with confirmation)
        summary = self.state_manager.get_project_summary(project)
        is_in_progress = summary and summary.get("current_status") == "in-progress"
        
        details = {
            "json_file": str(json_file),
            "project_dir": str(project_dir) if project_dir.exists() else None,
            "in_progress": is_in_progress,
        }
        
        if is_in_progress:
            return SafetyCheck(
                allowed=True,
                reason=f"⚠️ '{project}' has a running agent. Will stop agent before deleting.",
                details=details
            )
        
        return SafetyCheck(
            allowed=True,
            reason="Delete is safe (with confirmation)",
            details=details
        )
    
    def request_delete_confirmation(self, project: str) -> str:
        """Request confirmation for delete.
        
        Returns the confirmation code user must type.
        """
        confirmation = "DELETE"
        self._delete_confirmations[project] = confirmation
        logger.info(f"[SAFETY] Stored confirmation for '{project}': {confirmation}")
        logger.info(f"[SAFETY] Current confirmations: {self._delete_confirmations}")
        return confirmation
    
    def verify_delete_confirmation(self, project: str, user_input: str) -> bool:
        """
        Verify user's delete confirmation.
        
        Only removes the confirmation on successful match, allowing retries
        on typos without requiring re-confirmation.
        """
        expected = self._delete_confirmations.get(project)
        logger.info(f"[SAFETY] Verifying confirmation for '{project}': expected='{expected}', got='{user_input}'")
        logger.info(f"[SAFETY] All confirmations: {self._delete_confirmations}")
        if not expected:
            logger.warning(f"[SAFETY] No confirmation found for '{project}'")
            return False
        
        # Check match first
        is_valid = user_input.strip().upper() == expected
        
        # Only remove confirmation on success (allows retries on typos)
        if is_valid:
            del self._delete_confirmations[project]
            logger.info(f"[SAFETY] Confirmation verified and removed for '{project}'")
        else:
            logger.info(f"[SAFETY] Confirmation mismatch for '{project}', keeping for retry")
        
        return is_valid
    
    def check_stop_agent(self, project: str) -> SafetyCheck:
        """Check if stopping agent is safe."""
        summary = self.state_manager.get_project_summary(project)
        
        if not summary:
            return SafetyCheck(allowed=False, reason=f"Project '{project}' not found")
        
        if summary.get("current_status") != "in-progress":
            return SafetyCheck(
                allowed=False,
                reason=f"No running agent for '{project}'",
                details={"status": summary.get("current_status")}
            )
        
        return SafetyCheck(
            allowed=True,
            reason="Agent can be stopped",
            details={"agent": summary.get("agent"), "stage": summary.get("current_stage")}
        )
    
    def format_delete_preview(self, project: str, details: dict) -> str:
        """Format what will be deleted for user confirmation."""
        lines = [
            f"⚠️ *Delete {project}?*",
            "",
            "This will permanently remove:",
            "",
        ]
        
        json_file = details.get("json_file")
        if json_file:
            lines.append(f"📄 {json_file}")
        
        project_dir = details.get("project_dir")
        if project_dir:
            lines.append(f"📁 {project_dir}/")
            
            # List contents
            try:
                path = Path(project_dir)
                if path.exists():
                    contents = list(path.iterdir())
                    if contents:
                        lines.append(f"   ({len(contents)} items)")
            except (OSError, IOError, PermissionError):
                pass
        
        lines.extend([
            "",
            "*This cannot be undone.*",
            "",
            f"Type 'DELETE' to confirm:",
        ])
        
        return "\n".join(lines)
    
    def format_rename_preview(self, old_name: str, new_name: str) -> str:
        """Format rename preview."""
        projects_dir = Config.PROJECTS_DIR
        
        lines = [
            f"✏️ *Rename Project*",
            "",
            f"From: `{old_name}`",
            f"To: `{new_name}`",
            "",
            "Will rename:",
            f"📄 {old_name}.json → {new_name}.json",
        ]
        
        old_dir = projects_dir / old_name
        if old_dir.exists():
            lines.append(f"📁 {old_name}/ → {new_name}/")
        
        lines.append("")
        lines.append("Confirm rename?")
        
        return "\n".join(lines)
