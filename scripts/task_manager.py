#!/usr/bin/env python3
"""
Task Manager for Carby Studio

Adapted from team-tasks (https://github.com/win4r/team-tasks)
Provides utilities for creating GitHub issues, branches, and PRs.
Also manages project state in JSON format.
"""

import os
import json
import subprocess
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


class TaskManager:
    """Manages tasks for Carby Studio projects."""
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.state_dir = self.project_dir / "state"
        self.state_file = self.state_dir / "tasks.json"
        self.state_dir.mkdir(exist_ok=True)
        
        # Load or initialize state
        self.state = self._load_state()
    
    def _load_state(self) -> Dict[str, Any]:
        """Load project state from JSON file."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {
            "project": self.project_dir.name,
            "created": datetime.now().isoformat(),
            "mode": "linear",  # linear, dag, or debate
            "tasks": [],
            "current_stage": "discover"
        }
    
    def _save_state(self):
        """Save project state to JSON file."""
        self.state["updated"] = datetime.now().isoformat()
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def init_project(self, mode: str = "linear"):
        """Initialize a new project with specified workflow mode."""
        self.state["mode"] = mode
        self.state["current_stage"] = "discover"
        self._save_state()
        print(f"Initialized project '{self.project_dir.name}' with {mode} mode")
    
    def add_task(self, title: str, description: str = "", 
                 dependencies: Optional[List[str]] = None,
                 stage: str = "build") -> str:
        """Add a new task to the project."""
        task_id = f"TASK-{len(self.state['tasks']) + 1:03d}"
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "stage": stage,
            "status": "pending",
            "dependencies": dependencies or [],
            "created": datetime.now().isoformat(),
            "issue_url": None,
            "branch": None,
            "pr_url": None
        }
        self.state["tasks"].append(task)
        self._save_state()
        print(f"Added task {task_id}: {title}")
        return task_id
    
    def create_github_issue(self, task_id: str, repo: str) -> Optional[str]:
        """Create a GitHub issue for a task."""
        task = self._get_task(task_id)
        if not task:
            print(f"Task {task_id} not found")
            return None
        
        body = f"""## Description
{task['description']}

## Task ID
{task_id}

## Stage
{task['stage']}

## Dependencies
{', '.join(task['dependencies']) if task['dependencies'] else 'None'}
"""
        
        try:
            cmd = [
                "gh", "issue", "create",
                "--repo", repo,
                "--title", f"[{task_id}] {task['title']}",
                "--body", body,
                "--label", "carby-studio"
            ]
            result = subprocess.check_output(cmd, text=True).strip()
            task["issue_url"] = result
            self._save_state()
            print(f"Created issue: {result}")
            return result
        except subprocess.CalledProcessError as e:
            print(f"Failed to create issue: {e}")
            return None
    
    def create_branch(self, task_id: str, repo: str) -> Optional[str]:
        """Create a feature branch for a task."""
        task = self._get_task(task_id)
        if not task:
            print(f"Task {task_id} not found")
            return None
        
        branch_name = f"feature/{task_id}-{task['title'].lower().replace(' ', '-')[:30]}"
        
        try:
            # Ensure we're on main and up to date
            subprocess.check_call(["git", "checkout", "main"])
            subprocess.check_call(["git", "pull", "origin", "main"])
            
            # Create and checkout branch
            subprocess.check_call(["git", "checkout", "-b", branch_name])
            
            task["branch"] = branch_name
            self._save_state()
            print(f"Created branch: {branch_name}")
            return branch_name
        except subprocess.CalledProcessError as e:
            print(f"Failed to create branch: {e}")
            return None
    
    def update_task_status(self, task_id: str, status: str):
        """Update task status (pending, in-progress, done)."""
        task = self._get_task(task_id)
        if task:
            task["status"] = status
            task["updated"] = datetime.now().isoformat()
            self._save_state()
            print(f"Updated {task_id} to {status}")
    
    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """Get next task in linear mode."""
        if self.state["mode"] != "linear":
            print("get_next_task only works in linear mode")
            return None
        
        for task in self.state["tasks"]:
            if task["status"] == "pending":
                return task
        return None
    
    def get_ready_tasks(self) -> List[Dict[str, Any]]:
        """Get tasks ready to start (all dependencies done)."""
        if self.state["mode"] != "dag":
            print("get_ready_tasks only works in dag mode")
            return []
        
        ready = []
        done_ids = {t["id"] for t in self.state["tasks"] if t["status"] == "done"}
        
        for task in self.state["tasks"]:
            if task["status"] == "pending":
                if all(dep in done_ids for dep in task["dependencies"]):
                    ready.append(task)
        
        return ready
    
    def show_status(self):
        """Display project status."""
        print(f"\n📁 Project: {self.state['project']}")
        print(f"🔄 Mode: {self.state['mode']}")
        print(f"📊 Stage: {self.state['current_stage']}")
        print(f"\n📋 Tasks:")
        
        for task in self.state["tasks"]:
            status_icon = {
                "pending": "⏳",
                "in-progress": "🔄",
                "done": "✅"
            }.get(task["status"], "❓")
            
            deps = f" (deps: {', '.join(task['dependencies'])})" if task["dependencies"] else ""
            print(f"  {status_icon} {task['id']}: {task['title']}{deps}")
        
        pending = sum(1 for t in self.state["tasks"] if t["status"] == "pending")
        in_progress = sum(1 for t in self.state["tasks"] if t["status"] == "in-progress")
        done = sum(1 for t in self.state["tasks"] if t["status"] == "done")
        
        print(f"\n📈 Progress: {done} done, {in_progress} in progress, {pending} pending")
    
    def _get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task by ID."""
        for task in self.state["tasks"]:
            if task["id"] == task_id:
                return task
        return None


def main():
    parser = argparse.ArgumentParser(description="Carby Studio Task Manager")
    parser.add_argument("--project", "-p", default=".", help="Project directory")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize project")
    init_parser.add_argument("--mode", choices=["linear", "dag", "debate"], 
                            default="linear", help="Workflow mode")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("--description", "-d", default="", help="Task description")
    add_parser.add_argument("--deps", help="Comma-separated dependency task IDs")
    add_parser.add_argument("--stage", default="build", 
                           choices=["discover", "design", "build", "verify", "deliver"],
                           help="SDLC stage")
    
    # Issue command
    issue_parser = subparsers.add_parser("issue", help="Create GitHub issue")
    issue_parser.add_argument("task_id", help="Task ID")
    issue_parser.add_argument("--repo", "-r", required=True, help="GitHub repo (owner/repo)")
    
    # Branch command
    branch_parser = subparsers.add_parser("branch", help="Create feature branch")
    branch_parser.add_argument("task_id", help="Task ID")
    branch_parser.add_argument("--repo", "-r", required=True, help="GitHub repo (owner/repo)")
    
    # Status command
    subparsers.add_parser("status", help="Show project status")
    
    # Next command (linear mode)
    subparsers.add_parser("next", help="Get next task (linear mode)")
    
    # Ready command (dag mode)
    subparsers.add_parser("ready", help="Get ready tasks (dag mode)")
    
    # Update command
    update_parser = subparsers.add_parser("update", help="Update task status")
    update_parser.add_argument("task_id", help="Task ID")
    update_parser.add_argument("status", choices=["pending", "in-progress", "done"],
                              help="New status")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tm = TaskManager(Path(args.project))
    
    if args.command == "init":
        tm.init_project(args.mode)
    
    elif args.command == "add":
        deps = args.deps.split(",") if args.deps else None
        tm.add_task(args.title, args.description, deps, args.stage)
    
    elif args.command == "issue":
        tm.create_github_issue(args.task_id, args.repo)
    
    elif args.command == "branch":
        tm.create_branch(args.task_id, args.repo)
    
    elif args.command == "status":
        tm.show_status()
    
    elif args.command == "next":
        task = tm.get_next_task()
        if task:
            print(f"Next task: {task['id']} - {task['title']}")
        else:
            print("No pending tasks")
    
    elif args.command == "ready":
        tasks = tm.get_ready_tasks()
        if tasks:
            print("Ready tasks:")
            for t in tasks:
                print(f"  {t['id']}: {t['title']}")
        else:
            print("No ready tasks")
    
    elif args.command == "update":
        tm.update_task_status(args.task_id, args.status)


if __name__ == "__main__":
    main()
