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

from .sprint_repository import SprintRepository, SprintPaths


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
    """
    repo = SprintRepository(output_dir)
    sprint_data, paths = repo.load(sprint_id)
    
    # Validate result format
    if "status" not in result:
        raise ValueError("Result must contain 'status' field")
    
    status = result["status"]
    work_item_id = result.get("work_item_id")
    message = result.get("message", f"Agent {agent_type} completed with status: {status}")
    
    # Log the result
    _write_result_log(paths, agent_type, result)
    
    # Update work item status if applicable
    if work_item_id and agent_type == "build":
        _update_work_item_status(repo, paths, work_item_id, status, result)
    
    # Check if all work items are complete and advance gate if needed
    current_gate = sprint_data.get("current_gate", 3)  # Default to gate 3 for build
    if agent_type == "build":
        _check_gate_advancement(repo, paths, sprint_data, current_gate)
    elif agent_type in ["discover", "design", "verify", "deliver"]:
        # These agents advance their respective gates on success
        if status == "success":
            _advance_gate(sprint_data, agent_type)
    
    # Update sprint data
    sprint_data["last_agent_result"] = {
        "agent_type": agent_type,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "message": message,
    }
    
    # Update sprint status if all work items complete
    if _are_all_work_items_complete(repo, paths):
        if sprint_data.get("status") == "in_progress":
            sprint_data["status"] = "completed"
            sprint_data["completed_at"] = datetime.now().isoformat()
    
    repo.save(sprint_data, paths)
    
    return sprint_data


def _update_work_item_status(
    repo: SprintRepository,
    paths: SprintPaths,
    work_item_id: str,
    status: str,
    result: Dict[str, Any],
) -> None:
    """Update work item status based on agent result."""
    try:
        work_item = repo.load_work_item(paths, work_item_id)
        
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
        
        repo.save_work_item(paths, work_item)
        
    except FileNotFoundError:
        # Work item might not exist yet, log but don't fail
        _write_result_log(
            paths,
            "callback",
            {"warning": f"Work item {work_item_id} not found for status update"},
        )


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
            all_complete = False
            break
    
    if all_complete:
        # Advance to next gate
        next_gate = current_gate + 1
        sprint_data["current_gate"] = next_gate
        
        # Update gate status
        gates = sprint_data.get("gates", {})
        if str(current_gate) in gates:
            gates[str(current_gate)]["status"] = "passed" if not any_failed else "passed_with_warnings"
            gates[str(current_gate)]["passed_at"] = datetime.now().isoformat()
        
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
    """Advance gate based on agent type completion."""
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
    if str(gate_num) in gates:
        gates[str(gate_num)]["status"] = "passed"
        gates[str(gate_num)]["passed_at"] = datetime.now().isoformat()
    
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
            return False
    
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
