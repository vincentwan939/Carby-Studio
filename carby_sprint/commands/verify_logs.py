"""
Audit log verification command.

Verifies the integrity of the signed audit log and reports any tampering.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from carby_sprint.lib.signed_audit_log import SignedAuditLog


def get_audit_db_path(output_dir: str = ".carby-sprints") -> Path:
    """Get the path to the audit database."""
    return Path(output_dir) / "audit.db"


@click.command()
@click.option(
    "--sprint-id",
    "-s",
    help="Verify only entries for a specific sprint",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data and audit logs",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show detailed entry information",
)
@click.option(
    "--export",
    "-e",
    type=click.Path(),
    help="Export verified logs to JSON file",
)
def verify_logs(
    sprint_id: str | None,
    output_dir: str,
    verbose: bool,
    export: str | None,
) -> None:
    """
    Verify audit log integrity.

    Checks the hash chain and HMAC signatures of all audit log entries
    to detect any tampering. Reports any integrity violations found.
    """
    db_path: Path = get_audit_db_path(output_dir)

    if not db_path.exists():
        click.echo("⚠️  No audit log found.")
        return

    # Initialize audit log
    audit_log: SignedAuditLog = SignedAuditLog(db_path)

    # Run verification
    click.echo("🔍 Verifying audit log integrity...")
    click.echo()

    result: dict[str, Any] = audit_log.verify(sprint_id)

    # Display results
    if result["valid"]:
        click.echo("✅ Audit log integrity verified")
        click.echo(f"   Total entries checked: {result['total_entries']}")

        if sprint_id:
            click.echo(f"   Filtered by sprint: {sprint_id}")
    else:
        click.echo("❌ AUDIT LOG TAMPERING DETECTED")
        click.echo()
        click.echo(f"   Total entries checked: {result['total_entries']}")

        if result["broken_chain_at"]:
            click.echo()
            click.echo("   Broken hash chain at entries:")
            for broken in result["broken_chain_at"]:
                click.echo(f"     - Entry ID {broken['id']}")
                if verbose:
                    click.echo(f"       Expected previous hash: {broken['expected_previous']}")
                    click.echo(f"       Actual previous hash:   {broken['actual_previous']}")

        if result["tampered_entries"]:
            click.echo()
            click.echo("   Tampered entries detected:")
            for entry in result["tampered_entries"]:
                click.echo(f"     - Entry ID {entry['id']}: {entry['reason']}")
                if verbose:
                    if entry['reason'] == 'hash_mismatch':
                        click.echo(f"       Expected hash: {entry['expected_hash']}")
                        click.echo(f"       Actual hash:   {entry['actual_hash']}")
                    elif entry['reason'] == 'invalid_signature':
                        click.echo(f"       Entry hash: {entry['entry_hash']}")

        # Exit with error code if tampering detected
        raise click.ClickException("Audit log verification failed")

    # Show recent entries if verbose
    if verbose:
        click.echo()
        click.echo("Recent entries:")
        click.echo()

        entries = audit_log.get_entries(sprint_id=sprint_id, limit=5)
        for entry in entries:
            click.echo(f"  [{entry.timestamp}] {entry.event_type}")
            click.echo(f"    Sprint: {entry.sprint_id}")
            click.echo(f"    Hash: {entry.entry_hash[:16]}...")
            if entry.details:
                for key, value in entry.details.items():
                    click.echo(f"    {key}: {value}")
            click.echo()

    # Export if requested
    if export:
        export_path: Path = Path(export)
        audit_log.export_to_json(export_path)
        click.echo()
        click.echo(f"📁 Exported audit log to: {export_path}")
