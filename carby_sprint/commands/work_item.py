"""
Work item management commands.
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


def load_work_item(sprint_path: Path, work_item_id: str) -> dict[str, Any]:
    """Load a work item."""
    wi_path: Path = sprint_path / "work_items" / f"{work_item_id}.json"
    if not wi_path.exists():
        raise click.ClickException(f"Work item '{work_item_id}' not found.")

    with open(wi_path, "r") as f:
        data: dict[str, Any] = json.load(f)
        return data


def save_work_item(sprint_path: Path, work_item: dict[str, Any]) -> None:
    """Save a work item."""
    wi_path: Path = sprint_path / "work_items" / f"{work_item['id']}.json"
    with open(wi_path, "w") as f:
        json.dump(work_item, f, indent=2)


@click.group()
def work_item() -> None:
    """
    Manage work items within a sprint.

    Commands for adding, updating, and tracking work items.
    """
    pass


@work_item.command("add")
@click.argument("sprint_id")
@click.option(
    "--title",
    "-t",
    required=True,
    help="Work item title",
)
@click.option(
    "--description",
    "-d",
    default="",
    help="Work item description",
)
@click.option(
    "--priority",
    "-p",
    type=click.Choice(["low", "medium", "high", "critical"]),
    default="medium",
    help="Work item priority",
)
@click.option(
    "--estimated-hours",
    "-e",
    type=int,
    help="Estimated hours",
)
@click.option(
    "--assignee",
    "-a",
    help="Assigned person",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
def add(
    sprint_id: str,
    title: str,
    description: str,
    priority: str,
    estimated_hours: int | None,
    assignee: str | None,
    output_dir: str,
) -> None:
    """Add a new work item to the sprint."""
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    # Generate work item ID
    existing_items: list[str] = sprint_data.get("work_items", [])
    next_num: int = len(existing_items) + 1
    work_item_id: str = f"WI-{next_num}"

    # Create work item
    work_item: dict[str, Any] = {
        "id": work_item_id,
        "title": title,
        "description": description,
        "status": "planned",
        "priority": priority,
        "estimated_hours": estimated_hours,
        "assignee": assignee,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    # Save work item
    save_work_item(sprint_path, work_item)

    # Update sprint metadata
    sprint_data["work_items"] = existing_items + [work_item_id]
    sprint_data["work_item_count"] = len(sprint_data["work_items"])
    save_sprint(sprint_data, sprint_path)

    click.echo(f"✓ Work item added to sprint '{sprint_id}'")
    click.echo(f"  ID: {work_item_id}")
    click.echo(f"  Title: {title}")
    click.echo(f"  Priority: {priority}")


@work_item.command("update")
@click.argument("sprint_id")
@click.argument("work_item_id")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["planned", "in_progress", "completed", "blocked", "failed"]),
    help="Update status",
)
@click.option(
    "--title",
    "-t",
    help="Update title",
)
@click.option(
    "--description",
    "-d",
    help="Update description",
)
@click.option(
    "--priority",
    "-p",
    type=click.Choice(["low", "medium", "high", "critical"]),
    help="Update priority",
)
@click.option(
    "--assignee",
    "-a",
    help="Update assignee",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
def update(
    sprint_id: str,
    work_item_id: str,
    status: str | None,
    title: str | None,
    description: str | None,
    priority: str | None,
    assignee: str | None,
    output_dir: str,
) -> None:
    """Update a work item."""
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)
    work_item = load_work_item(sprint_path, work_item_id)

    # Update fields
    if status:
        work_item["status"] = status
        if status == "in_progress" and not work_item.get("started_at"):
            work_item["started_at"] = datetime.now().isoformat()
        if status in ["completed", "failed"]:
            work_item["completed_at"] = datetime.now().isoformat()

    if title:
        work_item["title"] = title
    if description:
        work_item["description"] = description
    if priority:
        work_item["priority"] = priority
    if assignee:
        work_item["assignee"] = assignee

    work_item["updated_at"] = datetime.now().isoformat()

    # Save work item
    save_work_item(sprint_path, work_item)

    # Update execution tracking
    execution: dict[str, list[str]] = sprint_data.get("execution", {})
    if status:
        # Remove from old status lists
        for key in ["in_progress", "completed", "blocked", "failed"]:
            if work_item_id in execution.get(key, []):
                execution[key].remove(work_item_id)

        # Add to new status list
        if status == "in_progress":
            execution.setdefault("in_progress", []).append(work_item_id)
        elif status == "completed":
            execution.setdefault("completed", []).append(work_item_id)
        elif status == "blocked":
            execution.setdefault("blocked", []).append(work_item_id)
        elif status == "failed":
            execution.setdefault("failed", []).append(work_item_id)

        sprint_data["execution"] = execution
        save_sprint(sprint_data, sprint_path)

    click.echo(f"✓ Work item '{work_item_id}' updated")
    click.echo(f"  Status: {work_item['status']}")


@work_item.command("list")
@click.argument("sprint_id")
@click.option(
    "--status",
    "-s",
    type=click.Choice(["planned", "in_progress", "completed", "blocked", "failed"]),
    help="Filter by status",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
def list_items(sprint_id: str, status: str | None, output_dir: str) -> None:
    """List work items in the sprint."""
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    work_items: list[str] = sprint_data.get("work_items", [])
    if not work_items:
        click.echo(f"No work items in sprint '{sprint_id}'")
        return

    click.echo(f"\nWork items for sprint '{sprint_id}':")
    click.echo("-" * 60)

    for wi_id in work_items:
        try:
            wi: dict[str, Any] = load_work_item(sprint_path, wi_id)
            if status and wi.get("status") != status:
                continue

            status_val: str | None = wi.get("status")
            status_icon: str = {
                "planned": "📋",
                "in_progress": "🔄",
                "completed": "✅",
                "blocked": "🚫",
                "failed": "❌",
            }.get(status_val or "", "❓")

            priority_val: str | None = wi.get("priority")
            priority_icon: str = {
                "low": "🔵",
                "medium": "🟡",
                "high": "🟠",
                "critical": "🔴",
            }.get(priority_val or "", "⚪")

            title_val2: str = wi.get('title', 'Untitled')
            priority_val2: str = wi.get('priority', 'none')
            status_val2: str = wi.get('status', 'unknown')
            
            click.echo(f"{status_icon} {wi_id}: {title_val2}")
            click.echo(f"   Priority: {priority_icon} {priority_val2}")
            click.echo(f"   Status: {status_val2}")
            if wi.get("assignee"):
                click.echo(f"   Assignee: {wi['assignee']}")
            if wi.get("estimated_hours"):
                click.echo(f"   Est. Hours: {wi['estimated_hours']}")
            click.echo()
        except click.ClickException:
            click.echo(f"❓ {wi_id}: (file missing)")


@work_item.command("show")
@click.argument("sprint_id")
@click.argument("work_item_id")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
def show(sprint_id: str, work_item_id: str, output_dir: str) -> None:
    """Show detailed information about a work item."""
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)
    work_item = load_work_item(sprint_path, work_item_id)

    click.echo(f"\nWork Item: {work_item_id}")
    click.echo("=" * 60)
    click.echo(f"Title: {work_item.get('title', 'Untitled')}")
    click.echo(f"Status: {work_item.get('status', 'unknown')}")
    click.echo(f"Priority: {work_item.get('priority', 'none')}")

    if work_item.get("description"):
        click.echo(f"\nDescription:\n{work_item['description']}")

    if work_item.get("assignee"):
        click.echo(f"\nAssignee: {work_item['assignee']}")

    if work_item.get("estimated_hours"):
        click.echo(f"Estimated Hours: {work_item['estimated_hours']}")

    click.echo(f"\nCreated: {work_item.get('created_at', 'unknown')}")
    click.echo(f"Updated: {work_item.get('updated_at', 'unknown')}")

    if work_item.get("started_at"):
        click.echo(f"Started: {work_item['started_at']}")
    if work_item.get("completed_at"):
        click.echo(f"Completed: {work_item['completed_at']}")
