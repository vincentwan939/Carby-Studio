"""
Approve command for Phase Lock - allows advancing to next phase in sequential mode.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from ..phase_lock import PhaseLock, PhaseLockState


def get_sprint_path(sprint_id: str, output_dir: str = ".carby-sprints") -> Path:
    """Get the path to a sprint directory."""
    return Path(output_dir) / sprint_id


def load_sprint(sprint_id: str, output_dir: str = ".carby-sprints") -> tuple[dict[str, Any], Path]:
    """Load sprint metadata."""
    sprint_path: Path = get_sprint_path(sprint_id, output_dir)
    metadata_path: Path = sprint_path / "metadata.json"

    if not metadata_path.exists():
        raise click.ClickException(f"Sprint '{sprint_id}' not found.")

    with open(metadata_path, "r") as f:
        return json.load(f), sprint_path


@click.command()
@click.argument("sprint_id")
@click.argument("phase_id", required=False)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.option(
    "--auto-advance",
    is_flag=True,
    help="Automatically start the next phase after approval",
)
@click.pass_context
def approve(
    ctx: click.Context,
    sprint_id: str,
    phase_id: str | None,
    output_dir: str,
    auto_advance: bool,
) -> None:
    """
    Approve a phase completion and unblock the next phase.
    
    In sequential mode, phases complete but wait for explicit approval
    before the next phase can start. This command marks a phase as
    APPROVED, allowing the next phase to proceed.
    
    If PHASE_ID is not provided, approves the phase currently waiting
    for approval (if any).
    
    Examples:
        carby-sprint approve my-sprint phase_1_discover
        carby-sprint approve my-sprint  # Approves waiting phase
    """
    verbose: bool = ctx.obj.get("verbose", False)
    
    # Load sprint
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)
    
    # Check if sprint is in sequential mode
    execution_mode = sprint_data.get("execution_mode", "parallel")
    if execution_mode != "sequential":
        click.echo(f"⚠ Sprint '{sprint_id}' is not in sequential mode.")
        click.echo(f"  Current mode: {execution_mode}")
        click.echo(f"  Approval only needed for sequential execution.")
        return
    
    # Initialize Phase Lock
    lock = PhaseLock(output_dir, sprint_id)
    
    # If no phase_id provided, find the waiting phase
    if phase_id is None:
        waiting_phase = lock.get_waiting_phase()
        if waiting_phase:
            phase_id = waiting_phase
            if verbose:
                click.echo(f"Found waiting phase: {phase_id}")
        else:
            raise click.ClickException(
                f"No phase waiting for approval in sprint '{sprint_id}'.\n"
                f"All phases may be approved or none have completed yet."
            )
    
    # Validate phase_id
    if phase_id not in PhaseLock.PHASE_SEQUENCE:
        valid_phases = "\n  ".join(PhaseLock.PHASE_SEQUENCE)
        raise click.ClickException(
            f"Invalid phase_id: '{phase_id}'\n\n"
            f"Valid phases:\n  {valid_phases}"
        )
    
    # Check current phase state
    status = lock.get_status()
    current_state = status.get(phase_id)
    
    if current_state == PhaseLockState.APPROVED:
        click.echo(f"Phase '{phase_id}' is already approved.")
        return
    
    if current_state != PhaseLockState.COMPLETED:
        raise click.ClickException(
            f"Cannot approve phase '{phase_id}': not in COMPLETED state.\n"
            f"Current state: {current_state}\n"
            f"Phase must complete before it can be approved."
        )
    
    # Approve the phase
    lock.approve_phase(phase_id)
    
    # Show success message
    click.echo(f"\n{'='*60}")
    click.echo(f"✓ PHASE APPROVED: {phase_id}")
    click.echo(f"{'='*60}")
    
    # Show phase summary if available
    summary = status.get(f"{phase_id}_summary", "")
    if summary:
        click.echo(f"Summary: {summary}")
    
    completed_at = status.get(f"{phase_id}_completed_at", "")
    if completed_at:
        click.echo(f"Completed: {completed_at}")
    
    # Show next phase
    current_phase = lock.get_current_phase()
    if current_phase:
        click.echo(f"\nNext phase ready: {current_phase}")
        
        if auto_advance:
            click.echo(f"\nAuto-advancing to next phase...")
            # Import here to avoid circular dependency
            from .start import start
            # Invoke start command to spawn next phase
            ctx.invoke(start, sprint_id=sprint_id, mode="sequential")
        else:
            click.echo(f"\nTo start the next phase, run:")
            click.echo(f"  carby-sprint start {sprint_id} --mode sequential")
    else:
        click.echo(f"\n🎉 All phases complete! Sprint is finished.")
    
    click.echo(f"{'='*60}\n")
