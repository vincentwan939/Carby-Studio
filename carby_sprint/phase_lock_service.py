"""Unified phase state management service.

Ensures consistency across:
- phase_lock.json (phase-level states)
- metadata.json (sprint-level status)
- design-approval-token.json (gate tokens)
"""

from __future__ import annotations

import json
import os
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime
from enum import Enum

from .sprint_repository import SprintRepository, SprintPaths
from .gate_enforcer import GateEnforcer, DesignGateEnforcer, GateBypassError, GateEnforcementError
from .transaction import atomic_sprint_update
from .lock_manager import DistributedLock


class PhaseState(str, Enum):
    """Phase states."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    FAILED = "failed"


class PhaseTransitionError(Exception):
    """Raised when a phase transition is invalid."""
    pass


class PhaseLockServiceError(Exception):
    """Base exception for phase lock service errors."""
    pass


class ConcurrentUpdateError(PhaseLockServiceError):
    """Raised when concurrent update is detected."""
    pass


# Phase order for sequential enforcement
PHASE_ORDER = ["discover", "design", "build", "verify", "deliver"]

# Valid state transitions
VALID_TRANSITIONS: Dict[str, List[str]] = {
    PhaseState.PENDING: [PhaseState.IN_PROGRESS],
    PhaseState.IN_PROGRESS: [PhaseState.AWAITING_APPROVAL, PhaseState.FAILED],
    PhaseState.AWAITING_APPROVAL: [PhaseState.APPROVED, PhaseState.IN_PROGRESS],
    PhaseState.APPROVED: [],  # Terminal state
    PhaseState.FAILED: [PhaseState.IN_PROGRESS, PhaseState.PENDING],  # Can retry
}


def _get_phase_lock_path(sprint_dir: Path) -> Path:
    """Get path to phase_lock.json."""
    return sprint_dir / "phase_lock.json"


def _get_design_token_path(sprint_dir: Path) -> Path:
    """Get path to design-approval-token.json."""
    return sprint_dir / "design-approval-token.json"


def _load_phase_lock(sprint_dir: Path) -> Dict[str, Any]:
    """Load phase lock data from file."""
    path = _get_phase_lock_path(sprint_dir)
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {
        "sprint_id": sprint_dir.name,
        "phases": {p: {"state": PhaseState.PENDING.value, "summary": None} for p in PHASE_ORDER}
    }


def _save_phase_lock(data: Dict[str, Any], sprint_dir: Path) -> None:
    """Save phase lock data to file atomically."""
    path = _get_phase_lock_path(sprint_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def _get_previous_phase(phase_id: str) -> Optional[str]:
    """Get the previous phase in sequence."""
    if phase_id not in PHASE_ORDER:
        return None
    idx = PHASE_ORDER.index(phase_id)
    return PHASE_ORDER[idx - 1] if idx > 0 else None


def _validate_state_transition(current_state: str, new_state: str) -> bool:
    """Check if state transition is valid."""
    if current_state not in VALID_TRANSITIONS:
        return False
    return new_state in VALID_TRANSITIONS[current_state]


class PhaseLockService:
    """Unified service for phase state management.
    
    Ensures consistency across:
    - phase_lock.json (phase-level states)
    - metadata.json (sprint-level status)
    - design-approval-token.json (gate tokens)
    """
    
    def __init__(self, repository: SprintRepository, gate_enforcer: Optional[GateEnforcer] = None):
        """
        Initialize the phase lock service.
        
        Args:
            repository: SprintRepository instance for data access
            gate_enforcer: Optional GateEnforcer for gate validation
        """
        self.repo = repository
        self.gate = gate_enforcer
        self.sprints_dir = repository.output_dir
    
    def _get_lock_file_path(self, sprint_id: str) -> Path:
        """Get the distributed lock file path for a sprint."""
        return self.sprints_dir / sprint_id / ".phase_lock_service.lock"
    
    def _load_all_states(self, sprint_id: str) -> tuple[Dict[str, Any], SprintPaths, Dict[str, Any], Optional[Dict[str, Any]]]:
        """
        Load all three state systems.
        
        Returns:
            Tuple of (sprint_data, paths, phase_lock_data, design_token_data)
        """
        # Load sprint metadata
        sprint_data, paths = self.repo.load(sprint_id)
        
        # Load phase lock data
        phase_lock_data = _load_phase_lock(paths.sprint_dir)
        
        # Load design token if exists
        design_token_path = _get_design_token_path(paths.sprint_dir)
        design_token_data = None
        if design_token_path.exists():
            with open(design_token_path) as f:
                design_token_data = json.load(f)
        
        return sprint_data, paths, phase_lock_data, design_token_data
    
    def _update_sprint_status_from_phases(
        self, 
        sprint_data: Dict[str, Any], 
        phase_lock_data: Dict[str, Any],
        now: str
    ) -> tuple[str, Dict[str, Any]]:
        """
        Derive sprint status from phase states.
        
        Args:
            sprint_data: Sprint data dictionary
            phase_lock_data: Phase lock data dictionary
            now: Current timestamp string
            
        Returns:
            Tuple of (updated sprint status, updated sprint data)
        """
        from datetime import datetime
        phases = phase_lock_data.get("phases", {})
        
        # Check if any phase is in progress
        for phase in PHASE_ORDER:
            if phases.get(phase, {}).get("state") == PhaseState.IN_PROGRESS.value:
                # Set started_at if not already set
                if not sprint_data.get("started_at"):
                    sprint_data["started_at"] = now
                return "in_progress", sprint_data
        
        # Check if all phases are approved
        all_approved = all(
            phases.get(phase, {}).get("state") == PhaseState.APPROVED.value
            for phase in PHASE_ORDER
        )
        if all_approved:
            if not sprint_data.get("completed_at"):
                sprint_data["completed_at"] = now
            return "completed", sprint_data
        
        # Check if any phase is awaiting approval
        for phase in PHASE_ORDER:
            if phases.get(phase, {}).get("state") == PhaseState.AWAITING_APPROVAL.value:
                # Use running status for awaiting approval (valid enum value)
                if not sprint_data.get("started_at"):
                    sprint_data["started_at"] = now
                return "running", sprint_data
        
        # Check if first phase is still pending
        if phases.get(PHASE_ORDER[0], {}).get("state") == PhaseState.PENDING.value:
            return "initialized", sprint_data
        
        # Default to current status
        return sprint_data.get("status", "initialized"), sprint_data
    
    def update_phase_state(
        self, 
        sprint_id: str, 
        phase_id: str, 
        state: str,
        summary: Optional[str] = None,
        check_gates: bool = True
    ) -> Dict[str, Any]:
        """
        Atomically update phase state across all systems.
        
        Args:
            sprint_id: Sprint identifier
            phase_id: Phase identifier (discover, design, build, verify, deliver)
            state: New state (pending, in_progress, awaiting_approval, approved, failed)
            summary: Optional summary text
            check_gates: Whether to validate gates before update
            
        Returns:
            Dict with update result and any errors
        """
        if phase_id not in PHASE_ORDER:
            return {
                "success": False,
                "error": f"Invalid phase '{phase_id}'. Valid: {PHASE_ORDER}",
                "sprint_id": sprint_id,
                "phase_id": phase_id
            }
        
        if state not in [s.value for s in PhaseState]:
            return {
                "success": False,
                "error": f"Invalid state '{state}'. Valid: {[s.value for s in PhaseState]}",
                "sprint_id": sprint_id,
                "phase_id": phase_id
            }
        
        lock_path = self._get_lock_file_path(sprint_id)
        
        try:
            # Acquire distributed lock for exclusive access
            with DistributedLock(lock_path):
                # 1. Load current states from all three systems
                try:
                    sprint_data, paths, phase_lock_data, design_token_data = self._load_all_states(sprint_id)
                except FileNotFoundError as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "sprint_id": sprint_id,
                        "phase_id": phase_id
                    }
                
                # 2. Validate state transition
                current_phase_state = phase_lock_data.get("phases", {}).get(phase_id, {}).get("state", PhaseState.PENDING.value)
                if not _validate_state_transition(current_phase_state, state):
                    return {
                        "success": False,
                        "error": f"Invalid state transition: '{current_phase_state}' -> '{state}'",
                        "sprint_id": sprint_id,
                        "phase_id": phase_id,
                        "current_state": current_phase_state,
                        "requested_state": state
                    }
                
                # 3. Check prerequisites for starting a phase
                if state == PhaseState.IN_PROGRESS.value:
                    prev_phase = _get_previous_phase(phase_id)
                    if prev_phase:
                        prev_state = phase_lock_data.get("phases", {}).get(prev_phase, {}).get("state")
                        if prev_state != PhaseState.APPROVED.value:
                            return {
                                "success": False,
                                "error": f"Cannot start '{phase_id}': previous phase '{prev_phase}' is not approved (state: {prev_state})",
                                "sprint_id": sprint_id,
                                "phase_id": phase_id,
                                "blocked_by": prev_phase,
                                "blocked_by_state": prev_state
                            }
                
                # 4. Check design gate if entering build phase
                if phase_id == "build" and state == PhaseState.IN_PROGRESS.value and check_gates:
                    if self.gate:
                        try:
                            # Use DesignGateEnforcer for design approval check
                            design_enforcer = DesignGateEnforcer(sprint_id, str(self.sprints_dir))
                            design_enforcer.check_approval()
                        except GateBypassError as e:
                            return {
                                "success": False,
                                "error": str(e),
                                "sprint_id": sprint_id,
                                "phase_id": phase_id,
                                "gate_blocked": True
                            }
                        except GateEnforcementError as e:
                            return {
                                "success": False,
                                "error": str(e),
                                "sprint_id": sprint_id,
                                "phase_id": phase_id,
                                "gate_error": True
                            }
                
                # 5. Update all three systems atomically
                now = datetime.utcnow().isoformat()
                
                # Update phase_lock.json
                phase_lock_data["phases"][phase_id] = {
                    "state": state,
                    "updated_at": now
                }
                if summary:
                    phase_lock_data["phases"][phase_id]["summary"] = summary
                
                # Add timestamps based on state
                if state == PhaseState.IN_PROGRESS.value:
                    phase_lock_data["phases"][phase_id]["started_at"] = now
                elif state == PhaseState.AWAITING_APPROVAL.value:
                    phase_lock_data["phases"][phase_id]["completed_at"] = now
                elif state == PhaseState.APPROVED.value:
                    phase_lock_data["phases"][phase_id]["approved_at"] = now
                elif state == PhaseState.FAILED.value:
                    phase_lock_data["phases"][phase_id]["failed_at"] = now
                
                _save_phase_lock(phase_lock_data, paths.sprint_dir)
                
                # Update metadata.json - derive sprint status from phases
                new_sprint_status, sprint_data = self._update_sprint_status_from_phases(sprint_data, phase_lock_data, now)
                sprint_data["status"] = new_sprint_status
                sprint_data["updated_at"] = now
                
                # Update current phase in sprint data
                if state == PhaseState.IN_PROGRESS.value:
                    sprint_data["current_phase"] = phase_id
                elif state == PhaseState.APPROVED.value:
                    # Find next phase
                    idx = PHASE_ORDER.index(phase_id)
                    if idx < len(PHASE_ORDER) - 1:
                        sprint_data["current_phase"] = PHASE_ORDER[idx + 1]
                    else:
                        sprint_data["current_phase"] = None
                
                self.repo.save(sprint_data, paths)
                
                return {
                    "success": True,
                    "sprint_id": sprint_id,
                    "phase_id": phase_id,
                    "previous_state": current_phase_state,
                    "new_state": state,
                    "sprint_status": new_sprint_status,
                    "updated_at": now
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Update failed: {str(e)}",
                "sprint_id": sprint_id,
                "phase_id": phase_id
            }
    
    def get_phase_state(self, sprint_id: str, phase_id: str) -> Dict[str, Any]:
        """
        Get unified phase state from all systems.
        
        Acquires distributed lock to prevent TOCTOU race conditions.
        
        Args:
            sprint_id: Sprint identifier
            phase_id: Phase identifier
            
        Returns:
            Dict with unified phase state
        """
        if phase_id not in PHASE_ORDER:
            return {
                "success": False,
                "error": f"Invalid phase '{phase_id}'. Valid: {PHASE_ORDER}",
                "sprint_id": sprint_id,
                "phase_id": phase_id
            }
        
        lock_path = self._get_lock_file_path(sprint_id)
        
        try:
            # Acquire lock to prevent TOCTOU race condition
            with DistributedLock(lock_path):
                sprint_data, paths, phase_lock_data, design_token_data = self._load_all_states(sprint_id)
        except FileNotFoundError as e:
            return {
                "success": False,
                "error": str(e),
                "sprint_id": sprint_id,
                "phase_id": phase_id
            }
        
        phase_info = phase_lock_data.get("phases", {}).get(phase_id, {})
        prev_phase = _get_previous_phase(phase_id)
        
        result = {
            "success": True,
            "sprint_id": sprint_id,
            "phase_id": phase_id,
            "state": phase_info.get("state", PhaseState.PENDING.value),
            "summary": phase_info.get("summary"),
            "previous_phase": prev_phase,
            "sprint_status": sprint_data.get("status"),
            "timestamps": {
                "started_at": phase_info.get("started_at"),
                "completed_at": phase_info.get("completed_at"),
                "approved_at": phase_info.get("approved_at"),
                "failed_at": phase_info.get("failed_at"),
                "updated_at": phase_info.get("updated_at")
            }
        }
        
        # Add design token info for build phase
        if phase_id == "build" and design_token_data:
            result["design_approval"] = {
                "approved": True,
                "token": design_token_data.get("token"),
                "approver": design_token_data.get("approver"),
                "approved_at": design_token_data.get("approved_at"),
                "expires_at": design_token_data.get("expires_at")
            }
        
        return result
    
    def can_start_phase(self, sprint_id: str, phase_id: str) -> Dict[str, Any]:
        """
        Check if phase can be started (all prerequisites met).
        
        Acquires distributed lock to prevent TOCTOU race conditions.
        
        Args:
            sprint_id: Sprint identifier
            phase_id: Phase identifier
            
        Returns:
            Dict with check result
        """
        if phase_id not in PHASE_ORDER:
            return {
                "can_start": False,
                "error": f"Invalid phase '{phase_id}'. Valid: {PHASE_ORDER}",
                "sprint_id": sprint_id,
                "phase_id": phase_id
            }
        
        lock_path = self._get_lock_file_path(sprint_id)
        
        try:
            # Acquire lock to prevent TOCTOU race condition
            with DistributedLock(lock_path):
                sprint_data, paths, phase_lock_data, design_token_data = self._load_all_states(sprint_id)
        except FileNotFoundError as e:
            return {
                "can_start": False,
                "error": str(e),
                "sprint_id": sprint_id,
                "phase_id": phase_id
            }
        
        phase_info = phase_lock_data.get("phases", {}).get(phase_id, {})
        current_state = phase_info.get("state", PhaseState.PENDING.value)
        
        # Check if already in progress or beyond
        if current_state != PhaseState.PENDING.value:
            return {
                "can_start": False,
                "error": f"Phase '{phase_id}' is already {current_state}",
                "sprint_id": sprint_id,
                "phase_id": phase_id,
                "current_state": current_state
            }
        
        # Check previous phase
        prev_phase = _get_previous_phase(phase_id)
        if prev_phase:
            prev_state = phase_lock_data.get("phases", {}).get(prev_phase, {}).get("state")
            if prev_state != PhaseState.APPROVED.value:
                return {
                    "can_start": False,
                    "error": f"Previous phase '{prev_phase}' is not approved (state: {prev_state})",
                    "sprint_id": sprint_id,
                    "phase_id": phase_id,
                    "blocked_by": prev_phase,
                    "blocked_by_state": prev_state
                }
        
        # Check design gate for build phase
        if phase_id == "build":
            if not design_token_data:
                return {
                    "can_start": False,
                    "error": "Design approval token not found. Design must be approved before starting build phase.",
                    "sprint_id": sprint_id,
                    "phase_id": phase_id,
                    "gate_blocked": True,
                    "approval_command": f"carby-sprint approve-design {sprint_id}"
                }
            
            # Check if token is still valid
            expires_at = design_token_data.get("expires_at")
            if expires_at:
                from datetime import datetime
                try:
                    expires = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if datetime.utcnow() > expires:
                        return {
                            "can_start": False,
                            "error": "Design approval token has expired.",
                            "sprint_id": sprint_id,
                            "phase_id": phase_id,
                            "gate_blocked": True,
                            "token_expired": True,
                            "approval_command": f"carby-sprint approve-design {sprint_id}"
                        }
                except ValueError:
                    # Invalid date format - reject the token
                    return {
                        "can_start": False,
                        "error": "Design approval token has invalid expiration date format.",
                        "sprint_id": sprint_id,
                        "phase_id": phase_id,
                        "gate_blocked": True,
                        "token_invalid": True,
                        "approval_command": f"carby-sprint approve-design {sprint_id}"
                    }
        
        return {
            "can_start": True,
            "sprint_id": sprint_id,
            "phase_id": phase_id,
            "previous_phase": prev_phase,
            "sprint_status": sprint_data.get("status")
        }
    
    def get_all_phases_state(self, sprint_id: str) -> Dict[str, Any]:
        """
        Get state of all phases for a sprint.
        
        Acquires distributed lock to prevent TOCTOU race conditions.
        
        Args:
            sprint_id: Sprint identifier
            
        Returns:
            Dict with all phases state
        """
        lock_path = self._get_lock_file_path(sprint_id)
        
        try:
            # Acquire lock to prevent TOCTOU race condition
            with DistributedLock(lock_path):
                sprint_data, paths, phase_lock_data, design_token_data = self._load_all_states(sprint_id)
        except FileNotFoundError as e:
            return {
                "success": False,
                "error": str(e),
                "sprint_id": sprint_id
            }
        
        phases = phase_lock_data.get("phases", {})
        phases_summary = {}
        
        for phase_id in PHASE_ORDER:
            phase_info = phases.get(phase_id, {})
            phases_summary[phase_id] = {
                "state": phase_info.get("state", PhaseState.PENDING.value),
                "summary": phase_info.get("summary"),
                "started_at": phase_info.get("started_at"),
                "completed_at": phase_info.get("completed_at"),
                "approved_at": phase_info.get("approved_at")
            }
        
        return {
            "success": True,
            "sprint_id": sprint_id,
            "sprint_status": sprint_data.get("status"),
            "current_phase": sprint_data.get("current_phase"),
            "phases": phases_summary
        }
    
    def approve_design(self, sprint_id: str, approver: str = "user") -> Dict[str, Any]:
        """
        Approve design phase and issue design approval token.
        
        Args:
            sprint_id: Sprint identifier
            approver: Name of approver
            
        Returns:
            Dict with approval result
        """
        lock_path = self._get_lock_file_path(sprint_id)
        
        try:
            with DistributedLock(lock_path):
                sprint_data, paths, phase_lock_data, _ = self._load_all_states(sprint_id)
                
                # Check if design phase is awaiting approval
                design_state = phase_lock_data.get("phases", {}).get("design", {}).get("state")
                if design_state != PhaseState.AWAITING_APPROVAL.value:
                    return {
                        "success": False,
                        "error": f"Design phase is not awaiting approval (current state: {design_state})",
                        "sprint_id": sprint_id
                    }
                
                # Create design gate enforcer and approve
                design_enforcer = DesignGateEnforcer(sprint_id, str(self.sprints_dir))
                
                try:
                    token = design_enforcer.approve(approver)
                except GateEnforcementError as e:
                    return {
                        "success": False,
                        "error": str(e),
                        "sprint_id": sprint_id
                    }
                
                # Update design phase state to approved
                now = datetime.utcnow().isoformat()
                phase_lock_data["phases"]["design"]["state"] = PhaseState.APPROVED.value
                phase_lock_data["phases"]["design"]["approved_at"] = now
                _save_phase_lock(phase_lock_data, paths.sprint_dir)
                
                # Update sprint metadata - use valid status enum
                sprint_data["status"] = "running"  # valid enum value
                sprint_data["current_phase"] = "build"
                sprint_data["updated_at"] = now
                self.repo.save(sprint_data, paths)
                
                return {
                    "success": True,
                    "sprint_id": sprint_id,
                    "phase_id": "design",
                    "new_state": PhaseState.APPROVED.value,
                    "sprint_status": "design_approved",
                    "token": token.to_dict(),
                    "next_phase": "build",
                    "next_command": f"carby-sprint start-phase {sprint_id} build"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Design approval failed: {str(e)}",
                "sprint_id": sprint_id
            }