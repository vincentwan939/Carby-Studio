"""
Agent Result Callback - Handle agent completion and update sprint state.

This module provides functions for agents to report their results back to
the sprint framework, updating work item status and advancing gates.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from .sprint_repository import SprintRepository, SprintPaths
    from .transaction import (
        atomic_sprint_update, 
        atomic_work_item_update,
        validate_work_item_exists,
        validate_gate_transition
    )
except ImportError:
    # When running as standalone script
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from carby_sprint.sprint_repository import SprintRepository, SprintPaths
    from carby_sprint.transaction import (
        atomic_sprint_update, 
        atomic_work_item_update,
        validate_work_item_exists,
        validate_gate_transition
    )


def report_agent_result(
    sprint_id: str,
    agent_type: str,
    result: Dict[str, Any],
    output_dir: str = ".carby-sprints",
) -> Dict[str, Any]:
    """
    Report agent completion result and update sprint state.
    
    Args:
        sprint_id: Sprint identifier
        agent_type: Type of agent that completed (discover, design, build, verify, deliver)
        result: Agent result dictionary containing:
            - status: "success" | "failure" | "blocked"
            - work_item_id: Optional work item ID (for build agents)
            - message: Human-readable result message
            - artifacts: List of generated artifact paths
            - next_gate: Suggested next gate (optional)
        output_dir: Directory containing sprint data
        
    Returns:
        Updated sprint data dictionary
        
    Raises:
        FileNotFoundError: If sprint not found
        ValueError: If result format is invalid
        KeyError: If work item does not exist when expected
    """
    repo = SprintRepository(output_dir)
    sprint_data, paths = repo.load(sprint_id)
    
    # Validate result format
    if "status" not in result:
        raise ValueError("Result must contain 'status' field")
    
    status = result["status"]
    work_item_id = result.get("work_item_id")
    message = result.get("message", f"Agent {agent_type} completed with status: {status}")
    
    # Perform all operations within a transaction
    with atomic_sprint_update(paths.sprint_dir) as sprint_data_tx:
        # Update work item status if applicable
        if work_item_id and agent_type == "build":
            # Validate work item exists before updating
            if not validate_work_item_exists(paths.work_items, work_item_id):
                raise KeyError(f"Work item '{work_item_id}' does not exist")
            
            # Update work item status within transaction
            _update_work_item_status(repo, paths, work_item_id, status, result)
        
        # Check if all work items are complete and advance gate if needed
        current_gate = sprint_data_tx.get("current_gate", 3)  # Default to gate 3 for build
        if agent_type == "build":
            _check_gate_advancement(repo, paths, sprint_data_tx, current_gate)
        elif agent_type in ["discover", "design", "verify", "deliver"]:
            # These agents advance their respective gates on success
            if status == "success":
                _advance_gate(sprint_data_tx, agent_type)
        
        # Update sprint data
        sprint_data_tx["last_agent_result"] = {
            "agent_type": agent_type,
            "status": status,
            "timestamp": datetime.now().isoformat(),
            "message": message,
        }
        
        # Update sprint status if all work items complete
        if _are_all_work_items_complete(repo, paths):
            if sprint_data_tx.get("status") == "in_progress":
                sprint_data_tx["status"] = "completed"
                sprint_data_tx["completed_at"] = datetime.now().isoformat()
    
    # Reload and return updated data
    updated_sprint_data, _ = repo.load(sprint_id)
    return updated_sprint_data


def _update_work_item_status(
    repo: SprintRepository,
    paths: SprintPaths,
    work_item_id: str,
    status: str,
    result: Dict[str, Any],
) -> None:
    """Update work item status based on agent result with validation."""
    # Validate work item exists before updating
    if not validate_work_item_exists(paths.work_items, work_item_id):
        raise KeyError(f"Work item '{work_item_id}' does not exist")
    
    # Load work item
    work_item = repo.load_work_item(paths, work_item_id)
    
    # Update status based on result
    if status == "success":
        work_item["status"] = "completed"
        work_item["completed_at"] = datetime.now().isoformat()
    elif status == "failure":
        work_item["status"] = "failed"
        work_item["failed_at"] = datetime.now().isoformat()
        work_item["failure_reason"] = result.get("message", "Unknown failure")
    elif status == "blocked":
        work_item["status"] = "blocked"
        work_item["blocked_at"] = datetime.now().isoformat()
        work_item["block_reason"] = result.get("message", "Unknown blocker")
    
    # Store artifacts
    if "artifacts" in result:
        work_item["artifacts"] = result["artifacts"]
    
    # Store GitHub issues created
    if "github_issues" in result:
        work_item["github_issues"] = result["github_issues"]
    
    # Save work item using atomic transaction
    repo.save_work_item(paths, work_item)


def _check_gate_advancement(
    repo: SprintRepository,
    paths: SprintPaths,
    sprint_data: Dict[str, Any],
    current_gate: int,
) -> bool:
    """
    Check if all work items are complete and advance gate.
    
    Returns:
        True if gate was advanced, False otherwise
    """
    work_item_ids = repo.list_work_items(paths)
    
    if not work_item_ids:
        return False
    
    all_complete = True
    any_failed = False
    
    for wi_id in work_item_ids:
        try:
            work_item = repo.load_work_item(paths, wi_id)
            status = work_item.get("status", "planned")
            
            if status not in ["completed", "failed", "cancelled"]:
                all_complete = False
                break
            if status == "failed":
                any_failed = True
                
        except FileNotFoundError:
            # Fail-fast: if work item doesn't exist during check, raise error
            raise FileNotFoundError(f"Work item {wi_id} referenced in sprint but not found")
    
    if all_complete:
        # Validate gate transition before making changes
        gates = sprint_data.get("gates", {})
        current_gate_str = str(current_gate)
        if current_gate_str in gates:
            current_status = gates[current_gate_str].get("status", "pending")
            if not validate_gate_transition(current_status, "passed"):
                raise ValueError(f"Invalid gate transition from {current_status} to passed for gate {current_gate}")
        
        # Advance to next gate
        next_gate = current_gate + 1
        sprint_data["current_gate"] = next_gate
        
        # Update gate status
        if current_gate_str in gates:
            gates[current_gate_str]["status"] = "passed" if not any_failed else "passed_with_warnings"
            gates[current_gate_str]["passed_at"] = datetime.now().isoformat()
        
        # Log gate advancement
        _write_result_log(
            paths,
            "gate_advancement",
            {
                "from_gate": current_gate,
                "to_gate": next_gate,
                "all_complete": True,
                "any_failed": any_failed,
            },
        )
        
        return True
    
    return False


def _advance_gate(sprint_data: Dict[str, Any], agent_type: str) -> None:
    """Advance gate based on agent type completion with validation."""
    # Map agent types to gates they complete
    agent_gate_map = {
        "discover": 1,
        "design": 2,
        "build": 3,
        "verify": 4,
        "deliver": 5,
    }
    
    gate_num = agent_gate_map.get(agent_type)
    if gate_num is None:
        return
    
    gates = sprint_data.get("gates", {})
    gate_str = str(gate_num)
    if gate_str in gates:
        current_status = gates[gate_str].get("status", "pending")
        
        # Validate the transition is allowed
        if not validate_gate_transition(current_status, "passed"):
            raise ValueError(f"Invalid gate transition from {current_status} to passed for gate {gate_num}")
        
        gates[gate_str]["status"] = "passed"
        gates[gate_str]["passed_at"] = datetime.now().isoformat()
    
    # Update current gate
    sprint_data["current_gate"] = gate_num + 1


def _are_all_work_items_complete(repo: SprintRepository, paths: SprintPaths) -> bool:
    """Check if all work items are in a terminal state."""
    work_item_ids = repo.list_work_items(paths)
    
    if not work_item_ids:
        return True  # No work items means complete
    
    for wi_id in work_item_ids:
        try:
            work_item = repo.load_work_item(paths, wi_id)
            status = work_item.get("status", "planned")
            
            if status not in ["completed", "failed", "cancelled"]:
                return False
                
        except FileNotFoundError:
            # Fail-fast: if work item doesn't exist during check, raise error
            raise FileNotFoundError(f"Work item {wi_id} referenced in sprint but not found")
    
    return True


def _write_result_log(
    paths: SprintPaths,
    agent_type: str,
    result: Dict[str, Any],
) -> None:
    """Write agent result to logs directory."""
    log_file = paths.logs / f"agent_results.jsonl"
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "agent_type": agent_type,
        "result": result,
    }
    
    # Append to JSONL file
    with open(log_file, "a") as f:
        f.write(json.dumps(log_entry) + "\n")