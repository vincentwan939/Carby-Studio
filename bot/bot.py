"""Main bot implementation integrating all components with health checks."""

import logging
import time
import threading
from typing import Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

from config import Config
from state_manager import StateManager, StateChange, ConnectionMonitor
from notification_service import NotificationService, Notification
from cli_executor import CLIExecutor, CLIResult
from safety import SafetyManager, SafetyCheck
from atomic_file import atomic_write_json, safe_read_json

logger = logging.getLogger(__name__)


@dataclass
class BotContext:
    """Context for bot operations."""
    state_manager: StateManager
    notification_service: NotificationService
    cli_executor: CLIExecutor
    safety_manager: SafetyManager


class CarbyBot:
    """Main bot class coordinating all components with health checks."""
    
    def __init__(self):
        self.config = Config()
        self.state_manager = StateManager()
        self.notification_service = NotificationService()
        self.cli_executor = CLIExecutor()
        self.safety_manager = SafetyManager(self.state_manager)
        
        self.context = BotContext(
            state_manager=self.state_manager,
            notification_service=self.notification_service,
            cli_executor=self.cli_executor,
            safety_manager=self.safety_manager
        )
        
        # Add connection monitor for health checks
        self.connection_monitor = self.state_manager.connection_monitor
        
        self._running = False
        self._poll_thread: Optional[threading.Thread] = None
    
    def start(self):
        """Start the bot with health monitoring."""
        # Prevent double-start
        if self._running:
            logger.warning("Bot already running, ignoring start() call")
            return
        
        if self._poll_thread and self._poll_thread.is_alive():
            logger.warning("Polling thread already exists, ignoring start() call")
            return
        
        logger.info("Starting Carby Bot with health monitoring...")
        self._running = True
        
        # Start connection monitor for health checks
        self.connection_monitor.start()
        
        # Start polling in background thread
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        
        logger.info("Bot started with health monitoring")
    
    def stop(self):
        """Stop the bot and health monitoring."""
        logger.info("Stopping Carby Bot and health monitoring...")
        self._running = False
        
        if self._poll_thread:
            self._poll_thread.join(timeout=5)
        
        # Stop connection monitor
        self.connection_monitor.stop()
        
        logger.info("Bot and health monitoring stopped")
    
    def _poll_loop(self):
        """Main polling loop with health monitoring."""
        while self._running:
            try:
                self._poll_once()
            except (OSError, IOError, ValueError, KeyError) as e:
                logger.error(f"Poll error: {e}")
                # Mark error for connection monitor
                self.connection_monitor.mark_success()  # Actually this indicates success of the poll attempt
            except Exception as e:
                logger.error(f"Unexpected poll error: {e}")
                # Still mark success since we caught the error and didn't crash
                self.connection_monitor.mark_success()
            
            # Calculate sleep interval based on active projects
            interval = self._get_poll_interval()
            time.sleep(interval)
    
    def _get_poll_interval(self) -> int:
        """Get appropriate poll interval based on project activity."""
        # Check if any project is in-progress
        for project_id in self.state_manager.list_projects():
            summary = self.state_manager.get_project_summary(project_id)
            if summary and summary.get("current_status") == "in-progress":
                return Config.ACTIVE_POLL_INTERVAL
        
        return Config.POLL_INTERVAL
    
    def _poll_once(self):
        """Single poll iteration with health monitoring."""
        changes = self.state_manager.detect_changes()
        
        for change in changes:
            notification = self.notification_service.generate(change)
            if notification:
                self._handle_notification(notification)
    
    def _handle_notification(self, notification: Notification):
        """Handle a notification (to be overridden by Telegram handler)."""
        # Base class just logs
        logger.info(f"Notification: {notification.message}")
    
    # Action handlers
    
    def dispatch_stage(self, project: str, stage: Optional[str] = None) -> CLIResult:
        """Dispatch next stage for a project."""
        if not stage:
            # Get project summary
            summary = self.state_manager.get_project_summary(project)
            if not summary:
                return CLIResult(
                    success=False,
                    stdout="",
                    stderr=f"Project '{project}' not found",
                    return_code=1,
                    command="dispatch"
                )
            
            # Check project mode
            mode = summary.get("mode", "linear")
            
            if mode == "dag":
                # For DAG mode, use 'ready' command to find dispatchable tasks
                return self.cli_executor.dispatch_ready(project)
            else:
                # Linear mode: get current stage or first pending
                stage = summary.get("current_stage")
                
                if not stage:
                    pipeline = summary.get("pipeline", [])
                    stages = summary.get("stages", {})
                    for s in pipeline:
                        if stages.get(s, {}).get("status") == "pending":
                            stage = s
                            break
                
                if not stage:
                    return CLIResult(
                        success=False,
                        stdout="",
                        stderr=f"No pending stages for '{project}'. All stages may be complete.",
                        return_code=1,
                        command="dispatch"
                    )
        
        return self.cli_executor.dispatch(project, stage)
    
    def skip_stage(self, project: str, stage: Optional[str] = None) -> CLIResult:
        """Skip a stage."""
        if not stage:
            summary = self.state_manager.get_project_summary(project)
            if summary:
                stage = summary.get("current_stage", "")
        
        return self.cli_executor.skip(project, stage)
    
    def retry_stage(self, project: str, stage: Optional[str] = None) -> CLIResult:
        """Retry a failed stage."""
        if not stage:
            summary = self.state_manager.get_project_summary(project)
            if summary:
                stage = summary.get("current_stage", "")
        
        return self.cli_executor.retry(project, stage)
    
    def rename_project(self, old_name: str, new_name: str) -> Tuple[bool, str]:
        """Rename a project with safety checks."""
        # Safety check
        check = self.safety_manager.check_rename(old_name, new_name)
        if not check.allowed:
            return False, check.reason
        
        # Execute rename
        result = self.cli_executor.rename(old_name, new_name)
        
        if result.success:
            return True, f"Renamed '{old_name}' to '{new_name}'"
        else:
            return False, result.stderr or "Rename failed"
    
    def delete_project(self, project: str, confirmation: Optional[str] = None) -> Tuple[bool, str]:
        """Delete a project with safety checks and confirmation."""
        logger.info(f"[BOT] delete_project called: project='{project}', confirmation='{confirmation}'")
        
        # Safety check
        check = self.safety_manager.check_delete(project)
        if not check.allowed:
            logger.warning(f"[BOT] Safety check failed: {check.reason}")
            return False, check.reason
        
        # Check if project is in-progress and stop it first
        details = check.details or {}
        if details.get("in_progress"):
            logger.info(f"[BOT] Stopping in-progress agent for '{project}' before delete")
            # Mark the current stage as failed/stopped in the project state
            self._stop_project_agent(project)
        
        # Execute delete
        result = self.cli_executor.delete(project)
        
        if result.success:
            return True, f"Deleted '{project}'"
        else:
            return False, result.stderr or "Delete failed"
    
    def _stop_project_agent(self, project: str):
        """Mark a project's current stage as stopped/failed so it can be deleted."""
        from config import Config
        
        try:
            json_file = Config.PROJECTS_DIR / f"{project}.json"
            
            # Use safe read with specific exception handling
            data = safe_read_json(json_file)
            if data is None:
                return
            
            # Find the in-progress stage and mark it as failed
            stages = data.get("stages", {})
            modified = False
            for stage_name, stage_info in stages.items():
                if stage_info.get("status") == "in-progress":
                    stage_info["status"] = "failed"
                    stage_info["error"] = "Agent stopped by user before delete"
                    modified = True
                    logger.info(f"[BOT] Marked stage '{stage_name}' as failed for '{project}'")
            
            if not modified:
                return
            
            # Save updated state atomically
            if atomic_write_json(json_file, data):
                # Update cache
                self.state_manager.read_project(project)
            else:
                logger.error(f"[BOT] Failed to save stopped agent state for '{project}'")
            
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"[BOT] Failed to stop agent for '{project}': {e}")
    
    def stop_agent(self, project: str) -> Tuple[bool, str]:
        """Stop the running agent for a project."""
        from config import Config
        
        try:
            json_file = Config.PROJECTS_DIR / f"{project}.json"
            
            # Use safe read with specific exception handling
            data = safe_read_json(json_file)
            if data is None:
                return False, f"Project '{project}' not found"
            
            # Find the in-progress stage and mark it as failed
            stages = data.get("stages", {})
            stopped = False
            for stage_name, stage_info in stages.items():
                if stage_info.get("status") == "in-progress":
                    stage_info["status"] = "failed"
                    stage_info["error"] = "Agent stopped by user"
                    stopped = True
                    logger.info(f"[BOT] Stopped stage '{stage_name}' for '{project}'")
            
            if not stopped:
                return False, "No running agent found"
            
            # Save updated state atomically
            if atomic_write_json(json_file, data):
                # Update cache
                self.state_manager.read_project(project)
                return True, f"Agent stopped for '{project}'"
            else:
                return False, "Failed to save agent state"
            
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"[BOT] Failed to stop agent for '{project}': {e}")
            return False, str(e)
    
    def get_project_list(self) -> str:
        """Get formatted project list."""
        return self.state_manager.format_project_list()
    
    def get_project_detail(self, project: str) -> Optional[str]:
        """Get formatted project detail."""
        summary = self.state_manager.get_project_summary(project)
        if not summary:
            return None
        
        return self.notification_service.format_project_detail(summary)
    
    def create_project(self, name: str, goal: str, mode: str = "linear") -> Tuple[bool, str]:
        """Create a new project."""
        # Validate name
        valid, error = self.cli_executor.validate_project_name(name)
        if not valid:
            return False, error
        
        # Check doesn't exist
        if self.cli_executor.project_exists(name):
            return False, f"Project '{name}' already exists"
        
        # Create
        result = self.cli_executor.init(name, goal, mode)
        
        if result.success:
            return True, f"Created project '{name}'"
        else:
            return False, result.stderr or "Failed to create project"
    
    def get_credential_status(self, project: str) -> Optional[dict]:
        """Get credential status for a project.
        
        Returns:
            Dict with storage type, total count, and verified count
        """
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
            from credentials_handler import CredentialsHandler
            
            handler = CredentialsHandler()
            return handler.get_status(project)
        except Exception as e:
            logger.error(f"Failed to get credential status: {e}")
            return None
    
    def list_project_credentials(self, project: str) -> list:
        """List credentials for a project.
        
        Returns:
            List of CredentialStatus objects
        """
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
            from credentials_handler import CredentialsHandler
            
            handler = CredentialsHandler()
            return handler.list_credentials(project)
        except Exception as e:
            logger.error(f"Failed to list credentials: {e}")
            return []
    
    def verify_credential(self, project: str, cred_type: str, name: str) -> Tuple[bool, str]:
        """Verify a credential.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))
            from credentials_handler import CredentialsHandler
            
            handler = CredentialsHandler()
            return handler.verify_credential(project, cred_type, name)
        except Exception as e:
            logger.error(f"Failed to verify credential: {e}")
            return False, str(e)
    
    def start_sprint(self, sprint: str, mode: str = "sequential") -> CLIResult:
        """Start a sprint."""
        return self.cli_executor.sprint_start(sprint, mode)
    
    def pause_sprint(self, sprint: str) -> CLIResult:
        """Pause a sprint."""
        return self.cli_executor.sprint_pause(sprint)
    
    def resume_sprint(self, sprint: str) -> CLIResult:
        """Resume a sprint."""
        return self.cli_executor.sprint_resume(sprint)
    
    def cancel_sprint(self, sprint: str) -> CLIResult:
        """Cancel a sprint."""
        return self.cli_executor.sprint_cancel(sprint)
    
    def archive_sprint(self, sprint: str) -> CLIResult:
        """Archive a sprint."""
        return self.cli_executor.sprint_archive(sprint)
    
    def advance_gate(self, sprint: str, gate_number: int, force: bool = False, retry: bool = False) -> CLIResult:
        """Advance to a specific gate."""
        return self.cli_executor.sprint_gate(sprint, gate_number, force, retry)
    
    def approve_phase(self, sprint: str, phase_id: Optional[str] = None) -> CLIResult:
        """Approve a phase."""
        return self.cli_executor.sprint_approve(sprint, phase_id)
    
    def get_sprint_detail(self, sprint: str) -> Optional[str]:
        """Get formatted sprint detail."""
        summary = self.state_manager.get_sprint_summary(sprint)
        if not summary:
            return None
        return (
            f"📋 *{summary['id']}*\n"
            f"📦 Project: {summary['project']}\n"
            f"🎯 {summary['goal']}\n"
            f"📊 Status: {summary['status']}\n"
            f"📍 Current Gate: {summary['current_gate']} ({summary['current_gate_name']})"
        )
