"""
GateAudit - Database operations for gate audit logging.

Handles SQLite database operations for audit trail management.
"""

import sqlite3
import secrets
import getpass
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any

from gate_types import GateType, AuditRecord


class GateAudit:
    """
    Manages audit logging to SQLite database.
    
    - Creates and manages audit database schema
    - Logs all gate events with full context
    - Retrieves audit history with filtering
    """
    
    def __init__(self, db_path: str, project_dir: Path):
        """
        Initialize the audit logger.
        
        Args:
            db_path: Path to the SQLite audit database
            project_dir: The project directory for context
        """
        self.db_path = db_path
        self.project_dir = project_dir
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the SQLite audit database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gate_audit (
                id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                gate_type TEXT NOT NULL,
                sprint_id TEXT NOT NULL,
                project_dir TEXT NOT NULL,
                action TEXT NOT NULL,
                result TEXT NOT NULL,
                signature TEXT,
                details TEXT,
                ip_address TEXT,
                user TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_gate_audit_sprint 
            ON gate_audit(sprint_id, gate_type)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_gate_audit_timestamp 
            ON gate_audit(timestamp)
        ''')
        
        conn.commit()
        conn.close()
    
    def _get_user_info(self) -> tuple:
        """Get current user and IP address."""
        try:
            user = getpass.getuser()
        except Exception:
            user = "unknown"
        
        try:
            ip_address = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip_address = "unknown"
        
        return user, ip_address
    
    def log_event(
        self,
        gate_type: GateType,
        sprint_id: str,
        action: str,
        result: str,
        signature: Optional[str] = None,
        details: str = ""
    ) -> AuditRecord:
        """
        Log an audit event to the database.
        
        Args:
            gate_type: The gate type
            sprint_id: The sprint ID
            action: The action being performed
            result: The result of the action
            signature: Optional signature associated with the event
            details: Additional details
        
        Returns:
            The created AuditRecord
        """
        record_id = secrets.token_hex(16)
        timestamp = datetime.now(timezone.utc).isoformat()
        user, ip_address = self._get_user_info()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO gate_audit 
            (id, timestamp, gate_type, sprint_id, project_dir, action, 
             result, signature, details, ip_address, user)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            record_id, timestamp, gate_type.value, sprint_id,
            str(self.project_dir), action, result, signature, details,
            ip_address, user
        ))
        
        conn.commit()
        conn.close()
        
        return AuditRecord(
            id=record_id,
            timestamp=timestamp,
            gate_type=gate_type.value,
            sprint_id=sprint_id,
            project_dir=str(self.project_dir),
            action=action,
            result=result,
            signature=signature,
            details=details,
            ip_address=ip_address,
            user=user
        )
    
    def get_audit_log(
        self,
        sprint_id: Optional[str] = None,
        gate_type: Optional[GateType] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Retrieve audit log entries.
        
        Args:
            sprint_id: Filter by sprint ID
            gate_type: Filter by gate type
            limit: Maximum number of entries (max 1000)
        
        Returns:
            List of audit records as dictionaries
        """
        # Validate limit parameter
        if not isinstance(limit, int) or limit < 1:
            limit = 100
        limit = min(limit, 1000)  # Cap at 1000 for safety
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM gate_audit WHERE 1=1"
        params = []
        
        if sprint_id is not None:
            # Validate sprint_id is a string
            if not isinstance(sprint_id, str):
                raise ValueError("sprint_id must be a string")
            query += " AND sprint_id = ?"
            params.append(sprint_id)
        
        if gate_type is not None:
            if not isinstance(gate_type, GateType):
                raise ValueError("gate_type must be a GateType enum")
            query += " AND gate_type = ?"
            params.append(gate_type.value)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
