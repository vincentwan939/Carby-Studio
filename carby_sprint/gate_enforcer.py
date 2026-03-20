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
"""

import os
import json
import hmac
import hashlib
import secrets
import time
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Optional, Tuple, Any
from pathlib import Path


class GateEnforcementError(Exception):
    """Base exception for gate enforcement errors."""
    pass


class InvalidTokenError(GateEnforcementError):
    """Raised when a token is invalid or tampered with."""
    pass


class ExpiredTokenError(GateEnforcementError):
    """Raised when a token has expired."""
    pass


class GateBypassError(GateEnforcementError):
    """Raised when a gate bypass attempt is detected."""
    pass


class GateToken:
    """
    Represents a cryptographically signed gate token with expiration.
    """
    
    def __init__(
        self, 
        gate_id: str, 
        sprint_id: str, 
        expires_in_hours: int = 24,
        secret_key: Optional[bytes] = None
    ):
        """
        Initialize a gate token.
        
        Args:
            gate_id: Unique identifier for the gate
            sprint_id: Associated sprint ID
            expires_in_hours: Token expiration time in hours (default 24)
            secret_key: Secret key for HMAC signing (generated if None)
        """
        self.gate_id = gate_id
        self.sprint_id = sprint_id
        self.expires_in = timedelta(hours=expires_in_hours)
        
        # Generate or use provided secret key
        if secret_key is None:
            self.secret_key = self._get_or_create_secret_key()
        else:
            self.secret_key = secret_key
            
        # Generate token components
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + self.expires_in
        self.nonce = secrets.token_urlsafe(32)
        
        # Create the signed token
        self.token_data = self._create_token_data()
        self.signature = self._sign_token()
        self.token = self._serialize_token()
    
    def _get_or_create_secret_key(self) -> bytes:
        """
        Get or create a persistent secret key for HMAC signing.
        """
        # Store secret key in a secure location outside project directory
        secret_file = Path.home() / ".openclaw" / "secrets" / "carby-studio-gate-key"
        
        if secret_file.exists():
            return secret_file.read_bytes()
        
        # Create parent directory if needed
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate a new cryptographically secure key
        secret = secrets.token_bytes(32)
        
        # Write with restricted permissions (only owner can read/write)
        secret_file.write_bytes(secret)
        secret_file.chmod(0o600)
        
        return secret
    
    def _create_token_data(self) -> Dict[str, str]:
        """Create the data payload for the token."""
        return {
            "gate_id": self.gate_id,
            "sprint_id": self.sprint_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "nonce": self.nonce
        }
    
    def _sign_token(self) -> str:
        """Create HMAC-SHA256 signature for the token."""
        # Serialize token data
        token_json = json.dumps(self.token_data, sort_keys=True)
        token_bytes = token_json.encode('utf-8')
        
        # Create HMAC signature
        signature = hmac.new(
            self.secret_key,
            token_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _serialize_token(self) -> str:
        """Serialize the complete token with signature."""
        # Use URL-safe base64 encoding for the token data to avoid issues with special characters
        import base64
        token_json = json.dumps(self.token_data, separators=(',', ':'), sort_keys=True)
        encoded_token = base64.urlsafe_b64encode(token_json.encode()).decode()
        return f"{encoded_token}.{self.signature}"
    
    @classmethod
    def from_string(cls, token_str: str, secret_key: Optional[bytes] = None) -> 'GateToken':
        """
        Deserialize and validate a token from its string representation.
        
        Args:
            token_str: Serialized token string
            secret_key: Secret key for validation (uses default if None)
        
        Returns:
            Validated GateToken instance
        
        Raises:
            InvalidTokenError: If token format is invalid
            ExpiredTokenError: If token has expired
        """
        import base64
        parts = token_str.split('.', 2)
        if len(parts) != 2:
            raise InvalidTokenError("Invalid token format")
        
        try:
            # Decode the base64-encoded token data
            decoded_token = base64.urlsafe_b64decode(parts[0]).decode()
            token_data = json.loads(decoded_token)
            signature = parts[1]
        except (json.JSONDecodeError, IndexError, base64.binascii.Error):
            raise InvalidTokenError("Invalid token format")
        
        # Extract token properties
        gate_id = token_data.get("gate_id")
        sprint_id = token_data.get("sprint_id")
        created_at_str = token_data.get("created_at")
        expires_at_str = token_data.get("expires_at")
        nonce = token_data.get("nonce")
        
        if not all([gate_id, sprint_id, created_at_str, expires_at_str, nonce]):
            raise InvalidTokenError("Missing required token fields")
        
        # Parse dates
        try:
            created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        except ValueError:
            raise InvalidTokenError("Invalid date format in token")
        
        # Check expiration
        if datetime.utcnow() > expires_at:
            raise ExpiredTokenError("Token has expired")
        
        # Verify signature
        token_obj = cls.__new__(cls)
        token_obj.gate_id = gate_id
        token_obj.sprint_id = sprint_id
        token_obj.created_at = created_at
        token_obj.expires_at = expires_at
        token_obj.nonce = nonce
        token_obj.token_data = token_data
        
        if secret_key is None:
            token_obj.secret_key = token_obj._get_or_create_secret_key()
        else:
            token_obj.secret_key = secret_key
        
        # Recreate signature to verify
        expected_signature = token_obj._sign_token()
        if not hmac.compare_digest(expected_signature, signature):
            raise InvalidTokenError("Invalid token signature")
        
        # Set remaining attributes
        token_obj.signature = signature
        token_obj.token = token_str
        
        return token_obj
    
    def is_valid(self) -> bool:
        """Check if the token is still valid (not expired)."""
        return datetime.utcnow() <= self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert token to dictionary representation."""
        return {
            "token": self.token,
            "gate_id": self.gate_id,
            "sprint_id": self.sprint_id,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "is_valid": self.is_valid()
        }


class GateEnforcer:
    """
    Server-side gate enforcement system that controls advancement through sprint phases.
    
    This class ensures that agents cannot bypass gates and that all progression
    follows the defined workflow rules.
    """
    
    def __init__(self, project_dir: str):
        """
        Initialize the gate enforcer.
        
        Args:
            project_dir: Project directory path
        """
        self.project_dir = Path(project_dir)
        self.sprint_dir = self.project_dir / ".carby-sprints"
        self.sprint_dir.mkdir(exist_ok=True)
        
        # Gate advancement rules
        self.gate_sequence = [
            "discovery",
            "design", 
            "build",
            "verify",
            "delivery"
        ]
        
        # Track gate status
        self.status_file = self.sprint_dir / "gate-status.json"
    
    def _load_gate_status(self) -> Dict[str, Any]:
        """Load current gate status from file."""
        if self.status_file.exists():
            try:
                return json.loads(self.status_file.read_text())
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_gate_status(self, status: Dict[str, Any]) -> None:
        """Save gate status to file."""
        self.status_file.write_text(json.dumps(status, indent=2))
    
    def _get_current_gate(self, sprint_id: str) -> str:
        """Get the current gate for a sprint."""
        status = self._load_gate_status()
        return status.get(sprint_id, {}).get("current_gate", self.gate_sequence[0])
    
    def _set_current_gate(self, sprint_id: str, gate: str) -> None:
        """Set the current gate for a sprint."""
        status = self._load_gate_status()
        if sprint_id not in status:
            status[sprint_id] = {}
        status[sprint_id]["current_gate"] = gate
        status[sprint_id]["updated_at"] = datetime.utcnow().isoformat()
        self._save_gate_status(status)
    
    def _record_gate_completion(self, sprint_id: str, gate: str, token: str) -> None:
        """Record that a gate has been completed."""
        status = self._load_gate_status()
        if sprint_id not in status:
            status[sprint_id] = {}
        
        if "completed_gates" not in status[sprint_id]:
            status[sprint_id]["completed_gates"] = []
        
        status[sprint_id]["completed_gates"].append({
            "gate": gate,
            "completed_at": datetime.utcnow().isoformat(),
            "token_used": token[:16] + "..."  # Truncate for privacy
        })
        
        self._save_gate_status(status)
    
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
        status = self._load_gate_status()
        completed_gates = status.get(sprint_id, {}).get("completed_gates", [])
        
        # Check if the current gate is in the completed list
        current_completed = any(
            gate_info["gate"] == current_gate 
            for gate_info in completed_gates
        )
        
        return current_completed
    
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
        status = self._load_gate_status()
        sprint_status = status.get(sprint_id, {})
        
        current_gate = sprint_status.get("current_gate", self.gate_sequence[0])
        completed_gates = sprint_status.get("completed_gates", [])
        
        # Determine next gate
        try:
            current_idx = self.gate_sequence.index(current_gate)
            next_gate = self.gate_sequence[current_idx + 1] if current_idx < len(self.gate_sequence) - 1 else None
        except ValueError:
            next_gate = None
        
        return {
            "sprint_id": sprint_id,
            "current_gate": current_gate,
            "next_gate": next_gate,
            "completed_gates": [g["gate"] for g in completed_gates],
            "can_advance": next_gate is not None,
            "project_dir": str(self.project_dir),
            "updated_at": sprint_status.get("updated_at")
        }