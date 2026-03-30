"""Gate state persistence and management."""
import json
from datetime import datetime
from typing import Dict, Any
from pathlib import Path

from .lock_manager import DistributedLock


class GateStateManager:
    """Manages gate status files with locking."""
    
    def __init__(self, project_dir: str):
        """
        Initialize the gate state manager.
        
        Args:
            project_dir: Project directory path
        """
        resolved = Path(project_dir).resolve()
        
        # Allow temp directories for testing
        if '/tmp' in str(resolved) or '/var/folders' in str(resolved):
            self.project_dir = resolved
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
            return
        
        # Otherwise validate path doesn't escape expected bounds
        if '..' in str(project_dir):
            raise ValueError(f"Invalid project_dir: path traversal detected in {project_dir}")

        self.project_dir = resolved
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
        """Save gate status to file with locking."""
        lock_path = self.sprint_dir / ".gate-status.lock"
        with DistributedLock(lock_path):
            self.status_file.write_text(json.dumps(status, indent=2))
    
    def get_current_gate(self, sprint_id: str) -> str:
        """Get the current gate for a sprint."""
        status = self._load_gate_status()
        return status.get(sprint_id, {}).get("current_gate", self.gate_sequence[0])
    
    def set_current_gate(self, sprint_id: str, gate: str) -> None:
        """Set the current gate for a sprint."""
        status = self._load_gate_status()
        if sprint_id not in status:
            status[sprint_id] = {}
        status[sprint_id]["current_gate"] = gate
        status[sprint_id]["updated_at"] = datetime.utcnow().isoformat()
        self._save_gate_status(status)
    
    def record_gate_completion(self, sprint_id: str, gate: str, token: str) -> None:
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
    
    def is_gate_completed(self, sprint_id: str, gate: str) -> bool:
        """Check if a specific gate has been completed."""
        status = self._load_gate_status()
        completed_gates = status.get(sprint_id, {}).get("completed_gates", [])
        return any(g["gate"] == gate for g in completed_gates)
    
    def get_completed_gates(self, sprint_id: str) -> list:
        """Get list of completed gates for a sprint."""
        status = self._load_gate_status()
        completed = status.get(sprint_id, {}).get("completed_gates", [])
        return [g["gate"] for g in completed]
    
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
