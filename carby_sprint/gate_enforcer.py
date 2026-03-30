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
        
        Performs three-stage validation:
        1. Token signature and expiration validation
        2. Token replay check (prevents reuse)
        3. Returns gate and sprint identifiers
        
        Args:
            token_str: Token string to validate
        
        Returns:
            Tuple of (is_valid, gate_id, sprint_id)
        
        Raises:
            TokenReplayError: If token has already been used (replay attack)
        """
        try:
            token = GateToken.from_string(token_str)
            
            # Check for replay attack - token has already been used
            if self.state_manager.is_token_used(token_str):
                raise TokenReplayError(token_str[:16])
            
            return True, token.gate_id, token.sprint_id
        except (InvalidTokenError, ExpiredTokenError) as e:
            return False, None, None
    
    def advance_gate(self, sprint_id: str, gate: str, token_str: str, user_id: Optional[str] = None) -> bool:
        """
        Advance to the next gate using a valid token.

        This method performs an atomic transaction that:
        1. Validates the token (signature, expiration, replay check)
        2. Checks advancement rules
        3. Marks the token as used
        4. Records completion
        5. Updates current gate

        Thread-safe: Uses atomic_update for the entire read-modify-write.

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
        # Validate the token signature and expiration
        is_valid, token_gate, token_sprint = self.validate_gate_token(token_str)
        
        if not is_valid or token_sprint != sprint_id or token_gate != gate:
            raise GateBypassError("Invalid token for gate advancement")
        
        # Check for replay attack BEFORE acquiring lock (read-only check)
        if self.state_manager.is_token_used(token_str):
            from .exceptions import TokenReplayError
            raise TokenReplayError(token_str[:16])
        
        # Perform atomic advancement
        def do_advance(status):
            # Re-check replay within lock to prevent concurrent replay
            token_hash = self.state_manager._hash_token(token_str)
            if self.state_manager.is_token_used(token_str):
                raise GateBypassError("Token replay detected during atomic operation")
            
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
        
        # Execute atomic update
        self.state_manager.atomic_update(sprint_id, do_advance)
        
        # Mark token as used AFTER successful advancement (separate lock but after commit)
        self.state_manager.mark_token_used(token_str, sprint_id, gate, user_id)

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
