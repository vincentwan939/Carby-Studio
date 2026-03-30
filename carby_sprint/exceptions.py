"""Standardized exceptions for Carby Studio."""


class CarbyStudioError(Exception):
    """Base exception for all Carby Studio errors."""
    pass


class PhaseBlockedError(CarbyStudioError):
    """Raised when a phase cannot be started due to blocking conditions.
    
    Attributes:
        phase_id: The phase that is blocked
        reason: Human-readable explanation
        resolution: Command or action to resolve
    """
    def __init__(self, phase_id: str, reason: str, resolution: str):
        self.phase_id = phase_id
        self.reason = reason
        self.resolution = resolution
        super().__init__(f"Phase '{phase_id}' blocked: {reason}. {resolution}")


class GateValidationError(CarbyStudioError):
    """Raised when gate validation fails."""
    def __init__(self, gate_id: str, sprint_id: str, details: str):
        self.gate_id = gate_id
        self.sprint_id = sprint_id
        self.details = details
        super().__init__(f"Gate '{gate_id}' validation failed for sprint '{sprint_id}': {details}")


class StateConsistencyError(CarbyStudioError):
    """Raised when state systems are inconsistent."""
    pass


class TokenExpiredError(CarbyStudioError):
    """Raised when a token has expired."""
    pass


class TokenInvalidError(CarbyStudioError):
    """Raised when a token signature is invalid."""
    pass


class GateEnforcementError(CarbyStudioError):
    """Base exception for gate enforcement errors."""
    pass


class GateBypassError(GateEnforcementError):
    """Raised when a gate bypass attempt is detected."""
    pass


class InvalidTokenError(TokenInvalidError, GateEnforcementError):
    """Raised when a token is invalid or tampered with."""
    pass


class ExpiredTokenError(TokenExpiredError, GateEnforcementError):
    """Raised when a token has expired."""
    pass


class TokenReplayError(GateEnforcementError):
    """Raised when a token has already been used (replay attack detected)."""
    def __init__(self, token_prefix: str = ""):
        self.token_prefix = token_prefix
        super().__init__(f"Token replay detected: token '{token_prefix}...' has already been used")
