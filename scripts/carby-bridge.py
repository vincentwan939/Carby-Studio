#!/usr/bin/env python3
"""
Carby Bridge

Connects the task manager with OpenClaw sessions.
Watches for artifacts produced by one agent and spawns the next agent.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
import argparse


class CarbyBridge:
    """Bridge between team-tasks state and OpenClaw agent spawning."""
    
    # Stage progression
    STAGES = ["discover", "design", "build", "verify", "deliver"]
    
    # Artifact triggers for each stage
    ARTIFACTS = {
        "discover": "docs/requirements.md",
        "design": "docs/design.md",
        "build": "tasks/build-complete.json",
        "verify": "docs/verify-report.md",
        "deliver": "docs/delivery-summary.md"
    }
    
    def __init__(self, project_dir: Path):
        self.project_dir = Path(project_dir)
        self.agents_dir = self.project_dir / "agents"
        self.state_file = self.project_dir / "state" / "tasks.json"
        
        # Verify structure
        if not self.agents_dir.exists():
            raise RuntimeError(f"Agents directory not found: {self.agents_dir}")
    
    def _load_state(self) -> Dict[str, Any]:
        """Load project state."""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                return json.load(f)
        return {"current_stage": "discover"}
    
    def _save_state(self, state: Dict[str, Any]):
        """Save project state."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def _get_current_stage(self) -> str:
        """Get current stage from state."""
        state = self._load_state()
        return state.get("current_stage", "discover")
    
    def _set_stage(self, stage: str):
        """Update current stage in state."""
        state = self._load_state()
        state["current_stage"] = stage
        self._save_state(state)
        print(f"🔄 Advanced to stage: {stage}")
    
    def _get_next_stage(self, current: str) -> Optional[str]:
        """Get next stage in sequence."""
        try:
            idx = self.STAGES.index(current)
            if idx + 1 < len(self.STAGES):
                return self.STAGES[idx + 1]
        except ValueError:
            pass
        return None
    
    def _wait_for_artifact(self, artifact_path: Path, timeout: int = 300) -> bool:
        """Wait for an artifact file to appear."""
        full_path = self.project_dir / artifact_path
        print(f"⏳ Waiting for artifact: {artifact_path}")
        
        start = time.time()
        while time.time() - start < timeout:
            if full_path.exists():
                print(f"✅ Found artifact: {artifact_path}")
                return True
            time.sleep(2)
        
        print(f"❌ Timeout waiting for {artifact_path}")
        return False
    
    def _spawn_agent(self, stage: str, context_files: Optional[list] = None):
        """Spawn the next agent using sessions_spawn."""
        agent_file = self.agents_dir / f"{stage}.md"
        
        if not agent_file.exists():
            print(f"❌ Agent file not found: {agent_file}")
            return False
        
        print(f"🚀 Spawning {stage} agent...")
        
        # Build command
        cmd = [
            "openclaw", "sessions_spawn",
            "--runtime", "subagent",
            "--mode", "run",
            "--task", f"Execute Carby Studio {stage} phase. Read the agent prompt at {agent_file} and follow instructions."
        ]
        
        # Add context files if provided
        if context_files:
            for cf in context_files:
                cmd.extend(["--attach", str(cf)])
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ {stage} agent spawned successfully")
                return True
            else:
                print(f"❌ Failed to spawn agent: {result.stderr}")
                return False
        except Exception as e:
            print(f"❌ Error spawning agent: {e}")
            return False
    
    def _spawn_agent_api(self, stage: str, context_files: Optional[list] = None):
        """Spawn agent using Python API (alternative to CLI)."""
        agent_file = self.agents_dir / f"{stage}.md"
        
        if not agent_file.exists():
            print(f"❌ Agent file not found: {agent_file}")
            return False
        
        print(f"🚀 Spawning {stage} agent via API...")
        
        try:
            # Import OpenClaw API (if available)
            # This is a placeholder - actual implementation depends on OpenClaw SDK
            import openclaw
            
            session = openclaw.spawn_session(
                runtime="subagent",
                mode="run",
                task=f"Execute Carby Studio {stage} phase",
                attachments=[str(agent_file)] + (context_files or [])
            )
            
            print(f"✅ {stage} agent spawned: {session.id}")
            return True
            
        except ImportError:
            print("⚠️ OpenClaw SDK not available, falling back to CLI")
            return self._spawn_agent(stage, context_files)
        except Exception as e:
            print(f"❌ Error spawning agent: {e}")
            return False
    
    def run_stage(self, stage: Optional[str] = None, wait: bool = True):
        """Run a specific stage or current stage."""
        if stage is None:
            stage = self._get_current_stage()
        
        if stage not in self.STAGES:
            print(f"❌ Unknown stage: {stage}")
            return False
        
        print(f"\n📍 Running stage: {stage.upper()}")
        
        # Determine context files based on stage
        context_files = []
        if stage == "design":
            context_files = ["docs/requirements.md"]
        elif stage == "build":
            context_files = ["docs/design.md", "docs/requirements.md"]
        elif stage == "verify":
            context_files = ["docs/design.md", "tasks/build-complete.json"]
        elif stage == "deliver":
            context_files = ["docs/verify-report.md"]
        
        # Spawn agent
        success = self._spawn_agent(stage, context_files)
        
        if success and wait:
            # Wait for artifact
            artifact = self.ARTIFACTS.get(stage)
            if artifact:
                if self._wait_for_artifact(Path(artifact)):
                    # Advance to next stage
                    next_stage = self._get_next_stage(stage)
                    if next_stage:
                        self._set_stage(next_stage)
                    else:
                        print("🎉 Pipeline complete!")
                    return True
                else:
                    return False
        
        return success
    
    def watch(self, interval: int = 5):
        """Watch for state changes and trigger next stages."""
        print("👁️  Starting watch mode...")
        print(f"   Project: {self.project_dir}")
        print(f"   Current stage: {self._get_current_stage()}")
        print("   Press Ctrl+C to stop\n")
        
        try:
            while True:
                current = self._get_current_stage()
                artifact = self.ARTIFACTS.get(current)
                
                if artifact:
                    full_path = self.project_dir / artifact
                    if full_path.exists():
                        print(f"\n📁 Detected artifact: {artifact}")
                        self.run_stage(current, wait=False)
                        # Give agent time to start
                        time.sleep(10)
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n👋 Watch mode stopped")
    
    def status(self):
        """Show bridge status."""
        current = self._get_current_stage()
        
        print(f"\n📊 Carby Bridge Status")
        print(f"   Project: {self.project_dir}")
        print(f"   Current stage: {current}")
        
        # Check artifacts
        print(f"\n📁 Artifacts:")
        for stage, artifact in self.ARTIFACTS.items():
            full_path = self.project_dir / artifact
            status = "✅" if full_path.exists() else "⏳"
            marker = "→" if stage == current else " "
            print(f"   {marker} {status} [{stage}] {artifact}")
        
        # Check agents
        print(f"\n🤖 Agents:")
        for stage in self.STAGES:
            agent_file = self.agents_dir / f"{stage}.md"
            status = "✅" if agent_file.exists() else "❌"
            print(f"   {status} {stage}.md")


def main():
    parser = argparse.ArgumentParser(description="Carby Bridge - Connects tasks to OpenClaw agents")
    parser.add_argument("--project", "-p", default=".", help="Project directory")
    parser.add_argument("--watch", "-w", action="store_true", help="Watch mode")
    parser.add_argument("--status", "-s", action="store_true", help="Show status")
    parser.add_argument("--stage", choices=CarbyBridge.STAGES, help="Run specific stage")
    parser.add_argument("--interval", "-i", type=int, default=5, help="Watch interval (seconds)")
    
    args = parser.parse_args()
    
    project_dir = Path(args.project).resolve()
    
    try:
        bridge = CarbyBridge(project_dir)
    except RuntimeError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    if args.status:
        bridge.status()
    elif args.watch:
        bridge.watch(args.interval)
    elif args.stage:
        bridge.run_stage(args.stage)
    else:
        # Run current stage
        bridge.run_stage()


if __name__ == "__main__":
    main()
