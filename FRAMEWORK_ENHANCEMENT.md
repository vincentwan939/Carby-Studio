# Carby Studio Framework Enhancement: Sequential Phase Delivery with User Approvals

**Version:** 3.1.0  
**Status:** Design Document  
**Date:** 2026-03-21

---

## Executive Summary

This document outlines enhancements to the Carby Sprint Framework to enforce **sequential phase delivery with user approval gates**. The current system uses technical gates (Planning, Design, Implementation, Validation, Release) that agents can pass automatically. The new system introduces **Phase Delivery Gates** that require explicit user approval before the next phase can begin.

### Problem Statement
- **Current:** Agents can run all phases in parallel
- **Current:** Gates are technical checkpoints, not delivery milestones
- **Needed:** Sequential phase execution with user approval between phases
- **Needed:** Clear phase completion → user review → approval → next phase workflow

---

## 1. Phase Delivery Gate Specification

### 1.1 New Gate Type: Phase Delivery Gate

A **Phase Delivery Gate** is a special gate type that:
- Marks the completion of a phase
- Requires explicit user approval to proceed
- Blocks all downstream phases until approved
- Generates a phase completion summary for user review

### 1.2 Gate States

```python
from enum import Enum

class PhaseDeliveryGateStatus(str, Enum):
    """Phase delivery gate statuses with user approval workflow."""
    IN_PROGRESS = "in_progress"           # Phase is currently running
    COMPLETED = "completed"               # Phase complete, awaiting approval
    PENDING_APPROVAL = "pending_approval" # Summary delivered, waiting for user
    APPROVED = "approved"                 # User approved, next phase can start
    REVISION_REQUESTED = "revision_requested"  # User requested changes
    ABORTED = "aborted"                   # User aborted the sprint
```

### 1.3 Phase Delivery Gate Structure

```python
from datetime import datetime
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

class PhaseDeliveryGate(BaseModel):
    """Phase delivery gate with user approval workflow."""
    
    phase_id: str = Field(..., description="e.g., 'phase_1_discover'")
    phase_name: str = Field(..., description="e.g., 'Discovery Phase'")
    status: PhaseDeliveryGateStatus
    
    # Timing
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None      # Phase work finished
    delivered_at: Optional[datetime] = None      # Summary delivered to user
    approved_at: Optional[datetime] = None       # User approved
    
    # Content
    completion_summary: Optional[str] = None     # Generated summary for user review
    artifacts: List[str] = Field(default_factory=list)      # Phase outputs
    deliverables: List[str] = Field(default_factory=list)   # What was produced
    
    # User approval
    approval_token: Optional[str] = None         # Secure token for approval action
    revision_notes: Optional[str] = None         # User feedback on revision
    
    # Dependencies
    depends_on: Optional[str] = None             # Previous phase (null for first)
    blocks: List[str] = Field(default_factory=list)  # Phases blocked by this gate
    
    # Execution mode
    execution_mode: str = "sequential"           # "sequential" or "parallel"
```

### 1.4 Phase Sequence Definition

```python
PHASE_SEQUENCE = [
    {
        "id": "phase_1_discover",
        "name": "Discovery Phase",
        "agent": "discover",
        "description": "Research and understand the problem space",
        "requires_approval": True,
        "execution_mode": "sequential",
    },
    {
        "id": "phase_2_design", 
        "name": "Design Phase",
        "agent": "design",
        "description": "Create technical design and architecture",
        "requires_approval": True,
        "execution_mode": "sequential",
        "depends_on": "phase_1_discover",
    },
    {
        "id": "phase_3_build",
        "name": "Build Phase",
        "agent": "build",
        "description": "Implement work items",
        "requires_approval": True,
        "execution_mode": "sequential",
        "depends_on": "phase_2_design",
        "parallel_work_items": True,  # Work items can run in parallel within phase
    },
    {
        "id": "phase_4_verify",
        "name": "Verification Phase",
        "agent": "verify",
        "description": "Validate implementation against requirements",
        "requires_approval": True,
        "execution_mode": "sequential",
        "depends_on": "phase_3_build",
    },
    {
        "id": "phase_5_deliver",
        "name": "Delivery Phase",
        "agent": "deliver",
        "description": "Package and deliver final artifacts",
        "requires_approval": False,  # Final phase, auto-completes
        "execution_mode": "sequential",
        "depends_on": "phase_4_verify",
    },
]
```

---

## 2. Sequential Enforcement Mechanism

### 2.1 Intent Detection: Sequential vs Parallel

The system detects execution intent through multiple signals:

#### Signal 1: Explicit User Declaration
```bash
# Sequential execution (explicit)
carby-sprint start my-project --mode sequential --phases "discover,design,build"

# Parallel execution (explicit)
carby-sprint start my-project --mode parallel --phases "discover,design"
```

#### Signal 2: Natural Language Parsing
```python
import re
from enum import Enum

class ExecutionMode(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"

def detect_execution_mode(user_input: str) -> ExecutionMode:
    """Detect sequential vs parallel intent from user input."""
    
    sequential_markers = [
        r"then", r"after", r"followed by", r"subsequently",
        r"phase \d+, then phase", r"first.*then.*finally",
        r"one by one", r"in sequence", r"sequentially",
    ]
    
    parallel_markers = [
        r"in parallel", r"simultaneously", r"at the same time",
        r"together", r"concurrently", r"all at once",
        r"while.*also", r"both.*and",
    ]
    
    # Check for explicit markers
    for pattern in sequential_markers:
        if re.search(pattern, user_input, re.IGNORECASE):
            return ExecutionMode.SEQUENTIAL
    
    for pattern in parallel_markers:
        if re.search(pattern, user_input, re.IGNORECASE):
            return ExecutionMode.PARALLEL
    
    # Default: sequential for phase transitions
    return ExecutionMode.SEQUENTIAL
```

#### Signal 3: Phase Dependency Chain
```python
from typing import Dict, List, Tuple, Optional

class PhaseDependencyGraph:
    """Manages phase dependencies and execution order."""
    
    def __init__(self, phases: List[Dict[str, Any]]):
        self.phases = {p["id"]: p for p in phases}
        self.dependencies = self._build_dependency_graph()
    
    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build dependency graph from phase configurations."""
        graph = {}
        for phase_id, phase in self.phases.items():
            graph[phase_id] = []
            if phase.get("depends_on"):
                graph[phase_id].append(phase["depends_on"])
        return graph
    
    def get_execution_order(self) -> List[str]:
        """Get topologically sorted phase execution order."""
        visited = set()
        order = []
        
        def visit(phase_id: str):
            if phase_id in visited:
                return
            visited.add(phase_id)
            for dep in self.dependencies.get(phase_id, []):
                visit(dep)
            order.append(phase_id)
        
        for phase_id in self.phases:
            visit(phase_id)
        
        return order
    
    def can_execute(self, phase_id: str, phase_statuses: Dict[str, str]) -> Tuple[bool, Optional[str]]:
        """Check if a phase can execute (all dependencies approved)."""
        phase = self.phases.get(phase_id)
        if not phase:
            return False, f"Unknown phase: {phase_id}"
        
        if phase.get("depends_on"):
            dep_status = phase_statuses.get(phase["depends_on"])
            if dep_status != PhaseDeliveryGateStatus.APPROVED:
                return False, f"Dependency {phase['depends_on']} not approved (status: {dep_status})"
        
        return True, None
    
    def get_blocked_phases(self, phase_id: str) -> List[str]:
        """Get all phases blocked by this phase."""
        blocked = []
        for pid, phase in self.phases.items():
            if phase.get("depends_on") == phase_id:
                blocked.append(pid)
        return blocked
```

### 2.2 Phase Dependency Chain Enforcement

```python
class PhaseDependencyEnforcer:
    """Enforces phase dependencies and blocks execution until approved."""
    
    def __init__(self, sprint_id: str, output_dir: str = ".carby-sprints"):
        self.sprint_id = sprint_id
        self.output_dir = Path(output_dir)
        self.sprint_path = self.output_dir / sprint_id
        self.phase_status_file = self.sprint_path / "phase_status.json"
    
    def _load_phase_status(self) -> Dict[str, Any]:
        """Load current phase status from file."""
        if self.phase_status_file.exists():
            return json.loads(self.phase_status_file.read_text())
        return {}
    
    def _save_phase_status(self, status: Dict[str, Any]) -> None:
        """Save phase status to file."""
        self.phase_status_file.write_text(json.dumps(status, indent=2, default=str))
    
    def is_phase_approved(self, phase_id: str) -> bool:
        """Check if a phase has been approved by the user."""
        status = self._load_phase_status()
        phase_data = status.get(phase_id, {})
        return phase_data.get("status") == PhaseDeliveryGateStatus.APPROVED
    
    def block_until_approved(self, phase_id: str, timeout: Optional[int] = None) -> bool:
        """Block execution until phase is approved (with optional timeout)."""
        import time
        
        start_time = time.time()
        while not self.is_phase_approved(phase_id):
            if timeout and (time.time() - start_time) > timeout:
                return False
            time.sleep(5)  # Check every 5 seconds
        return True
```

---

## 3. Approval Workflow Design

### 3.1 Phase Completion → User Review Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Phase Running  │────▶│ Phase Complete  │────▶│ Generate Summary│
│   (IN_PROGRESS) │     │   (COMPLETED)   │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                              ┌──────────────────────────┘
                              ▼
                    ┌─────────────────┐
                    │ Deliver Summary │
                    │  to User        │
                    └────────┬────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│    APPROVE      │ │    REVISE       │ │     ABORT       │
│                 │ │                 │ │                 │
│ Next phase      │ │ Agent fixes     │ │ Sprint ends     │
│ begins          │ │ issues          │ │                 │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

### 3.2 Approval State Machine

```python
from enum import Enum, auto

class ApprovalAction(str, Enum):
    """User actions on phase completion."""
    APPROVE = "approve"
    REVISE = "revise"
    ABORT = "abort"

class PhaseApprovalWorkflow:
    """Manages the phase approval workflow state machine."""
    
    TRANSITIONS = {
        PhaseDeliveryGateStatus.IN_PROGRESS: [
            PhaseDeliveryGateStatus.COMPLETED,
            PhaseDeliveryGateStatus.ABORTED,
        ],
        PhaseDeliveryGateStatus.COMPLETED: [
            PhaseDeliveryGateStatus.PENDING_APPROVAL,
        ],
        PhaseDeliveryGateStatus.PENDING_APPROVAL: [
            PhaseDeliveryGateStatus.APPROVED,
            PhaseDeliveryGateStatus.REVISION_REQUESTED,
            PhaseDeliveryGateStatus.ABORTED,
        ],
        PhaseDeliveryGateStatus.REVISION_REQUESTED: [
            PhaseDeliveryGateStatus.IN_PROGRESS,  # Back to work
            PhaseDeliveryGateStatus.ABORTED,
        ],
        PhaseDeliveryGateStatus.APPROVED: [
            # Terminal state - next phase can begin
        ],
        PhaseDeliveryGateStatus.ABORTED: [
            # Terminal state
        ],
    }
    
    @classmethod
    def can_transition(cls, from_status: PhaseDeliveryGateStatus, 
                       to_status: PhaseDeliveryGateStatus) -> bool:
        """Check if a status transition is valid."""
        allowed = cls.TRANSITIONS.get(from_status, [])
        return to_status in allowed
    
    @classmethod
    def handle_user_action(cls, sprint_id: str, phase_id: str, 
                           action: ApprovalAction,
                           notes: Optional[str] = None) -> Dict[str, Any]:
        """Handle user approval action and transition state."""
        
        repo = PhaseDeliveryRepository()
        phase = repo.load_phase(sprint_id, phase_id)
        
        if action == ApprovalAction.APPROVE:
            if not cls.can_transition(phase.status, PhaseDeliveryGateStatus.APPROVED):
                raise ValueError(f"Cannot approve phase in status: {phase.status}")
            
            phase.status = PhaseDeliveryGateStatus.APPROVED
            phase.approved_at = datetime.now()
            repo.save_phase(sprint_id, phase)
            
            # Unlock next phase
            enforcer = PhaseDependencyEnforcer(sprint_id)
            blocked = enforcer.get_blocked_phases(phase_id)
            
            return {
                "success": True,
                "message": f"Phase {phase_id} approved. Next phases unblocked: {blocked}",
                "unblocked_phases": blocked,
            }
        
        elif action == ApprovalAction.REVISE:
            if not cls.can_transition(phase.status, PhaseDeliveryGateStatus.REVISION_REQUESTED):
                raise ValueError(f"Cannot request revision for phase in status: {phase.status}")
            
            phase.status = PhaseDeliveryGateStatus.REVISION_REQUESTED
            phase.revision_notes = notes
            repo.save_phase(sprint_id, phase)
            
            return {
                "success": True,
                "message": f"Revision requested for phase {phase_id}",
                "notes": notes,
            }
        
        elif action == ApprovalAction.ABORT:
            phase.status = PhaseDeliveryGateStatus.ABORTED
            repo.save_phase(sprint_id, phase)
            
            # Abort entire sprint
            sprint_repo = SprintRepository()
            sprint_data = sprint_repo.load(sprint_id)
            sprint_data["status"] = "cancelled"
            sprint_repo.save(sprint_data, sprint_repo.get_paths(sprint_id))
            
            return {
                "success": True,
                "message": f"Sprint {sprint_id} aborted",
            }
```

### 3.3 Phase Completion Summary Generation

```python
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path

class PhaseCompletionSummary:
    """Generates a summary of phase completion for user review."""
    
    def __init__(self, sprint_id: str, phase_id: str, output_dir: str = ".carby-sprints"):
        self.sprint_id = sprint_id
        self.phase_id = phase_id
        self.output_dir = Path(output_dir)
        self.sprint_path = self.output_dir / sprint_id
    
    def generate(self) -> str:
        """Generate a human-readable phase completion summary."""
        
        # Load phase data
        repo = PhaseDeliveryRepository(self.output_dir)
        phase = repo.load_phase(self.sprint_id, self.phase_id)
        
        # Load sprint data
        sprint_repo = SprintRepository(self.output_dir)
        sprint_data, _ = sprint_repo.load(self.sprint_id)
        
        # Gather artifacts
        artifacts = self._gather_artifacts()
        
        # Build summary
        summary = f"""# Phase Completion Summary

## Sprint Information
- **Sprint ID:** {self.sprint_id}
- **Project:** {sprint_data.get('project', 'N/A')}
- **Goal:** {sprint_data.get('goal', 'N/A')}

## Phase Information
- **Phase:** {phase.phase_name} ({self.phase_id})
- **Status:** {phase.status}
- **Started:** {phase.started_at.strftime('%Y-%m-%d %H:%M') if phase.started_at else 'N/A'}
- **Completed:** {phase.completed_at.strftime('%Y-%m-%d %H:%M') if phase.completed_at else 'N/A'}

## Deliverables Produced
"""
        
        for i, deliverable in enumerate(phase.deliverables, 1):
            summary += f"{i}. {deliverable}\\n"
        
        summary += "\\n## Artifacts Generated\\n"
        for artifact in artifacts:
            summary += f"- `{artifact}`\\n"
        
        summary += f"""
## Completion Notes
{phase.completion_summary or "No completion notes provided."}

---

**Please review this phase completion and choose an action:**

1. **APPROVE** - Phase is complete and satisfactory. Proceed to next phase.
2. **REVISE** - Phase needs changes. Provide feedback below.
3. **ABORT** - Stop the sprint entirely.

To approve: `carby-sprint approve {self.sprint_id} {self.phase_id}`
To revise: `carby-sprint revise {self.sprint_id} {self.phase_id} --notes "Your feedback"`
To abort: `carby-sprint abort {self.sprint_id}`
"""
        
        return summary
    
    def _gather_artifacts(self) -> List[str]:
        """Gather all artifacts from the phase."""
        phase_output_dir = self.sprint_path / "phases" / self.phase_id / "output"
        if not phase_output_dir.exists():
            return []
        
        artifacts = []
        for file in phase_output_dir.rglob("*"):
            if file.is_file():
                artifacts.append(str(file.relative_to(self.sprint_path)))
        
        return sorted(artifacts)
    
    def save_summary(self) -> Path:
        """Save the summary to file and return the path."""
        summary = self.generate()
        
        summary_path = self.sprint_path / "phases" / self.phase_id / "completion_summary.md"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary)
        
        return summary_path
```

---

## 4. Implementation Plan

### 4.1 New Files to Create

| File | Purpose |
|------|---------|
| `carby_sprint/phase_delivery.py` | Core phase delivery gate logic |
| `carby_sprint/phase_enforcer.py` | Sequential enforcement and dependency management |
| `carby_sprint/phase_repository.py` | Phase data persistence |
| `carby_sprint/commands/phase.py` | CLI commands for phase management |
| `carby_sprint/commands/approve.py` | Approval workflow CLI commands |

### 4.2 Files to Modify

| File | Changes |
|------|---------|
| `carby_sprint/validators.py` | Add `PhaseDeliveryGate` and `PhaseDeliveryGateStatus` models |
| `carby_sprint/sprint_repository.py` | Add phase status tracking methods |
| `carby_sprint/commands/start.py` | Add `--mode` flag, implement sequential spawning |
| `carby_sprint/commands/gate.py` | Integrate with phase delivery gates |
| `carby_sprint/agent_callback.py` | Add phase completion reporting |
| `carby_sprint/cli.py` | Register new phase commands |

### 4.3 CLI Commands to Add

```bash
# Phase management
carby-sprint phase status <sprint-id>              # Show phase status
carby-sprint phase list <sprint-id>                # List all phases
carby-sprint phase start <sprint-id> <phase-id>    # Start a phase manually

# Approval workflow
carby-sprint approve <sprint-id> <phase-id>        # Approve phase completion
carby-sprint revise <sprint-id> <phase-id> --notes "..."  # Request revision
carby-sprint abort <sprint-id>                     # Abort sprint

# Modified start command
carby-sprint start <sprint-id> --mode sequential   # Start with sequential phases
carby-sprint start <sprint-id> --mode parallel     # Start with parallel phases
carby-sprint start <sprint-id> --auto-approve      # Skip approval gates (dangerous)
```

---

## 5. Code Examples for New Gate Types

### 5.1 Phase Delivery Gate Enforcer

```python
"""
Phase Delivery Gate Enforcer - Server-side enforcement of phase dependencies.
"""

import json
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from enum import Enum


class PhaseDeliveryGateStatus(str, Enum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REVISION_REQUESTED = "revision_requested"
    ABORTED = "aborted"


class PhaseDeliveryToken:
    """Secure token for phase approval actions."""
    
    def __init__(self, sprint_id: str, phase_id: str, action: str):
        self.sprint_id = sprint_id
        self.phase_id = phase_id
        self.action = action
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(hours=24)
        self.token = self._generate_token()
    
    def _generate_token(self) -> str:
        """Generate HMAC-signed token."""
        secret = self._get_secret()
        data = f"{self.sprint_id}:{self.phase_id}:{self.action}:{self.created_at.isoformat()}"
        signature = hmac.new(secret, data.encode(), hashlib.sha256).hexdigest()
        return f"{data}:{signature}"
    
    def _get_secret(self) -> bytes:
        """Get or create secret key."""
        secret_file = Path.home() / ".openclaw" / "secrets" / "carby-phase-key"
        if secret_file.exists():
            return secret_file.read_bytes()
        
        secret_file.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_bytes(32)
        secret_file.write_bytes(secret)
        secret_file.chmod(0o600)
        return secret
    
    def verify(self, token: str) -> bool:
        """Verify token is valid and not expired."""
        try:
            parts = token.rsplit(":", 1)
            if len(parts) != 2:
                return False
            
            data, signature = parts
            expected_token = self._generate_token()
            expected_parts = expected_token.rsplit(":", 1)
            
            if len(expected_parts) != 2:
                return False
            
            return hmac.compare_digest(expected_parts[1], signature)
        except Exception:
            return False


class PhaseDeliveryGateEnforcer:
    """Enforces phase delivery gates with user approval."""
    
    PHASE_SEQUENCE = [
        "phase_1_discover",
        "phase_2_design",
        "phase_3_build",
        "phase_4_verify",
        "phase_5_deliver",
    ]
    
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.sprint_dir = self.project_dir / ".carby-sprints"
        self.phase_status_file = self.sprint_dir / "phase-delivery-status.json"
    
    def _load_phase_status(self) -> Dict[str, Any]:
        """Load phase delivery status from file."""
        if self.phase_status_file.exists():
            return json.loads(self.phase_status_file.read_text())
        return {}
    
    def _save_phase_status(self, status: Dict[str, Any]) -> None:
        """Save phase delivery status to file."""
        self.phase_status_file.write_text(json.dumps(status, indent=2, default=str))
    
    def can_start_phase(self, sprint_id: str, phase_id: str) -> Tuple[bool, Optional[str]]:
        """Check if a phase can be started."""
        status = self._load_phase_status()
        sprint_phases = status.get(sprint_id, {})
        
        # Get phase index
        try:
            phase_idx = self.PHASE_SEQUENCE.index(phase_id)
        except ValueError:
            return False, f"Unknown phase: {phase_id}"
        
        # First phase can always start
        if phase_idx == 0:
            return True, None
        
        # Check previous phase is approved
        prev_phase = self.PHASE_SEQUENCE[phase_idx - 1]
        prev_status = sprint_phases.get(prev_phase, {}).get("status")
        
        if prev_status != PhaseDeliveryGateStatus.APPROVED:
            return False, f"Previous phase {prev_phase} not approved (status: {prev_status})"
        
        return True, None
    
    def record_phase_completion(self, sprint_id: str, phase_id: str, 
                                 summary: str, artifacts: List[str]) -> str:
        """Record phase completion and generate approval token."""
        status = self._load_phase_status()
        
        if sprint_id not in status:
            status[sprint_id] = {}
        
        # Generate approval token
        token = PhaseDeliveryToken(sprint_id, phase_id, "approve")
        
        status[sprint_id][phase_id] = {
            "status": PhaseDeliveryGateStatus.PENDING_APPROVAL,
            "completed_at": datetime.utcnow().isoformat(),
            "completion_summary": summary,
            "artifacts": artifacts,
            "approval_token": token.token,
        }
        
        self._save_phase_status(status)
        return token.token
    
    def approve_phase(self, sprint_id: str, phase_id: str, token: str) -> bool:
        """Approve a phase and unblock next phase."""
        # Verify token
        expected_token = PhaseDeliveryToken(sprint_id, phase_id, "approve")
        if not expected_token.verify(token):
            raise ValueError("Invalid approval token")
        
        status = self._load_phase_status()
        
        if sprint_id not in status or phase_id not in status[sprint_id]:
            raise ValueError(f"Phase {phase_id} not found for sprint {sprint_id}")
        
        phase_data = status[sprint_id][phase_id]
        
        if phase_data["status"] != PhaseDeliveryGateStatus.PENDING_APPROVAL:
            raise ValueError(f"Phase {phase_id} is not pending approval (status: {phase_data['status']})")
        
        phase_data["status"] = PhaseDeliveryGateStatus.APPROVED
        phase_data["approved_at"] = datetime.utcnow().isoformat()
        
        self._save_phase_status(status)
        return True
    
    def get_next_runnable_phase(self, sprint_id: str) -> Optional[str]:
        """Get the next phase that can be started."""
        status = self._load_phase_status()
        sprint_phases = status.get(sprint_id, {})
        
        for phase_id in self.PHASE_SEQUENCE:
            phase_data = sprint_phases.get(phase_id, {})
            phase_status = phase_data.get("status")
            
            if phase_status == PhaseDeliveryGateStatus.IN_PROGRESS:
                return phase_id  # Current phase still running
            
            if phase_status is None:
                # Check if can start
                can_start, _ = self.can_start_phase(sprint_id, phase_id)
                if can_start:
                    return phase_id
                return None  # Blocked by previous phase
        
        return None  # All phases complete
```

### 5.2 Sequential Agent Spawner

```python
"""
Sequential Agent Spawner - Spawns agents in sequence with approval gates.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime


class SequentialAgentSpawner:
    """Spawns agents sequentially with phase delivery gates."""
    
    AGENT_MAP = {
        "phase_1_discover": "discover",
        "phase_2_design": "design",
        "phase_3_build": "build",
        "phase_4_verify": "verify",
        "phase_5_deliver": "deliver",
    }
    
    def __init__(self, sprint_id: str, output_dir: str = ".carby-sprints"):
        self.sprint_id = sprint_id
        self.output_dir = Path(output_dir)
        self.enforcer = PhaseDeliveryGateEnforcer(self.output_dir.parent)
    
    def spawn_next_phase(self, wait_for_approval: bool = True) -> Optional[subprocess.Popen]:
        """Spawn the next phase that can run."""
        
        next_phase = self.enforcer.get_next_runnable_phase(self.sprint_id)
        
        if not next_phase:
            print(f"No runnable phase for sprint {self.sprint_id}")
            return None
        
        # Check if phase needs approval first
        can_start, reason = self.enforcer.can_start_phase(self.sprint_id, next_phase)
        
        if not can_start:
            print(f"Cannot start {next_phase}: {reason}")
            print("Waiting for user approval...")
            
            if wait_for_approval:
                # This would integrate with notification system
                self._notify_user_approval_pending(next_phase, reason)
            
            return None
        
        # Spawn the agent
        agent_type = self.AGENT_MAP.get(next_phase)
        if not agent_type:
            raise ValueError(f"Unknown agent type for phase: {next_phase}")
        
        process = self._spawn_agent(agent_type, next_phase)
        
        # Record phase as in progress
        self._record_phase_started(next_phase)
        
        return process
    
    def _spawn_agent(self, agent_type: str, phase_id: str) -> subprocess.Popen:
        """Spawn an agent process."""
        carby_studio_path = self.output_dir.parent
        bridge_script = carby_studio_path / "scripts" / "sprint-agent-bridge.py"
        
        cmd = [
            sys.executable,
            str(bridge_script),
            "--agent", agent_type,
            "--sprint-id", self.sprint_id,
            "--phase", phase_id,
        ]
        
        env = {
            **os.environ,
            "CARBY_STUDIO_PATH": str(carby_studio_path),
            "SPRINT_ID": self.sprint_id,
            "PHASE_ID": phase_id,
            "EXECUTION_MODE": "sequential",
        }
        
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
            shell=False,
        )
    
    def _record_phase_started(self, phase_id: str) -> None:
        """Record that a phase has started."""
        status = self.enforcer._load_phase_status()
        
        if self.sprint_id not in status:
            status[self.sprint_id] = {}
        
        status[self.sprint_id][phase_id] = {
            "status": PhaseDeliveryGateStatus.IN_PROGRESS,
            "started_at": datetime.utcnow().isoformat(),
        }
        
        self.enforcer._save_phase_status(status)
    
    def _notify_user_approval_pending(self, phase_id: str, reason: str) -> None:
        """Notify user that approval is pending."""
        # This would integrate with notification system (Telegram, etc.)
        print(f"\\n{'='*60}")
        print(f"PHASE APPROVAL REQUIRED")
        print(f"{'='*60}")
        print(f"Sprint: {self.sprint_id}")
        print(f"Phase: {phase_id}")
        print(f"Reason: {reason}")
        print(f"\\nRun: carby-sprint approve {self.sprint_id} {phase_id}")
        print(f"{'='*60}\\n")
```

### 5.3 Approval CLI Command

```python
"""
Approval CLI commands for phase delivery gates.
"""

import click
from pathlib import Path
from datetime import datetime


@click.group()
def approve_cmd():
    """Phase approval commands."""
    pass


@approve_cmd.command()
@click.argument("sprint_id")
@click.argument("phase_id")
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
@click.pass_context
def approve(ctx: click.Context, sprint_id: str, phase_id: str, output_dir: str):
    """Approve a phase completion and unblock next phase."""
    
    enforcer = PhaseDeliveryGateEnforcer(Path(output_dir).parent)
    
    # Load phase data to get token
    status = enforcer._load_phase_status()
    phase_data = status.get(sprint_id, {}).get(phase_id, {})
    token = phase_data.get("approval_token")
    
    if not token:
        raise click.ClickException(f"No approval token found for phase {phase_id}")
    
    try:
        enforcer.approve_phase(sprint_id, phase_id, token)
        click.echo(f"✓ Phase {phase_id} approved for sprint '{sprint_id}'")
        
        # Check if next phase can start
        next_phase = enforcer.get_next_runnable_phase(sprint_id)
        if next_phase:
            click.echo(f"\\nNext phase ready: {next_phase}")
            click.echo(f"Run: carby-sprint phase start {sprint_id} {next_phase}")
        else:
            click.echo("\\nAll phases complete!")
            
    except ValueError as e:
        raise click.ClickException(str(e))


@approve_cmd.command()
@click.argument("sprint_id")
@click.argument("phase_id")
@click.option(
    "--notes",
    "-n",
    required=True,
    help="Revision notes explaining what needs to be fixed",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
def revise(sprint_id: str, phase_id: str, notes: str, output_dir: str):
    """Request revision for a phase."""
    
    enforcer = PhaseDeliveryGateEnforcer(Path(output_dir).parent)
    
    status = enforcer._load_phase_status()
    
    if sprint_id not in status or phase_id not in status[sprint_id]:
        raise click.ClickException(f"Phase {phase_id} not found")
    
    phase_data = status[sprint_id][phase_id]
    
    if phase_data["status"] != PhaseDeliveryGateStatus.PENDING_APPROVAL:
        raise click.ClickException(f"Phase {phase_id} is not pending approval")
    
    phase_data["status"] = PhaseDeliveryGateStatus.REVISION_REQUESTED
    phase_data["revision_notes"] = notes
    phase_data["revised_at"] = datetime.utcnow().isoformat()
    
    enforcer._save_phase_status(status)
    
    click.echo(f"✓ Revision requested for phase {phase_id}")
    click.echo(f"Notes: {notes}")
    click.echo(f"\\nThe agent will be notified to fix the issues.")


@approve_cmd.command()
@click.argument("sprint_id")
@click.option(
    "--reason",
    "-r",
    help="Reason for aborting",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(),
    default=".carby-sprints",
    help="Directory containing sprint data",
)
def abort(sprint_id: str, reason: Optional[str], output_dir: str):
    """Abort the entire sprint."""
    
    enforcer = PhaseDeliveryGateEnforcer(Path(output_dir).parent)
    
    status = enforcer._load_phase_status()
    
    if sprint_id not in status:
        raise click.ClickException(f"Sprint {sprint_id} not found")
    
    # Mark all phases as aborted
    for phase_id in enforcer.PHASE_SEQUENCE:
        if phase_id in status[sprint_id]:
            status[sprint_id][phase_id]["status"] = PhaseDeliveryGateStatus.ABORTED
    
    enforcer._save_phase_status(status)
    
    # Update sprint status
    from ..sprint_repository import SprintRepository
    repo = SprintRepository(output_dir)
    sprint_data, paths = repo.load(sprint_id)
    sprint_data["status"] = "cancelled"
    sprint_data["aborted_at"] = datetime.utcnow().isoformat()
    sprint_data["abort_reason"] = reason or "User requested"
    repo.save(sprint_data, paths)
    
    click.echo(f"✓ Sprint '{sprint_id}' aborted")
    if reason:
        click.echo(f"Reason: {reason}")
```

---

## 6. Integration with Existing Framework

### 6.1 Modified Sprint Start Command

```python
# In carby_sprint/commands/start.py

@click.command()
@click.argument("sprint_id")
@click.option(
    "--mode",
    type=click.Choice(["sequential", "parallel"]),
    default="sequential",
    help="Execution mode: sequential (phases with approval) or parallel (work items)",
)
@click.option(
    "--auto-approve",
    is_flag=True,
    help="Auto-approve phases (skips user approval - use with caution)",
)
@click.option(
    "--max-parallel",
    "-p",
    default=3,
    type=int,
    help="Maximum parallel work items within a phase (default: 3)",
)
def start(sprint_id: str, mode: str, auto_approve: bool, max_parallel: int):
    """Start a sprint with sequential phase delivery."""
    
    if mode == "sequential":
        # Use sequential spawner with phase delivery gates
        spawner = SequentialAgentSpawner(sprint_id)
        process = spawner.spawn_next_phase(wait_for_approval=not auto_approve)
        
        if process:
            click.echo(f"✓ Started phase for sprint '{sprint_id}'")
            click.echo(f"PID: {process.pid}")
        else:
            click.echo("No phase to start (waiting for approval)")
    else:
        # Use existing parallel spawning logic
        # ... existing code ...
```

### 6.2 Agent Callback Integration

```python
# In carby_sprint/agent_callback.py

def report_phase_completion(
    sprint_id: str,
    phase_id: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Report phase completion and trigger approval workflow."""
    
    from .phase_enforcer import PhaseDeliveryGateEnforcer, PhaseCompletionSummary
    
    enforcer = PhaseDeliveryGateEnforcer()
    
    # Generate completion summary
    summary_gen = PhaseCompletionSummary(sprint_id, phase_id)
    summary_path = summary_gen.save_summary()
    summary_text = summary_gen.generate()
    
    # Record phase completion
    artifacts = result.get("artifacts", [])
    token = enforcer.record_phase_completion(
        sprint_id=sprint_id,
        phase_id=phase_id,
        summary=result.get("message", "Phase completed"),
        artifacts=artifacts,
    )
    
    # Notify user (this would integrate with notification system)
    print(f"\\n{'='*60}")
    print(f"PHASE COMPLETE - APPROVAL REQUIRED")
    print(f"{'='*60}")
    print(f"Sprint: {sprint_id}")
    print(f"Phase: {phase_id}")
    print(f"\\nSummary saved to: {summary_path}")
    print(f"\\nTo approve and continue:")
    print(f"  carby-sprint approve {sprint_id} {phase_id}")
    print(f"\\nTo request revision:")
    print(f"  carby-sprint revise {sprint_id} {phase_id} --notes 'Your feedback'")
    print(f"{'='*60}\\n")
    
    return {
        "status": "pending_approval",
        "phase_id": phase_id,
        "summary_path": str(summary_path),
        "approval_token": token,
    }
```

---

## 7. Summary

This enhancement introduces **Phase Delivery Gates** to the Carby Sprint Framework, enforcing sequential phase execution with user approval checkpoints. The key components are:

### Key Features

1. **Phase Delivery Gates**: New gate type requiring user approval before next phase
2. **Sequential Enforcement**: Dependency chain ensures phases run in order
3. **Approval Workflow**: Three actions (approve/revise/abort) with state machine
4. **Intent Detection**: Automatic detection of sequential vs parallel execution
5. **Secure Tokens**: HMAC-signed tokens prevent unauthorized gate bypass

### Benefits

- **User Control**: User reviews and approves each phase before proceeding
- **Quality Assurance**: Catches issues early before they compound
- **Visibility**: Clear phase status and completion summaries
- **Flexibility**: Can still run work items in parallel within a phase
- **Safety**: Secure tokens prevent agents from bypassing approval

### Migration Path

1. Add new phase delivery modules (non-breaking)
2. Update CLI with `--mode` flag (default: sequential)
3. Gradually migrate existing sprints to use phase delivery gates
4. Deprecate old parallel-only mode in v4.0.0

---

*Framework Enhancement Design Document v1.0*  
*Carby Studio v3.1.0*

