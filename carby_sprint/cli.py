"""
Main CLI entry point for Carby Sprint.
"""

from __future__ import annotations

import json
from pathlib import Path

import click
from .commands import init, plan, start, status, control, gate, work_item, verify_logs, approve, list as list_cmd, phase


@click.group()
@click.version_option(version="2.0.0", prog_name="carby-sprint")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to configuration file",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output",
)
@click.pass_context
def cli(ctx: click.Context, config: str | None, verbose: bool) -> None:
    """
    Carby Sprint - CLI for sprint management with validation gates.

    Manage sprints with integrated validation gates, documentation compliance,
    and parallel execution support.
    """
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose


# Register command groups
cli.add_command(init.init)
cli.add_command(plan.plan)
cli.add_command(start.start)
cli.add_command(status.status)
cli.add_command(control.pause)
cli.add_command(control.resume)
cli.add_command(control.cancel)
cli.add_command(control.archive)
cli.add_command(gate.gate)
cli.add_command(work_item.work_item)
cli.add_command(list_cmd.list_sprints)
cli.add_command(list_cmd.list_sprints, name="list")  # Alias for list-sprints
cli.add_command(verify_logs.verify_logs)
cli.add_command(approve.approve)

# Register phase commands (both group and individual commands)
cli.add_command(phase.phase_group)
cli.add_command(phase.approve_phase, name="approve")
cli.add_command(phase.phase_status, name="phase-status")
cli.add_command(phase.phase_list, name="phase-list")


@cli.command(name="approve-design")
@click.argument('sprint_id')
@click.option('--approver', default='user', help='Who approved the design')
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.pass_context
def approve_design(ctx: click.Context, sprint_id: str, approver: str, output_dir: str):
    """Approve design specification, allowing Build phase to start."""
    from .gate_enforcer import DesignGateEnforcer
    
    enforcer = DesignGateEnforcer(sprint_id, output_dir)
    
    # Check if approval was requested
    request_path = Path(output_dir) / sprint_id / "design-approval-request.json"
    if not request_path.exists():
        click.echo(f"❌ No design approval request found for '{sprint_id}'")
        click.echo(f"   Design phase must complete first.")
        raise click.Abort()
        
    # Show spec summary
    with open(request_path) as f:
        request = json.load(f)
    
    click.echo(f"📋 Design Approval Request")
    click.echo(f"   Sprint: {sprint_id}")
    click.echo(f"   Summary: {request['design_summary']}")
    click.echo(f"")
    
    # Show spec preview
    spec_path = Path(request['spec_path'])
    if spec_path.exists():
        click.echo(f"📄 Specification: {spec_path}")
        click.echo(f"   Preview (first 10 lines):")
        with open(spec_path) as f:
            for i, line in enumerate(f):
                if i >= 10:
                    break
                click.echo(f"   {line.rstrip()}")
        click.echo(f"")
    
    # Confirm approval
    if click.confirm("Approve this design?"):
        token = enforcer.approve(approver=approver)
        click.echo(f"")
        click.echo(f"✅ Design approved!")
        click.echo(f"   Token: {token.token[:16]}...")
        click.echo(f"   Expires: {token.expires_at}")
        click.echo(f"")
        click.echo(f"   Build phase can now start:")
        click.echo(f"   $ carby-sprint start {sprint_id} --phase build")
    else:
        click.echo("❌ Approval cancelled.")


if __name__ == "__main__":
    cli()
