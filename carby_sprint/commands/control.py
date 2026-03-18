"""
Control commands: pause, resume, cancel, archive.
"""

from __future__ import annotations

import json
import shutil
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
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.pass_context
def pause(ctx: click.Context, sprint_id: str, output_dir: str) -> None:
    """
    Pause the given SPRINT_ID.

    Temporarily halts sprint execution. Can be resumed later.
    """
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    if sprint_data["status"] != "running":
        raise click.ClickException(
            f"Cannot pause sprint with status '{sprint_data['status']}'. Must be 'running'.")

    sprint_data["status"] = "paused"
    sprint_data["paused_at"] = datetime.now().isoformat()

    save_sprint(sprint_data, sprint_path)

    click.echo(f"✓ Sprint '{sprint_id}' paused")
    click.echo(f"  Paused at: {sprint_data['paused_at']}")
    click.echo(f"\nResume with: carby-sprint resume {sprint_id}")


@click.command()
@click.argument("sprint_id")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.pass_context
def resume(ctx: click.Context, sprint_id: str, output_dir: str) -> None:
    """
    Resume the given SPRINT_ID.

    Continues sprint execution after being paused.
    """
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    if sprint_data["status"] != "paused":
        raise click.ClickException(
            f"Cannot resume sprint with status '{sprint_data['status']}'. Must be 'paused'.")

    sprint_data["status"] = "running"
    sprint_data["resumed_at"] = datetime.now().isoformat()

    # Track total paused time
    if sprint_data.get("paused_at"):
        paused_duration = datetime.now() - datetime.fromisoformat(sprint_data["paused_at"])
        sprint_data["total_paused_seconds"] = sprint_data.get("total_paused_seconds", 0) + paused_duration.total_seconds()

    save_sprint(sprint_data, sprint_path)

    click.echo(f"✓ Sprint '{sprint_id}' resumed")
    click.echo(f"  Resumed at: {sprint_data['resumed_at']}")


@click.command()
@click.argument("sprint_id")
@click.option(
    "--reason",
    "-r",
    default="",
    help="Reason for cancellation",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.pass_context
def cancel(ctx: click.Context, sprint_id: str, reason: str, output_dir: str) -> None:
    """
    Cancel the given SPRINT_ID.

    Permanently stops the sprint. Cannot be resumed.
    """
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    if sprint_data["status"] in ["cancelled", "archived"]:
        raise click.ClickException(f"Sprint '{sprint_id}' is already {sprint_data['status']}.")

    sprint_data["status"] = "cancelled"
    sprint_data["cancelled_at"] = datetime.now().isoformat()
    sprint_data["cancellation_reason"] = reason or "No reason provided"

    save_sprint(sprint_data, sprint_path)

    click.echo(f"✓ Sprint '{sprint_id}' cancelled")
    click.echo(f"  Cancelled at: {sprint_data['cancelled_at']}")
    if reason:
        click.echo(f"  Reason: {reason}")
    click.echo(f"\nArchive with: carby-sprint archive {sprint_id}")


@click.command()
@click.argument("sprint_id")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.option(
    "--archive-dir",
    "-a",
    type=click.Path(),
    default=".carby-sprints/archive",
    help="Archive directory",
)
@click.pass_context
def archive(ctx: click.Context, sprint_id: str, output_dir: str, archive_dir: str) -> None:
    """
    Archive the given SPRINT_ID.

    Moves sprint data to archive directory.
    """
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    if sprint_data["status"] not in ["completed", "cancelled"]:
        click.confirm(
            f"Sprint '{sprint_id}' is '{sprint_data['status']}'. Archive anyway?",
            abort=True
        )

    # Create archive directory
    archive_path: Path = Path(archive_dir)
    archive_path.mkdir(parents=True, exist_ok=True)

    # Move sprint to archive
    dest_path: Path = archive_path / sprint_id
    if dest_path.exists():
        raise click.ClickException(f"Archive destination '{dest_path}' already exists.")

    shutil.move(str(sprint_path), str(dest_path))

    # Update status
    sprint_data["status"] = "archived"
    sprint_data["archived_at"] = datetime.now().isoformat()

    metadata_path: Path = dest_path / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(sprint_data, f, indent=2)

    click.echo(f"✓ Sprint '{sprint_id}' archived")
    click.echo(f"  Archived at: {sprint_data['archived_at']}")
    click.echo(f"  Location: {dest_path}")
