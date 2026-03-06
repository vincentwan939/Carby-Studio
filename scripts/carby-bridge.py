"""Carby Bridge

Connects the task manager with OpenClaw sessions. It watches for artifacts produced by one agent (e.g., requirements.md) and spawns the next agent using `openclaw sessions_spawn`.
"""

import os
import subprocess
import time
import pathlib

# Configuration – adjust as needed
CARBY_ROOT = pathlib.Path(__file__).resolve().parents[2]
PROJECTS_DIR = CARBY_ROOT.parent / "projects"

def find_project_dir():
    # Assume current working directory is the project root
    cwd = pathlib.Path.cwd()
    if (cwd / "templates").exists():
        return cwd
    # fallback: search upward
    for parent in cwd.parents:
        if (parent / "templates").exists():
            return parent
    raise RuntimeError("Could not locate Carby Studio project directory")

def wait_for_file(path, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        if path.exists():
            return True
        time.sleep(2)
    return False

def spawn_agent(agent_md_path):
    cmd = ["openclaw", "sessions_spawn", "--skill", str(agent_md_path)]
    subprocess.Popen(cmd)
    print(f"Spawned agent {agent_md_path}")

def main():
    proj = find_project_dir()
    # Stage order
    stages = [
        (proj / "templates" / "requirements.md", proj / "agents" / "design.md"),
        (proj / "templates" / "design.md", proj / "agents" / "build.md"),
        (proj / "tasks", proj / "agents" / "verify.md"),
        (proj / "verify_report.md", proj / "agents" / "deliver.md"),
    ]
    for trigger, next_agent in stages:
        print(f"Waiting for {trigger} to appear...")
        if not wait_for_file(trigger):
            print(f"Timeout waiting for {trigger}, aborting.")
            return
        spawn_agent(next_agent)
        # Give the next agent time to start before proceeding
        time.sleep(5)

if __name__ == "__main__":
    main()
