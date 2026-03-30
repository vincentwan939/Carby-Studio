"""
Phase Lock Module for Carby Studio Sequential Phase Enforcement.

Enforces sequential phase execution: discover → design → build → verify → deliver
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from .exceptions import PhaseBlockedError

PHASE_ORDER = ["discover", "design", "build", "verify", "deliver"]
DEFAULT_OUTPUT_DIR = ".carby-sprints"


def _lock_path(sprint_id: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> Path:
    return Path(output_dir) / sprint_id / "phase_lock.json"


def _load(sprint_id: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    path = _lock_path(sprint_id, output_dir)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "sprint_id": sprint_id,
        "phases": {p: {"state": "pending", "summary": None} for p in PHASE_ORDER}
    }


def _save(data: Dict[str, Any], sprint_id: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> None:
    path = _lock_path(sprint_id, output_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def _prev(phase_id: str) -> str | None:
    idx = PHASE_ORDER.index(phase_id) if phase_id in PHASE_ORDER else -1
    return PHASE_ORDER[idx - 1] if idx > 0 else None


def get_phase_status(sprint_id: str, phase_id: str,
                     output_dir: str = DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    """Get current status of a phase."""
    if phase_id not in PHASE_ORDER:
        raise ValueError(f"Invalid phase '{phase_id}'. Valid: {PHASE_ORDER}")
    data = _load(sprint_id, output_dir)
    p = data["phases"].get(phase_id, {})
    return {
        "phase": phase_id, "state": p.get("state", "pending"),
        "summary": p.get("summary"), "previous_phase": _prev(phase_id),
    }


def wait_for_previous_phase(sprint_id: str, phase_id: str,
                            output_dir: str = DEFAULT_OUTPUT_DIR,
                            poll_interval: float = 1.0,
                            check_design_gate: bool = False) -> Dict[str, Any]:
    """Block until previous phase is approved. Raises PhaseBlockedError if blocked.
    
    Args:
        sprint_id: Sprint identifier
        phase_id: Phase to wait for
        output_dir: Directory containing sprint data
        poll_interval: Polling interval (unused, kept for compatibility)
        check_design_gate: If True, also check design approval gate for build phase
    """
    if phase_id not in PHASE_ORDER:
        raise ValueError(f"Invalid phase '{phase_id}'. Valid: {PHASE_ORDER}")
    prev = _prev(phase_id)
    if prev is None:
        return {"ready": True, "phase": phase_id}

    while True:
        data = _load(sprint_id, output_dir)
        prev_state = data["phases"].get(prev, {}).get("state", "pending")

        if prev_state == "approved":
            # NEW: Design Gate check for Build phase (opt-in via check_design_gate)
            if phase_id == "build" and check_design_gate:
                from .gate_enforcer import DesignGateEnforcer
                enforcer = DesignGateEnforcer(sprint_id, output_dir)
                enforcer.check_approval()
            return {"ready": True, "phase": phase_id, "previous_phase": prev}

        if prev_state == "awaiting_approval":
            summary = data["phases"][prev].get("summary", "N/A")
            raise PhaseBlockedError(
                phase_id=phase_id,
                reason=f"Previous phase '{prev}' complete, awaiting approval",
                resolution=f"Run: carby phase approve {sprint_id} {prev}"
            )

        raise PhaseBlockedError(
            phase_id=phase_id,
            reason=f"Previous phase '{prev}' is {prev_state}",
            resolution=f"Complete '{prev}' before starting '{phase_id}'"
        )


def mark_phase_complete(sprint_id: str, phase_id: str, summary: str,
                        output_dir: str = DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    """Mark phase complete, awaiting approval."""
    if phase_id not in PHASE_ORDER:
        raise ValueError(f"Invalid phase '{phase_id}'. Valid: {PHASE_ORDER}")
    data = _load(sprint_id, output_dir)
    data["phases"][phase_id] = {
        "state": "awaiting_approval", "summary": summary,
        "completed_at": datetime.now().isoformat(),
    }
    _save(data, sprint_id, output_dir)
    return {
        "phase": phase_id, "state": "awaiting_approval",
        "message": f"✅ Phase '{phase_id}' complete. Awaiting approval.",
        "approve_command": f"carby phase approve {sprint_id} {phase_id}",
    }


def approve_phase(sprint_id: str, phase_id: str,
                  output_dir: str = DEFAULT_OUTPUT_DIR) -> Dict[str, Any]:
    """Approve phase, allowing next to proceed."""
    if phase_id not in PHASE_ORDER:
        raise ValueError(f"Invalid phase '{phase_id}'. Valid: {PHASE_ORDER}")
    data = _load(sprint_id, output_dir)
    cur = data["phases"].get(phase_id, {})
    if cur.get("state") != "awaiting_approval":
        raise ValueError(f"Phase '{phase_id}' state is {cur.get('state')}, not awaiting_approval")
    data["phases"][phase_id]["state"] = "approved"
    data["phases"][phase_id]["approved_at"] = datetime.now().isoformat()
    _save(data, sprint_id, output_dir)
    idx = PHASE_ORDER.index(phase_id)
    next_p = PHASE_ORDER[idx + 1] if idx < len(PHASE_ORDER) - 1 else None
    result = {"phase": phase_id, "state": "approved", "message": f"✅ Phase '{phase_id}' approved."}
    if next_p:
        result.update({"next_phase": next_p, "next_command": f"carby phase start {sprint_id} {next_p}"})
    return result


# Class-based interface for compatibility with start.py
from enum import Enum

class PhaseLockState(str, Enum):
    """Phase lock states."""
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    REJECTED = "rejected"


class PhaseLock:
    """Class-based Phase Lock interface."""
    
    PHASE_SEQUENCE = ["phase_1_discover", "phase_2_design", "phase_3_build", "phase_4_verify", "phase_5_deliver"]
    
    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        self.output_dir = output_dir
    
    def can_start_phase(self, sprint_id: str, phase_id: str) -> tuple[bool, str | None]:
        """Check if a phase can be started."""
        # Map phase_id to simple name
        simple_phase = phase_id.replace("phase_1_", "").replace("phase_2_", "").replace("phase_3_", "").replace("phase_4_", "").replace("phase_5_", "")
        try:
            result = wait_for_previous_phase(sprint_id, simple_phase, self.output_dir)
            return True, None
        except PhaseBlockedError as e:
            return False, str(e)
    
    def start_phase(self, sprint_id: str, phase_id: str) -> None:
        """Mark phase as started."""
        simple_phase = phase_id.replace("phase_1_", "").replace("phase_2_", "").replace("phase_3_", "").replace("phase_4_", "").replace("phase_5_", "")
        data = _load(sprint_id, self.output_dir)
        data["phases"][simple_phase]["state"] = "in_progress"
        data["phases"][simple_phase]["started_at"] = datetime.now().isoformat()
        _save(data, sprint_id, self.output_dir)
    
    def complete_phase(self, sprint_id: str, phase_id: str, summary: str = "") -> None:
        """Mark phase as completed."""
        simple_phase = phase_id.replace("phase_1_", "").replace("phase_2_", "").replace("phase_3_", "").replace("phase_4_", "").replace("phase_5_", "")
        mark_phase_complete(sprint_id, simple_phase, summary, self.output_dir)
    
    def approve_phase(self, sprint_id: str, phase_id: str) -> None:
        """Approve a phase."""
        simple_phase = phase_id.replace("phase_1_", "").replace("phase_2_", "").replace("phase_3_", "").replace("phase_4_", "").replace("phase_5_", "")
        approve_phase_func(sprint_id, simple_phase, self.output_dir)
    
    def get_current_phase(self, sprint_id: str) -> str | None:
        """Get current phase."""
        data = _load(sprint_id, self.output_dir)
        for phase in PHASE_ORDER:
            if data["phases"].get(phase, {}).get("state") == "in_progress":
                return phase
        return None
    
    def get_waiting_phase(self, sprint_id: str) -> str | None:
        """Get phase waiting for approval."""
        data = _load(sprint_id, self.output_dir)
        for phase in PHASE_ORDER:
            if data["phases"].get(phase, {}).get("state") == "awaiting_approval":
                return phase
        return None

    def is_phase_approved(self, sprint_id: str, phase_id: str) -> bool:
        """Check if a phase is approved.

        Args:
            sprint_id: Sprint identifier
            phase_id: Phase identifier (can be simple name like 'discover' or full like 'phase_1_discover')

        Returns:
            True if phase is approved, False otherwise
        """
        # Map phase_id to simple name
        simple_phase = phase_id.replace("phase_1_", "").replace("phase_2_", "").replace("phase_3_", "").replace("phase_4_", "").replace("phase_5_", "")
        if simple_phase not in PHASE_ORDER:
            return False
        data = _load(sprint_id, self.output_dir)
        return data["phases"].get(simple_phase, {}).get("state") == "approved"


def approve_phase_func(sprint_id: str, phase_id: str, output_dir: str = DEFAULT_OUTPUT_DIR) -> dict:
    """Function version of approve_phase for internal use."""
    return approve_phase(sprint_id, phase_id, output_dir)


# Example usage
if __name__ == "__main__":
    SID = "demo-sprint"
    print("Phase Lock Demo")
    wait_for_previous_phase(SID, "discover")
    print(mark_phase_complete(SID, "discover", "Requirements done"))
    print(approve_phase(SID, "discover"))
    print(get_phase_status(SID, "design"))
