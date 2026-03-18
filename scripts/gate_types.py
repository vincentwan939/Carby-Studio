"""
GateTypes - Shared types and data classes for gate enforcement.
"""

from dataclasses import dataclass, asdict
from typing import Dict, Any
from enum import Enum


class GateStatus(Enum):
    """Status of a gate check."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


class GateType(Enum):
    """Types of gates in the sprint framework."""
    PREP = "gate-0-prep"
    START = "gate-1-start"
    MID = "gate-2-mid"
    COMPLETE = "gate-3-complete"


@dataclass
class GateSignature:
    """Cryptographic signature for a gate pass."""
    gate_type: str
    sprint_id: str
    timestamp: str
    hmac_signature: str
    nonce: str
    validator_version: str = "1.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GateSignature':
        return cls(**data)


@dataclass
class AuditRecord:
    """Record of a gate decision for audit purposes."""
    id: str
    timestamp: str
    gate_type: str
    sprint_id: str
    project_dir: str
    action: str
    result: str
    signature: Any  # Optional[str]
    details: str
    ip_address: Any = None  # Optional[str]
    user: Any = None  # Optional[str]


class GateEnforcerError(Exception):
    """Base exception for gate enforcer errors."""
    pass


class SignatureVerificationError(GateEnforcerError):
    """Raised when signature verification fails."""
    pass


class GateBypassAttemptError(GateEnforcerError):
    """Raised when a bypass attempt is detected."""
    pass


class GateSequenceError(GateEnforcerError):
    """Raised when gates are attempted out of order."""
    pass
