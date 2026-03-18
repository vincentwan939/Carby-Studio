"""
GateCLI - Command line interface for gate enforcement.

Provides argparse-based CLI for executing and verifying gates.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Optional, List

from gate_enforcer import GateEnforcer
from gate_types import GateType


class GateCLI:
    """
    Command-line interface for the Gate Enforcer.
    
    Handles argument parsing and command execution.
    """
    
    def __init__(self):
        self.parser = self._create_parser()
    
    def _create_parser(self) -> argparse.ArgumentParser:
        """Create the argument parser."""
        parser = argparse.ArgumentParser(
            description="Gate Enforcer - Cryptographic gate validation"
        )
        parser.add_argument(
            "--project-dir",
            default=".",
            help="Project directory (default: current directory)"
        )
        parser.add_argument(
            "--sprint-id",
            required=True,
            help="Sprint ID"
        )
        
        subparsers = parser.add_subparsers(dest="command", help="Commands")
        
        # Execute gate
        exec_parser = subparsers.add_parser("execute", help="Execute a gate")
        exec_parser.add_argument(
            "gate",
            choices=[g.value for g in GateType],
            help="Gate to execute"
        )
        exec_parser.add_argument(
            "--script",
            help="Path to gate script"
        )
        
        # Verify gate
        verify_parser = subparsers.add_parser("verify", help="Verify a gate pass")
        verify_parser.add_argument(
            "gate",
            choices=[g.value for g in GateType],
            help="Gate to verify"
        )
        
        # Status
        subparsers.add_parser("status", help="Get gate status")
        
        # Audit log
        audit_parser = subparsers.add_parser("audit", help="View audit log")
        audit_parser.add_argument("--limit", type=int, default=50)
        
        return parser
    
    def run(self, args: Optional[List[str]] = None) -> int:
        """
        Run the CLI with the given arguments.
        
        Args:
            args: Command line arguments (uses sys.argv if None)
        
        Returns:
            Exit code (0 for success, 1 for failure)
        """
        parsed_args = self.parser.parse_args(args)
        
        if not parsed_args.command:
            self.parser.print_help()
            return 1
        
        # Initialize enforcer
        enforcer = GateEnforcer(parsed_args.project_dir)
        
        if parsed_args.command == "execute":
            return self._cmd_execute(enforcer, parsed_args)
        
        elif parsed_args.command == "verify":
            return self._cmd_verify(enforcer, parsed_args)
        
        elif parsed_args.command == "status":
            return self._cmd_status(enforcer, parsed_args)
        
        elif parsed_args.command == "audit":
            return self._cmd_audit(enforcer, parsed_args)
        
        return 0
    
    def _cmd_execute(self, enforcer: GateEnforcer, args) -> int:
        """Handle the execute command."""
        gate_type = GateType(args.gate)
        try:
            signature = enforcer.execute_gate(gate_type, args.sprint_id, args.script)
            print(f"✓ Gate {args.gate} passed")
            print(f"  Signature: {signature.hmac_signature[:16]}...")
            print(f"  Timestamp: {signature.timestamp}")
            return 0
        except Exception as e:
            print(f"✗ Gate {args.gate} failed: {e}", file=sys.stderr)
            return 1
    
    def _cmd_verify(self, enforcer: GateEnforcer, args) -> int:
        """Handle the verify command."""
        gate_type = GateType(args.gate)
        if enforcer.verify_gate_pass(gate_type, args.sprint_id):
            print(f"✓ Gate {args.gate} signature valid")
            return 0
        else:
            print(f"✗ Gate {args.gate} signature invalid or missing")
            return 1
    
    def _cmd_status(self, enforcer: GateEnforcer, args) -> int:
        """Handle the status command."""
        status = enforcer.get_gate_status(args.sprint_id)
        print(json.dumps(status, indent=2))
        return 0
    
    def _cmd_audit(self, enforcer: GateEnforcer, args) -> int:
        """Handle the audit command."""
        logs = enforcer.get_audit_log(sprint_id=args.sprint_id, limit=args.limit)
        for entry in logs:
            print(f"[{entry['timestamp']}] {entry['action']}: {entry['result']}")
            print(f"  Gate: {entry['gate_type']}, Sprint: {entry['sprint_id']}")
            if entry['details']:
                print(f"  Details: {entry['details']}")
            print()
        return 0


def main():
    """Entry point for the CLI."""
    cli = GateCLI()
    sys.exit(cli.run())


if __name__ == "__main__":
    main()
