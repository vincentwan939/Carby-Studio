#!/usr/bin/env python3
"""
Sprint Agent Bridge - Preprocessor for sprint-aware agent prompts.

This script reads agent prompt templates and injects sprint context
(sprint_id, current_gate, validation_token) to produce processed prompts
ready for sessions_spawn.

Usage:
    python sprint-agent-bridge.py \
        --agent discover|design|build|verify|deliver \
        --sprint-id <sprint_id> \
        --gate <gate_number> \
        [--validation-token <token>] \
        [--risk-score <score>] \
        [--output <path>]

Environment Variables:
    SPRINT_ID - Default sprint ID
    VALIDATION_TOKEN - Default validation token
    CARBY_STUDIO_PATH - Path to carby-studio skill (default: auto-detect)
"""

from __future__ import annotations

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SprintContext:
    """Container for sprint context variables."""
    sprint_id: str
    current_gate: int
    validation_token: Optional[str] = None
    risk_score: Optional[float] = None
    project_name: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template substitution."""
        return {
            "SPRINT_ID": self.sprint_id,
            "CURRENT_GATE": str(self.current_gate),
            "GATE_NAME": self._get_gate_name(),
            "VALIDATION_TOKEN": self.validation_token or "NOT_ISSUED",
            "RISK_SCORE": str(self.risk_score) if self.risk_score else "N/A",
            "PROJECT_NAME": self.project_name or self.sprint_id,
        }
    
    def _get_gate_name(self) -> str:
        """Get human-readable gate name."""
        gate_names = {
            0: "Prep",
            1: "Start",
            2: "Design",
            3: "Implementation",
            4: "Validation",
            5: "Release",
        }
        return gate_names.get(self.current_gate, f"Gate-{self.current_gate}")


class SprintAgentBridge:
    """Bridge between sprint framework and agent prompts."""
    
    # Agent to gate mapping
    AGENT_GATES = {
        "discover": 0,   # Gate 0 (Prep) and Gate 1 (Start)
        "design": 2,     # Gate 2 (Design)
        "build": 3,      # Gate 3 (Implementation)
        "verify": 4,     # Gate 4 (Validation)
        "deliver": 5,    # Gate 5 (Release)
    }
    
    def __init__(self, carby_studio_path: Optional[str] = None):
        """
        Initialize the bridge.
        
        Args:
            carby_studio_path: Path to carby-studio skill directory
        """
        self.carby_studio_path = self._detect_carby_studio_path(carby_studio_path)
        self.agents_dir = self.carby_studio_path / "agents" / "sprint"
        
    def _detect_carby_studio_path(self, provided_path: Optional[str]) -> Path:
        """
        Auto-detect carby-studio path if not provided.
        
        Searches in order:
        1. Provided path
        2. Environment variable CARBY_STUDIO_PATH
        3. Standard OpenClaw skill locations
        4. Current workspace
        """
        if provided_path:
            path = Path(provided_path)
            if path.exists():
                return path
            raise ValueError(f"Provided path does not exist: {provided_path}")
        
        # Check environment variable
        env_path = os.environ.get("CARBY_STUDIO_PATH")
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path
        
        # Standard locations
        standard_paths = [
            Path.home() / ".openclaw" / "workspace" / "skills" / "carby-studio",
            Path.home() / ".openclaw" / "skills" / "carby-studio",
            Path.cwd() / "skills" / "carby-studio",
            Path.cwd().parent / "skills" / "carby-studio",
        ]
        
        for path in standard_paths:
            if path.exists():
                return path
        
        raise RuntimeError(
            "Could not auto-detect carby-studio path. "
            "Please set CARBY_STUDIO_PATH environment variable "
            "or provide --carby-studio-path argument."
        )
    
    def load_agent_prompt(self, agent_name: str) -> str:
        """
        Load agent prompt template.
        
        Args:
            agent_name: Name of agent (discover, design, build, verify, deliver)
            
        Returns:
            Prompt template content
            
        Raises:
            FileNotFoundError: If agent prompt not found
        """
        prompt_file = self.agents_dir / f"{agent_name}-sprint.md"
        
        if not prompt_file.exists():
            # Fallback to non-sprint version
            fallback_file = self.carby_studio_path / "agents" / f"{agent_name}.md"
            if fallback_file.exists():
                print(f"Warning: Sprint-aware prompt not found, using fallback: {fallback_file}", 
                      file=sys.stderr)
                return fallback_file.read_text()
            raise FileNotFoundError(f"Agent prompt not found: {prompt_file}")
        
        return prompt_file.read_text()
    
    def process_prompt(self, template: str, context: SprintContext) -> str:
        """
        Process prompt template with sprint context.
        
        Args:
            template: Prompt template with {{VARIABLE}} placeholders
            context: Sprint context variables
            
        Returns:
            Processed prompt with substitutions
        """
        processed = template
        context_dict = context.to_dict()
        
        # Replace {{VARIABLE}} placeholders
        for key, value in context_dict.items():
            placeholder = f"{{{{{key}}}}}"
            processed = processed.replace(placeholder, str(value))
        
        # Also support ${VARIABLE} format for shell compatibility
        for key, value in context_dict.items():
            placeholder = f"${{{key}}}"
            processed = processed.replace(placeholder, str(value))
        
        return processed
    
    def generate_prompt(
        self,
        agent_name: str,
        sprint_id: str,
        gate: Optional[int] = None,
        validation_token: Optional[str] = None,
        risk_score: Optional[float] = None,
        project_name: Optional[str] = None,
    ) -> str:
        """
        Generate processed prompt for an agent.
        
        Args:
            agent_name: Name of agent
            sprint_id: Sprint identifier
            gate: Gate number (auto-detected from agent if not provided)
            validation_token: Validation token for gate access
            risk_score: Risk score from previous phase
            project_name: Project name (defaults to sprint_id)
            
        Returns:
            Processed prompt ready for sessions_spawn
        """
        # Auto-detect gate from agent name if not provided
        if gate is None:
            gate = self.AGENT_GATES.get(agent_name)
            if gate is None:
                raise ValueError(f"Unknown agent: {agent_name}. Cannot auto-detect gate.")
        
        # Create context
        context = SprintContext(
            sprint_id=sprint_id,
            current_gate=gate,
            validation_token=validation_token,
            risk_score=risk_score,
            project_name=project_name,
        )
        
        # Load and process template
        template = self.load_agent_prompt(agent_name)
        processed = self.process_prompt(template, context)
        
        return processed


def create_sessions_spawn_config(prompt: str, **kwargs) -> Dict[str, Any]:
    """
    Create configuration for sessions_spawn.
    
    Args:
        prompt: Processed agent prompt
        **kwargs: Additional sessions_spawn parameters
        
    Returns:
        Configuration dictionary for sessions_spawn
    """
    config = {
        "task": prompt,
        "runtime": "subagent",
        "mode": "run",
    }
    config.update(kwargs)
    return config


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(
        description="Sprint Agent Bridge - Process sprint-aware agent prompts"
    )
    parser.add_argument(
        "--agent",
        required=True,
        choices=["discover", "design", "build", "verify", "deliver"],
        help="Agent to generate prompt for"
    )
    parser.add_argument(
        "--sprint-id",
        default=os.environ.get("SPRINT_ID"),
        help="Sprint identifier (or set SPRINT_ID env var)"
    )
    parser.add_argument(
        "--gate",
        type=int,
        choices=[0, 1, 2, 3, 4, 5],
        help="Gate number (auto-detected from agent if not provided)"
    )
    parser.add_argument(
        "--validation-token",
        default=os.environ.get("VALIDATION_TOKEN"),
        help="Validation token for gate access"
    )
    parser.add_argument(
        "--risk-score",
        type=float,
        help="Risk score from previous phase"
    )
    parser.add_argument(
        "--project-name",
        help="Project name (defaults to sprint_id)"
    )
    parser.add_argument(
        "--carby-studio-path",
        help="Path to carby-studio skill directory"
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: stdout)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON for sessions_spawn"
    )
    parser.add_argument(
        "--print-context",
        action="store_true",
        help="Print sprint context variables and exit"
    )
    
    args = parser.parse_args()
    
    # Validate required args
    if not args.sprint_id:
        parser.error("--sprint-id is required (or set SPRINT_ID environment variable)")
    
    # Initialize bridge
    try:
        bridge = SprintAgentBridge(carby_studio_path=args.carby_studio_path)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Print context only mode
    if args.print_context:
        gate = args.gate or bridge.AGENT_GATES.get(args.agent, 0)
        context = SprintContext(
            sprint_id=args.sprint_id,
            current_gate=gate,
            validation_token=args.validation_token,
            risk_score=args.risk_score,
            project_name=args.project_name,
        )
        print("Sprint Context Variables:")
        print("-" * 40)
        for key, value in context.to_dict().items():
            print(f"  {key}: {value}")
        return
    
    # Generate prompt
    try:
        prompt = bridge.generate_prompt(
            agent_name=args.agent,
            sprint_id=args.sprint_id,
            gate=args.gate,
            validation_token=args.validation_token,
            risk_score=args.risk_score,
            project_name=args.project_name,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Output
    if args.json:
        import json
        config = create_sessions_spawn_config(prompt)
        output = json.dumps(config, indent=2)
    else:
        output = prompt
    
    if args.output:
        Path(args.output).write_text(output)
        print(f"Prompt written to: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()