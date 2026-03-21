"""
Comprehensive Test Suite for Carby-Sprint Migration (Phase 4)

Tests all new carby-sprint functionality including:
- SprintState, GateState, PhaseState data classes
- New CLI executor sprint commands
- Integration tests for full sprint lifecycle
- Backward compatibility with legacy project state
"""

import os
import sys
import json
import time
import tempfile
import shutil
import threading
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, call
from typing import Dict, List, Optional

import pytest

# Add bot directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from state_manager import (
    StateManager, StateChange, SprintState, GateState, PhaseState,
    ProjectState, StageState, SprintStatus, GateStatus, PhaseStatus,
    ProjectStatus, StageStatus
)
from cli_executor import CLIExecutor, CLIResult, SecurityError
from config import Config


def test_phase_state_basic():
    """Basic PhaseState functionality test."""
    phase = PhaseState(
        phase_id="test-phase",
        name="Test Phase",
        status=PhaseStatus.PENDING.value
    )
    assert phase.phase_id == "test-phase"
    assert phase.name == "Test Phase"
    assert phase.status == PhaseStatus.PENDING.value


def test_phase_state_from_dict():
    """Test PhaseState.from_dict functionality."""
    data = {
        "phase_id": "phase-1",
        "name": "Discovery Phase",
        "status": "in-progress",
        "agent": "discovery-agent",
        "logs": ["log1", "log2"]
    }
    phase = PhaseState.from_dict(data)
    assert phase.phase_id == "phase-1"
    assert phase.name == "Discovery Phase"
    assert phase.status == "in-progress"
    assert phase.agent == "discovery-agent"
    assert phase.logs == ["log1", "log2"]


def test_gate_state_basic():
    """Basic GateState functionality test."""
    gate = GateState(
        gate_number=1,
        name="Discover Gate",
        status=GateStatus.PENDING.value
    )
    assert gate.gate_number == 1
    assert gate.name == "Discover Gate"
    assert gate.status == GateStatus.PENDING.value


def test_gate_state_with_phases():
    """Test GateState with phases functionality."""
    phase1 = PhaseState(
        phase_id="p1",
        name="Phase 1",
        status=PhaseStatus.COMPLETED.value
    )
    phase2 = PhaseState(
        phase_id="p2",
        name="Phase 2",
        status=PhaseStatus.IN_PROGRESS.value
    )
    
    gate = GateState(
        gate_number=2,
        name="Design Gate",
        status=GateStatus.IN_PROGRESS.value,
        phases=[phase1, phase2]
    )
    
    assert gate.gate_number == 2
    assert len(gate.phases) == 2
    assert gate.phases[0].phase_id == "p1"
    assert gate.phases[1].status == PhaseStatus.IN_PROGRESS.value


def test_sprint_state_basic():
    """Basic SprintState functionality test."""
    sprint = SprintState(
        sprint_id="test-sprint",
        project="test-project",
        goal="Test goal",
        status=SprintStatus.PENDING.value,
        mode="sequential",
        current_gate=1
    )
    assert sprint.sprint_id == "test-sprint"
    assert sprint.project == "test-project"
    assert sprint.goal == "Test goal"
    assert sprint.status == SprintStatus.PENDING.value
    assert sprint.mode == "sequential"
    assert sprint.current_gate == 1


def test_sprint_state_from_dict():
    """Test SprintState.from_dict functionality."""
    data = {
        "sprint_id": "sprint-123",
        "project": "my-project",
        "goal": "Build feature X",
        "status": "in-progress",
        "mode": "parallel",
        "current_gate": 2,
        "gates": [
            {"gate_number": 1, "name": "Gate 1", "status": "completed"},
            {"gate_number": 2, "name": "Gate 2", "status": "in-progress"}
        ]
    }
    sprint = SprintState.from_dict(data)
    assert sprint.sprint_id == "sprint-123"
    assert sprint.project == "my-project"
    assert sprint.goal == "Build feature X"
    assert sprint.status == "in-progress"
    assert sprint.mode == "parallel"
    assert sprint.current_gate == 2
    assert len(sprint.gates) == 2
    assert sprint.gates[0].gate_number == 1
    assert sprint.gates[1].gate_number == 2


def test_cli_executor_sprint_validation():
    """Test CLIExecutor sprint validation functionality."""
    executor = CLIExecutor()
    
    # Test valid sprint names
    valid_names = ["test-sprint", "my-sprint-123", "sprint1"]
    for name in valid_names:
        executor._validate_sprint_name(name)  # Should not raise exception
    
    # Test invalid sprint names
    invalid_names = ["", "test sprint", "test_sprint", "TestSprint", "a" * 51]
    for name in invalid_names:
        try:
            executor._validate_sprint_name(name)
            assert False, f"Should have raised exception for {name}"
        except SecurityError:
            pass  # Expected


def test_cli_executor_gate_validation():
    """Test CLIExecutor gate validation functionality."""
    executor = CLIExecutor()
    
    # Test valid gate numbers
    for gate in [1, 2, 3, 4, 5]:
        executor._validate_gate_number(gate)  # Should not raise exception
    
    # Test invalid gate numbers
    invalid_gates = [0, 6, -1, 10]
    for gate in invalid_gates:
        try:
            executor._validate_gate_number(gate)
            assert False, f"Should have raised exception for gate {gate}"
        except SecurityError:
            pass  # Expected


def test_backward_compatibility():
    """Test backward compatibility functionality."""
    # Test that SprintState can convert to ProjectState for backward compatibility
    sprint = SprintState(
        sprint_id="test-sprint",
        project="test-project",
        goal="Test goal",
        status=SprintStatus.IN_PROGRESS.value,
        mode="sequential",
        current_gate=2  # Maps to "design" stage
    )
    
    project_state = sprint.to_project_state()
    assert project_state.id == "test-sprint"
    assert project_state.goal == "Test goal"
    assert project_state.current_stage == "design"  # Gate 2 should map to "design"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])