"""
GateCrypto - Cryptographic operations for gate enforcement.

Handles HMAC signatures, nonce generation, and signature verification.
"""

import hmac
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Tuple

from gate_types import GateType


class GateCrypto:
    """
    Handles all cryptographic operations for gate enforcement.
    
    - HMAC-SHA256 signature generation
    - Cryptographically secure nonce generation
    - Constant-time signature verification
    """
    
    def __init__(self, secret_key: bytes):
        """
        Initialize with a secret key.
        
        Args:
            secret_key: The HMAC secret key (32+ bytes recommended)
        """
        self._secret_key = secret_key
    
    def generate_nonce(self) -> str:
        """Generate a cryptographically secure nonce."""
        return secrets.token_hex(16)
    
    def create_signature(
        self,
        gate_type: GateType,
        sprint_id: str,
        nonce: str
    ) -> Tuple[str, str]:
        """
        Create HMAC-SHA256 signature for a gate pass.
        
        The signature includes:
        - Gate type
        - Sprint ID
        - Timestamp
        - Nonce (prevents replay attacks)
        
        Returns:
            Tuple of (signature, timestamp)
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Create message to sign
        message = f"{gate_type.value}:{sprint_id}:{timestamp}:{nonce}"
        message_bytes = message.encode('utf-8')
        
        # Generate HMAC
        signature = hmac.new(
            self._secret_key,
            message_bytes,
            hashlib.sha256
        ).hexdigest()
        
        return signature, timestamp
    
    def verify_signature(
        self,
        gate_type: GateType,
        sprint_id: str,
        timestamp: str,
        nonce: str,
        signature: str
    ) -> bool:
        """
        Verify an HMAC signature.
        
        Args:
            gate_type: The type of gate
            sprint_id: The sprint ID
            timestamp: ISO timestamp when signature was created
            nonce: The nonce used
            signature: The signature to verify
        
        Returns:
            True if signature is valid
        """
        # Recreate the message
        message = f"{gate_type.value}:{sprint_id}:{timestamp}:{nonce}"
        message_bytes = message.encode('utf-8')
        
        # Generate expected signature
        expected = hmac.new(
            self._secret_key,
            message_bytes,
            hashlib.sha256
        ).hexdigest()
        
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected)
