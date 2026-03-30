"""
Carby Sprint - CLI for sprint management with validation gates.

A production-ready CLI tool for managing sprints with integrated
validation gates, documentation compliance, and parallel execution.
"""

from __future__ import annotations

__version__ = "3.2.2"
__author__ = "Carby Studio"
__license__ = "MIT"

from .cli import cli
from .sprint_repository import SprintRepository, SprintPaths
from .agent_callback import report_agent_result
from .lock_manager import with_sprint_lock, DistributedLock
from .validators import validate_sprint, validate_work_item, SprintModel, WorkItemModel
from .path_utils import validate_sprint_id, validate_work_item_id, generate_work_item_id

__all__ = [
    "cli",
    "SprintRepository",
    "SprintPaths",
    "report_agent_result",
    "with_sprint_lock",
    "DistributedLock",
    "validate_sprint",
    "validate_work_item",
    "SprintModel",
    "WorkItemModel",
    "validate_sprint_id",
    "validate_work_item_id",
    "generate_work_item_id",
    "phase_lock",
    "design_gate",
    "gate_state",
    "gate_token",
]
