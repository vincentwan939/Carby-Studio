"""State management for Carby Studio Bot.

Supports both legacy project-based state (carby-studio) and new sprint-based state (carby-sprint).
During the transition period, both formats are supported with automatic detection.
"""

import os
import time
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, asdict, field
from threading import Lock, Event
from enum import Enum

from config import Config
from atomic_file import atomic_write_json, safe_read_json, locked_json_read, locked_json_write
from file_lock import get_lock_manager

logger = logging.getLogger(__name__)


class StageStatus(str, Enum):
    """Stage status values - using str Enum for JSON serialization compatibility."""
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    DONE = "done"
    APPROVED = "approved"
    FAILED = "failed"
    SKIPPED = "skipped"


class ProjectStatus(str, Enum):
    """Project status values - using str Enum for JSON serialization compatibility."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    PAUSED = "paused"
    COMPLETED = "completed"


class PhaseStatus(str, Enum):
    """Phase status values for carby-sprint."""
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    FAILED = "failed"
    SKIPPED = "skipped"


class GateStatus(str, Enum):
    """Gate status values for carby-sprint."""
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    APPROVED = "approved"
    FAILED = "failed"
    SKIPPED = "skipped"


class SprintStatus(str, Enum):
    """Sprint status values for carby-sprint."""
    PENDING = "pending"
    IN_PROGRESS = "in-progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


# ============================================================================
# Legacy Data Classes (carby-studio)
# ============================================================================

@dataclass
class StageState:
    """State of a single stage (legacy carby-studio)."""
    name: str
    status: str
    agent: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    task: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "StageState":
        """Create StageState from dictionary with proper status handling."""
        if not data:
            return cls(name="", status=StageStatus.PENDING.value)

        # Ensure status is a string
        status = data.get("status", StageStatus.PENDING.value)
        if isinstance(status, Enum):
            status = status.value

        return cls(
            name=data.get("name", ""),
            status=status,
            agent=data.get("agent"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            task=data.get("task"),
            output=data.get("output"),
            error=data.get("error"),
            retry_count=data.get("retry_count", 0)
        )


@dataclass
class ProjectState:
    """State of a project (legacy carby-studio)."""
    id: str
    goal: str
    status: str
    mode: str
    current_stage: str
    stages: Dict[str, StageState]
    updated_at: str
    created_at: Optional[str] = None
    pipeline: Optional[List[str]] = None

    @classmethod
    def from_dict(cls, data: dict, project_id: str = "") -> "ProjectState":
        """Create ProjectState from dictionary with proper status handling."""
        if not data:
            return cls(
                id=project_id,
                goal="",
                status=ProjectStatus.ACTIVE.value,
                mode="linear",
                current_stage="",
                stages={},
                updated_at=datetime.now().isoformat()
            )

        # Convert stages dict to StageState objects
        stages_data = data.get("stages", {})
        stages = {}
        for name, stage_data in stages_data.items():
            if isinstance(stage_data, dict):
                stages[name] = StageState.from_dict(stage_data)
            elif isinstance(stage_data, StageState):
                stages[name] = stage_data
            else:
                stages[name] = StageState(name=name, status=str(stage_data))

        # Ensure status is a string
        status = data.get("status", ProjectStatus.ACTIVE.value)
        if isinstance(status, Enum):
            status = status.value

        return cls(
            id=data.get("id", project_id),
            goal=data.get("goal", ""),
            status=status,
            mode=data.get("mode", "linear"),
            current_stage=data.get("current_stage", data.get("currentStage", "")),
            stages=stages,
            updated_at=data.get("updated_at", data.get("updated", datetime.now().isoformat())),
            created_at=data.get("created_at", data.get("created", "")),
            pipeline=data.get("pipeline", [])
        )


# ============================================================================
# New Data Classes (carby-sprint)
# ============================================================================

@dataclass
class PhaseState:
    """State of a single phase within a gate (carby-sprint)."""
    phase_id: str
    name: str
    status: str
    agent: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    task: Optional[str] = None
    output: Optional[str] = None
    error: Optional[str] = None
    logs: List[str] = field(default_factory=list)
    retry_count: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "PhaseState":
        """Create PhaseState from dictionary."""
        if not data:
            return cls(phase_id="", name="", status=PhaseStatus.PENDING.value)

        # Ensure status is a string
        status = data.get("status", PhaseStatus.PENDING.value)
        if isinstance(status, Enum):
            status = status.value

        return cls(
            phase_id=data.get("phase_id", data.get("id", "")),
            name=data.get("name", ""),
            status=status,
            agent=data.get("agent"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            task=data.get("task"),
            output=data.get("output"),
            error=data.get("error"),
            logs=data.get("logs", []),
            retry_count=data.get("retry_count", 0)
        )


@dataclass
class GateState:
    """State of a gate containing multiple phases (carby-sprint)."""
    gate_number: int
    name: str
    status: str
    phases: List[PhaseState] = field(default_factory=list)
    current_phase: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "GateState":
        """Create GateState from dictionary."""
        if not data:
            return cls(gate_number=0, name="", status=GateStatus.PENDING.value)

        # Parse phases
        phases_data = data.get("phases", [])
        phases = []
        for phase_data in phases_data:
            if isinstance(phase_data, dict):
                phases.append(PhaseState.from_dict(phase_data))
            elif isinstance(phase_data, PhaseState):
                phases.append(phase_data)
            else:
                phases.append(PhaseState.from_dict({"name": str(phase_data), "status": PhaseStatus.PENDING.value}))

        # Ensure status is a string
        status = data.get("status", GateStatus.PENDING.value)
        if isinstance(status, Enum):
            status = status.value

        return cls(
            gate_number=data.get("gate_number", data.get("number", 0)),
            name=data.get("name", ""),
            status=status,
            phases=phases,
            current_phase=data.get("current_phase"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at")
        )


@dataclass
class SprintState:
    """State of a sprint (carby-sprint)."""
    sprint_id: str
    project: str
    goal: str
    status: str
    mode: str
    current_gate: int
    gates: List[GateState] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_dict(cls, data: dict, sprint_id: str = "") -> "SprintState":
        """Create SprintState from dictionary."""
        if not data:
            return cls(
                sprint_id=sprint_id,
                project="",
                goal="",
                status=SprintStatus.PENDING.value,
                mode="sequential",
                current_gate=1,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat()
            )

        # Parse gates
        gates_data = data.get("gates", [])
        gates = []
        for gate_data in gates_data:
            if isinstance(gate_data, dict):
                gates.append(GateState.from_dict(gate_data))
            elif isinstance(gate_data, GateState):
                gates.append(gate_data)
            else:
                gates.append(GateState.from_dict({"name": str(gate_data), "status": GateStatus.PENDING.value}))

        # Ensure status is a string
        status = data.get("status", SprintStatus.PENDING.value)
        if isinstance(status, Enum):
            status = status.value

        return cls(
            sprint_id=data.get("sprint_id", sprint_id),
            project=data.get("project", data.get("id", "")),
            goal=data.get("goal", ""),
            status=status,
            mode=data.get("mode", "sequential"),
            current_gate=data.get("current_gate", data.get("currentGate", 1)),
            gates=gates,
            created_at=data.get("created_at", data.get("created", datetime.now().isoformat())),
            updated_at=data.get("updated_at", data.get("updated", datetime.now().isoformat()))
        )


# ============================================================================
# State Change Tracking
# ============================================================================

@dataclass
class StateChange:
    """Represents a change in project/sprint state."""
    entity_id: str  # Can be project_id or sprint_id
    entity_type: str  # "project" or "sprint"
    change_type: str  # "new", "stage_changed", "phase_changed", "gate_changed", "deleted", "status_changed"
    stage_name: Optional[str] = None  # For legacy projects
    phase_id: Optional[str] = None  # For sprints
    gate_number: Optional[int] = None  # For sprints
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class ConnectionMonitor:
    """Monitors connection health and triggers reconnection if needed."""

    def __init__(self, timeout_seconds: float = 60.0, check_interval: float = 5.0):
        self.timeout_seconds = timeout_seconds
        self.check_interval = check_interval
        self._last_successful_poll: float = time.time()
        self._lock = Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._reconnect_callbacks: List[Callable[[], None]] = []
        self._stop_event = Event()

    def register_reconnect_callback(self, callback: Callable[[], None]):
        """Register a callback to be called when reconnection is needed."""
        self._reconnect_callbacks.append(callback)

    def mark_success(self):
        """Mark that a successful poll occurred."""
        with self._lock:
            self._last_successful_poll = time.time()

    def is_healthy(self) -> bool:
        """Check if connection is healthy (recent successful poll)."""
        with self._lock:
            elapsed = time.time() - self._last_successful_poll
            return elapsed < self.timeout_seconds

    def get_time_since_last_success(self) -> float:
        """Get time in seconds since last successful poll."""
        with self._lock:
            return time.time() - self._last_successful_poll

    def start(self):
        """Start the connection monitor."""
        if self._running:
            return

        self._running = True
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Connection monitor started")

    def stop(self):
        """Stop the connection monitor."""
        self._running = False
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=self.check_interval + 1)
        logger.info("Connection monitor stopped")

    def _monitor_loop(self):
        """Monitor loop that checks connection health."""
        while self._running and not self._stop_event.is_set():
            try:
                time_since_success = self.get_time_since_last_success()

                if time_since_success > self.timeout_seconds:
                    logger.warning(
                        f"Connection appears hung: no successful poll for {time_since_success:.1f}s"
                    )
                    self._trigger_reconnection()

            except Exception as e:
                logger.error(f"Error in connection monitor: {e}")

            # Wait for next check or stop signal
            self._stop_event.wait(self.check_interval)

    def _trigger_reconnection(self):
        """Trigger all registered reconnection callbacks."""
        logger.info("Triggering reconnection...")
        for callback in self._reconnect_callbacks:
            try:
                callback()
            except Exception as e:
                logger.error(f"Error in reconnection callback: {e}")


class StateManager:
    """Manages reading and caching project/sprint states with file locking."""

    def __init__(self):
        self.projects_dir = Config.PROJECTS_DIR
        # Handle case where WORKSPACE_DIR is not defined in Config
        if hasattr(Config, 'WORKSPACE_DIR'):
            self.sprints_dir = Path(Config.WORKSPACE_DIR) / ".carby-sprints"
        else:
            # Use the parent directory of PROJECTS_DIR as workspace
            self.sprints_dir = Config.PROJECTS_DIR.parent / ".carby-sprints"
        self.cache_file = Config.CACHE_FILE
        self._cache: Dict[str, dict] = {}  # Combined cache for projects and sprints
        self._lock = Lock()
        self._lock_manager = get_lock_manager(self.projects_dir)
        self.connection_monitor = ConnectionMonitor()
        self._load_cache()

    def _get_project_path(self, project_id: str) -> Path:
        """Get path to project JSON file."""
        return self.projects_dir / f"{project_id}.json"

    def _get_sprint_path(self, sprint_id: str) -> Path:
        """Get path to sprint state file."""
        return self.sprints_dir / sprint_id / "state.json"

    def _load_cache(self):
        """Load cached state from disk."""
        if self.cache_file.exists():
            cache_data = safe_read_json(self.cache_file)
            if cache_data is not None:
                self._cache = cache_data
                logger.info(f"Loaded cache with {len(self._cache)} entities")
            else:
                logger.warning("Failed to load cache, starting fresh")
                self._cache = {}
        else:
            self._cache = {}

    def _save_cache(self):
        """Save cache to disk atomically."""
        Config.ensure_directories()
        if not atomic_write_json(self.cache_file, self._cache):
            logger.error(f"Failed to save cache to {self.cache_file}")

    def read_project(self, project_id: str) -> Optional[dict]:
        """Read project state from JSON file with locking."""
        path = self._get_project_path(project_id)
        try:
            with locked_json_read(path, project_id, self.projects_dir) as data:
                return data
        except TimeoutError:
            logger.error(f"Timeout reading project '{project_id}' - another process has the lock")
            # Fallback to non-locked read
            return safe_read_json(path)

    def read_project_state(self, project_id: str) -> Optional[ProjectState]:
        """Read project and return as ProjectState object with proper type handling."""
        data = self.read_project(project_id)
        if data is None:
            return None
        return ProjectState.from_dict(data, project_id)

    def read_sprint(self, sprint_id: str) -> Optional[dict]:
        """Read sprint state from JSON file with locking."""
        path = self._get_sprint_path(sprint_id)
        try:
            with locked_json_read(path, sprint_id, self.sprints_dir) as data:
                return data
        except TimeoutError:
            logger.error(f"Timeout reading sprint '{sprint_id}' - another process has the lock")
            # Fallback to non-locked read
            return safe_read_json(path)

    def read_sprint_state(self, sprint_id: str) -> Optional[SprintState]:
        """Read sprint and return as SprintState object."""
        data = self.read_sprint(sprint_id)
        if data is None:
            return None
        return SprintState.from_dict(data, sprint_id)

    def write_project(self, project_id: str, data: dict) -> bool:
        """Write project state to JSON file with locking."""
        path = self._get_project_path(project_id)
        try:
            with locked_json_write(path, project_id, self.projects_dir) as current_data:
                # Update current_data with new data
                current_data.clear()
                current_data.update(data)
            return True
        except TimeoutError:
            logger.error(f"Timeout writing project '{project_id}' - another process has the lock")
            return False
        except IOError as e:
            logger.error(f"Failed to write project '{project_id}': {e}")
            return False

    def write_project_state(self, project_state: ProjectState) -> bool:
        """Write ProjectState object to file with proper serialization."""
        # Convert to dict, handling Enum values
        data = {
            "id": project_state.id,
            "goal": project_state.goal,
            "status": project_state.status.value if isinstance(project_state.status, Enum) else project_state.status,
            "mode": project_state.mode,
            "current_stage": project_state.current_stage,
            "updated_at": project_state.updated_at,
            "created_at": project_state.created_at,
            "pipeline": project_state.pipeline,
            "stages": {}
        }

        for name, stage in project_state.stages.items():
            stage_dict = {
                "name": stage.name,
                "status": stage.status.value if isinstance(stage.status, Enum) else stage.status,
                "agent": stage.agent,
                "started_at": stage.started_at,
                "completed_at": stage.completed_at,
                "task": stage.task,
                "output": stage.output,
                "error": stage.error,
                "retry_count": stage.retry_count
            }
            data["stages"][name] = stage_dict

        return self.write_project(project_state.id, data)

    def write_sprint(self, sprint_id: str, data: dict) -> bool:
        """Write sprint state to JSON file with locking."""
        path = self._get_sprint_path(sprint_id)
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with locked_json_write(path, sprint_id, self.sprints_dir) as current_data:
                # Update current_data with new data
                current_data.clear()
                current_data.update(data)
            return True
        except TimeoutError:
            logger.error(f"Timeout writing sprint '{sprint_id}' - another process has the lock")
            return False
        except IOError as e:
            logger.error(f"Failed to write sprint '{sprint_id}': {e}")
            return False

    def write_sprint_state(self, sprint_state: SprintState) -> bool:
        """Write SprintState object to file with proper serialization."""
        # Convert to dict, handling Enum values
        data = {
            "sprint_id": sprint_state.sprint_id,
            "project": sprint_state.project,
            "goal": sprint_state.goal,
            "status": sprint_state.status.value if isinstance(sprint_state.status, Enum) else sprint_state.status,
            "mode": sprint_state.mode,
            "current_gate": sprint_state.current_gate,
            "updated_at": sprint_state.updated_at,
            "created_at": sprint_state.created_at,
            "gates": []
        }

        for gate in sprint_state.gates:
            gate_dict = {
                "gate_number": gate.gate_number,
                "name": gate.name,
                "status": gate.status.value if isinstance(gate.status, Enum) else gate.status,
                "current_phase": gate.current_phase,
                "started_at": gate.started_at,
                "completed_at": gate.completed_at,
                "phases": []
            }

            for phase in gate.phases:
                phase_dict = {
                    "phase_id": phase.phase_id,
                    "name": phase.name,
                    "status": phase.status.value if isinstance(phase.status, Enum) else phase.status,
                    "agent": phase.agent,
                    "started_at": phase.started_at,
                    "completed_at": phase.completed_at,
                    "task": phase.task,
                    "output": phase.output,
                    "error": phase.error,
                    "logs": phase.logs,
                    "retry_count": phase.retry_count
                }
                gate_dict["phases"].append(phase_dict)

            data["gates"].append(gate_dict)

        return self.write_sprint(sprint_state.sprint_id, data)

    def list_projects(self) -> List[str]:
        """List all project IDs from legacy projects directory."""
        projects = []
        try:
            for f in self.projects_dir.iterdir():
                if f.suffix == '.json':
                    projects.append(f.stem)
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Failed to list projects: {e}")
        return sorted(projects)

    def list_sprints(self) -> List[str]:
        """List all sprint IDs from .carby-sprints directory."""
        sprints = []
        try:
            for sprint_dir in self.sprints_dir.iterdir():
                if sprint_dir.is_dir():
                    state_file = sprint_dir / "state.json"
                    if state_file.exists():
                        sprints.append(sprint_dir.name)
        except (OSError, IOError, PermissionError) as e:
            logger.error(f"Failed to list sprints: {e}")
        return sorted(sprints)

    def list_all_entities(self) -> List[tuple[str, str]]:
        """List all entities (projects and sprints) with their types."""
        entities = []
        for project_id in self.list_projects():
            entities.append((project_id, "project"))
        for sprint_id in self.list_sprints():
            entities.append((sprint_id, "sprint"))
        return sorted(entities, key=lambda x: x[0])

    def detect_changes(self) -> List[StateChange]:
        """Detect changes since last poll for both projects and sprints."""
        changes = []
        current_entities = set()

        with self._lock:
            # Process projects (legacy)
            for project_id in self.list_projects():
                entity_key = f"project_{project_id}"
                current_entities.add(entity_key)
                new_state = self.read_project(project_id)

                if new_state is None:
                    continue

                old_state = self._cache.get(entity_key)

                if old_state is None:
                    # New project
                    changes.append(StateChange(
                        entity_id=project_id,
                        entity_type="project",
                        change_type="new"
                    ))
                else:
                    # Check for stage changes
                    changes.extend(self._detect_project_stage_changes(
                        project_id, old_state, new_state
                    ))

                # Update cache
                self._cache[entity_key] = new_state

            # Process sprints (new)
            for sprint_id in self.list_sprints():
                entity_key = f"sprint_{sprint_id}"
                current_entities.add(entity_key)
                new_state = self.read_sprint(sprint_id)

                if new_state is None:
                    continue

                old_state = self._cache.get(entity_key)

                if old_state is None:
                    # New sprint
                    changes.append(StateChange(
                        entity_id=sprint_id,
                        entity_type="sprint",
                        change_type="new"
                    ))
                else:
                    # Check for gate/phase changes
                    changes.extend(self._detect_sprint_changes(
                        sprint_id, old_state, new_state
                    ))

                # Update cache
                self._cache[entity_key] = new_state

            # Check for deleted entities
            for entity_key in list(self._cache.keys()):
                if entity_key not in current_entities:
                    # Extract entity_id and entity_type from key
                    if entity_key.startswith("project_"):
                        entity_id = entity_key[8:]  # Remove "project_" prefix
                        entity_type = "project"
                    elif entity_key.startswith("sprint_"):
                        entity_id = entity_key[7:]  # Remove "sprint_" prefix
                        entity_type = "sprint"
                    else:
                        continue  # Unknown entity type

                    changes.append(StateChange(
                        entity_id=entity_id,
                        entity_type=entity_type,
                        change_type="deleted"
                    ))
                    del self._cache[entity_key]

            # Save cache
            self._save_cache()

        # Mark successful poll for connection monitoring
        self.connection_monitor.mark_success()

        return changes

    def _detect_project_stage_changes(self, project_id: str, old: dict, new: dict) -> List[StateChange]:
        """Detect changes in project stage statuses."""
        changes = []

        old_stages = old.get("stages", {})
        new_stages = new.get("stages", {})

        for stage_name, new_stage in new_stages.items():
            old_stage = old_stages.get(stage_name, {})
            old_status = old_stage.get("status")
            new_status = new_stage.get("status")

            if old_status != new_status:
                changes.append(StateChange(
                    entity_id=project_id,
                    entity_type="project",
                    change_type="stage_changed",
                    stage_name=stage_name,
                    old_status=old_status,
                    new_status=new_status
                ))

        # Check for project status changes
        old_project_status = old.get("status")
        new_project_status = new.get("status")
        if old_project_status != new_project_status:
            changes.append(StateChange(
                entity_id=project_id,
                entity_type="project",
                change_type="status_changed",
                old_status=old_project_status,
                new_status=new_project_status
            ))

        return changes

    def _detect_sprint_changes(self, sprint_id: str, old: dict, new: dict) -> List[StateChange]:
        """Detect changes in sprint gate/phase statuses."""
        changes = []

        # Check for sprint status changes
        old_sprint_status = old.get("status")
        new_sprint_status = new.get("status")
        if old_sprint_status != new_sprint_status:
            changes.append(StateChange(
                entity_id=sprint_id,
                entity_type="sprint",
                change_type="status_changed",
                old_status=old_sprint_status,
                new_status=new_sprint_status
            ))

        # Check for current gate changes
        old_current_gate = old.get("current_gate", old.get("currentGate", 1))
        new_current_gate = new.get("current_gate", new.get("currentGate", 1))
        if old_current_gate != new_current_gate:
            changes.append(StateChange(
                entity_id=sprint_id,
                entity_type="sprint",
                change_type="gate_changed",
                gate_number=new_current_gate,
                old_status=str(old_current_gate),
                new_status=str(new_current_gate)
            ))

        # Check for gate and phase changes
        old_gates = old.get("gates", [])
        new_gates = new.get("gates", [])

        # Compare gates by gate number
        old_gate_map = {gate.get("gate_number", gate.get("number", i)): gate 
                        for i, gate in enumerate(old_gates)}
        new_gate_map = {gate.get("gate_number", gate.get("number", i)): gate 
                        for i, gate in enumerate(new_gates)}

        for gate_num, new_gate in new_gate_map.items():
            old_gate = old_gate_map.get(gate_num)
            if old_gate:
                # Check gate status changes
                old_gate_status = old_gate.get("status")
                new_gate_status = new_gate.get("status")
                if old_gate_status != new_gate_status:
                    changes.append(StateChange(
                        entity_id=sprint_id,
                        entity_type="sprint",
                        change_type="gate_changed",
                        gate_number=gate_num,
                        old_status=old_gate_status,
                        new_status=new_gate_status
                    ))

                # Check phase changes within the gate
                old_phases = {phase.get("phase_id", phase.get("id", f"phase_{i}")): phase 
                              for i, phase in enumerate(old_gate.get("phases", []))}
                new_phases = {phase.get("phase_id", phase.get("id", f"phase_{i}")): phase 
                              for i, phase in enumerate(new_gate.get("phases", []))}

                for phase_id, new_phase in new_phases.items():
                    old_phase = old_phases.get(phase_id)
                    if old_phase:
                        old_phase_status = old_phase.get("status")
                        new_phase_status = new_phase.get("status")
                        if old_phase_status != new_phase_status:
                            changes.append(StateChange(
                                entity_id=sprint_id,
                                entity_type="sprint",
                                change_type="phase_changed",
                                phase_id=phase_id,
                                gate_number=gate_num,
                                old_status=old_phase_status,
                                new_status=new_phase_status
                            ))
                    else:
                        # New phase
                        changes.append(StateChange(
                            entity_id=sprint_id,
                            entity_type="sprint",
                            change_type="phase_changed",
                            phase_id=phase_id,
                            gate_number=gate_num,
                            new_status=new_phase.get("status")
                        ))
            else:
                # New gate
                changes.append(StateChange(
                    entity_id=sprint_id,
                    entity_type="sprint",
                    change_type="gate_changed",
                    gate_number=gate_num,
                    new_status=new_gate.get("status")
                ))

        return changes

    def get_entity_summary(self, entity_id: str, entity_type: str) -> Optional[dict]:
        """Get summary of entity (project or sprint) for display."""
        if entity_type == "project":
            return self.get_project_summary(entity_id)
        elif entity_type == "sprint":
            return self.get_sprint_summary(entity_id)
        else:
            return None

    def get_project_summary(self, project_id: str) -> Optional[dict]:
        """Get summary of project for display."""
        state = self.read_project(project_id)
        if not state:
            return None

        current_stage = state.get("currentStage") or state.get("current_stage", "")
        stages = state.get("stages", {})
        current_stage_data = stages.get(current_stage, {}) if current_stage else {}

        # Determine current status
        current_status = current_stage_data.get("status", "unknown")

        # If no current stage or status is unknown, check project status
        if not current_stage or current_status == "unknown":
            project_status = state.get("status", "")
            if project_status == "completed":
                current_status = "completed"
            elif project_status == "failed":
                current_status = "failed"
            elif not current_stage:
                # No current stage set - check if any stages are in progress
                for stage_name, stage_data in stages.items():
                    if stage_data.get("status") == "in-progress":
                        current_stage = stage_name
                        current_status = "in-progress"
                        break
                else:
                    # No in-progress stages, find first pending
                    for stage_name in state.get("pipeline", []):
                        stage_data = stages.get(stage_name, {})
                        if stage_data.get("status") == "pending":
                            current_stage = stage_name
                            current_status = "pending"
                            break

        return {
            "id": project_id,
            "goal": state.get("goal", ""),
            "status": state.get("status", ""),
            "mode": state.get("mode", ""),
            "current_stage": current_stage,
            "current_status": current_status,
            "agent": current_stage_data.get("agent"),
            "updated_at": state.get("updated", ""),
            "type": "project"
        }

    def get_sprint_summary(self, sprint_id: str) -> Optional[dict]:
        """Get summary of sprint for display."""
        state = self.read_sprint(sprint_id)
        if not state:
            return None

        current_gate = state.get("current_gate", state.get("currentGate", 1))
        gates = state.get("gates", [])
        
        # Find current gate info
        current_gate_info = None
        for gate in gates:
            if gate.get("gate_number", gate.get("number", 0)) == current_gate:
                current_gate_info = gate
                break

        # Determine current status based on current gate
        current_status = "unknown"
        if current_gate_info:
            current_status = current_gate_info.get("status", "unknown")
        else:
            # Look for the highest completed gate
            for gate in sorted(gates, key=lambda g: g.get("gate_number", g.get("number", 0)), reverse=True):
                if gate.get("status") in ["completed", "approved"]:
                    current_gate = gate.get("gate_number", gate.get("number", 0))
                    current_status = gate.get("status")
                    break
            else:
                current_status = state.get("status", "unknown")

        # Get gate name
        gate_name = "Unknown"
        if current_gate_info:
            gate_name = current_gate_info.get("name", f"Gate {current_gate}")

        return {
            "id": sprint_id,
            "project": state.get("project", state.get("id", sprint_id)),
            "goal": state.get("goal", ""),
            "status": state.get("status", ""),
            "mode": state.get("mode", ""),
            "current_gate": current_gate,
            "current_gate_name": gate_name,
            "current_status": current_status,
            "updated_at": state.get("updated_at", state.get("updated", "")),
            "type": "sprint"
        }

    def format_entity_list(self) -> str:
        """Format entities list for Telegram - header only, entities shown in buttons."""
        entities = self.list_all_entities()
        if not entities:
            return "📋 No projects or sprints found.\n\nCreate one with ➕ New Project/Sprint"

        projects = [e[0] for e in entities if e[1] == "project"]
        sprints = [e[0] for e in entities if e[1] == "sprint"]

        msg = f"📋 Your Projects & Sprints ({len(entities)})\n\n"
        if projects:
            msg += f"Projects ({len(projects)}):\n"
            for proj in projects[:5]:  # Show first 5 projects
                msg += f"• {proj}\n"
            if len(projects) > 5:
                msg += f"... and {len(projects) - 5} more\n"
            msg += "\n"
        
        if sprints:
            msg += f"Sprints ({len(sprints)}):\n"
            for sprint in sprints[:5]:  # Show first 5 sprints
                msg += f"• {sprint}\n"
            if len(sprints) > 5:
                msg += f"... and {len(sprints) - 5} more\n"

        msg += "\nTap an entity to view details:"
        return msg

    def format_project_list(self) -> str:
        """Format project list for backward compatibility."""
        projects = self.list_projects()
        if not projects:
            return "📋 No projects found.\n\nCreate one with /new"

        msg = f"📋 Your Projects ({len(projects)})\n\n"
        for proj in projects[:10]:  # Show first 10 projects
            summary = self.get_project_summary(proj)
            if summary:
                status_icon = self._get_status_icon(summary.get("current_status", "unknown"))
                current = summary.get("current_stage", "unknown")
                msg += f"{status_icon} {proj} - {current}\n"
            else:
                msg += f"📋 {proj}\n"
        
        if len(projects) > 10:
            msg += f"\n... and {len(projects) - 10} more"
        
        return msg

    def _get_status_icon(self, status: str) -> str:
        """Get status icon for display."""
        status_icons = {
            "pending": "⬜",
            "in-progress": "🟢",
            "done": "✅",
            "failed": "🔴",
            "skipped": "⏭️",
            "archived": "🗄️",
            "completed": "🎉",
            "unknown": "❓",
        }
        return status_icons.get(status, "❓")


@dataclass
class SprintState:
    """Complete sprint state (carby-sprint)."""
    sprint_id: str
    project: str
    goal: str
    status: str
    mode: str  # sequential or parallel
    current_gate: int
    gates: List[GateState] = field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict, sprint_id: str = "") -> "SprintState":
        """Create SprintState from dictionary."""
        if not data:
            return cls(
                sprint_id=sprint_id,
                project="",
                goal="",
                status=SprintStatus.PENDING.value,
                mode="sequential",
                current_gate=1,
                gates=[]
            )

        # Parse gates
        gates_data = data.get("gates", [])
        gates = []
        for gate_data in gates_data:
            if isinstance(gate_data, dict):
                gates.append(GateState.from_dict(gate_data))
            elif isinstance(gate_data, GateState):
                gates.append(gate_data)

        return cls(
            sprint_id=data.get("sprint_id", data.get("id", sprint_id)),
            project=data.get("project", ""),
            goal=data.get("goal", ""),
            status=data.get("status", SprintStatus.PENDING.value),
            mode=data.get("mode", "sequential"),
            current_gate=data.get("current_gate", data.get("currentGate", 1)),
            gates=gates,
            created_at=data.get("created_at", data.get("createdAt")),
            updated_at=data.get("updated_at", data.get("updatedAt")),
            started_at=data.get("started_at", data.get("startedAt")),
            completed_at=data.get("completed_at", data.get("completedAt")),
            metadata=data.get("metadata", {})
        )

    def to_project_state(self) -> ProjectState:
        """Convert SprintState to legacy ProjectState for backward compatibility."""
        # Map current gate to stage
        gate_to_stage = {
            1: "discover",
            2: "design",
            3: "build",
            4: "verify",
            5: "deliver"
        }

        current_stage = gate_to_stage.get(self.current_gate, "discover")

        # Get current gate status
        current_gate_obj = None
        for gate in self.gates:
            if gate.gate_number == self.current_gate:
                current_gate_obj = gate
                break

        stage_status = StageStatus.PENDING.value
        if current_gate_obj:
            status_map = {
                GateStatus.IN_PROGRESS.value: StageStatus.IN_PROGRESS.value,
                GateStatus.COMPLETED.value: StageStatus.DONE.value,
                GateStatus.APPROVED.value: StageStatus.APPROVED.value,
                GateStatus.FAILED.value: StageStatus.FAILED.value,
                GateStatus.SKIPPED.value: StageStatus.SKIPPED.value
            }
            stage_status = status_map.get(current_gate_obj.status, StageStatus.PENDING.value)

        return ProjectState(
            id=self.sprint_id,
            goal=self.goal,
            status=ProjectStatus.ACTIVE.value if self.status != SprintStatus.ARCHIVED.value else ProjectStatus.ARCHIVED.value,
            mode=self.mode,
            current_stage=current_stage,
            stages={},  # Simplified - gates contain detailed info
            updated_at=self.updated_at or datetime.now().isoformat(),
            created_at=self.created_at,
            pipeline=[]  # Could map gates to pipeline if needed
        )


