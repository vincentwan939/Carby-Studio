"""
Initialize a new sprint.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import click


@click.command()
@click.argument("sprint_id")
@click.option(
    "--project",
    "-p",
    required=True,
    help="Project identifier",
)
@click.option(
    "--goal",
    "-g",
    required=True,
    help="Sprint goal description",
)
@click.option(
    "--description",
    "-d",
    default="",
    help="Additional sprint description",
)
@click.option(
    "--start-date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Sprint start date (YYYY-MM-DD)",
)
@click.option(
    "--duration",
    default=14,
    type=int,
    help="Sprint duration in days (default: 14)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Output directory for sprint data",
)
@click.pass_context
def init(
    ctx: click.Context,
    sprint_id: str,
    project: str,
    goal: str,
    description: str,
    start_date: datetime | None,
    duration: int,
    output_dir: str,
) -> None:
    """
    Initialize a new sprint with the given SPRINT_ID.

    Creates sprint configuration and metadata files.
    """
    verbose: bool = ctx.obj.get("verbose", False)

    # Calculate dates
    start: datetime = start_date or datetime.now()
    end: datetime = start + timedelta(days=duration)

    # Create sprint data structure
    sprint_data: dict[str, Any] = {
        "sprint_id": sprint_id,
        "project": project,
        "goal": goal,
        "description": description,
        "status": "initialized",
        "created_at": datetime.now().isoformat(),
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "duration_days": duration,
        "work_items": [],
        "gates": {
            "1": {"status": "pending", "name": "Planning Gate"},
            "2": {"status": "pending", "name": "Design Gate"},
            "3": {"status": "pending", "name": "Implementation Gate"},
            "4": {"status": "pending", "name": "Validation Gate"},
            "5": {"status": "pending", "name": "Release Gate"},
        },
        "validation_token": None,
        "risk_score": None,
    }

    # Ensure output directory exists
    sprints_dir: Path = Path(output_dir)
    sprints_dir.mkdir(parents=True, exist_ok=True)

    sprint_dir: Path = sprints_dir / sprint_id
    if sprint_dir.exists():
        click.echo(f"Error: Sprint '{sprint_id}' already exists.", err=True)
        raise click.Abort()

    sprint_dir.mkdir(parents=True)

    # Write sprint metadata
    metadata_path: Path = sprint_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(sprint_data, f, indent=2)

    # Create subdirectories
    (sprint_dir / "work_items").mkdir()
    (sprint_dir / "gates").mkdir()
    (sprint_dir / "logs").mkdir()

    if verbose:
        click.echo(f"Created sprint directory: {sprint_dir}")

    click.echo(f"✓ Sprint '{sprint_id}' initialized successfully")
    click.echo(f"  Project: {project}")
    click.echo(f"  Goal: {goal}")
    click.echo(f"  Duration: {duration} days ({start.strftime('%Y-%m-%d')} to {end.strftime('%Y-%m-%d')})")
    click.echo(f"  Status: initialized")
    click.echo(f"\nNext steps:")
    click.echo(f"  carby-sprint plan {sprint_id} --work-items <items>")
