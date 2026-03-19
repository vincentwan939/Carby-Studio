"""
Start a sprint.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from ..sprint_repository import SprintRepository, SprintPaths


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


def spawn_agent(
    agent_type: str,
    sprint_id: str,
    gate: int,
    work_item_id: str | None = None,
    validation_token: str | None = None,
    carby_studio_path: Path | None = None,
) -> subprocess.Popen:
    """
    Spawn an agent process for sprint execution.
    
    Args:
        agent_type: Type of agent (discover, design, build, verify, deliver)
        sprint_id: Sprint identifier
        gate: Current gate number
        work_item_id: Optional work item ID for build agents
        validation_token: Optional validation token
        carby_studio_path: Path to carby-studio skill directory
        
    Returns:
        Subprocess.Popen object for the spawned agent
    """
    if carby_studio_path is None:
        # Auto-detect carby-studio path
        carby_studio_path = Path(__file__).parent.parent.parent.resolve()
    
    bridge_script = carby_studio_path / "scripts" / "sprint-agent-bridge.py"
    
    cmd = [
        sys.executable,
        str(bridge_script),
        "--agent", agent_type,
        "--sprint-id", sprint_id,
        "--gate", str(gate),
    ]
    
    if validation_token:
        cmd.extend(["--validation-token", validation_token])
    
    # Generate the prompt and pass it to a subagent via sessions_spawn
    # We'll use openclaw's sessions_spawn via a wrapper script
    env = {
        **dict(subprocess.os.environ),
        "CARBY_STUDIO_PATH": str(carby_studio_path),
        "SPRINT_ID": sprint_id,
    }
    
    # Run the bridge to get the processed prompt, then spawn agent
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    
    processed_prompt = result.stdout
    
    # Create a temporary file for the prompt
    logs_dir = carby_studio_path / ".carby-sprints" / sprint_id / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    prompt_file = logs_dir / f"agent_{agent_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.prompt"
    prompt_file.write_text(processed_prompt)
    
    # Spawn the agent using openclaw sessions_spawn
    # We use a wrapper that calls the actual agent with the prompt
    agent_script = carby_studio_path / "scripts" / "spawn-sprint-agent.sh"
    
    if agent_script.exists():
        agent_cmd = [
            "bash",
            str(agent_script),
            agent_type,
            sprint_id,
            str(gate),
            str(prompt_file),
        ]
        if work_item_id:
            agent_cmd.append(work_item_id)
    else:
        # Fallback: use Python to spawn via openclaw CLI
        agent_cmd = [
            sys.executable,
            "-c",
            f"""
import subprocess
import sys

# Read the processed prompt
prompt = open('{prompt_file}').read()

# Spawn subagent using openclaw CLI
result = subprocess.run(
    [
        "openclaw", "sessions", "spawn",
        "--task", prompt,
        "--runtime", "subagent",
        "--mode", "run",
        "--label", f"sprint-{sprint_id}-{agent_type}",
    ],
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)
"""
        ]
    
    process = subprocess.Popen(
        agent_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    
    return process


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

    # Update sprint status to in_progress
    sprint_data["status"] = "in_progress"
    save_sprint(sprint_data, sprint_path)

    if verbose:
        click.echo(f"Updated sprint status: in_progress")

    # Determine which agent to spawn based on sprint state
    repo = SprintRepository(output_dir)
    paths = repo.get_paths(sprint_id)
    
    # Check if work items exist
    work_item_files = list(paths.work_items.glob("*.json")) if paths.work_items.exists() else []
    
    spawned_processes: list[tuple[str, subprocess.Popen]] = []
    
    if not work_item_files:
        # No work items: spawn Discover agent (Gate 1)
        if verbose:
            click.echo(f"No work items found. Spawning Discover agent for Gate 1...")
        
        try:
            process = spawn_agent(
                agent_type="discover",
                sprint_id=sprint_id,
                gate=1,
                validation_token=sprint_data.get("validation_token"),
                carby_studio_path=Path(output_dir).parent.parent if output_dir != ".carby-sprints" else None,
            )
            spawned_processes.append(("discover", process))
            click.echo(f"✓ Spawned Discover agent for sprint '{sprint_id}'")
        except Exception as e:
            click.echo(f"⚠ Failed to spawn Discover agent: {e}", err=True)
    else:
        # Work items exist: spawn Build agents for each
        if verbose:
            click.echo(f"Found {len(work_item_files)} work items. Spawning Build agents...")
        
        for wi_file in work_item_files[:max_parallel]:  # Respect max_parallel
            try:
                work_item = json.loads(wi_file.read_text())
                wi_id = work_item.get("id", wi_file.stem)
                
                # Skip already completed work items
                if work_item.get("status") == "completed":
                    if verbose:
                        click.echo(f"  Skipping completed work item: {wi_id}")
                    continue
                
                process = spawn_agent(
                    agent_type="build",
                    sprint_id=sprint_id,
                    gate=3,
                    work_item_id=wi_id,
                    validation_token=work_item.get("validation_token") or sprint_data.get("validation_token"),
                    carby_studio_path=Path(output_dir).parent.parent if output_dir != ".carby-sprints" else None,
                )
                spawned_processes.append((f"build-{wi_id}", process))
                
                # Update work item status
                work_item["status"] = "in_progress"
                work_item["started_at"] = datetime.now().isoformat()
                repo.save_work_item(paths, work_item)
                
                click.echo(f"✓ Spawned Build agent for work item: {wi_id}")
                
            except Exception as e:
                click.echo(f"⚠ Failed to spawn Build agent for {wi_file.stem}: {e}", err=True)

    # Log spawned processes
    if spawned_processes:
        execution_log = paths.logs / "execution.log"
        with open(execution_log, "a") as f:
            f.write(f"\n[{datetime.now().isoformat()}] Sprint started\n")
            for name, proc in spawned_processes:
                f.write(f"  Spawned {name} (PID: {proc.pid})\n")

    click.echo(f"\n✓ Sprint '{sprint_id}' started successfully")
    click.echo(f"  Status: in_progress")
    click.echo(f"  Max parallel: {max_parallel}")
    click.echo(f"  Work items: {len(work_items)}")
    click.echo(f"  Agents spawned: {len(spawned_processes)}")
    click.echo(f"  Started at: {sprint_data['started_at']}")
    click.echo(f"\nMonitor with:")
    click.echo(f"  carby-sprint status {sprint_id} --watch")
