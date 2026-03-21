"""CLI command executor for Carby Studio Bot.

MIGRATION NOTE: This module has been migrated from carby-studio to carby-sprint.
All new commands use `carby-sprint` CLI instead of the deprecated `carby-studio`.

BACKWARD COMPATIBILITY: Old method signatures are preserved but delegate to
new sprint-based commands where applicable.
"""

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

# Security: Valid project/sprint name pattern
VALID_PROJECT_PATTERN = re.compile(r'^[a-z0-9-]+$')
MAX_PROJECT_LEN = 50

# Security: Valid gate numbers for carby-sprint
VALID_GATE_NUMBERS = {1, 2, 3, 4, 5}

# Gate number to name mapping (for reference)
GATE_NAMES = {
    1: "discover",
    2: "design",
    3: "build",
    4: "verify",
    5: "deliver"
}


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
    """Executes carby-sprint CLI commands with security validation.

    MIGRATION: This class has been migrated from carby-studio to carby-sprint.
    All methods now use the `carby-sprint` CLI command.
    """

    # DEPRECATED: Old stage names whitelist (kept for backward compatibility reference)
    VALID_STAGES = {'discover', 'design', 'build', 'verify', 'deliver'}

    def __init__(self):
        self.timeout = 60  # seconds

    def _validate_project_name(self, name: str, context: str = "project") -> None:
        """Validate project/sprint name for security before passing to shell.

        Args:
            name: The project or sprint name to validate
            context: Context for error messages ("project", "sprint", etc.)

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

    def _validate_sprint_name(self, name: str) -> None:
        """Validate sprint name (alias for _validate_project_name).

        Args:
            name: The sprint name to validate

        Raises:
            SecurityError: If name contains invalid characters
        """
        self._validate_project_name(name, context="sprint")

    def _validate_gate_number(self, gate: int) -> None:
        """Validate gate number (1-5).

        Args:
            gate: The gate number to validate

        Raises:
            SecurityError: If gate is not in valid range (1-5)
        """
        if gate not in VALID_GATE_NUMBERS:
            raise SecurityError(
                f"Invalid gate number {gate}. Must be one of: {', '.join(map(str, sorted(VALID_GATE_NUMBERS)))}"
            )

    def _validate_stage_name(self, stage: str) -> None:
        """Validate stage name against whitelist.

        DEPRECATED: Stages are replaced by gates (1-5) in carby-sprint.
        Kept for backward compatibility reference.

        Raises:
            SecurityError: If stage is not in valid stages
        """
        if stage not in self.VALID_STAGES:
            raise SecurityError(
                f"Invalid stage '{stage}'. Must be one of: {', '.join(self.VALID_STAGES)}"
            )

    def _run(self, command: list, cwd: Optional[str] = None) -> CLIResult:
        """Run a CLI command using list-based subprocess for security.

        Args:
            command: List of command arguments (first element is the executable)
            cwd: Optional working directory for the command

        Returns:
            CLIResult with execution outcome
        """
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
            logger.error(f"Command timed out after {self.timeout}s: {cmd_str}")
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Command timed out after {self.timeout}s",
                return_code=-1,
                command=cmd_str
            )
        except FileNotFoundError:
            logger.error(f"Command not found: {command[0]}")
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Command not found: {command[0]}",
                return_code=-1,
                command=cmd_str
            )
        except subprocess.SubprocessError as e:
            logger.error(f"Subprocess error: {e}")
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"Subprocess error: {e}",
                return_code=-1,
                command=cmd_str
            )
        except OSError as e:
            logger.error(f"OS error: {e}")
            return CLIResult(
                success=False,
                stdout="",
                stderr=f"OS error: {e}",
                return_code=-1,
                command=cmd_str
            )

    # =========================================================================
    # NEW carby-sprint COMMANDS
    # =========================================================================

    def sprint_init(self, sprint: str, project: str, goal: str, duration: Optional[int] = None) -> CLIResult:
        """Initialize a new sprint.

        Maps to: carby-sprint init <sprint> --project <project> --goal <goal> [--duration <days>]

        Args:
            sprint: Sprint ID (e.g., "my-project-sprint1")
            project: Project reference (e.g., "my-project")
            goal: Sprint goal description
            duration: Optional duration in days

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"init {sprint}")

        # Security: Validate goal length
        if not goal or len(goal) > 500:
            return CLIResult(
                False, "", "Goal must be between 1 and 500 characters", 1, f"init {sprint}"
            )

        command = ["carby-sprint", "init", sprint, "--project", project, "--goal", goal]
        if duration is not None:
            # Security: Validate duration is a positive integer
            if not isinstance(duration, int) or duration < 1 or duration > 365:
                return CLIResult(
                    False, "", "Duration must be between 1 and 365 days", 1,
                    f"init {sprint}"
                )
            command.extend(["--duration", str(duration)])

        return self._run(command)

    def sprint_start(self, sprint: str, mode: str = "sequential") -> CLIResult:
        """Start a sprint execution.

        Maps to: carby-sprint start <sprint> [--mode sequential|parallel]

        Args:
            sprint: Sprint ID to start
            mode: Execution mode (sequential or parallel)

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"start {sprint}")

        # Security: Validate mode
        valid_modes = {"sequential", "parallel"}
        if mode not in valid_modes:
            return CLIResult(
                False, "", f"Invalid mode '{mode}'. Must be one of: {', '.join(valid_modes)}",
                1, f"start {sprint}"
            )

        command = ["carby-sprint", "start", sprint, "--mode", mode]
        return self._run(command)

    def sprint_gate(self, sprint: str, gate_number: int, force: bool = False, retry: bool = False) -> CLIResult:
        """Advance to or retry a specific gate.

        Maps to: carby-sprint gate <sprint> <gate_number> [--force] [--retry]

        Args:
            sprint: Sprint ID
            gate_number: Gate number (1-5)
            force: Whether to force advance (skip gate)
            retry: Whether to retry current gate

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
            self._validate_gate_number(gate_number)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"gate {sprint} {gate_number}")

        command = ["carby-sprint", "gate", sprint, str(gate_number)]
        if force:
            command.append("--force")
        if retry:
            command.append("--retry")

        return self._run(command)

    def sprint_approve(self, sprint: str, phase_id: Optional[str] = None, auto_advance: bool = False) -> CLIResult:
        """Approve current phase or specific phase.

        Maps to: carby-sprint approve <sprint> [phase_id] [--auto-advance]

        Args:
            sprint: Sprint ID
            phase_id: Optional specific phase to approve (otherwise approves current)
            auto_advance: Whether to auto-advance to next gate after approval

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"approve {sprint}")

        command = ["carby-sprint", "approve", sprint]
        if phase_id:
            # Security: Validate phase_id format (simple validation)
            if not re.match(r'^[a-zA-Z0-9_-]+$', phase_id):
                return CLIResult(
                    False, "", f"Invalid phase ID '{phase_id}'. Must contain only alphanumeric characters, hyphens, and underscores",
                    1, f"approve {sprint}"
                )
            command.append(phase_id)

        if auto_advance:
            command.append("--auto-advance")

        return self._run(command)

    def sprint_pause(self, sprint: str) -> CLIResult:
        """Pause sprint execution.

        Maps to: carby-sprint pause <sprint>

        Args:
            sprint: Sprint ID to pause

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"pause {sprint}")

        command = ["carby-sprint", "pause", sprint]
        return self._run(command)

    def sprint_resume(self, sprint: str) -> CLIResult:
        """Resume paused sprint.

        Maps to: carby-sprint resume <sprint>

        Args:
            sprint: Sprint ID to resume

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"resume {sprint}")

        command = ["carby-sprint", "resume", sprint]
        return self._run(command)

    def sprint_cancel(self, sprint: str) -> CLIResult:
        """Cancel sprint execution.

        Maps to: carby-sprint cancel <sprint>

        Args:
            sprint: Sprint ID to cancel

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"cancel {sprint}")

        command = ["carby-sprint", "cancel", sprint]
        return self._run(command)

    def sprint_archive(self, sprint: str) -> CLIResult:
        """Archive completed sprint.

        Maps to: carby-sprint archive <sprint>

        Args:
            sprint: Sprint ID to archive

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"archive {sprint}")

        command = ["carby-sprint", "archive", sprint]
        return self._run(command)

    def sprint_status(self, sprint: str, watch: bool = False) -> CLIResult:
        """Get sprint status.

        Maps to: carby-sprint status <sprint> [--watch]

        Args:
            sprint: Sprint ID to check
            watch: Whether to continuously watch status

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"status {sprint}")

        command = ["carby-sprint", "status", sprint]
        if watch:
            command.append("--watch")

        return self._run(command)

    def sprint_phase_status(self, sprint: str) -> CLIResult:
        """Get detailed phase status.

        Maps to: carby-sprint phase-status <sprint>

        Args:
            sprint: Sprint ID to check

        Returns:
            CLIResult with execution outcome
        """
        try:
            self._validate_sprint_name(sprint)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"phase-status {sprint}")

        command = ["carby-sprint", "phase-status", sprint]
        return self._run(command)

    def sprint_list(self, json_format: bool = False) -> CLIResult:
        """List all sprints.

        Maps to: carby-sprint list [--json]

        Args:
            json_format: Whether to return results in JSON format

        Returns:
            CLIResult with execution outcome
        """
        command = ["carby-sprint", "list"]
        if json_format:
            command.append("--json")

        return self._run(command)

    # =========================================================================
    # BACKWARD COMPATIBILITY: Old carby-studio commands (deprecated)
    # These are maintained temporarily during migration period
    # =========================================================================

    def dispatch(self, project: str, stage: str) -> CLIResult:
        """DEPRECATED: Dispatch agent for a stage.

        This method is maintained for backward compatibility during migration.
        In carby-sprint, use sprint_gate() to advance through gates.
        """
        try:
            self._validate_project_name(project)
            self._validate_stage_name(stage)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"dispatch {project} {stage}")

        # Map old stages to new gates for backward compatibility
        stage_to_gate = {
            'discover': 1,
            'design': 2,
            'build': 3,
            'verify': 4,
            'deliver': 5
        }

        gate_number = stage_to_gate.get(stage)
        if gate_number:
            # Use the new sprint_gate method with the project name as sprint name
            return self.sprint_gate(project, gate_number)
        else:
            command = ["carby-studio", "dispatch", project, stage]
            return self._run(command)

    def skip(self, project: str, stage: str) -> CLIResult:
        """DEPRECATED: Skip a stage.

        This method is maintained for backward compatibility during migration.
        In carby-sprint, use sprint_gate() with force=True.
        """
        try:
            self._validate_project_name(project)
            self._validate_stage_name(stage)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"skip {project} {stage}")

        # Map old stages to new gates for backward compatibility
        stage_to_gate = {
            'discover': 1,
            'design': 2,
            'build': 3,
            'verify': 4,
            'deliver': 5
        }

        gate_number = stage_to_gate.get(stage)
        if gate_number:
            # Use the new sprint_gate method with force=True
            return self.sprint_gate(project, gate_number, force=True)
        else:
            command = ["carby-studio", "skip", project, stage]
            return self._run(command)

    def retry(self, project: str, stage: str) -> CLIResult:
        """DEPRECATED: Retry a failed stage.

        This method is maintained for backward compatibility during migration.
        In carby-sprint, use sprint_gate() with retry=True.
        """
        try:
            self._validate_project_name(project)
            self._validate_stage_name(stage)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"retry {project} {stage}")

        # Map old stages to new gates for backward compatibility
        stage_to_gate = {
            'discover': 1,
            'design': 2,
            'build': 3,
            'verify': 4,
            'deliver': 5
        }

        gate_number = stage_to_gate.get(stage)
        if gate_number:
            # Use the new sprint_gate method with retry=True
            return self.sprint_gate(project, gate_number, retry=True)
        else:
            command = ["carby-studio", "retry", project, stage]
            return self._run(command)

    def approve(self, project: str) -> CLIResult:
        """DEPRECATED: Approve current stage.

        This method is maintained for backward compatibility during migration.
        In carby-sprint, use sprint_approve().
        """
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"approve {project}")

        # Use the new sprint_approve method with the project name as sprint name
        return self.sprint_approve(project)

    def status(self, project: str) -> CLIResult:
        """DEPRECATED: Get project status.

        This method is maintained for backward compatibility during migration.
        In carby-sprint, use sprint_status().
        """
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"status {project}")

        # Use the new sprint_status method with the project name as sprint name
        return self.sprint_status(project)

    def stop(self, project: str) -> CLIResult:
        """DEPRECATED: Stop current agent.

        This method is maintained for backward compatibility during migration.
        In carby-sprint, use sprint_pause().
        """
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"stop {project}")

        # Use the new sprint_pause method with the project name as sprint name
        return self.sprint_pause(project)

    def logs(self, project: str) -> CLIResult:
        """DEPRECATED: Get project logs.

        This method is maintained for backward compatibility during migration.
        In carby-sprint, use appropriate log commands.
        """
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"logs {project}")

        # In carby-sprint, logs are typically accessed differently
        # For now, we'll try the old command but this might need adjustment
        command = ["carby-studio", "logs", project]
        return self._run(command)

    def init(self, project: str, goal: str, mode: str = "linear") -> CLIResult:
        """DEPRECATED: Initialize a new project.

        This method is maintained for backward compatibility during migration.
        In carby-sprint, use sprint_init().
        """
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

        # Use the new sprint_init method with the project name as both sprint and project
        return self.sprint_init(project, project, goal)

    def dispatch_ready(self, project: str) -> CLIResult:
        """DEPRECATED: Dispatch all ready tasks for a DAG project.

        This method is maintained for backward compatibility during migration.
        """
        try:
            self._validate_project_name(project)
        except SecurityError as e:
            return CLIResult(False, "", str(e), 1, f"dispatch-ready {project}")

        # Get ready tasks (this might need adjustment for carby-sprint)
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

    def rename(self, old_name: str, new_name: str) -> CLIResult:
        """DEPRECATED: Rename a project.

        This method is maintained for backward compatibility during migration.
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
        """DEPRECATED: Delete a project.

        This method is maintained for backward compatibility during migration.
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