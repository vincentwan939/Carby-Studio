"""
Phase management commands for approval workflow.

Provides commands to approve completed phases and check phase statuses.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from ..sprint_repository import SprintRepository, SprintPaths
from ..exceptions import PhaseBlockedError, StateConsistencyError


# Phase definitions with their order and requirements
PHASE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "1": {"name": "Discovery", "description": "Requirements gathering and analysis"},
    "2": {"name": "Design", "description": "Architecture and design decisions"},
    "3": {"name": "Implementation", "description": "Code development and unit testing"},
    "4": {"name": "Validation", "description": "Testing and quality assurance"},
    "5": {"name": "Deployment", "description": "Release and deployment activities"},
}

# Status icons for visual indicators
STATUS_ICONS: dict[str, str] = {
    "approved": "✓",
    "pending_approval": "⏳",
    "in_progress": "🔄",
    "completed": "✅",
    "not_started": "○",
    "blocked": "🚫",
    "failed": "❌",
}


def get_sprint_path(sprint_id: str, output_dir: str = ".carby-sprints") -> Path:
    """Get the path to a sprint directory."""
    return Path(output_dir) / sprint_id


def load_sprint(sprint_id: str, output_dir: str = ".carby-sprints") -> tuple[dict[str, Any], Path]:
    """Load sprint metadata."""
    sprint_path: Path = get_sprint_path(sprint_id, output_dir)
    metadata_path: Path = sprint_path / "metadata.json"

    if not metadata_path.exists():
        raise StateConsistencyError(f"Sprint '{sprint_id}' not found.")

    with open(metadata_path, "r") as f:
        return json.load(f), sprint_path


def save_sprint(sprint_data: dict[str, Any], sprint_path: Path) -> None:
    """Save sprint metadata."""
    metadata_path: Path = sprint_path / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(sprint_data, f, indent=2)


def initialize_phases(sprint_data: dict[str, Any]) -> dict[str, Any]:
    """Initialize phases structure if not present."""
    if "phases" not in sprint_data:
        sprint_data["phases"] = {}
        
    # Ensure all phases exist with default status
    for phase_id, phase_def in PHASE_DEFINITIONS.items():
        if phase_id not in sprint_data["phases"]:
            sprint_data["phases"][phase_id] = {
                "id": phase_id,
                "name": phase_def["name"],
                "description": phase_def["description"],
                "status": "not_started",
                "approved": False,
                "approved_at": None,
                "approved_by": None,
            }
    
    return sprint_data


def validate_phase_id(phase_id: str) -> bool:
    """Validate that a phase ID exists."""
    return phase_id in PHASE_DEFINITIONS


def get_phase_status_display(phase: dict[str, Any]) -> str:
    """Get the display status for a phase with appropriate icon."""
    status: str = phase.get("status", "not_started")
    approved: bool = phase.get("approved", False)
    
    if approved:
        return f"{STATUS_ICONS['approved']} approved"
    elif status == "completed":
        return f"{STATUS_ICONS['pending_approval']} pending_approval"
    else:
        return f"{STATUS_ICONS.get(status, '❓')} {status}"


def can_approve_phase(sprint_data: dict[str, Any], phase_id: str) -> tuple[bool, str | None]:
    """Check if a phase can be approved. Returns (can_approve, error_message)."""
    phases: dict[str, Any] = sprint_data.get("phases", {})
    phase: dict[str, Any] | None = phases.get(phase_id)
    
    if not phase:
        return False, f"Phase '{phase_id}' not found in sprint."
    
    # Check if already approved
    if phase.get("approved", False):
        return False, f"Phase {phase_id} ({phase['name']}) is already approved."
    
    # Check if phase is completed (ready for approval)
    if phase.get("status") != "completed":
        current_status: str = phase.get("status", "not_started")
        return False, f"Phase {phase_id} ({phase['name']}) is not completed. Current status: {current_status}"
    
    # Check if previous phases are approved (sequential approval)
    phase_num: int = int(phase_id)
    for prev_num in range(1, phase_num):
        prev_phase: dict[str, Any] | None = phases.get(str(prev_num))
        if prev_phase and not prev_phase.get("approved", False):
            return False, f"Cannot approve phase {phase_id}. Previous phase {prev_num} ({prev_phase.get('name', 'Unknown')}) is not yet approved."
    
    return True, None


def raise_phase_error(sprint_data: dict[str, Any], phase_id: str, error_msg: str, force: bool = False) -> None:
    """Raise appropriate exception for phase approval errors."""
    phases: dict[str, Any] = sprint_data.get("phases", {})
    phase: dict[str, Any] | None = phases.get(phase_id)
    
    if phase and phase.get("approved", False):
        raise StateConsistencyError(error_msg)
    elif phase and phase.get("status") != "completed":
        raise StateConsistencyError(error_msg)
    elif "Previous phase" in error_msg:
        if force:
            return  # Allow force approval
        # Extract previous phase info for better error
        raise PhaseBlockedError(
            phase_id=phase_id,
            reason="Previous phase not approved",
            resolution=f"Approve previous phases first or use --force to override"
        )
    else:
        raise StateConsistencyError(error_msg)


@click.command(name="approve")
@click.argument("sprint_id")
@click.argument("phase_id")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force approval even if previous phases are not approved (requires confirmation)",
)
@click.pass_context
def approve_phase(
    ctx: click.Context,
    sprint_id: str,
    phase_id: str,
    output_dir: str,
    force: bool,
) -> None:
    """
    Approve a completed phase for the given SPRINT_ID and PHASE_ID.
    
    Phases:
      1 - Discovery: Requirements gathering and analysis
      2 - Design: Architecture and design decisions
      3 - Implementation: Code development and unit testing
      4 - Validation: Testing and quality assurance
      5 - Deployment: Release and deployment activities
    
    The phase must be in 'completed' status before it can be approved.
    Previous phases must be approved before a phase can be approved
    (unless using --force).
    """
    verbose: bool = ctx.obj.get("verbose", False)
    
    # Validate phase ID
    if not validate_phase_id(phase_id):
        valid_phases: str = ", ".join([f"{k}={v['name']}" for k, v in PHASE_DEFINITIONS.items()])
        raise click.ClickException(f"Invalid phase ID '{phase_id}'. Valid phases: {valid_phases}")
    
    # Load sprint
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)
    
    # Initialize phases if not present
    sprint_data = initialize_phases(sprint_data)
    
    # Check if phase can be approved
    can_approve, error_msg = can_approve_phase(sprint_data, phase_id)
    
    if not can_approve:
        if force and "Previous phase" in (error_msg or ""):
            # Allow force approval with warning
            click.echo(f"⚠️  Warning: {error_msg}")
            if not click.confirm("Do you want to force approval anyway?"):
                raise click.ClickException("Approval cancelled.")
            click.echo("🔄 Force approving phase...")
        else:
            raise_phase_error(sprint_data, phase_id, error_msg or "Cannot approve phase.", force=force)
    
    # Approve the phase
    phase: dict[str, Any] = sprint_data["phases"][phase_id]
    phase["approved"] = True
    phase["approved_at"] = datetime.now().isoformat()
    phase["status"] = "approved"
    
    # Save sprint
    save_sprint(sprint_data, sprint_path)
    
    # Success output
    click.echo(f"✓ Phase {phase_id} approved for sprint '{sprint_id}'")
    click.echo(f"  Name: {phase['name']}")
    click.echo(f"  Approved at: {phase['approved_at']}")
    
    # Show next steps
    next_phase_num: int = int(phase_id) + 1
    if str(next_phase_num) in PHASE_DEFINITIONS:
        next_phase: dict[str, Any] = sprint_data["phases"].get(str(next_phase_num), {})
        if next_phase.get("status") == "completed":
            click.echo(f"\nNext: carby-sprint approve {sprint_id} {next_phase_num}")
        else:
            click.echo(f"\nNext phase ({next_phase_num}) is not yet completed.")
    else:
        click.echo(f"\nAll phases approved! Sprint is ready for completion.")


@click.command(name="phase-status")
@click.argument("sprint_id")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.option(
    "--pending-only",
    "-p",
    is_flag=True,
    help="Show only phases pending approval",
)
@click.pass_context
def phase_status(
    ctx: click.Context,
    sprint_id: str,
    output_dir: str,
    pending_only: bool,
) -> None:
    """
    Show all phase statuses for the given SPRINT_ID.
    
    Displays a summary of all phases with their current status,
    highlighting phases that are pending approval.
    """
    verbose: bool = ctx.obj.get("verbose", False)
    
    # Load sprint
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)
    
    # Initialize phases if not present
    sprint_data = initialize_phases(sprint_data)
    
    phases: dict[str, Any] = sprint_data.get("phases", {})
    
    # Header
    click.echo(f"{'=' * 60}")
    click.echo(f"Phase Status for Sprint: {sprint_id}")
    click.echo(f"{'=' * 60}")
    
    # Count phases by status
    approved_count: int = 0
    pending_count: int = 0
    in_progress_count: int = 0
    not_started_count: int = 0
    completed_count: int = 0
    
    for phase_id in sorted(phases.keys(), key=int):
        phase: dict[str, Any] = phases[phase_id]
        status: str = phase.get("status", "not_started")
        approved: bool = phase.get("approved", False)
        
        if approved:
            approved_count += 1
        elif status == "completed":
            completed_count += 1
            pending_count += 1
        elif status == "in_progress":
            in_progress_count += 1
        elif status == "not_started":
            not_started_count += 1
    
    # Summary stats
    click.echo(f"\n📊 Summary")
    click.echo(f"  {STATUS_ICONS['approved']} Approved: {approved_count}")
    click.echo(f"  {STATUS_ICONS['pending_approval']} Pending Approval: {pending_count}")
    click.echo(f"  {STATUS_ICONS['in_progress']} In Progress: {in_progress_count}")
    click.echo(f"  {STATUS_ICONS['not_started']} Not Started: {not_started_count}")
    
    # Phase details
    click.echo(f"\n📋 Phases")
    
    has_pending: bool = False
    for phase_id in sorted(phases.keys(), key=int):
        phase: dict[str, Any] = phases[phase_id]
        status_display: str = get_phase_status_display(phase)
        
        # Skip if pending-only and not pending approval
        is_pending: bool = phase.get("status") == "completed" and not phase.get("approved", False)
        if pending_only and not is_pending:
            continue
        
        if is_pending:
            has_pending = True
        
        click.echo(f"  {status_display} Phase {phase_id}: {phase['name']}")
        
        if verbose:
            click.echo(f"     Description: {phase['description']}")
            if phase.get("approved_at"):
                click.echo(f"     Approved: {phase['approved_at']}")
    
    # Show message if no pending phases
    if pending_only and not has_pending:
        click.echo(f"\n  No phases pending approval.")
    
    # Footer
    click.echo(f"\n{'=' * 60}")
    
    # Progress bar
    total_phases: int = len(PHASE_DEFINITIONS)
    progress: int = approved_count
    progress_pct: float = (progress / total_phases) * 100
    bar_width: int = 30
    filled: int = int((progress / total_phases) * bar_width)
    bar: str = "█" * filled + "░" * (bar_width - filled)
    click.echo(f"Progress: [{bar}] {progress}/{total_phases} ({progress_pct:.0f}%)")


@click.command(name="phase-list")
@click.argument("sprint_id")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "json", "compact"]),
    default="table",
    help="Output format (default: table)",
)
@click.pass_context
def phase_list(
    ctx: click.Context,
    sprint_id: str,
    output_dir: str,
    format: str,
) -> None:
    """
    List all phases and their states for the given SPRINT_ID.
    
    Shows a detailed list of phases with their current state,
    useful for getting a quick overview of sprint progress.
    """
    # Load sprint
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)
    
    # Initialize phases if not present
    sprint_data = initialize_phases(sprint_data)
    
    phases: dict[str, Any] = sprint_data.get("phases", {})
    
    if format == "json":
        # JSON output
        output: dict[str, Any] = {
            "sprint_id": sprint_id,
            "phases": phases,
        }
        click.echo(json.dumps(output, indent=2))
        return
    
    if format == "compact":
        # Compact output - one line per phase
        click.echo(f"Sprint: {sprint_id}")
        for phase_id in sorted(phases.keys(), key=int):
            phase: dict[str, Any] = phases[phase_id]
            status_icon: str = STATUS_ICONS.get(phase.get("status", "not_started"), "❓")
            approved_icon: str = STATUS_ICONS["approved"] if phase.get("approved") else ""
            click.echo(f"  [{phase_id}] {status_icon} {phase['name']:<20} {approved_icon}")
        return
    
    # Table format (default)
    click.echo(f"\n{'=' * 70}")
    click.echo(f"{'Phase':<8} {'Name':<20} {'Status':<20} {'Approved':<12}")
    click.echo(f"{'-' * 70}")
    
    for phase_id in sorted(phases.keys(), key=int):
        phase: dict[str, Any] = phases[phase_id]
        status: str = phase.get("status", "not_started")
        approved: str = "Yes" if phase.get("approved") else "No"
        status_icon: str = STATUS_ICONS.get(status, "❓")
        
        # Highlight pending approvals
        if status == "completed" and not phase.get("approved"):
            status_str: str = f"{status_icon} {status} ⏳"
        else:
            status_str = f"{status_icon} {status}"
        
        click.echo(f"{phase_id:<8} {phase['name']:<20} {status_str:<20} {approved:<12}")
    
    click.echo(f"{'=' * 70}")
    
    # Legend
    click.echo(f"\nLegend:")
    click.echo(f"  {STATUS_ICONS['approved']} = Approved")
    click.echo(f"  {STATUS_ICONS['pending_approval']} = Pending Approval")
    click.echo(f"  {STATUS_ICONS['in_progress']} = In Progress")
    click.echo(f"  {STATUS_ICONS['completed']} = Completed (not approved)")
    click.echo(f"  {STATUS_ICONS['not_started']} = Not Started")
    click.echo(f"  {STATUS_ICONS['blocked']} = Blocked")
    click.echo(f"  {STATUS_ICONS['failed']} = Failed")


# Command group for phase commands
@click.group(name="phase")
def phase_group():
    """
    Phase management commands.
    
    Manage sprint phases with approval workflow. Phases represent
    major milestones in the sprint lifecycle that require explicit
    approval before proceeding to the next phase.
    """
    pass


# Register commands to the group
phase_group.add_command(approve_phase)
phase_group.add_command(phase_status)
phase_group.add_command(phase_list)


# Also export individual commands for direct CLI registration
__all__ = [
    "approve_phase",
    "phase_status", 
    "phase_list",
    "phase_group",
    "PHASE_DEFINITIONS",
    "STATUS_ICONS",
]