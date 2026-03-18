"""
GateStorage - File I/O operations for gate enforcement.

Handles secret management, signature file storage, and logging.
"""

import os
import json
import logging
import secrets
from pathlib import Path
from typing import Optional

from gate_types import GateSignature, GateType


class GateStorage:
    """
    Manages file-based storage for gate enforcement.
    
    - Secure secret key storage
    - Signature file read/write
    - Structured logging setup
    """
    
    def __init__(self, sprint_dir: Path, project_name: str):
        """
        Initialize storage.
        
        Args:
            sprint_dir: Path to the .sprint directory
            project_name: Name of the project (for logging)
        """
        self.sprint_dir = sprint_dir
        self.sprint_dir.mkdir(parents=True, exist_ok=True)
        self.project_name = project_name
        self._logger: Optional[logging.Logger] = None
    
    @staticmethod
    def load_or_create_secret(provided_key: Optional[str] = None) -> bytes:
        """
        Load existing secret or create a new one.
        
        Secrets are stored in a secure location outside the project directory
        to prevent accidental commits.
        
        Args:
            provided_key: Optional key to use (will be saved if provided)
        
        Returns:
            The secret key as bytes
        """
        secret_file = Path.home() / ".openclaw" / "secrets" / "gate-enforcer.key"
        
        if provided_key:
            secret = provided_key.encode('utf-8')
            # Save for future use
            secret_file.parent.mkdir(parents=True, exist_ok=True)
            secret_file.write_bytes(secret)
            # Set restrictive permissions
            os.chmod(secret_file, 0o600)
            return secret
        
        if secret_file.exists():
            return secret_file.read_bytes()
        
        # Generate new cryptographically secure key
        secret = secrets.token_bytes(32)
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret_file.write_bytes(secret)
        os.chmod(secret_file, 0o600)
        
        return secret
    
    def get_logger(self) -> logging.Logger:
        """
        Get or create the structured logger.
        
        Returns:
            Configured logger instance
        """
        if self._logger is not None:
            return self._logger
        
        logger = logging.getLogger(f"gate_enforcer.{self.project_name}")
        logger.setLevel(logging.INFO)
        
        # Prevent duplicate handlers
        if logger.handlers:
            self._logger = logger
            return logger
        
        # File handler for audit trail
        log_file = self.sprint_dir / "gate_enforcer.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        self._logger = logger
        return logger
    
    def save_signature(
        self,
        gate_type: GateType,
        sprint_id: str,
        signature: GateSignature
    ) -> Path:
        """
        Save a gate signature to file.
        
        Args:
            gate_type: The type of gate
            sprint_id: The sprint ID
            signature: The signature to save
        
        Returns:
            Path to the saved signature file
        """
        sig_file = self.sprint_dir / f"gate-pass-{gate_type.value}-{sprint_id}.json"
        sig_file.write_text(json.dumps(signature.to_dict(), indent=2))
        return sig_file
    
    def load_signature(
        self,
        gate_type: GateType,
        sprint_id: str
    ) -> Optional[GateSignature]:
        """
        Load a gate signature from file.
        
        Args:
            gate_type: The type of gate
            sprint_id: The sprint ID
        
        Returns:
            The loaded GateSignature, or None if file doesn't exist or is invalid
        """
        sig_file = self.sprint_dir / f"gate-pass-{gate_type.value}-{sprint_id}.json"
        
        if not sig_file.exists():
            return None
        
        try:
            data = json.loads(sig_file.read_text())
            return GateSignature.from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None
    
    def signature_exists(self, gate_type: GateType, sprint_id: str) -> bool:
        """
        Check if a signature file exists.
        
        Args:
            gate_type: The type of gate
            sprint_id: The sprint ID
        
        Returns:
            True if signature file exists
        """
        sig_file = self.sprint_dir / f"gate-pass-{gate_type.value}-{sprint_id}.json"
        return sig_file.exists()
    
    def invalidate_signature(
        self,
        gate_type: GateType,
        sprint_id: str
    ) -> bool:
        """
        Rename a signature file to invalidate it.
        
        Args:
            gate_type: The type of gate
            sprint_id: The sprint ID
        
        Returns:
            True if file was renamed, False if it didn't exist
        """
        sig_file = self.sprint_dir / f"gate-pass-{gate_type.value}-{sprint_id}.json"
        
        if sig_file.exists():
            invalid_file = self.sprint_dir / f"gate-pass-{gate_type.value}-{sprint_id}.invalid"
            sig_file.rename(invalid_file)
            return True
        return False
    
    def get_signature_path(self, gate_type: GateType, sprint_id: str) -> Path:
        """
        Get the path to a signature file.
        
        Args:
            gate_type: The type of gate
            sprint_id: The sprint ID
        
        Returns:
            Path to the signature file (may not exist)
        """
        return self.sprint_dir / f"gate-pass-{gate_type.value}-{sprint_id}.json"
    
    def log_to_file(self, message: str) -> None:
        """
        Log a message to the audit log file.
        
        Args:
            message: The message to log
        """
        logger = self.get_logger()
        logger.info(message)
