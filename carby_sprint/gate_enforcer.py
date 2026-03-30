"""
Server-Side Gate Enforcement System

Implements cryptographic gate enforcement with HMAC-signed tokens,
expiration validation, and server-side can_advance() checks to prevent
agents from bypassing gates.

This module provides:
- HMAC-SHA256 signed tokens with 24-hour expiration
- Server-side gate advancement validation
- Tamper-evident gate logs
- No client-side bypass capability
- Design Approval Gate for design-first workflow

Note: This module now re-exports from split modules:
- gate_token.py: GateToken, DesignApprovalToken
- gate_state.py: GateStateManager
- design_gate.py: DesignGateEnforcer
"""

from datetime import datetime
from typing import Dict, Optional, Tuple, Any

from .exceptions import (
    CarbyStudioError,
    InvalidTokenError,
    ExpiredTokenError,
    GateEnforcementError,
    GateBypassError,
    TokenReplayError
)
from .gate_token import GateToken, DesignApprovalToken
from .gate_state import GateStateManager
from .design_gate import DesignGateEnforcer


class GateEnforcer:
    """
    Server-side gate enforcement system that controls advancement through sprint phases.
    
    This class ensures that agents cannot bypass gates and that all progression
    follows the defined workflow rules.
    
    Note: This class now delegates to GateStateManager for persistence
    and GateToken for token operations.
    """
    
    def __init__(self, project_dir: str):
        """
        Initialize the gate enforcer.
        
        Args:
            project_dir: Project directory path
        """
        self.state_manager = GateStateManager(project_dir)
        self.project_dir = self.state_manager.project_dir
        self.sprint_dir = self.state_manager.sprint_dir
        self.gate_sequence = self.state_manager.gate_sequence
        self.status_file = self.state_manager.status_file
    
    # NOTE: _load_gate_status and _save_gate_status are now internal to
    # GateStateManager and MUST be called within a lock context.
    # Use the state_manager's public methods which handle locking automatically.
    
    def _get_current_gate(self, sprint_id: str) -> str:
        """Get the current gate for a sprint."""
        return self.state_manager.get_current_gate(sprint_id)
    
    def _set_current_gate(self, sprint_id: str, gate: str) -> None:
        """Set the current gate for a sprint."""
        self.state_manager.set_current_gate(sprint_id, gate)
    
    def _record_gate_completion(self, sprint_id: str, gate: str, token: str, user_id: Optional[str] = None) -> None:
        """Record that a gate has been completed."""
        self.state_manager.record_gate_completion(sprint_id, gate, token, user_id)
    
    def can_advance(self, sprint_id: str, current_gate: str, next_gate: str) -> bool:
        """
        Server-side check to determine if advancement is allowed.
        
        Args:
            sprint_id: Sprint identifier
            current_gate: Current gate
            next_gate: Next gate to advance to
        
        Returns:
            True if advancement is allowed, False otherwise
        """
        # Check if the transition is valid according to the sequence
        try:
            current_idx = self.gate_sequence.index(current_gate)
            next_idx = self.gate_sequence.index(next_gate)
        except ValueError:
            return False  # Invalid gate name
        
        # Can only advance to the next gate in sequence
        if next_idx != current_idx + 1:
            return False
        
        # Check if the current gate has been properly completed
        return self.state_manager.is_gate_completed(sprint_id, current_gate)
    
    def request_gate_token(self, sprint_id: str, gate: str) -> GateToken:
        """
        Request a signed token for a specific gate.
        
        Args:
            sprint_id: Sprint identifier
            gate: Gate identifier
        
        Returns:
            Signed GateToken
        """
        token = GateToken(gate_id=gate, sprint_id=sprint_id)
        return token
    
    def validate_gate_token(self, token_str: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate a gate token and return validation result.
        
        Performs signature and expiration validation ONLY.
        
        SECURITY FIX (INT-N3): Token replay checking has been REMOVED from this method
        to eliminate the "Token Replay Window" vulnerability. Previously, this method
        checked is_token_used() which created a race condition window:
        
        1. Thread A calls validate_gate_token() -> is_token_used() returns False
        2. Thread B calls validate_gate_token() -> is_token_used() returns False  
        3. Thread A proceeds to advance_gate() and marks token as used
        4. Thread B proceeds to advance_gate() - token already used but passed validation
        
        The fix: Replay protection is now handled ONLY by check_and_mark_token_used()
        which is called atomically within advance_gate(). This ensures that the
        check and mark happen in a single atomic operation, eliminating the window.
        
        Args:
            token_str: Token string to validate
        
        Returns:
            Tuple of (is_valid, gate_id, sprint_id)
        """
        try:
            token = GateToken.from_string(token_str)
            
            # SECURITY: No replay check here. Replay protection is handled
            # atomically in advance_gate() via check_and_mark_token_used().
            # This eliminates the Token Replay Window vulnerability.
            
            return True, token.gate_id, token.sprint_id
        except (InvalidTokenError, ExpiredTokenError) as e:
            return False, None, None
    
    def advance_gate(self, sprint_id: str, gate: str, token_str: str, user_id: Optional[str] = None) -> bool:
        """
        Advance to the next gate using a valid token.

        This method performs an atomic transaction that:
        1. Validates the token (signature, expiration)
        2. Atomically checks and marks token as used (replay protection)
        3. Checks advancement rules
        4. Records completion
        5. Updates current gate

        Thread-safe: Uses atomic check_and_mark for replay protection, then
        atomic_update for gate status changes.

        Args:
            sprint_id: Sprint identifier
            gate: Gate to advance to
            token_str: Valid gate token
            user_id: ID of the user who performed the action

        Returns:
            True if advancement successful, False otherwise

        Raises:
            GateBypassError: If token is invalid or advancement not allowed
            TokenReplayError: If token has already been used
        """
        # Validate the token signature and expiration (no replay check here)
        is_valid, token_gate, token_sprint = self.validate_gate_token(token_str)
        
        if not is_valid or token_sprint != sprint_id or token_gate != gate:
            raise GateBypassError("Invalid token for gate advancement")
        
        # SECURITY FIX (INT-N3): Atomically check and mark token as used.
        # This prevents the Token Replay Window vulnerability where two concurrent
        # threads could both pass validation before either marks the token as used.
        # The atomic check-and-mark ensures only one thread can successfully claim a token.
        token_claimed, _ = self.state_manager.check_and_mark_token_used(
            token_str, sprint_id, gate, user_id
        )
        if not token_claimed:
            raise TokenReplayError(token_str[:16])
        
        # Now perform the gate advancement (token is already marked as used)
        def do_advance(status):
            # Get current gate from status
            current_gate = status.get(sprint_id, {}).get("current_gate", self.gate_sequence[0])
            
            # Check advancement rules
            try:
                current_idx = self.gate_sequence.index(current_gate)
                next_idx = self.gate_sequence.index(gate)
            except ValueError:
                raise GateBypassError(f"Invalid gate: {current_gate} or {gate}")
            
            if next_idx != current_idx + 1:
                raise GateBypassError(f"Cannot advance from {current_gate} to {gate}")
            
            # Check if current gate is completed (within lock)
            completed_gates = status.get(sprint_id, {}).get("completed_gates", [])
            current_completed = any(g["gate"] == current_gate for g in completed_gates)
            
            if not current_completed and current_gate != self.gate_sequence[0]:
                # First gate (discovery) doesn't need completion to advance
                raise GateBypassError(f"Current gate {current_gate} not completed")
            
            # All checks passed - perform updates atomically
            if sprint_id not in status:
                status[sprint_id] = {}
            
            # Record completion of current gate
            if "completed_gates" not in status[sprint_id]:
                status[sprint_id]["completed_gates"] = []
            status[sprint_id]["completed_gates"].append({
                "gate": current_gate,
                "completed_at": datetime.utcnow().isoformat(),
                "token_hash": self.state_manager._hash_token(token_str),  # Full SHA-256 hash for forensic correlation
                "user_id": user_id or "system",
            })
            
            # Set new gate
            status[sprint_id]["current_gate"] = gate
            status[sprint_id]["updated_at"] = datetime.utcnow().isoformat()
            
            return status
        
        # Execute atomic update for gate status
        self.state_manager.atomic_update(sprint_id, do_advance)

        return True
    
    def get_gate_status(self, sprint_id: str) -> Dict[str, Any]:
        """
        Get the current status of gates for a sprint.
        
        Args:
            sprint_id: Sprint identifier
        
        Returns:
            Gate status information
        """
        return self.state_manager.get_gate_status(sprint_id)


# Re-export all public classes for backward compatibility
__all__ = [
    'GateEnforcer',
    'GateToken',
    'DesignApprovalToken',
    'GateStateManager',
    'DesignGateEnforcer',
    'GateEnforcementError',
    'GateBypassError',
    'InvalidTokenError',
    'ExpiredTokenError',
    'TokenReplayError',
]
