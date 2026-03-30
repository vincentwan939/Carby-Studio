"""
Signed audit log with hash chain and HMAC verification.

Provides tamper-evident audit logging using SHA-256 hash chains
and HMAC-SHA256 signatures for integrity verification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class AuditEntry:
    """Represents a single audit log entry."""
    timestamp: str
    event_type: str
    sprint_id: str
    details: dict[str, Any]
    previous_hash: str
    entry_hash: str
    signature: str
    user_id: str = "system"


class SignedAuditLog:
    """
    Tamper-evident audit log using hash chains and HMAC signatures.

    Each entry contains:
    - Event data (timestamp, type, sprint_id, details)
    - Previous entry's hash (forms the chain)
    - Current entry hash (SHA-256 of all fields)
    - HMAC-SHA256 signature for integrity
    """

    def __init__(self, db_path: Path | str, key: Optional[str] = None):
        """
        Initialize the signed audit log.

        Args:
            db_path: Path to SQLite database file
            key: HMAC key for signing (auto-generated if not provided)
        """
        self.db_path: Path = Path(db_path)
        self.key: bytes = (key or self._get_or_create_key()).encode()
        self._init_db()

    def _get_or_create_key(self) -> str:
        """Get existing HMAC key or create new one."""
        # Try to get key from environment
        env_key: Optional[str] = os.environ.get("CARBY_AUDIT_KEY")
        if env_key:
            return env_key

        # Check for key file (for migration/compatibility)
        key_file: Path = self.db_path.parent / ".audit_key"
        if key_file.exists():
            with open(key_file, "r") as f:
                return f.read().strip()

        # Generate new key
        new_key: str = hashlib.sha256(os.urandom(32)).hexdigest()[:32]

        # Store in environment for this session
        os.environ["CARBY_AUDIT_KEY"] = new_key

        return new_key

    def _init_db(self) -> None:
        """Initialize the SQLite database with audit log table."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    sprint_id TEXT NOT NULL,
                    details TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    user_id TEXT NOT NULL DEFAULT 'system'
                )
            """)

            # Create index for faster lookups
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sprint_id
                ON audit_log(sprint_id)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_type
                ON audit_log(event_type)
            """)

            conn.commit()

    def _get_last_hash(self) -> str:
        """Get the hash of the last entry (or genesis hash if empty)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT entry_hash FROM audit_log ORDER BY id DESC LIMIT 1"
            )
            row: Optional[tuple[str]] = cursor.fetchone()
            if row:
                return row[0]

        # Genesis hash for empty chain
        return "0" * 64

    def _compute_hash(self, data: dict[str, Any]) -> str:
        """Compute SHA-256 hash of entry data."""
        # Sort keys for deterministic hashing
        json_data: str = json.dumps(data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(json_data.encode()).hexdigest()

    def _sign(self, entry_hash: str) -> str:
        """Create HMAC-SHA256 signature for the entry hash."""
        return hmac.new(
            self.key,
            entry_hash.encode(),
            hashlib.sha256
        ).hexdigest()

    def _verify_signature(self, entry_hash: str, signature: str) -> bool:
        """Verify HMAC signature matches expected value."""
        expected: str = self._sign(entry_hash)
        return hmac.compare_digest(expected, signature)

    def append(
        self,
        event_type: str,
        sprint_id: str,
        details: dict[str, Any],
        user_id: Optional[str] = None
    ) -> AuditEntry:
        """
        Append a new event to the audit log.

        Args:
            event_type: Type of event (e.g., 'gate_pass', 'sprint_start')
            sprint_id: ID of the sprint
            details: Additional event details
            user_id: ID of the user who performed the action (None for system)

        Returns:
            The created AuditEntry
        """
        timestamp: str = datetime.utcnow().isoformat()
        previous_hash: str = self._get_last_hash()

        # Build entry data (without hash and signature for hashing)
        entry_data: dict[str, Any] = {
            "timestamp": timestamp,
            "event_type": event_type,
            "sprint_id": sprint_id,
            "details": details,
            "previous_hash": previous_hash,
            "user_id": user_id or "system",
        }

        # Compute entry hash
        entry_hash: str = self._compute_hash(entry_data)

        # Sign the hash
        signature: str = self._sign(entry_hash)

        # Store in database
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audit_log
                (timestamp, event_type, sprint_id, details, previous_hash, entry_hash, signature, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    timestamp,
                    event_type,
                    sprint_id,
                    json.dumps(details, separators=(',', ':')),
                    previous_hash,
                    entry_hash,
                    signature,
                    user_id or "system",
                )
            )
            conn.commit()

        return AuditEntry(
            timestamp=timestamp,
            event_type=event_type,
            sprint_id=sprint_id,
            details=details,
            previous_hash=previous_hash,
            entry_hash=entry_hash,
            signature=signature,
            user_id=user_id or "system",
        )

    def verify(self, sprint_id: Optional[str] = None) -> dict[str, Any]:
        """
        Verify the integrity of the audit log.

        Args:
            sprint_id: Optional sprint ID to filter verification

        Returns:
            Verification result with status and any tampered entries
        """
        results: dict[str, Any] = {
            "valid": True,
            "total_entries": 0,
            "tampered_entries": [],
            "broken_chain_at": [],
        }

        query: str = "SELECT * FROM audit_log ORDER BY id ASC"
        params: tuple = ()

        if sprint_id:
            query = "SELECT * FROM audit_log WHERE sprint_id = ? ORDER BY id ASC"
            params = (sprint_id,)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            rows: list[tuple] = cursor.fetchall()

        results["total_entries"] = len(rows)

        if not rows:
            return results

        previous_hash: str = "0" * 64
        is_first_entry: bool = True

        for row in rows:
            (
                entry_id,
                timestamp,
                event_type,
                row_sprint_id,
                details_json,
                stored_prev_hash,
                entry_hash,
                signature,
                user_id,
            ) = row

            # Verify chain integrity
            # Skip chain check for first entry when filtering by sprint_id
            # (previous entry may be from different sprint)
            if not (sprint_id and is_first_entry):
                if stored_prev_hash != previous_hash:
                    results["valid"] = False
                    results["broken_chain_at"].append({
                        "id": entry_id,
                        "expected_previous": previous_hash,
                        "actual_previous": stored_prev_hash,
                    })

            is_first_entry = False

            # Verify signature
            if not self._verify_signature(entry_hash, signature):
                results["valid"] = False
                results["tampered_entries"].append({
                    "id": entry_id,
                    "reason": "invalid_signature",
                    "entry_hash": entry_hash,
                })

            # Verify entry hash integrity
            entry_data: dict[str, Any] = {
                "timestamp": timestamp,
                "event_type": event_type,
                "sprint_id": row_sprint_id,
                "details": json.loads(details_json),
                "previous_hash": stored_prev_hash,
                "user_id": user_id or "system",
            }
            computed_hash: str = self._compute_hash(entry_data)

            if computed_hash != entry_hash:
                results["valid"] = False
                results["tampered_entries"].append({
                    "id": entry_id,
                    "reason": "hash_mismatch",
                    "expected_hash": computed_hash,
                    "actual_hash": entry_hash,
                })

            previous_hash = entry_hash

        return results

    def get_entries(
        self,
        sprint_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> list[AuditEntry]:
        """
        Retrieve audit log entries.

        Args:
            sprint_id: Filter by sprint ID
            event_type: Filter by event type
            limit: Maximum number of entries to return

        Returns:
            List of AuditEntry objects
        """
        query: str = "SELECT * FROM audit_log WHERE 1=1"
        params: list = []

        if sprint_id:
            query += " AND sprint_id = ?"
            params.append(sprint_id)

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        entries: list[AuditEntry] = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            rows: list[tuple] = cursor.fetchall()

            for row in rows:
                entries.append(AuditEntry(
                    timestamp=row[1],
                    event_type=row[2],
                    sprint_id=row[3],
                    details=json.loads(row[4]),
                    previous_hash=row[5],
                    entry_hash=row[6],
                    signature=row[7],
                    user_id=row[8] if len(row) > 8 else "system",
                ))

        return entries

    def export_to_json(self, output_path: Path | str) -> None:
        """Export the entire audit log to JSON for backup/analysis."""
        entries: list[dict[str, Any]] = []

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT * FROM audit_log ORDER BY id ASC")
            rows: list[tuple] = cursor.fetchall()

            for row in rows:
                entries.append({
                    "id": row[0],
                    "timestamp": row[1],
                    "event_type": row[2],
                    "sprint_id": row[3],
                    "details": json.loads(row[4]),
                    "previous_hash": row[5],
                    "entry_hash": row[6],
                    "signature": row[7],
                    "user_id": row[8] if len(row) > 8 else "system",
                })

        with open(output_path, "w") as f:
            json.dump(entries, f, indent=2)
