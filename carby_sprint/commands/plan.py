"""
Plan sprint work items.
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
    "--work-items",
    "-w",
    required=True,
    help="Comma-separated list of work item IDs",
)
@click.option(
    "--from-file",
    "-f",
    type=click.Path(exists=True),
    help="Load work items from JSON file",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.pass_context
def plan(
    ctx: click.Context,
    sprint_id: str,
    work_items: str,
    from_file: str | None,
    output_dir: str,
) -> None:
    """
    Plan work items for the given SPRINT_ID.

    Associates work items with the sprint and prepares for execution.
    """
    verbose: bool = ctx.obj.get("verbose", False)

    # Load sprint
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    # Parse work items
    items: list[str] | list[dict[str, Any]]
    if from_file:
        with open(from_file, "r") as f:
            items_data: dict[str, Any] | list[Any] = json.load(f)
            if isinstance(items_data, list):
                items = items_data
            elif isinstance(items_data, dict) and "work_items" in items_data:
                items = items_data["work_items"]
            else:
                raise click.ClickException("Invalid work items file format.")
    else:
        items = [item.strip() for item in work_items.split(",")]

    # Create work item objects
    work_item_objects: list[dict[str, Any]] = []
    for i, item in enumerate(items, 1):
        wi: dict[str, Any]
        if isinstance(item, dict):
            wi = {
                "id": item.get("id", f"WI-{i}"),
                "title": item.get("title", f"Work Item {i}"),
                "description": item.get("description", ""),
                "status": "planned",
                "priority": item.get("priority", "medium"),
                "estimated_hours": item.get("estimated_hours"),
                "assignee": item.get("assignee"),
            }
        else:
            wi = {
                "id": f"WI-{i}",
                "title": item,
                "description": "",
                "status": "planned",
                "priority": "medium",
                "estimated_hours": None,
                "assignee": None,
            }
        work_item_objects.append(wi)

        # Create individual work item file
        wi_path: Path = sprint_path / "work_items" / f"{wi['id']}.json"
        with open(wi_path, "w") as f:
            json.dump(wi, f, indent=2)

    # Update sprint metadata
    sprint_data["work_items"] = [wi["id"] for wi in work_item_objects]
    sprint_data["status"] = "planned"
    sprint_data["planned_at"] = datetime.now().isoformat()
    sprint_data["work_item_count"] = len(work_item_objects)

    save_sprint(sprint_data, sprint_path)

    if verbose:
        click.echo(f"Created {len(work_item_objects)} work item files")

    click.echo(f"✓ Sprint '{sprint_id}' planned successfully")
    click.echo(f"  Work items: {len(work_item_objects)}")
    for wi in work_item_objects:
        click.echo(f"    - {wi['id']}: {wi['title']}")
    click.echo(f"\nNext steps:")
    click.echo(f"  carby-sprint gate {sprint_id} 1  # Pass planning gate")
