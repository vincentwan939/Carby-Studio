"""
Sprint Repository - Centralized sprint data access layer.

Provides a unified interface for loading, saving, and managing sprint data.
Eliminates code duplication across CLI commands and maintains backward
compatibility with existing function-based API.
"""

from __future__ import annotations

import json
import shutil
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Tuple, Optional
from dataclasses import dataclass

# Import security modules
from .lock_manager import with_sprint_lock, default_sprint_lock_path
from .validators import validate_sprint, validate_work_item
from .path_utils import validate_sprint_id, validate_work_item_id, safe_join_path


@dataclass
class SprintPaths:
    """Container for sprint-related file paths."""
    sprint_dir: Path
    metadata: Path
    work_items: Path
    gates: Path
    logs: Path

    @property
    def execution_lock(self) -> Path:
        """Path to execution lock file."""
        return self.sprint_dir / ".execution.lock"


class SprintRepository:
    """
    Repository for sprint data access and manipulation.

    This class centralizes all sprint-related file operations,
    providing a clean API for loading, saving, and managing sprint data.
    """

    DEFAULT_OUTPUT_DIR = ".carby-sprints"

    def __init__(self, output_dir: str = DEFAULT_OUTPUT_DIR):
        """
        Initialize the repository.

        Args:
            output_dir: Base directory for sprint data storage
        """
        self.output_dir = Path(output_dir)
        # Thread-local storage for connections - properly initialized
        self._local = threading.local()
        # Ensure thread-local has required attributes
        self._local.connections = {}
        self._local.locks = {}

    def get_sprint_path(self, sprint_id: str) -> Path:
        """Get the path to a sprint directory with validation."""
        # Validate the sprint ID to prevent path traversal
        validate_sprint_id(sprint_id)
        return self.output_dir / sprint_id

    def get_paths(self, sprint_id: str) -> SprintPaths:
        """Get all relevant paths for a sprint."""
        sprint_dir = self.get_sprint_path(sprint_id)
        return SprintPaths(
            sprint_dir=sprint_dir,
            metadata=sprint_dir / "metadata.json",
            work_items=sprint_dir / "work_items",
            gates=sprint_dir / "gates",
            logs=sprint_dir / "logs",
        )

    def exists(self, sprint_id: str) -> bool:
        """Check if a sprint exists with validation."""
        # Validate the sprint ID to prevent path traversal
        validate_sprint_id(sprint_id)
        paths = self.get_paths(sprint_id)
        return paths.metadata.exists()

    def load(self, sprint_id: str) -> Tuple[Dict[str, Any], SprintPaths]:
        """
        Load sprint metadata.

        Args:
            sprint_id: The sprint identifier

        Returns:
            Tuple of (sprint_data, paths)

        Raises:
            FileNotFoundError: If sprint not found
        """
        paths = self.get_paths(sprint_id)

        if not paths.metadata.exists():
            raise FileNotFoundError(f"Sprint '{sprint_id}' not found.")

        with open(paths.metadata, "r") as f:
            sprint_data = json.load(f)

        return sprint_data, paths

    def load_or_raise(self, sprint_id: str, exception_class: type | None = None, message: str | None = None) -> tuple[dict[str, Any], SprintPaths]:
        """
        Load sprint with custom exception handling.

        Args:
            sprint_id: The sprint identifier
            exception_class: Exception class to raise (default: FileNotFoundError)
            message: Custom error message

        Returns:
            Tuple of (sprint_data, paths)
        """
        try:
            return self.load(sprint_id)
        except FileNotFoundError as e:
            exc_class = exception_class or FileNotFoundError
            msg = message or str(e)
            raise exc_class(msg)

    def save(self, sprint_data: Dict[str, Any], paths: SprintPaths) -> None:
        """
        Save sprint metadata with validation and atomic transaction.

        Args:
            sprint_data: Sprint data dictionary
            paths: SprintPaths object
        """
        # Validate sprint data before saving
        try:
            validated_data = validate_sprint(sprint_data)
            # Use Pydantic's serialization that handles datetime properly
            sprint_data = validated_data.model_dump(mode='json')
        except Exception as e:
            raise ValueError(f"Sprint data validation failed: {str(e)}")
        
        from .transaction import atomic_sprint_update
        # Use atomic transaction to ensure data integrity
        with atomic_sprint_update(paths.sprint_dir) as data:
            # Update the data in the transaction context
            data.clear()
            data.update(sprint_data)

    @with_sprint_lock(default_sprint_lock_path)
    def save_by_id(self, sprint_id: str, sprint_data: Dict[str, Any]) -> None:
        """
        Save sprint metadata by sprint ID with locking and atomic transaction.

        Args:
            sprint_id: The sprint identifier
            sprint_data: Sprint data dictionary
        """
        paths = self.get_paths(sprint_id)
        self.save(sprint_data, paths)

    def create(
        self,
        sprint_id: str,
        project: str,
        goal: str,
        description: str = "",
        duration_days: int = 14,
        start_date: Optional[datetime] = None,
    ) -> Tuple[Dict[str, Any], SprintPaths]:
        """
        Create a new sprint.

        Args:
            sprint_id: Unique sprint identifier
            project: Project name
            goal: Sprint goal
            description: Optional description
            duration_days: Sprint duration in days
            start_date: Optional start date (defaults to now)

        Returns:
            Tuple of (sprint_data, paths)
        """
        start = start_date or datetime.now()
        from datetime import timedelta
        end = start + timedelta(days=duration_days)

        sprint_data = {
            "sprint_id": sprint_id,
            "project": project,
            "goal": goal,
            "description": description,
            "status": "initialized",
            "created_at": datetime.now().isoformat(),
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "duration_days": duration_days,
            "work_items": [],
            "gates": {
                "1": {"status": "pending", "name": "Planning Gate"},
                "2": {"status": "pending", "name": "Design Gate"},
                "3": {"status": "pending", "name": "Implementation Gate"},
                "4": {"status": "pending", "name": "Validation Gate"},
                "5": {"status": "pending", "name": "Release Gate"},
            },
            "validation_token": None,
            "risk_score": None,
        }

        paths = self.get_paths(sprint_id)
        paths.sprint_dir.mkdir(parents=True, exist_ok=True)

        # Save metadata using atomic transaction
        self.save(sprint_data, paths)

        # Create subdirectories
        paths.work_items.mkdir(exist_ok=True)
        paths.gates.mkdir(exist_ok=True)
        paths.logs.mkdir(exist_ok=True)

        return sprint_data, paths

    def delete(self, sprint_id: str) -> None:
        """Delete a sprint directory."""
        paths = self.get_paths(sprint_id)
        if paths.sprint_dir.exists():
            shutil.rmtree(paths.sprint_dir)

    def archive(
        self,
        sprint_id: str,
        archive_dir: Path,
        update_status: bool = True,
    ) -> Path:
        """
        Archive a sprint.

        Args:
            sprint_id: Sprint to archive
            archive_dir: Destination directory
            update_status: Whether to update status to 'archived'

        Returns:
            Path to archived sprint
        """
        sprint_data, paths = self.load(sprint_id)

        if update_status:
            sprint_data["status"] = "archived"
            sprint_data["archived_at"] = datetime.now().isoformat()
            self.save(sprint_data, paths)

        archive_dir.mkdir(parents=True, exist_ok=True)
        dest_path = archive_dir / sprint_id

        if dest_path.exists():
            shutil.rmtree(dest_path)

        shutil.move(str(paths.sprint_dir), str(dest_path))

        return dest_path

    # Work item operations

    def load_work_item(self, paths: SprintPaths, work_item_id: str) -> Dict[str, Any]:
        """Load a work item with path validation."""
        # Validate the work item ID to prevent path traversal
        validate_work_item_id(work_item_id)
        
        wi_path = paths.work_items / f"{work_item_id}.json"
        if not wi_path.exists():
            raise FileNotFoundError(f"Work item '{work_item_id}' not found.")

        with open(wi_path, "r") as f:
            data: dict[str, Any] = json.load(f)
            return data

    def save_work_item(self, paths: SprintPaths, work_item: Dict[str, Any]) -> None:
        """Save a work item with validation and atomic transaction."""
        # Validate work item data before saving
        try:
            validated_data = validate_work_item(work_item)
            # Use Pydantic's serialization that handles datetime properly
            work_item = validated_data.model_dump(mode='json')
        except Exception as e:
            raise ValueError(f"Work item data validation failed: {str(e)}")
        
        # Validate the work item ID to prevent path traversal
        validate_work_item_id(work_item['id'])
        
        from .transaction import atomic_work_item_update
        with atomic_work_item_update(paths.work_items, work_item['id']) as data:
            # Update the data in the transaction context
            data.clear()
            data.update(work_item)

    def list_work_items(self, paths: SprintPaths) -> list[str]:
        """List all work item IDs."""
        if not paths.work_items.exists():
            return []
        return [f.stem for f in paths.work_items.glob("*.json")]

    def delete_work_item(self, paths: SprintPaths, work_item_id: str) -> None:
        """Delete a work item with path validation."""
        # Validate the work item ID to prevent path traversal
        validate_work_item_id(work_item_id)
        
        wi_path = paths.work_items / f"{work_item_id}.json"
        if wi_path.exists():
            wi_path.unlink()


# Backward compatibility functions - deprecated but maintained for compatibility

def get_sprint_path(sprint_id: str, output_dir: str = SprintRepository.DEFAULT_OUTPUT_DIR) -> Path:
    """
    Get the path to a sprint directory.

    DEPRECATED: Use SprintRepository.get_sprint_path() instead.
    """
    repo = SprintRepository(output_dir)
    return repo.get_sprint_path(sprint_id)


def load_sprint(sprint_id: str, output_dir: str = SprintRepository.DEFAULT_OUTPUT_DIR) -> Tuple[Dict[str, Any], Path]:
    """
    Load sprint metadata.

    DEPRECATED: Use SprintRepository.load() instead.
    Returns tuple of (sprint_data, sprint_path) for backward compatibility.
    """
    repo = SprintRepository(output_dir)
    sprint_data, paths = repo.load_or_raise(
        sprint_id,
        exception_class=Exception,
        message=f"Sprint '{sprint_id}' not found."
    )
    return sprint_data, paths.sprint_dir


def save_sprint(sprint_data: Dict[str, Any], sprint_path: Path) -> None:
    """
    Save sprint metadata.

    DEPRECATED: Use SprintRepository.save() instead.
    """
    from .transaction import atomic_sprint_update
    paths = SprintPaths(
        sprint_dir=Path(sprint_path),
        metadata=Path(sprint_path) / "metadata.json",
        work_items=Path(sprint_path) / "work_items",
        gates=Path(sprint_path) / "gates",
        logs=Path(sprint_path) / "logs",
    )
    
    # Use atomic transaction to ensure data integrity
    with atomic_sprint_update(Path(sprint_path)) as (data, temp_dir):
        # Update the data in the transaction context
        for key, value in sprint_data.items():
            data[key] = value