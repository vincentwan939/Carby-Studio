"""
Gate to Agent Mapping - Defines which agent handles each gate.

This module provides the mapping between sprint gates and the agents
responsible for executing work in each gate.
"""

from __future__ import annotations

from typing import Dict, Optional

# Gate number to agent type mapping
# Gate 0: Prep - No agent (manual setup)
# Gate 1: Start - Discover agent
# Gate 2: Design - Design agent
# Gate 3: Implementation - Build agent
# Gate 4: Validation - Verify agent
# Gate 5: Release - Deliver agent

GATE_AGENT_MAP: Dict[int, Optional[str]] = {
    0: None,       # Prep - Manual setup phase
    1: "discover", # Start - Discovery and requirements
    2: "design",   # Design - Architecture and planning
    3: "build",    # Implementation - Code development
    4: "verify",   # Validation - Testing and verification
    5: "deliver",  # Release - Deployment and delivery
}

# Reverse mapping: agent type to gate number
AGENT_GATE_MAP: Dict[str, int] = {
    "discover": 1,
    "design": 2,
    "build": 3,
    "verify": 4,
    "deliver": 5,
}

# Gate names for display
GATE_NAMES: Dict[int, str] = {
    0: "Prep",
    1: "Start",
    2: "Design",
    3: "Implementation",
    4: "Validation",
    5: "Release",
}

# Agent descriptions
AGENT_DESCRIPTIONS: Dict[str, str] = {
    "discover": "Discovery and requirements analysis",
    "design": "Architecture and technical design",
    "build": "Implementation and code development",
    "verify": "Testing and quality verification",
    "deliver": "Deployment and release management",
}


def get_agent_for_gate(gate_number: int) -> Optional[str]:
    """
    Get the agent type responsible for a given gate.
    
    Args:
        gate_number: Gate number (0-5)
        
    Returns:
        Agent type string or None if no agent (e.g., gate 0)
        
    Raises:
        ValueError: If gate number is invalid
    """
    if gate_number not in GATE_AGENT_MAP:
        raise ValueError(f"Invalid gate number: {gate_number}. Must be 0-5.")
    return GATE_AGENT_MAP[gate_number]


def get_gate_for_agent(agent_type: str) -> int:
    """
    Get the gate number for a given agent type.
    
    Args:
        agent_type: Agent type (discover, design, build, verify, deliver)
        
    Returns:
        Gate number (1-5)
        
    Raises:
        ValueError: If agent type is invalid
    """
    if agent_type not in AGENT_GATE_MAP:
        raise ValueError(f"Invalid agent type: {agent_type}. Must be one of: {list(AGENT_GATE_MAP.keys())}")
    return AGENT_GATE_MAP[agent_type]


def get_gate_name(gate_number: int) -> str:
    """
    Get the human-readable name for a gate.
    
    Args:
        gate_number: Gate number (0-5)
        
    Returns:
        Gate name string
    """
    return GATE_NAMES.get(gate_number, f"Gate-{gate_number}")


def get_agent_description(agent_type: str) -> str:
    """
    Get the description for an agent type.
    
    Args:
        agent_type: Agent type (discover, design, build, verify, deliver)
        
    Returns:
        Agent description string
    """
    return AGENT_DESCRIPTIONS.get(agent_type, "Unknown agent")


def is_valid_gate(gate_number: int) -> bool:
    """Check if a gate number is valid."""
    return gate_number in GATE_AGENT_MAP


def is_valid_agent(agent_type: str) -> bool:
    """Check if an agent type is valid."""
    return agent_type in AGENT_GATE_MAP


def list_gates() -> list[int]:
    """Return a list of all valid gate numbers."""
    return list(GATE_AGENT_MAP.keys())


def list_agents() -> list[str]:
    """Return a list of all valid agent types."""
    return list(AGENT_GATE_MAP.keys())
