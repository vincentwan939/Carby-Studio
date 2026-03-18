"""
Main CLI entry point for Carby Sprint.
"""

from __future__ import annotations

import click
from .commands import init, plan, start, status, control, gate, work_item


@click.group()
@click.version_option(version="0.1.0", prog_name="carby-sprint")
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


if __name__ == "__main__":
    cli()
