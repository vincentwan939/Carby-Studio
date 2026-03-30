"""
Start a sprint with Phase Lock integration for sequential execution.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click

from ..sprint_repository import SprintRepository, SprintPaths
from ..phase_lock import PhaseLock, PhaseLockState
from ..exceptions import PhaseBlockedError, GateValidationError, StateConsistencyError


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


def spawn_phase_agent(
    agent_type: str,
    sprint_id: str,
    gate: int,
    phase_id: str,
    work_item_id: str | None = None,
    validation_token: str | None = None,
    carby_studio_path: Path | None = None,
    sequential: bool = False,
    output_dir: str = ".carby-sprints",
) -> subprocess.Popen:
    """
    Spawn an agent process for sprint execution with Phase Lock enforcement.
    
    PHASE LOCK INTEGRATION:
    - If sequential mode is enabled, checks Phase Lock before spawning
    - Blocks if previous phase not approved
    - Marks phase as IN_PROGRESS on successful spawn
    
    Args:
        agent_type: Type of agent (discover, design, build, verify, deliver)
        sprint_id: Sprint identifier
        gate: Current gate number
        phase_id: Phase identifier for Phase Lock tracking
        work_item_id: Optional work item ID for build agents
        validation_token: Optional validation token
        carby_studio_path: Path to carby-studio skill directory
        sequential: Whether to enforce sequential phase execution
        output_dir: Directory containing sprint data
        
    Returns:
        Subprocess.Popen object for the spawned agent
        
    Raises:
        click.ClickException: If Phase Lock blocks this phase
    """
    import re

    # Validate sprint_id format before using in code string
    if not re.match(r'^[a-zA-Z0-9_-]+$', sprint_id):
        raise ValueError(f"Invalid sprint_id format: {sprint_id}")

    # Validate agent_type is in allowed list
    if agent_type not in ["discover", "design", "build", "verify", "deliver"]:
        raise ValueError(f"Invalid agent_type: {agent_type}")

    # PHASE LOCK HOOK: Check sequential enforcement before spawning
    if sequential:
        lock = PhaseLock(output_dir)
        
        can_start, error_msg = lock.can_start_phase(sprint_id, phase_id)
        if not can_start:
            waiting_phase = lock.get_waiting_phase()
            if waiting_phase:
                raise PhaseBlockedError(
                    phase_id=phase_id,
                    reason=f"{waiting_phase} is waiting for approval",
                    resolution=f"Run: carby-sprint approve {sprint_id} {waiting_phase}"
                )
            else:
                prev_idx = PhaseLock.PHASE_SEQUENCE.index(phase_id) - 1
                if prev_idx >= 0:
                    prev_phase = PhaseLock.PHASE_SEQUENCE[prev_idx]
                    raise PhaseBlockedError(
                        phase_id=phase_id,
                        reason=f"{prev_phase} not approved",
                        resolution=f"Run: carby-sprint approve {sprint_id} {prev_phase}"
                    )
        
        # Mark phase as in progress
        lock.start_phase(phase_id)
    
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
    
    # Run the bridge to get the processed prompt, then spawn agent
    # Set up environment for bridge script
    bridge_env = os.environ.copy()
    bridge_env["CARBY_STUDIO_PATH"] = str(carby_studio_path)
    bridge_env["SPRINT_ID"] = sprint_id
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=bridge_env,
        check=True,
        # SECURITY: Never use shell=True with user-provided input
        shell=False,
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
    
    # Set PYTHONPATH so spawned agent can access carby_sprint
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{carby_studio_path}:{env.get('PYTHONPATH', '')}"
    env["CARBY_STUDIO_PATH"] = str(carby_studio_path)
    env["SPRINT_ID"] = sprint_id
    
    # Pass sequential mode and phase info to spawned agent
    if sequential:
        env["PHASE_LOCK_ENABLED"] = "1"
        env["PHASE_ID"] = phase_id
    
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
        # SECURITY: Use a safer approach to avoid potential command injection
        agent_cmd = [
            sys.executable,
            "-c",
            f"""
import subprocess
import sys
import json

# Read the processed prompt safely
with open('{prompt_file}', 'r') as f:
    prompt = f.read()

# Escape special characters in sprint_id and agent_type to prevent command injection
sprint_id_safe = sprint_id.replace('"', '').replace("'", "")
agent_type_safe = agent_type.replace('"', '').replace("'", "")

# Spawn subagent using openclaw CLI with properly formatted arguments
result = subprocess.run([
    'openclaw', 'sessions', 'spawn',
    '--task', prompt,
    '--runtime', 'subagent',
    '--mode', 'run',
    '--label', f'sprint-{{sprint_id_safe}}-{{agent_type_safe}}',
], capture_output=True, text=True, shell=False)

print(result.stdout)
if result.returncode != 0:
    print(result.stderr, file=sys.stderr)
    sys.exit(result.returncode)
"""
        ]
    
    # SECURITY FIX: Use list-based command construction instead of shell=True
    # This prevents command injection by ensuring arguments are properly separated
    process = subprocess.Popen(
        agent_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        # SECURITY: Never use shell=True with user-provided input
        shell=False,
    )
    
    return process


def report_phase_completion(
    sprint_id: str,
    phase_id: str,
    summary: str,
    output_dir: str = ".carby-sprints",
) -> None:
    """
    Report phase completion and wait for user approval.
    
    PHASE LOCK INTEGRATION:
    - Marks phase as COMPLETED in Phase Lock
    - Displays approval instructions to user
    - Next phase blocked until approval given
    
    Args:
        sprint_id: Sprint identifier
        phase_id: Phase that completed
        summary: Summary of phase completion
        output_dir: Directory containing sprint data
    """
    lock = PhaseLock(output_dir)
    lock.complete_phase(sprint_id, phase_id, summary)
    
    # Display approval banner
    click.echo(f"\n{'='*60}")
    click.echo(f"PHASE COMPLETE: {phase_id}")
    click.echo(f"{'='*60}")
    click.echo(f"Summary: {summary}")
    click.echo(f"\nTo approve and continue to next phase:")
    click.echo(f"  carby-sprint approve {sprint_id} {phase_id}")
    click.echo(f"{'='*60}\n")


def get_phase_for_agent(agent_type: str) -> str:
    """
    Map agent type to phase ID for Phase Lock tracking.
    
    Args:
        agent_type: Type of agent (discover, design, build, verify, deliver)
        
    Returns:
        Phase ID string for Phase Lock
    """
    phase_map = {
        "discover": "phase_1_discover",
        "design": "phase_2_design",
        "build": "phase_3_build",
        "verify": "phase_4_verify",
        "deliver": "phase_5_deliver",
    }
    return phase_map.get(agent_type, "phase_1_discover")


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
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["parallel", "sequential"], case_sensitive=False),
    default="sequential",
    help="Execution mode: sequential (default) with Phase Lock or parallel",
)
@click.pass_context
def start(
    ctx: click.Context,
    sprint_id: str,
    max_parallel: int,
    dry_run: bool,
    output_dir: str,
    mode: str,
) -> None:
    """
    Start the given SPRINT_ID.

    Validates gates are passed and begins execution of work items.
    
    In sequential mode (--mode sequential), agents run one phase at a time
    with explicit approval required before advancing to the next phase.
    """
    verbose: bool = ctx.obj.get("verbose", False)
    sequential: bool = mode.lower() == "sequential"

    # Load sprint
    sprint_data, sprint_path = load_sprint(sprint_id, output_dir)

    # Check if sprint can be started
    if sprint_data["status"] == "running":
        raise StateConsistencyError(f"Sprint '{sprint_id}' is already running.")

    if sprint_data["status"] in ["completed", "cancelled", "archived"]:
        raise StateConsistencyError(
            f"Sprint '{sprint_id}' is {sprint_data['status']} and cannot be started."
        )

    # Check required gates with progress indicator
    click.echo("")
    with click.progressbar(length=3, label='Validating prerequisites') as bar:
        # Step 1: Validate gate requirements
        bar.update(1)
        gates: dict[str, dict[str, Any]] = sprint_data.get("gates", {})
        required_gates: list[str] = ["1", "2"]  # Planning and Design gates required to start
        blocked_gates: list[str] = []

        for gate_num in required_gates:
            gate_info: dict[str, Any] = gates.get(gate_num, {})
            if gate_info.get("status") != "passed":
                blocked_gates.append(f"Gate {gate_num} ({gate_info.get('name', 'Unknown')})")

        if blocked_gates:
            raise GateValidationError(
                gate_id=", ".join(blocked_gates),
                sprint_id=sprint_id,
                details=f"Required gates not passed. Run 'carby-sprint gate {sprint_id} <gate-number>' to pass gates."
            )

        # Step 2: Check phase lock (if sequential mode)
        bar.update(1)
        if sequential:
            lock = PhaseLock(output_dir)
            waiting_phase = lock.get_waiting_phase(sprint_id)
            if waiting_phase:
                click.echo(f"\n⚠ Phase '{waiting_phase}' is waiting for approval.")
                click.echo(f"Run: carby-sprint approve {sprint_id} {waiting_phase}")
                return

        # Step 3: Validate work items exist
        bar.update(1)
        work_items_check: list[str] = sprint_data.get("work_items", [])
        if not work_items_check:
            raise StateConsistencyError(
                f"No work items planned. Run 'carby-sprint plan {sprint_id} --work-items <items>' first."
            )

    # Check if there are work items (for dry-run and other paths)
    work_items: list[str] = sprint_data.get("work_items", [])
    if not work_items:
        raise StateConsistencyError(
            f"No work items planned. Run 'carby-sprint plan {sprint_id} --work-items <items>' first."
        )

    if dry_run:
        click.echo(f"[DRY RUN] Would start sprint '{sprint_id}'")
        click.echo(f"  Mode: {mode}")
        click.echo(f"  Max parallel: {max_parallel}")
        click.echo(f"  Work items: {len(work_items)}")
        if sequential:
            click.echo(f"  Phase Lock: ENABLED (sequential execution)")
        return

    # Update sprint status
    sprint_data["status"] = "running"
    sprint_data["started_at"] = datetime.now().isoformat()
    sprint_data["max_parallel"] = max_parallel
    sprint_data["execution_mode"] = mode
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
        "execution_mode": mode,
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
    
    # PHASE LOCK INTEGRATION: Determine current phase and check if we can proceed
    if sequential:
        lock = PhaseLock(output_dir)
        current_phase = lock.get_current_phase(sprint_id)

        if verbose:
            click.echo(f"Phase Lock enabled. Current phase: {current_phase}")

        # Check if there's a phase waiting for approval
        waiting_phase = lock.get_waiting_phase(sprint_id)
        if waiting_phase:
            click.echo(f"\n⚠ Phase '{waiting_phase}' is waiting for approval.")
            click.echo(f"Run: carby-sprint approve {sprint_id} {waiting_phase}")
            return

    if not work_item_files:
        # No work items: spawn Discover agent (Gate 1)
        phase_id = get_phase_for_agent("discover")
        
        # PHASE LOCK CHECK: In sequential mode, verify we can start this phase
        if sequential:
            lock = PhaseLock(output_dir)
            can_start, error_msg = lock.can_start_phase(sprint_id, phase_id)
            if not can_start:
                click.echo(f"\n⚠ Cannot start {phase_id}: {error_msg}")
                return
        
        if verbose:
            click.echo(f"No work items found. Spawning Discover agent for Gate 1...")

        try:
            # Progress indicator for agent spawning
            with click.progressbar(length=3, label='Spawning Discover agent') as bar:
                # Step 1: Validate gate
                bar.update(1)
                # Gate already validated above

                # Step 2: Acquire phase lock
                bar.update(1)
                if sequential:
                    lock = PhaseLock(output_dir)
                    lock.start_phase(sprint_id, phase_id)

                # Step 3: Spawn agent
                bar.update(1)
                process = spawn_phase_agent(
                    agent_type="discover",
                    sprint_id=sprint_id,
                    gate=1,
                    phase_id=phase_id,
                    validation_token=sprint_data.get("validation_token"),
                    carby_studio_path=Path(output_dir).parent.parent if output_dir != ".carby-sprints" else None,
                    sequential=sequential,
                    output_dir=output_dir,
                )
            spawned_processes.append(("discover", process))
            click.echo(f"✓ Spawned Discover agent for sprint '{sprint_id}'")

            # PHASE LOCK: Report that phase is running
            if sequential:
                click.echo(f"  Phase Lock: {phase_id} is now IN_PROGRESS")

        except PhaseBlockedError as e:
            # PHASE LOCK BLOCK: Show the blocking message
            click.echo(f"\n{e}")
            return
        except Exception as e:
            click.echo(f"⚠ Failed to spawn Discover agent: {e}", err=True)
    else:
        # Work items exist: spawn Build agents for each
        phase_id = get_phase_for_agent("build")
        
        # PHASE LOCK CHECK: In sequential mode, verify we can start this phase
        if sequential:
            lock = PhaseLock(output_dir)
            can_start, error_msg = lock.can_start_phase(sprint_id, phase_id)
            if not can_start:
                waiting_phase = lock.get_waiting_phase(sprint_id)
                if waiting_phase:
                    click.echo(f"\n⚠ Cannot start {phase_id}: '{waiting_phase}' is waiting for approval.")
                    click.echo(f"Run: carby-sprint approve {sprint_id} {waiting_phase}")
                else:
                    click.echo(f"\n⚠ Cannot start {phase_id}: previous phase not approved")
                return
        
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

                # Progress indicator for each Build agent spawn
                with click.progressbar(length=3, label=f'Spawning Build agent for {wi_id}') as bar:
                    # Step 1: Validate gate
                    bar.update(1)
                    # Gate already validated above

                    # Step 2: Acquire phase lock
                    bar.update(1)
                    if sequential:
                        lock = PhaseLock(output_dir)
                        lock.start_phase(sprint_id, phase_id)

                    # Step 3: Spawn agent
                    bar.update(1)
                    process = spawn_phase_agent(
                        agent_type="build",
                        sprint_id=sprint_id,
                        gate=3,
                        phase_id=phase_id,
                        work_item_id=wi_id,
                        validation_token=work_item.get("validation_token") or sprint_data.get("validation_token"),
                        carby_studio_path=Path(output_dir).parent.parent if output_dir != ".carby-sprints" else None,
                        sequential=sequential,
                        output_dir=output_dir,
                    )
                spawned_processes.append((f"build-{wi_id}", process))

                # Update work item status
                work_item["status"] = "in_progress"
                work_item["started_at"] = datetime.now().isoformat()
                repo.save_work_item(paths, work_item)

                click.echo(f"✓ Spawned Build agent for work item: {wi_id}")

            except PhaseBlockedError as e:
                # PHASE LOCK BLOCK: Show the blocking message
                click.echo(f"\n{e}")
                return
            except Exception as e:
                click.echo(f"⚠ Failed to spawn Build agent for {wi_file.stem}: {e}", err=True)

    # Log spawned processes
    if spawned_processes:
        execution_log = paths.logs / "execution.log"
        with open(execution_log, "a") as f:
            f.write(f"\n[{datetime.now().isoformat()}] Sprint started\n")
            f.write(f"  Mode: {mode}\n")
            for name, proc in spawned_processes:
                f.write(f"  Spawned {name} (PID: {proc.pid})\n")

    click.echo(f"\n✓ Sprint '{sprint_id}' started successfully")
    click.echo(f"  Status: in_progress")
    click.echo(f"  Mode: {mode}")
    click.echo(f"  Max parallel: {max_parallel}")
    click.echo(f"  Work items: {len(work_items)}")
    click.echo(f"  Agents spawned: {len(spawned_processes)}")
    click.echo(f"  Started at: {sprint_data['started_at']}")
    
    if sequential:
        click.echo(f"\nSequential mode enabled. Phases will wait for approval.")
        click.echo(f"Use 'carby-sprint approve {sprint_id} <phase>' to advance.")
    
    click.echo(f"\nMonitor with:")
    click.echo(f"  carby-sprint status {sprint_id} --watch")
