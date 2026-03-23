"""HMAC token management for gate enforcement."""
import hmac
import hashlib
import json
import base64
import secrets
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from pathlib import Path

from .exceptions import InvalidTokenError, ExpiredTokenError


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
        
        # Create token object for signature verification
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
        
        # Verify signature FIRST (prevents timing attacks on expiration)
        expected_signature = token_obj._sign_token()
        if not hmac.compare_digest(expected_signature, signature):
            raise InvalidTokenError("Invalid token signature")
        
        # Check expiration AFTER signature verification
        if datetime.utcnow() > expires_at:
            raise ExpiredTokenError("Token has expired")
        
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


class DesignApprovalToken(GateToken):
    """
    Token issued when design phase is explicitly approved.
    Required before Build phase can start.
    """
    
    def __init__(self, sprint_id: str, design_version: str, approver: str = "user"):
        super().__init__(
            gate_id="design-approval",
            sprint_id=sprint_id,
            expires_in_hours=168  # 7 days
        )
        self.design_version = design_version
        self.approver = approver
        self.approved_at = datetime.utcnow().isoformat()
        
    def to_dict(self) -> Dict[str, Any]:
        """Serialize token with design-specific metadata."""
        base = super().to_dict()
        base.update({
            "design_version": self.design_version,
            "approver": self.approver,
            "approved_at": self.approved_at,
            "spec_path": f"docs/carby/specs/{self.sprint_id}-design.md"
        })
        return base
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DesignApprovalToken':
        """Deserialize from dictionary."""
        token = cls.__new__(cls)
        token.gate_id = data.get("gate_id", "design-approval")
        token.sprint_id = data.get("sprint_id", "")
        token.design_version = data.get("design_version", "")
        token.approver = data.get("approver", "user")
        token.approved_at = data.get("approved_at", "")
        token.token = data.get("token", "")
        
        # Parse dates - handle both with and without timezone
        expires_at_str = data.get("expires_at", datetime.utcnow().isoformat())
        created_at_str = data.get("created_at", datetime.utcnow().isoformat())
        
        try:
            token.expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
        except ValueError:
            token.expires_at = datetime.utcnow() + timedelta(hours=168)
        
        try:
            token.created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
        except ValueError:
            token.created_at = datetime.utcnow()
            
        return token