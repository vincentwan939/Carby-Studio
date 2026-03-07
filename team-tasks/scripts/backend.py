#!/usr/bin/env python3
"""Backend abstraction for team-tasks storage.

Supports two backends:
- FileBackend: JSON file storage with fcntl locking (default)
- SQLiteBackend: SQLite database for high-concurrency scenarios

Usage:
    from backend import get_backend
    
    backend = get_backend()  # Uses CARBY_BACKEND env var or defaults to file
    data = backend.load_project("my-project")
    backend.save_project("my-project", data)
    
    # Atomic update
    backend.atomic_update("my-project", lambda data: data["status"] = "done")
"""

import json
import os
import sys
import fcntl
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Any, Optional

# Default tasks directory
if sys.platform == "darwin":
    DEFAULT_TASKS_DIR = Path.home() / ".openclaw" / "workspace" / "projects"
elif sys.platform == "linux":
    DEFAULT_TASKS_DIR = Path("/home/ubuntu/clawd/data/team-tasks")
else:
    DEFAULT_TASKS_DIR = Path.home() / ".openclaw" / "workspace" / "projects"

TASKS_DIR = Path(os.environ.get("TEAM_TASKS_DIR", DEFAULT_TASKS_DIR))


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class Backend(ABC):
    """Abstract base class for storage backends."""
    
    @abstractmethod
    def load_project(self, project_id: str) -> Dict[str, Any]:
        """Load a project by ID."""
        pass
    
    @abstractmethod
    def save_project(self, project_id: str, data: Dict[str, Any]) -> None:
        """Save a project."""
        pass
    
    @abstractmethod
    def atomic_update(self, project_id: str, update_func: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        """Atomically update a project.
        
        Args:
            project_id: Project identifier
            update_func: Function that modifies the data dict in place
            
        Returns:
            The updated project data
        """
        pass
    
    @abstractmethod
    def list_projects(self) -> list:
        """List all project IDs."""
        pass
    
    @abstractmethod
    def delete_project(self, project_id: str) -> None:
        """Delete a project."""
        pass


class FileBackend(Backend):
    """File-based JSON storage with fcntl locking."""
    
    def __init__(self, tasks_dir: Optional[Path] = None):
        self.tasks_dir = Path(tasks_dir) if tasks_dir else TASKS_DIR
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
    
    def _project_path(self, project_id: str) -> Path:
        return self.tasks_dir / f"{project_id}.json"
    
    def load_project(self, project_id: str) -> Dict[str, Any]:
        path = self._project_path(project_id)
        if not path.exists():
            raise FileNotFoundError(f"Project '{project_id}' not found at {path}")
        with open(path) as f:
            return json.load(f)
    
    def save_project(self, project_id: str, data: Dict[str, Any]) -> None:
        path = self._project_path(project_id)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def atomic_update(self, project_id: str, update_func: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        path = self._project_path(project_id)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        
        # Open in read+write mode, create if doesn't exist
        with open(path, "a+") as f:
            # Acquire exclusive lock
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                # Read current state
                f.seek(0)
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    # File is empty or corrupted, start fresh
                    data = {"project": project_id, "stages": {}, "status": "active"}
                
                # Apply update
                update_func(data)
                
                # Write updated state
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2, ensure_ascii=False)
                
                return data
            finally:
                # Release lock
                fcntl.flock(f, fcntl.LOCK_UN)
    
    def list_projects(self) -> list:
        projects = []
        if self.tasks_dir.exists():
            for f in self.tasks_dir.iterdir():
                if f.suffix == ".json":
                    projects.append(f.stem)
        return sorted(projects)
    
    def delete_project(self, project_id: str) -> None:
        path = self._project_path(project_id)
        if path.exists():
            path.unlink()


class SQLiteBackend(Backend):
    """SQLite-based storage for high-concurrency scenarios."""
    
    SCHEMA = """
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        goal TEXT,
        mode TEXT,
        status TEXT,
        created_at TIMESTAMP,
        updated_at TIMESTAMP,
        data JSON
    );
    
    CREATE TABLE IF NOT EXISTS stages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT,
        stage_id TEXT,
        agent TEXT,
        status TEXT,
        task TEXT,
        output TEXT,
        started_at TIMESTAMP,
        completed_at TIMESTAMP,
        depends_on JSON,
        logs JSON,
        FOREIGN KEY (project_id) REFERENCES projects(id),
        UNIQUE(project_id, stage_id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_stages_project ON stages(project_id);
    CREATE INDEX IF NOT EXISTS idx_stages_status ON stages(status);
    CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
    """
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = Path(db_path)
        else:
            # Store in same directory as tasks
            self.db_path = TASKS_DIR / "carby.db"
        
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()
    
    def _row_to_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        return {key: row[key] for key in row.keys()}
    
    def load_project(self, project_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Load project
            cursor.execute(
                "SELECT * FROM projects WHERE id = ?",
                (project_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                raise FileNotFoundError(f"Project '{project_id}' not found")
            
            # Parse JSON data
            data = json.loads(row["data"]) if row["data"] else {}
            
            # Load stages
            cursor.execute(
                "SELECT * FROM stages WHERE project_id = ?",
                (project_id,)
            )
            stages = {}
            for stage_row in cursor.fetchall():
                stage_id = stage_row["stage_id"]
                stages[stage_id] = {
                    "agent": stage_row["agent"],
                    "status": stage_row["status"],
                    "task": stage_row["task"] or "",
                    "output": stage_row["output"] or "",
                    "startedAt": stage_row["started_at"],
                    "completedAt": stage_row["completed_at"],
                    "logs": json.loads(stage_row["logs"]) if stage_row["logs"] else [],
                }
                if stage_row["depends_on"]:
                    stages[stage_id]["dependsOn"] = json.loads(stage_row["depends_on"])
            
            # Build full project data
            project_data = {
                "project": row["id"],
                "goal": row["goal"] or "",
                "mode": row["mode"] or "linear",
                "status": row["status"] or "active",
                "created": row["created_at"],
                "updated": row["updated_at"],
                "stages": stages,
            }
            
            # Merge with stored JSON data for extra fields
            project_data.update(data)
            
            return project_data
    
    def save_project(self, project_id: str, data: Dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Extract core fields
            goal = data.get("goal", "")
            mode = data.get("mode", "linear")
            status = data.get("status", "active")
            created = data.get("created", now_iso())
            updated = now_iso()
            
            # Store extra fields as JSON
            extra_data = {k: v for k, v in data.items() 
                         if k not in ("project", "goal", "mode", "status", 
                                     "created", "updated", "stages")}
            
            # Insert or update project
            cursor.execute(
                """INSERT OR REPLACE INTO projects 
                   (id, goal, mode, status, created_at, updated_at, data)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (project_id, goal, mode, status, created, updated, 
                 json.dumps(extra_data))
            )
            
            # Save stages
            stages = data.get("stages", {})
            for stage_id, stage_data in stages.items():
                cursor.execute(
                    """INSERT OR REPLACE INTO stages
                       (project_id, stage_id, agent, status, task, output,
                        started_at, completed_at, depends_on, logs)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (project_id, stage_id,
                     stage_data.get("agent", stage_id),
                     stage_data.get("status", "pending"),
                     stage_data.get("task", ""),
                     stage_data.get("output", ""),
                     stage_data.get("startedAt"),
                     stage_data.get("completedAt"),
                     json.dumps(stage_data.get("dependsOn")),
                     json.dumps(stage_data.get("logs", [])))
                )
            
            conn.commit()
    
    def atomic_update(self, project_id: str, update_func: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'EXCLUSIVE'
            cursor = conn.cursor()
            
            try:
                cursor.execute("BEGIN EXCLUSIVE")
                
                # Load current data
                try:
                    data = self.load_project(project_id)
                except FileNotFoundError:
                    data = {"project": project_id, "stages": {}, "status": "active"}
                
                # Apply update
                update_func(data)
                
                # Save updated data
                self.save_project(project_id, data)
                
                conn.commit()
                return data
            except Exception:
                conn.rollback()
                raise
    
    def list_projects(self) -> list:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM projects ORDER BY id")
            return [row[0] for row in cursor.fetchall()]
    
    def delete_project(self, project_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM stages WHERE project_id = ?", (project_id,))
            cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()


def get_backend(backend_type: Optional[str] = None) -> Backend:
    """Get the configured backend.
    
    Args:
        backend_type: 'file', 'sqlite', or None (uses CARBY_BACKEND env var)
        
    Returns:
        Backend instance
    """
    if backend_type is None:
        backend_type = os.environ.get("CARBY_BACKEND", "file")
    
    if backend_type == "sqlite":
        return SQLiteBackend()
    elif backend_type == "file":
        return FileBackend()
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


def migrate_to_sqlite(project_id: Optional[str] = None) -> None:
    """Migrate projects from file backend to SQLite backend.
    
    Args:
        project_id: Specific project to migrate, or None for all
    """
    file_backend = FileBackend()
    sqlite_backend = SQLiteBackend()
    
    if project_id:
        projects = [project_id]
    else:
        projects = file_backend.list_projects()
    
    migrated = 0
    for pid in projects:
        try:
            data = file_backend.load_project(pid)
            sqlite_backend.save_project(pid, data)
            print(f"✓ Migrated: {pid}")
            migrated += 1
        except Exception as e:
            print(f"✗ Failed to migrate {pid}: {e}")
    
    print(f"\nMigrated {migrated}/{len(projects)} projects to SQLite")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Backend management")
    parser.add_argument("--migrate", "-m", metavar="PROJECT",
                       help="Migrate project(s) to SQLite (use 'all' for all)")
    parser.add_argument("--list", "-l", action="store_true",
                       help="List projects in current backend")
    parser.add_argument("--backend", "-b", choices=["file", "sqlite"],
                       help="Backend to use")
    
    args = parser.parse_args()
    
    if args.backend:
        os.environ["CARBY_BACKEND"] = args.backend
    
    if args.migrate:
        project = None if args.migrate == "all" else args.migrate
        migrate_to_sqlite(project)
    elif args.list:
        backend = get_backend()
        projects = backend.list_projects()
        print(f"Projects ({len(projects)}):")
        for p in projects:
            print(f"  - {p}")
    else:
        parser.print_help()
