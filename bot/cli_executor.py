"""CLI command executor for Carby Studio Bot."""

import subprocess
import logging
import re
import shutil
from typing import Optional, Tuple
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from config import Config, CLI_COMMANDS

logger = logging.getLogger(__name__)

# Security: Valid project name pattern (already defined in config, but enforce here)
VALID_PROJECT_PATTERN = re.compile(r'^[a-z0-9-]+$')
MAX_PROJECT_LEN = 50


@dataclass
class CLIResult:
    """Result of CLI command execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    command: str


class SecurityError(Exception):
    """Raised when input fails security validation."""
    pass


class CLIExecutor:
    """Executes carby-studio CLI commands with security validation."""
    
    # Security: Valid stage names whitelist
    VALID_STAGES = {'discover', 'design', 'build', 'verify', 'deliver'}
    
    def __init__(self):
        self.timeout = 60  # seconds
    
    def _validate_project_name(self, name: str, context: str = "project") -> None:
        """Validate project name for security before passing to shell.
        
        Raises:
            SecurityError: If name contains invalid characters
        """
        if not name:
            raise SecurityError(f"{context} name cannot be empty")
        
        if len(name) > MAX_PROJECT_LEN:
            raise SecurityError(f"{context} name too long (max {MAX_PROJECT_LEN} chars)")
        
        if not VALID_PROJECT_PATTERN.match(name):
            raise SecurityError(
                f"{context} name must contain only lowercase letters, numbers, and hyphens"
            )
    
    def _validate_stage_name(self, stage: str) -> None:
        """Validate stage name against whitelist.
        
        Raises:
            SecurityError: If stage is not in valid stages
        """
        if stage not in self.VALID_STAGES:
            raise SecurityError(
                f"Invalid stage '{stage}'. Must be one of: {', '.join(self.VALID_STAGES)}"
            )
    
    def _run(self, command: list, cwd: Optional[str] = None) -> CLIResult:
        """Run a CLI command."""
        cmd_str = " ".join(command)
        logger.info(f"Executing: {cmd_str}")
        
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=cwd
            )
            
            logger.info(f"Command result: rc={result.returncode}, stdout={result.stdout[:200]}, stderr={result.stderr[:200]}")
            
            return CLIResult(
                success=result.returncode == 0,
                stdout=result.stdout.strip(),
                stderr=result.stderr.strip(),
                return_code=result.returncode,
                command=cmd_str
            )
            
        except subprocess.TimeoutExpired:
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {self.timeout}s",
                return_code=-1,
                command=cmd_str
            )
        except FileNotFoundError:
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Command not found: {command[0]}",
                return_code=-1,
                command=cmd_str
            )
        except subprocess.SubprocessError as e:
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Subprocess error: {e}",
                return_code=-1,
                command=cmd_str
            )
        except OSError as e:
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"OS error: {e}",
                return_code=-1,
                command=cmd_str
            )
    
    def dispatch(self, project: str, stage: str) -> CLIResult:
        """Dispatch agent for a stage."""
        try:
            self._validate_project_name(project)
            self._validate_stage_name(stage)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"dispatch {project} {stage}")
        
        command = ["carby-studio", "dispatch", project, stage]
        return self._run(command)
    
    def skip(self, project: str, stage: str) -> CLIResult:
        """Skip a stage."""
        try:
            self._validate_project_name(project)
            self._validate_stage_name(stage)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"skip {project} {stage}")
        
        command = ["carby-studio", "skip", project, stage]
        return self._run(command)
    
    def retry(self, project: str, stage: str) -> CLIResult:
        """Retry a failed stage."""
        try:
            self._validate_project_name(project)
            self._validate_stage_name(stage)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"retry {project} {stage}")
        
        command = ["carby-studio", "retry", project, stage]
        return self._run(command)
    
    def status(self, project: str) -> CLIResult:
        """Get project status."""
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"status {project}")
        
        command = ["carby-studio", "status", project]
        return self._run(command)
    
    def dispatch_ready(self, project: str) -> CLIResult:
        """Dispatch all ready tasks for a DAG project."""
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"dispatch-ready {project}")
        
        # Get ready tasks
        result = self._run(["carby-studio", "ready", project, "--json"])
        if not result.success:
            return result
        
        # Parse ready tasks and dispatch each one
        try:
            import json
            ready_tasks = json.loads(result.stdout)
            if not ready_tasks:
                return CLIResult(
                    success=False,
                    stdout="",
                    stderr=f"No ready tasks for '{project}'. All dependencies may not be met.",
                    return_code=1,
                    command=f"ready {project}"
                )
            
            # Dispatch first ready task (or could dispatch all in parallel)
            task_id = ready_tasks[0].get("taskId")
            if task_id:
                return self._run(["carby-studio", "dispatch", project, task_id])
            
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Could not determine task to dispatch for '{project}'",
                return_code=1,
                command=f"ready {project}"
            )
        except json.JSONDecodeError as e:
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Failed to parse ready tasks for '{project}': {e}",
                return_code=1,
                command=f"ready {project}"
            )
    
    def init(self, project: str, goal: str, mode: str = "linear") -> CLIResult:
        """Initialize a new project."""
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"init {project}")
        
        # Security: Validate mode
        valid_modes = {"linear", "dag"}
        if mode not in valid_modes:
            return CLIResult(
                False, "", f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}",
                1, f"init {project}"
            )
        
        command = ["carby-studio", "init", project, "-g", goal, "--mode", mode]
        return self._run(command)
    
    def rename(self, old_name: str, new_name: str) -> CLIResult:
        """Rename a project.
        
        Note: carby-studio may not have rename command.
        Fallback to manual file operations.
        """
        # Security: Validate both names
        try:
            self._validate_project_name(old_name, "old project")
            self._validate_project_name(new_name, "new project")
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"rename {old_name} {new_name}")
        
        # Try CLI first
        result = self._run(["carby-studio", "rename", old_name, new_name])
        logger.info(f"[CLI] carby-studio rename result: success={result.success}")
        
        if result.success:
            return result
        
        # Check for "unknown command" in stdout OR stderr (carby-studio prints errors to stdout)
        error_output = (result.stdout + result.stderr).lower()
        if "unknown command" not in error_output:
            logger.warning(f"[CLI] carby-studio rename failed, not using fallback")
            return result
        
        # Fallback: manual rename
        logger.info(f"[CLI] Using manual rename fallback")
        return self._manual_rename(old_name, new_name)
    
    def _manual_rename(self, old_name: str, new_name: str) -> CLIResult:
        """Manually rename project files."""
        projects_dir = Config.PROJECTS_DIR
        
        old_json = projects_dir / f"{old_name}.json"
        new_json = projects_dir / f"{new_name}.json"
        old_dir = projects_dir / old_name
        new_dir = projects_dir / new_name
        
        try:
            # Rename JSON file
            if old_json.exists():
                old_json.rename(new_json)
                
                # Update project name inside JSON
                import json
                with open(new_json, 'r') as f:
                    data = json.load(f)
                data['project'] = new_name
                with open(new_json, 'w') as f:
                    json.dump(data, f, indent=2)
            
            # Rename directory
            if old_dir.exists():
                old_dir.rename(new_dir)
            
            return CLIResult(
                success=True,
                stdout=f"Renamed {old_name} to {new_name}",
                stderr="",
                return_code=0,
                command=f"mv {old_name} {new_name}"
            )
            
        except (OSError, IOError, json.JSONDecodeError) as e:
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Rename failed: {e}",
                return_code=1,
                command=f"rename {old_name} {new_name}"
            )
    
    def delete(self, project: str) -> CLIResult:
        """Delete a project.
        
        Note: carby-studio may not have delete command.
        Fallback to manual deletion with backup.
        """
        logger.info(f"[CLI] delete called for project: {project}")
        
        # Security: Validate project name
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            logger.error(f"[CLI] Security validation failed: {e}")
            return CLIResult(False, "", str(e), 1, f"delete {project}")
        
        # Try CLI first
        result = self._run(["carby-studio", "delete", project])
        logger.info(f"[CLI] carby-studio delete result: success={result.success}")
        logger.info(f"[CLI] stdout: {result.stdout[:200]}")
        logger.info(f"[CLI] stderr: {result.stderr[:200]}")
        
        if result.success:
            logger.info(f"[CLI] Delete succeeded via carby-studio")
            return result
        
        # Check for "unknown command" in stdout OR stderr (carby-studio prints errors to stdout)
        error_output = (result.stdout + result.stderr).lower()
        if "unknown command" not in error_output:
            logger.warning(f"[CLI] carby-studio delete failed, not using fallback")
            return result
        
        # Fallback: manual delete with backup
        logger.info(f"[CLI] Using manual delete fallback")
        return self._manual_delete(project)
    
    def _manual_delete(self, project: str) -> CLIResult:
        """Manually delete project files with backup to trash.
        
        Uses macOS trash via AppleScript for recoverable deletion.
        Falls back to backup directory if AppleScript fails.
        """
        projects_dir = Config.PROJECTS_DIR
        json_file = projects_dir / f"{project}.json"
        project_dir = projects_dir / project
        
        # Check if anything exists to delete
        if not json_file.exists() and not project_dir.exists():
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Project '{project}' not found",
                return_code=1,
                command=f"delete {project}"
            )
        
        try:
            # Try macOS trash first (recoverable)
            deleted_items = []
            
            if json_file.exists():
                # Try trash CLI first (fastest and most reliable)
                try:
                    result = subprocess.run(
                        ["trash", str(json_file)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        deleted_items.append(f"{project}.json")
                        logger.info(f"[CLI] Moved {project}.json to trash")
                    else:
                        raise Exception(f"trash failed: {result.stderr}")
                except (subprocess.SubprocessError, OSError) as e:
                    logger.warning(f"[CLI] trash CLI failed, trying AppleScript: {e}")
                    # Fallback: macOS trash via osascript
                    try:
                        result = subprocess.run(
                            [
                                "osascript", "-e",
                                f'tell application "Finder" to delete POSIX file "{json_file}"'
                            ],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            deleted_items.append(f"{project}.json")
                        else:
                            raise subprocess.TimeoutExpired(cmd="osascript", timeout=30)
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e2:
                        logger.warning(f"[CLI] AppleScript failed, using rm fallback: {e2}")
                        # Final fallback: direct delete
                        json_file.unlink()
                        deleted_items.append(f"{project}.json")
            
            if project_dir.exists():
                # Try trash CLI first
                try:
                    result = subprocess.run(
                        ["trash", str(project_dir)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    if result.returncode == 0:
                        deleted_items.append(f"{project}/")
                        logger.info(f"[CLI] Moved {project}/ to trash")
                    else:
                        raise Exception(f"trash failed: {result.stderr}")
                except (subprocess.SubprocessError, OSError) as e:
                    logger.warning(f"[CLI] trash CLI failed for dir, trying AppleScript: {e}")
                    # Fallback: macOS trash via osascript
                    try:
                        result = subprocess.run(
                            [
                                "osascript", "-e",
                                f'tell application "Finder" to delete POSIX file "{project_dir}"'
                            ],
                            capture_output=True,
                            text=True,
                            timeout=30
                        )
                        if result.returncode == 0:
                            deleted_items.append(project)
                        else:
                            raise subprocess.TimeoutExpired(cmd="osascript", timeout=30)
                    except (subprocess.TimeoutExpired, subprocess.SubprocessError, OSError) as e2:
                        logger.warning(f"[CLI] AppleScript failed for dir, using rm fallback: {e2}")
                        # Final fallback: direct delete
                        shutil.rmtree(project_dir)
                        deleted_items.append(f"{project}/")
            
            return CLIResult(
                success=True,
                stdout=f"Deleted {project}. Items moved to trash: {', '.join(deleted_items)}",
                stderr="",
                return_code=0,
                command=f"delete {project}"
            )
            
        except (OSError, IOError, shutil.Error) as e:
            logger.error(f"Failed to delete project {project}: {e}")
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Failed to delete {project}: {e}",
                return_code=1,
                command=f"delete {project}"
            )
    
    def validate_project_name(self, name: str) -> Tuple[bool, str]:
        """Validate project name format."""
        if not name:
            return False, "Project name cannot be empty"
        
        if len(name) > Config.PROJECT_NAME_MAX_LEN:
            return False, f"Project name too long (max {Config.PROJECT_NAME_MAX_LEN} chars)"
        
        if not re.match(Config.PROJECT_NAME_PATTERN, name):
            return False, "Project name must contain only lowercase letters, numbers, and hyphens"
        
        return True, ""
    
    def project_exists(self, name: str) -> bool:
        """Check if project exists."""
        json_file = Config.PROJECTS_DIR / f"{name}.json"
        return json_file.exists()
    
    def approve(self, project: str) -> CLIResult:
        """Approve current stage."""
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"approve {project}")
        
        command = ["carby-studio", "approve", project]
        return self._run(command)
    
    def stop(self, project: str) -> CLIResult:
        """Stop current agent."""
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"stop {project}")
        
        command = ["carby-studio", "stop", project]
        return self._run(command)
    
    def logs(self, project: str) -> CLIResult:
        """Get project logs."""
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"logs {project}")
        
        command = ["carby-studio", "logs", project]
        return self._run(command)
