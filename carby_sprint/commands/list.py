"""List sprints command."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click


def get_sprint_path(sprint_id: str, output_dir: str = ".carby-sprints") -> Path:
    """Get the path to a sprint directory."""
    return Path(output_dir) / sprint_id


def load_sprint_metadata(sprint_path: Path) -> dict[str, Any] | None:
    """Load sprint metadata from a directory."""
    metadata_path = sprint_path / "metadata.json"
    if not metadata_path.exists():
        return None
    try:
        with open(metadata_path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def get_gate_status(sprint_data: dict[str, Any]) -> str:
    """Get the current gate status for display."""
    gates = sprint_data.get("gates", {})
    if not gates:
        return "No gates"

    # Find the highest passed gate
    passed_gates = [
        int(g) for g, info in gates.items()
        if info.get("status") == "passed"
    ]

    if passed_gates:
        current_gate = max(passed_gates) + 1
        return f"Gate {current_gate}"
    else:
        return "Gate 1"


@click.command()
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.option(
    "--all",
    "-a",
    is_flag=True,
    help="Show all sprints including archived",
)
def list_sprints(output_dir: str, all: bool) -> None:
    """List all sprints in the .carby-sprints directory."""
    output_path = Path(output_dir)

    if not output_path.exists():
        click.echo(f"No sprints directory found at '{output_dir}'")
        return

    sprint_dirs = [d for d in output_path.iterdir() if d.is_dir()]

    if not sprint_dirs:
        click.echo(f"No sprints found in '{output_dir}'")
        return

    # Load all sprint metadata
    sprints = []
    for sprint_dir in sorted(sprint_dirs):
        metadata = load_sprint_metadata(sprint_dir)
        if metadata:
            sprints.append((sprint_dir.name, metadata))

    if not sprints:
        click.echo(f"No valid sprints found in '{output_dir}'")
        return

    # Filter out archived unless --all
    if not all:
        sprints = [
            (name, data) for name, data in sprints
            if data.get("status") != "archived"
        ]

    if not sprints:
        click.echo("No active sprints (use --all to see archived)")
        return

    # Print header
    click.echo(f"\n{'Sprint ID':<20} {'Status':<12} {'Current Gate':<14} {'Project':<20}")
    click.echo("-" * 70)

    # Print each sprint
    for sprint_id, sprint_data in sprints:
        status = sprint_data.get("status", "unknown")
        project = sprint_data.get("project", "N/A")
        gate_status = get_gate_status(sprint_data)

        click.echo(f"{sprint_id:<20} {status:<12} {gate_status:<14} {project:<20}")

    click.echo()
    click.echo(f"Total: {len(sprints)} sprint(s)")
