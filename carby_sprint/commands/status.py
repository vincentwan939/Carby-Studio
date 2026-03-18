"""
Check sprint status.
"""

from __future__ import annotations

import json
import time
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


def format_duration(start_iso: str, end_iso: str | None = None) -> str:
    """Format duration between two timestamps."""
    start: datetime = datetime.fromisoformat(start_iso)
    end: datetime = datetime.fromisoformat(end_iso) if end_iso else datetime.now()
    duration = end - start
    days: int = duration.days
    hours: int
    remainder: int
    hours, remainder = divmod(duration.seconds, 3600)
    minutes: int
    minutes, _ = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def get_work_item_status(sprint_path: Path, work_item_id: str) -> dict[str, Any]:
    """Get detailed status of a work item."""
    wi_path: Path = sprint_path / "work_items" / f"{work_item_id}.json"
    if not wi_path.exists():
        return {"id": work_item_id, "status": "unknown", "title": "Unknown"}

    with open(wi_path, "r") as f:
        data: dict[str, Any] = json.load(f)
        return data


@click.command()
@click.argument("sprint_id")
@click.option(
    "--watch",
    "-w",
    is_flag=True,
    help="Watch status continuously (refresh every 2 seconds)",
)
@click.option(
    "--refresh",
    "-r",
    default=2,
    type=int,
    help="Refresh interval in seconds (default: 2)",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.pass_context
def status(
    ctx: click.Context,
    sprint_id: str,
    watch: bool,
    refresh: int,
    output_dir: str,
) -> None:
    """
    Check status of the given SPRINT_ID.

    Displays current sprint status, gate progress, and work item states.
    """
    verbose: bool = ctx.obj.get("verbose", False)

    def display_status() -> None:
        # Load sprint
        sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

        # Clear screen for watch mode
        if watch:
            click.clear()

        # Header
        click.echo(f"{'=' * 60}")
        click.echo(f"Sprint: {sprint_data['sprint_id']}")
        click.echo(f"{'=' * 60}")

        # Basic info
        click.echo(f"\n📋 General")
        click.echo(f"  Project: {sprint_data['project']}")
        click.echo(f"  Goal: {sprint_data['goal']}")
        click.echo(f"  Status: {sprint_data['status'].upper()}")

        if sprint_data.get("created_at"):
            click.echo(f"  Created: {sprint_data['created_at'][:10]}")

        # Timeline
        click.echo(f"\n📅 Timeline")
        click.echo(f"  Start: {sprint_data.get('start_date', 'N/A')}")
        click.echo(f"  End: {sprint_data.get('end_date', 'N/A')}")
        click.echo(f"  Duration: {sprint_data.get('duration_days', 'N/A')} days")

        if sprint_data.get("started_at"):
            elapsed: str = format_duration(sprint_data["started_at"])
            click.echo(f"  Elapsed: {elapsed}")

        # Gates
        click.echo(f"\n🚪 Gates")
        gates: dict[str, dict[str, Any]] = sprint_data.get("gates", {})
        for gate_num in sorted(gates.keys(), key=int):
            gate: dict[str, Any] = gates[gate_num]
            gate_status: str | None = gate.get("status")
            gate_name: str = gate.get('name', 'Unknown')
            gate_status_display: str = gate.get('status', 'unknown')
            
            status_icon: str = {
                "pending": "⏳",
                "in_progress": "🔄",
                "passed": "✅",
                "failed": "❌",
                "blocked": "🚫",
            }.get(gate_status or "", "❓")
            click.echo(f"  {status_icon} Gate {gate_num}: {gate_name} [{gate_status_display}]")

        # Work items
        click.echo(f"\n📦 Work Items")
        work_items: list[str] = sprint_data.get("work_items", [])
        if not work_items:
            click.echo("  No work items planned")
        else:
            status_counts: dict[str, int] = {}
            for wi_id in work_items:
                wi: dict[str, Any] = get_work_item_status(sprint_path, wi_id)
                status_val: str = wi.get("status", "unknown")
                status_counts[status_val] = status_counts.get(status_val, 0) + 1

            click.echo(f"  Total: {len(work_items)}")
            for status_val, count in sorted(status_counts.items()):
                icon: str = {
                    "planned": "📋",
                    "in_progress": "🔄",
                    "completed": "✅",
                    "blocked": "🚫",
                    "failed": "❌",
                }.get(status_val, "❓")
                click.echo(f"    {icon} {status_val}: {count}")

        # Execution details
        execution: dict[str, Any] | None = sprint_data.get("execution")
        if execution:
            click.echo(f"\n⚙️  Execution")
            click.echo(f"  Max parallel: {sprint_data.get('max_parallel', 'N/A')}")
            click.echo(f"  In progress: {len(execution.get('in_progress', []))}")
            click.echo(f"  Completed: {len(execution.get('completed', []))}")
            click.echo(f"  Failed: {len(execution.get('failed', []))}")

        # Validation
        if sprint_data.get("validation_token"):
            click.echo(f"\n🔐 Validation")
            click.echo(f"  Token: {sprint_data['validation_token']}")
            if sprint_data.get("risk_score") is not None:
                click.echo(f"  Risk Score: {sprint_data['risk_score']}")

        # Footer
        click.echo(f"\n{'=' * 60}")
        if watch:
            click.echo(f"Refreshing every {refresh}s (Ctrl+C to exit)")

    # Initial display
    display_status()

    # Watch mode
    if watch:
        try:
            while True:
                time.sleep(refresh)
                display_status()
        except KeyboardInterrupt:
            click.echo("\n\nStopped watching.")
