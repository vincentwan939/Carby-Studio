"""
Start a sprint.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import click


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


def save_sprint(sprint_data: dict[str, Any], sprint_path: Path) -> None:
    """Save sprint metadata."""
    metadata_path: Path = sprint_path / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(sprint_data, f, indent=2)


@click.command()
@click.argument("sprint_id")
@click.option(
    "--max-parallel",
    "-p",
    default=3,
    type=int,
    help="Maximum parallel work items (default: 3)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Simulate start without making changes",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.pass_context
def start(
    ctx: click.Context,
    sprint_id: str,
    max_parallel: int,
    dry_run: bool,
    output_dir: str,
) -> None:
    """
    Start the given SPRINT_ID.

    Validates gates are passed and begins execution of work items.
    """
    verbose: bool = ctx.obj.get("verbose", False)

    # Load sprint
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    # Check if sprint can be started
    if sprint_data["status"] == "running":
        raise click.ClickException(f"Sprint '{sprint_id}' is already running.")

    if sprint_data["status"] in ["completed", "cancelled", "archived"]:
        raise click.ClickException(
            f"Sprint '{sprint_id}' is {sprint_data['status']} and cannot be started."
        )

    # Check required gates
    gates: dict[str, dict[str, Any]] = sprint_data.get("gates", {})
    required_gates: list[str] = ["1", "2"]  # Planning and Design gates required to start
    blocked_gates: list[str] = []

    for gate_num in required_gates:
        gate_info: dict[str, Any] = gates.get(gate_num, {})
        if gate_info.get("status") != "passed":
            blocked_gates.append(f"Gate {gate_num} ({gate_info.get('name', 'Unknown')})")

    if blocked_gates:
        raise click.ClickException(
            f"Cannot start sprint. Required gates not passed:\n  " +
            "\n  ".join(blocked_gates) +
            f"\n\nRun 'carby-sprint gate {sprint_id} <gate-number>' to pass gates."
        )

    # Check if there are work items
    work_items: list[str] = sprint_data.get("work_items", [])
    if not work_items:
        raise click.ClickException(
            f"No work items planned. Run 'carby-sprint plan {sprint_id} --work-items <items>' first."
        )

    if dry_run:
        click.echo(f"[DRY RUN] Would start sprint '{sprint_id}'")
        click.echo(f"  Max parallel: {max_parallel}")
        click.echo(f"  Work items: {len(work_items)}")
        return

    # Update sprint status
    sprint_data["status"] = "running"
    sprint_data["started_at"] = datetime.now().isoformat()
    sprint_data["max_parallel"] = max_parallel
    sprint_data["execution"] = {
        "in_progress": [],
        "completed": [],
        "blocked": [],
        "failed": [],
    }

    save_sprint(sprint_data, sprint_path)

    # Create execution lock file for parallel coordination
    lock_file: Path = sprint_path / ".execution.lock"
    lock_data: dict[str, Any] = {
        "sprint_id": sprint_id,
        "started_at": sprint_data["started_at"],
        "max_parallel": max_parallel,
        "active_slots": [],
    }
    with open(lock_file, "w") as f:
        json.dump(lock_data, f, indent=2)

    if verbose:
        click.echo(f"Created execution lock: {lock_file}")

    click.echo(f"✓ Sprint '{sprint_id}' started successfully")
    click.echo(f"  Status: running")
    click.echo(f"  Max parallel: {max_parallel}")
    click.echo(f"  Work items: {len(work_items)}")
    click.echo(f"  Started at: {sprint_data['started_at']}")
    click.echo(f"\nMonitor with:")
    click.echo(f"  carby-sprint status {sprint_id} --watch")
