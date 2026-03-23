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

from typing import Dict, Optional, Tuple, Any

from .exceptions import (
    CarbyStudioError,
    InvalidTokenError,
    ExpiredTokenError,
    GateEnforcementError,
    GateBypassError
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
    
    def _load_gate_status(self) -> Dict[str, Any]:
        """Load current gate status from file."""
        return self.state_manager._load_gate_status()
    
    def _save_gate_status(self, status: Dict[str, Any]) -> None:
        """Save gate status to file with locking."""
        self.state_manager._save_gate_status(status)
    
    def _get_current_gate(self, sprint_id: str) -> str:
        """Get the current gate for a sprint."""
        return self.state_manager.get_current_gate(sprint_id)
    
    def _set_current_gate(self, sprint_id: str, gate: str) -> None:
        """Set the current gate for a sprint."""
        self.state_manager.set_current_gate(sprint_id, gate)
    
    def _record_gate_completion(self, sprint_id: str, gate: str, token: str) -> None:
        """Record that a gate has been completed."""
        self.state_manager.record_gate_completion(sprint_id, gate, token)
    
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
        
        Args:
            token_str: Token string to validate
        
        Returns:
            Tuple of (is_valid, gate_id, sprint_id)
        """
        try:
            token = GateToken.from_string(token_str)
            return True, token.gate_id, token.sprint_id
        except (InvalidTokenError, ExpiredTokenError) as e:
            return False, None, None
    
    def advance_gate(self, sprint_id: str, gate: str, token_str: str) -> bool:
        """
        Advance to the next gate using a valid token.
        
        Args:
            sprint_id: Sprint identifier
            gate: Gate to advance to
            token_str: Valid gate token
        
        Returns:
            True if advancement successful, False otherwise
        
        Raises:
            GateBypassError: If token is invalid or advancement not allowed
        """
        # Validate the token
        is_valid, token_gate, token_sprint = self.validate_gate_token(token_str)
        
        if not is_valid or token_sprint != sprint_id or token_gate != gate:
            raise GateBypassError("Invalid token for gate advancement")
        
        # Get current gate
        current_gate = self._get_current_gate(sprint_id)
        
        # Check if advancement is allowed
        if not self.can_advance(sprint_id, current_gate, gate):
            raise GateBypassError(f"Cannot advance from {current_gate} to {gate}")
        
        # Record completion of current gate and advancement
        self._record_gate_completion(sprint_id, current_gate, token_str)
        self._set_current_gate(sprint_id, gate)
        
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
]
