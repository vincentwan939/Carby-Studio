"""Gate state persistence and management with thread-safe operations."""
import json
import hashlib
import os
import hmac
import secrets
from datetime import datetime, timedelta
from typing import Dict, Any, Set, Generator, Optional
from pathlib import Path
from contextlib import contextmanager

from .lock_manager import DistributedLock


# Token retention configuration
DEFAULT_TOKEN_RETENTION_DAYS = 90
TOKEN_RETENTION_DAYS = int(os.environ.get("CARBY_TOKEN_RETENTION_DAYS", DEFAULT_TOKEN_RETENTION_DAYS))

# Periodic cleanup trigger: cleanup every N token operations
# Set to 0 to disable periodic cleanup
TOKEN_CLEANUP_INTERVAL = int(os.environ.get("CARBY_TOKEN_CLEANUP_INTERVAL", 100))


class StateTamperError(Exception):
    """Raised when state file integrity check fails (tampering detected)."""
    pass


class StateIntegrityManager:
    """
    Manages HMAC-based integrity protection for state files.
    
    Uses a master key stored in a protected location to sign and verify
    state file contents. Prevents tampering by detecting any modifications.
    """
    
    def __init__(self, project_dir: Path):
        """
        Initialize the integrity manager.
        
        Args:
            project_dir: Project directory path where state files are stored
        """
        self.project_dir = project_dir
        self.sprint_dir = project_dir / ".carby-sprints"
        self.sprint_dir.mkdir(exist_ok=True)
        
        # Master signature file stores HMAC keys and file signatures
        self.master_file = self.sprint_dir / ".state-signatures.json"
        self._key = self._load_or_create_key()
    
    def _load_or_create_key(self) -> bytes:
        """
        Load existing HMAC key or create a new one.
        
        The key is stored in a separate file with restricted permissions.
        
        Returns:
            32-byte HMAC key
        """
        key_file = self.sprint_dir / ".state-key"
        
        if key_file.exists():
            # Read existing key with restricted permissions
            key_data = key_file.read_bytes()
            # Key is stored as hex, convert back to bytes
            return bytes.fromhex(key_data.decode().strip())
        else:
            # Generate new 256-bit key
            key = secrets.token_bytes(32)
            # Store as hex with restricted permissions (owner read/write only)
            key_file.write_text(key.hex())
            os.chmod(key_file, 0o600)  # Owner read/write only
            return key
    
    def _compute_signature(self, data: Dict[str, Any]) -> str:
        """
        Compute HMAC-SHA256 signature for state data.
        
        Args:
            data: State data dictionary
            
        Returns:
            Hex-encoded HMAC signature
        """
        # Canonical JSON representation (sorted keys, no extra whitespace)
        canonical = json.dumps(data, sort_keys=True, separators=(',', ':'))
        signature = hmac.new(
            self._key,
            canonical.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def sign_state(self, state_file: Path, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign state data and return wrapped data with signature.
        
        Args:
            state_file: Path to the state file (for tracking)
            data: State data to sign
            
        Returns:
            Dictionary with '_integrity' metadata and 'data' payload
        """
        signature = self._compute_signature(data)
        
        wrapped = {
            "_integrity": {
                "version": 1,
                "algorithm": "HMAC-SHA256",
                "signature": signature,
                "file": str(state_file.name),
                "signed_at": datetime.utcnow().isoformat()
            },
            "data": data
        }
        
        # Also update master signature file for cross-check
        self._update_master_signature(state_file, signature)
        
        return wrapped
    
    def verify_state(self, state_file: Path, wrapped_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Verify state data integrity and return the unwrapped data.
        
        Args:
            state_file: Path to the state file
            wrapped_data: Wrapped state data with integrity metadata
            
        Returns:
            The original state data if verification passes
            
        Raises:
            StateTamperError: If integrity check fails
        """
        # Check if this is signed data
        if "_integrity" not in wrapped_data:
            # Legacy unsigned data - reject for security
            raise StateTamperError(
                f"State file {state_file.name} has no integrity protection. "
                f"This may indicate tampering or an outdated file format."
            )
        
        integrity = wrapped_data["_integrity"]
        data = wrapped_data.get("data", {})
        
        # Verify signature
        expected_sig = self._compute_signature(data)
        stored_sig = integrity.get("signature", "")
        
        if not hmac.compare_digest(expected_sig, stored_sig):
            raise StateTamperError(
                f"State file {state_file.name} has been tampered with! "
                f"Signature mismatch detected. Expected: {expected_sig[:16]}..., "
                f"Found: {stored_sig[:16]}..."
            )
        
        # Cross-check with master signature file
        master_sig = self._get_master_signature(state_file)
        if master_sig and not hmac.compare_digest(expected_sig, master_sig):
            raise StateTamperError(
                f"State file {state_file.name} signature does not match master record. "
                f"This may indicate targeted tampering."
            )
        
        return data
    
    def _update_master_signature(self, state_file: Path, signature: str) -> None:
        """
        Update the master signature file with the latest signature.
        
        Args:
            state_file: Path to the state file
            signature: HMAC signature to store
        """
        master_data = {}
        if self.master_file.exists():
            try:
                master_data = json.loads(self.master_file.read_text())
            except (json.JSONDecodeError, IOError):
                master_data = {}
        
        # Store signature with timestamp
        master_data[state_file.name] = {
            "signature": signature,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        # Write with atomic update
        temp_file = self.master_file.with_suffix('.tmp')
        temp_file.write_text(json.dumps(master_data, indent=2))
        temp_file.rename(self.master_file)
        os.chmod(self.master_file, 0o600)  # Owner read/write only
    
    def _get_master_signature(self, state_file: Path) -> Optional[str]:
        """
        Get the master signature for a state file.
        
        Args:
            state_file: Path to the state file
            
        Returns:
            Stored signature or None if not found
        """
        if not self.master_file.exists():
            return None
        
        try:
            master_data = json.loads(self.master_file.read_text())
            entry = master_data.get(state_file.name, {})
            return entry.get("signature")
        except (json.JSONDecodeError, IOError):
            return None
    
    def verify_all_states(self) -> Dict[str, Any]:
        """
        Verify all tracked state files.
        
        Returns:
            Dictionary with verification results
        """
        results = {
            "verified": [],
            "failed": [],
            "missing": []
        }
        
        if not self.master_file.exists():
            return results
        
        try:
            master_data = json.loads(self.master_file.read_text())
        except (json.JSONDecodeError, IOError):
            return results
        
        for filename, entry in master_data.items():
            state_file = self.sprint_dir / filename
            if not state_file.exists():
                results["missing"].append(filename)
                continue
            
            try:
                wrapped_data = json.loads(state_file.read_text())
                self.verify_state(state_file, wrapped_data)
                results["verified"].append(filename)
            except StateTamperError as e:
                results["failed"].append({"file": filename, "error": str(e)})
            except (json.JSONDecodeError, IOError) as e:
                results["failed"].append({"file": filename, "error": f"Read error: {e}"})
        
        return results


class GateStateManager:
    """Manages gate status files with locking for thread-safe operations."""
    
    # Allowed base directories for sprint projects
    # These are the only locations where .carby-sprints directories can be created
    ALLOWED_BASE_DIRS = None  # Initialized in __init__ to expand ~ properly
    
    def __init__(self, project_dir: str):
        """
        Initialize the gate state manager.
        
        Args:
            project_dir: Project directory path
            
        Raises:
            ValueError: If path traversal is detected or path is outside allowed directories
        """
        # Initialize allowed directories (done once, with proper ~ expansion)
        # IMPORTANT: Include both symlink paths and their resolved targets
        # On macOS, /tmp -> /private/tmp and /var -> /private/var
        if GateStateManager.ALLOWED_BASE_DIRS is None:
            home_openclaw = os.path.expanduser("~/.openclaw")
            GateStateManager.ALLOWED_BASE_DIRS = [
                home_openclaw,
                # Temp directories for testing (include resolved paths for macOS)
                "/tmp",
                "/private/tmp",
                "/var/folders",
                "/private/var/folders",
            ]
            # Also add the resolved version of home_openclaw
            resolved_home = str(Path(home_openclaw).resolve())
            if resolved_home not in GateStateManager.ALLOWED_BASE_DIRS:
                GateStateManager.ALLOWED_BASE_DIRS.append(resolved_home)
        
        # CRITICAL: Resolve path BEFORE any validation to prevent:
        # 1. Path traversal via ".." sequences (e.g., "/tmp/../etc/passwd")
        # 2. Symlink attacks that escape allowed directories
        # Also check raw input for dangerous characters that won't be caught by resolve:
        # - '~' which could expand to user's home directory unpredictably
        
        # Check for dangerous characters in raw input that resolve() won't handle properly
        if '~' in str(project_dir):
            raise ValueError(
                f"Invalid project_dir: path traversal detected. "
                f"Input contains '~' which may expand unpredictably. "
                f"Original input: '{project_dir}'"
            )
        
        resolved = Path(project_dir).resolve()
        resolved_str = str(resolved)
        
        # Validate the RESOLVED path, not the raw input
        # This prevents both ".." traversal and symlink-based attacks
        if not self._is_path_allowed(resolved_str):
            raise ValueError(
                f"Invalid project_dir: path traversal detected. "
                f"Resolved path '{resolved_str}' is outside allowed directories. "
                f"Original input: '{project_dir}'"
            )

        self.project_dir = resolved
        self.sprint_dir = self.project_dir / ".carby-sprints"
        self.sprint_dir.mkdir(exist_ok=True)
        
        # Initialize integrity manager for tamper detection
        self._integrity = StateIntegrityManager(self.project_dir)
        
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
        
        # Token replay protection registry
        self.token_registry_file = self.sprint_dir / "token-registry.json"
        
        # Token operation counter for periodic cleanup
        self._token_ops_counter = 0
    
    def _is_path_allowed(self, resolved_path: str) -> bool:
        """
        Check if a resolved path is within allowed directories.
        
        This validation happens AFTER path resolution to prevent:
        - Path traversal via ".." sequences (e.g., "/tmp/../etc/passwd")
        - Symlink attacks (e.g., "/tmp/link_to_etc/passwd" where link_to_etc -> /etc)
        
        Args:
            resolved_path: The fully resolved (canonical) path to validate
            
        Returns:
            True if the path is within an allowed directory, False otherwise
        """
        # Normalize the resolved path for comparison
        normalized = os.path.normpath(resolved_path)
        
        # Check against each allowed base directory
        for allowed_base in self.ALLOWED_BASE_DIRS:
            # Normalize the allowed base for comparison
            normalized_base = os.path.normpath(allowed_base)
            
            # Path is allowed if it's the base itself or a subdirectory
            if normalized == normalized_base:
                return True
            if normalized.startswith(normalized_base + os.sep):
                return True
        
        return False
    
    @property
    def _lock_path(self) -> Path:
        """Get the lock file path for gate status operations."""
        return self.sprint_dir / ".gate-status.lock"
    
    @property
    def _token_lock_path(self) -> Path:
        """Get the lock file path for token registry operations."""
        return self.sprint_dir / ".token-registry.lock"
    
    @contextmanager
    def _gate_lock(self) -> Generator[None, None, None]:
        """
        Context manager to acquire the gate status lock.
        
        This ensures that all read-modify-write operations are atomic
        and prevents TOCTOU race conditions.
        
        Usage:
            with self._gate_lock():
                status = self._load_gate_status()
                # modify status
                self._save_gate_status(status)
        """
        with DistributedLock(self._lock_path):
            yield
    
    @contextmanager
    def _token_lock(self) -> Generator[None, None, None]:
        """
        Context manager to acquire the token registry lock.
        
        Ensures atomic operations on the token replay protection registry.
        """
        with DistributedLock(self._token_lock_path):
            yield
    
    def _load_gate_status(self) -> Dict[str, Any]:
        """
        Load current gate status from file with integrity verification.
        
        WARNING: This method MUST be called while holding the gate lock
        via `_gate_lock()` context manager. Calling without the lock
        exposes a TOCTOU race condition.
        
        Returns:
            Dictionary of gate status data
            
        Raises:
            StateTamperError: If integrity check fails (tampering detected)
        """
        if self.status_file.exists():
            try:
                wrapped_data = json.loads(self.status_file.read_text())
                return self._integrity.verify_state(self.status_file, wrapped_data)
            except StateTamperError:
                raise  # Re-raise tamper errors
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_gate_status(self, status: Dict[str, Any]) -> None:
        """
        Save gate status to file with integrity protection.
        
        WARNING: This method MUST be called while holding the gate lock
        via `_gate_lock()` context manager. Calling without the lock
        could result in data corruption or lost updates.
        
        Args:
            status: Dictionary of gate status data to save
        """
        # Sign the data before saving
        wrapped_data = self._integrity.sign_state(self.status_file, status)
        self.status_file.write_text(json.dumps(wrapped_data, indent=2))
    
    def _load_token_registry(self) -> Dict[str, Any]:
        """
        Load token registry from file with integrity verification.
        
        WARNING: Must be called while holding `_token_lock()`.
        
        Returns:
            Dictionary mapping token hashes to usage info
            
        Raises:
            StateTamperError: If integrity check fails (tampering detected)
        """
        if self.token_registry_file.exists():
            try:
                wrapped_data = json.loads(self.token_registry_file.read_text())
                return self._integrity.verify_state(self.token_registry_file, wrapped_data)
            except StateTamperError:
                raise  # Re-raise tamper errors
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def _save_token_registry(self, registry: Dict[str, Any]) -> None:
        """
        Save token registry to file with integrity protection.
        
        WARNING: Must be called while holding `_token_lock()`.
        
        Args:
            registry: Dictionary of token usage data
        """
        # Sign the data before saving
        wrapped_data = self._integrity.sign_state(self.token_registry_file, registry)
        self.token_registry_file.write_text(json.dumps(wrapped_data, indent=2))
    
    def _hash_token(self, token: str) -> str:
        """
        Create a hash of a token for registry storage.
        
        We hash tokens to prevent the registry itself from containing
        usable token data that could be exploited.
        
        Args:
            token: Token string to hash
            
        Returns:
            SHA-256 hash of the token
        """
        return hashlib.sha256(token.encode()).hexdigest()
    
    def is_token_used(self, token: str) -> bool:
        """
        Check if a token has already been used (replay attack prevention).
        
        Thread-safe: Acquires lock for atomic read.
        
        Args:
            token: Token string to check
            
        Returns:
            True if token has been used, False otherwise
        """
        token_hash = self._hash_token(token)
        with self._token_lock():
            registry = self._load_token_registry()
            return token_hash in registry
    
    def mark_token_used(self, token: str, sprint_id: str, gate: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Mark a token as used to prevent replay attacks.

        Thread-safe: Acquires lock for atomic read-modify-write.

        Args:
            token: Token string to mark as used
            sprint_id: Sprint that used the token
            gate: Gate that was advanced using this token
            user_id: ID of the user who used the token
        
        Returns:
            Cleanup results if periodic cleanup was triggered, None otherwise
        """
        token_hash = self._hash_token(token)
        with self._token_lock():
            registry = self._load_token_registry()
            registry[token_hash] = {
                "sprint_id": sprint_id,
                "gate": gate,
                "used_at": datetime.utcnow().isoformat(),
                "user_id": user_id or "system",
            }
            self._save_token_registry(registry)
        
        # Trigger periodic cleanup outside the lock to avoid holding it during cleanup
        return self._maybe_cleanup_tokens()
    
    def get_current_gate(self, sprint_id: str) -> str:
        """
        Get the current gate for a sprint.
        
        Thread-safe: Acquires lock for atomic read.
        
        Args:
            sprint_id: Sprint identifier
            
        Returns:
            Current gate name
        """
        with self._gate_lock():
            status = self._load_gate_status()
            return status.get(sprint_id, {}).get("current_gate", self.gate_sequence[0])
    
    def set_current_gate(self, sprint_id: str, gate: str) -> None:
        """
        Set the current gate for a sprint.
        
        Thread-safe: Acquires lock for atomic read-modify-write.
        
        Args:
            sprint_id: Sprint identifier
            gate: Gate name to set
        """
        with self._gate_lock():
            status = self._load_gate_status()
            if sprint_id not in status:
                status[sprint_id] = {}
            status[sprint_id]["current_gate"] = gate
            status[sprint_id]["updated_at"] = datetime.utcnow().isoformat()
            self._save_gate_status(status)
    
    def record_gate_completion(self, sprint_id: str, gate: str, token: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Record that a gate has been completed.

        Thread-safe: Acquires lock for atomic read-modify-write.

        Args:
            sprint_id: Sprint identifier
            gate: Gate name that was completed
            token: Token used to complete the gate
            user_id: ID of the user who completed the gate
        
        Returns:
            Cleanup results if sprint completion triggered cleanup, None otherwise
        """
        with self._gate_lock():
            status = self._load_gate_status()
            if sprint_id not in status:
                status[sprint_id] = {}

            if "completed_gates" not in status[sprint_id]:
                status[sprint_id]["completed_gates"] = []

            status[sprint_id]["completed_gates"].append({
                "gate": gate,
                "completed_at": datetime.utcnow().isoformat(),
                "token_hash": self._hash_token(token),  # Full SHA-256 hash for forensic correlation
                "user_id": user_id or "system",
            })

            self._save_gate_status(status)
        
        # Trigger cleanup on sprint completion (delivery gate)
        if gate == "delivery":
            return self.cleanup_expired_tokens(dry_run=False)
        
        return None
    
    def is_gate_completed(self, sprint_id: str, gate: str) -> bool:
        """
        Check if a specific gate has been completed.
        
        Thread-safe: Acquires lock for atomic read.
        
        Args:
            sprint_id: Sprint identifier
            gate: Gate name to check
            
        Returns:
            True if gate has been completed, False otherwise
        """
        with self._gate_lock():
            status = self._load_gate_status()
            completed_gates = status.get(sprint_id, {}).get("completed_gates", [])
            return any(g["gate"] == gate for g in completed_gates)
    
    def get_completed_gates(self, sprint_id: str) -> list:
        """
        Get list of completed gates for a sprint.
        
        Thread-safe: Acquires lock for atomic read.
        
        Args:
            sprint_id: Sprint identifier
            
        Returns:
            List of completed gate names
        """
        with self._gate_lock():
            status = self._load_gate_status()
            completed = status.get(sprint_id, {}).get("completed_gates", [])
            return [g["gate"] for g in completed]
    
    def get_gate_status(self, sprint_id: str) -> Dict[str, Any]:
        """
        Get the current status of gates for a sprint.
        
        Thread-safe: Acquires lock for atomic read.
        
        Args:
            sprint_id: Sprint identifier
        
        Returns:
            Gate status information with:
            - sprint_id: Sprint identifier
            - current_gate: Current gate name
            - next_gate: Next gate in sequence (or None)
            - completed_gates: List of completed gate names
            - can_advance: Whether advancement is possible
            - project_dir: Project directory path
            - updated_at: Last update timestamp
        """
        with self._gate_lock():
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
    
    def atomic_update(self, sprint_id: str, update_func) -> Any:
        """
        Perform an atomic read-modify-write operation on gate status.
        
        This method provides a safe way to perform complex updates that
        require reading the current state, modifying it, and writing it back
        atomically.
        
        Thread-safe: Acquires lock for the entire operation.
        
        Args:
            sprint_id: Sprint identifier
            update_func: Callable that takes the current status dict and
                        returns the modified status dict. The function
                        receives the full status dict and should modify
                        the entry for sprint_id.
        
        Returns:
            The return value of update_func
        
        Example:
            def mark_gate_done(status):
                if sprint_id not in status:
                    status[sprint_id] = {}
                status[sprint_id]['done'] = True
                return status
            
            manager.atomic_update("my-sprint", mark_gate_done)
        """
        with self._gate_lock():
            status = self._load_gate_status()
            result = update_func(status)
            self._save_gate_status(status)
            return result
    
    def verify_state_integrity(self) -> Dict[str, Any]:
        """
        Verify integrity of all state files.
        
        Returns:
            Dictionary with verification results containing:
            - verified: List of files that passed verification
            - failed: List of files that failed verification with error details
            - missing: List of files tracked but missing
        """
        return self._integrity.verify_all_states()
    
    def cleanup_expired_tokens(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Remove tokens older than the retention period from the registry.
        
        This cleanup only removes entries from the token registry, not from
        the audit trail (gate-status.json completed_gates). The audit trail
        is preserved for forensic purposes.
        
        Thread-safe: Acquires token lock for atomic read-modify-write.
        
        Args:
            dry_run: If True, return what would be cleaned without modifying
        
        Returns:
            Dictionary with cleanup results:
            - removed: Number of tokens removed
            - retained: Number of tokens kept
            - removed_tokens: List of removed token hashes (for logging)
            - retention_days: Retention policy in days
            - cutoff_date: ISO timestamp of the cutoff
        """
        cutoff_date = datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS)
        cutoff_iso = cutoff_date.isoformat()
        
        with self._token_lock():
            registry = self._load_token_registry()
            
            to_remove = []
            retained = 0
            
            for token_hash, info in registry.items():
                used_at = info.get("used_at", "")
                # Parse the ISO timestamp
                try:
                    token_date = datetime.fromisoformat(used_at)
                    if token_date < cutoff_date:
                        to_remove.append(token_hash)
                    else:
                        retained += 1
                except (ValueError, TypeError):
                    # If we can't parse the date, keep the token (safer)
                    retained += 1
            
            result = {
                "removed": len(to_remove),
                "retained": retained,
                "removed_tokens": to_remove if dry_run else [f"{t[:16]}..." for t in to_remove],
                "retention_days": TOKEN_RETENTION_DAYS,
                "cutoff_date": cutoff_iso,
                "dry_run": dry_run,
            }
            
            if not dry_run and to_remove:
                for token_hash in to_remove:
                    del registry[token_hash]
                self._save_token_registry(registry)
            
            return result
    
    def get_token_registry_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the token registry.
        
        Returns:
            Dictionary with:
            - total_tokens: Total number of tokens in registry
            - oldest_token: ISO timestamp of oldest token (or None)
            - newest_token: ISO timestamp of newest token (or None)
            - retention_days: Current retention policy
            - would_cleanup: Number of tokens that would be cleaned
        """
        with self._token_lock():
            registry = self._load_token_registry()
            
            if not registry:
                return {
                    "total_tokens": 0,
                    "oldest_token": None,
                    "newest_token": None,
                    "retention_days": TOKEN_RETENTION_DAYS,
                    "would_cleanup": 0,
                }
            
            timestamps = []
            for info in registry.values():
                used_at = info.get("used_at", "")
                try:
                    timestamps.append(datetime.fromisoformat(used_at))
                except (ValueError, TypeError):
                    pass
            
            cutoff_date = datetime.utcnow() - timedelta(days=TOKEN_RETENTION_DAYS)
            would_cleanup = sum(1 for t in timestamps if t < cutoff_date)
            
            return {
                "total_tokens": len(registry),
                "oldest_token": min(timestamps).isoformat() if timestamps else None,
                "newest_token": max(timestamps).isoformat() if timestamps else None,
                "retention_days": TOKEN_RETENTION_DAYS,
                "would_cleanup": would_cleanup,
            }
    
    def _maybe_cleanup_tokens(self) -> Optional[Dict[str, Any]]:
        """
        Trigger periodic cleanup if the operation counter threshold is reached.
        
        This is called automatically after token operations.
        
        Returns:
            Cleanup results if cleanup was triggered, None otherwise
        """
        if TOKEN_CLEANUP_INTERVAL <= 0:
            return None
        
        self._token_ops_counter += 1
        
        if self._token_ops_counter >= TOKEN_CLEANUP_INTERVAL:
            self._token_ops_counter = 0
            return self.cleanup_expired_tokens(dry_run=False)
        
        return None