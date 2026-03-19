"""
Gate enforcement with hardware-backed key storage.

Provides token-based validation enforcement using macOS Keychain
for secure key storage instead of file-based storage.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .gate_key_storage import GateKeyStorage


class GateValidationError(Exception):
    """Raised when gate validation fails."""

    def __init__(self, message: str, gate_number: str | None = None) -> None:
        super().__init__(message)
        self.gate_number = gate_number
        self.message = message


class GateEnforcer:
    """
    Enforces gate validation using secure token-based mechanism.

    Keys are stored in macOS Keychain for hardware-backed security.
    Supports migration from legacy file-based storage.
    """

    LEGACY_KEY_FILE: str = ".gate_key"

    def __init__(self, sprint_data: dict[str, Any] | Path, sprint_path: Path | None = None):
        """
        Initialize gate enforcer.

        Args:
            sprint_data: Sprint data dict OR path to sprint directory
            sprint_path: Optional path to sprint directory (if sprint_data is dict)
        """
        if isinstance(sprint_data, Path):
            self.sprint_path: Path = sprint_data
            self.sprint_data: dict[str, Any] = {}
        else:
            self.sprint_data = sprint_data
            self.sprint_path = sprint_path or Path()

        self._migrate_if_needed()

    def _migrate_if_needed(self) -> None:
        """
        Migrate existing keys from file-based to Keychain storage.

        This runs once on first access to migrate legacy keys.
        """
        legacy_key_path: Path = self.sprint_path / self.LEGACY_KEY_FILE

        if legacy_key_path.exists():
            # Check if key already in Keychain
            if not GateKeyStorage.key_exists():
                try:
                    with open(legacy_key_path, "r") as f:
                        legacy_key: str = f.read().strip()

                    if legacy_key:
                        # Migrate to Keychain
                        GateKeyStorage.store_key(legacy_key)
                        print(f"Migrated gate key to Keychain for {self.sprint_path.name}")

                    # Remove legacy file after successful migration
                    legacy_key_path.unlink()

                except Exception as e:
                    print(f"Warning: Failed to migrate legacy key: {e}")
            else:
                # Key already in Keychain, just remove legacy file
                try:
                    legacy_key_path.unlink()
                except Exception:
                    pass

    def validate_gate(self, gate_number: str) -> None:
        """
        Validate that a gate can be passed.

        Raises:
            GateValidationError: If validation fails.
        """
        # Check if gate already passed
        gates: dict[str, dict[str, Any]] = self.sprint_data.get("gates", {})
        gate_info: dict[str, Any] = gates.get(gate_number, {})

        if gate_info.get("status") == "passed":
            raise GateValidationError(
                f"Gate {gate_number} already passed",
                gate_number=gate_number
            )

        # Check gate requirements
        can_pass, error_msg = self._check_gate_requirements(gate_number)
        if not can_pass:
            raise GateValidationError(
                f"Cannot pass gate {gate_number}: {error_msg}",
                gate_number=gate_number
            )

    def _check_gate_requirements(
        self, gate_number: str
    ) -> tuple[bool, str | None]:
        """Check if gate requirements are met."""
        requirements: dict[str, dict[str, Any]] = {
            "1": {  # Planning Gate
                "required_status": ["initialized", "planned"],
                "needs_work_items": True,
                "description": "Sprint must be initialized and have work items planned",
            },
            "2": {  # Design Gate
                "required_status": ["planned"],
                "needs_work_items": True,
                "description": "Sprint must be planned",
            },
            "3": {  # Implementation Gate
                "required_status": ["running"],
                "needs_work_items": True,
                "description": "Sprint must be running",
            },
            "4": {  # Validation Gate
                "required_status": ["running"],
                "needs_work_items": True,
                "description": "Sprint must be running and work items in progress/completed",
            },
            "5": {  # Release Gate
                "required_status": ["running"],
                "needs_work_items": True,
                "description": "Sprint must be running with completed work items",
            },
        }

        req: dict[str, Any] | None = requirements.get(gate_number)
        if not req:
            return False, f"Unknown gate number: {gate_number}"

        current_status: str = self.sprint_data.get("status", "")
        if current_status not in req["required_status"]:
            return (
                False,
                f"Sprint status is '{current_status}', required: {req['required_status']}"
            )

        if req["needs_work_items"] and not self.sprint_data.get("work_items"):
            return False, "No work items planned"

        return True, None

    def store_validation_key(self, key: str) -> bool:
        """Store validation key in Keychain."""
        return GateKeyStorage.store_key(key)

    def retrieve_validation_key(self) -> Optional[str]:
        """Retrieve validation key from Keychain."""
        return GateKeyStorage.retrieve_key()

    def validate_token(self, token: str) -> bool:
        """Validate a gate token against stored key."""
        stored_key: Optional[str] = self.retrieve_validation_key()
        if not stored_key:
            return False
        return token == stored_key

    def generate_validation_token(self, gate_number: str, tier: int) -> str:
        """Generate a new validation token for a gate."""
        import uuid
        token_id: str = str(uuid.uuid4())[:8]
        token: str = f"val-tier{tier}-{gate_number}-{token_id}"
        self.store_validation_key(token)
        return token

    def get_gate_status(self, gate_number: str) -> dict[str, Any]:
        """Get the status of a specific gate."""
        gate_file: Path = self.sprint_path / "gates" / f"gate_{gate_number}.json"
        if not gate_file.exists():
            return {"status": "pending", "passed": False}
        try:
            with open(gate_file, "r") as f:
                data: dict[str, Any] = json.load(f)
                return {
                    "status": data.get("status", "pending"),
                    "passed": data.get("status") == "passed",
                    "tier": data.get("tier", 1),
                    "risk_score": data.get("risk_score", 0.0),
                    "validation_token": data.get("validation_token"),
                    "passed_at": data.get("passed_at"),
                }
        except (json.JSONDecodeError, IOError):
            return {"status": "error", "passed": False}

    def record_gate_pass(
        self,
        gate_number: str,
        tier: int,
        risk_score: float,
        forced: bool = False
    ) -> dict[str, Any]:
        """Record a gate pass with validation token."""
        from datetime import datetime
        token: str = self.generate_validation_token(gate_number, tier)
        record: dict[str, Any] = {
            "status": "passed",
            "gate_number": gate_number,
            "tier": tier,
            "risk_score": risk_score,
            "validation_token": token,
            "passed_at": datetime.now().isoformat(),
            "forced": forced,
        }
        gate_dir: Path = self.sprint_path / "gates"
        gate_dir.mkdir(parents=True, exist_ok=True)
        gate_file: Path = gate_dir / f"gate_{gate_number}.json"
        with open(gate_file, "w") as f:
            json.dump(record, f, indent=2)
        return record
