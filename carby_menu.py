"""
Carby Studio Interactive Menu for OpenClaw AI Agent
Provides button-based project/sprint listing using OpenClaw's interactive blocks
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# Paths
WORKSPACE_PROJECTS = Path("~/.openclaw/workspace/projects").expanduser()
CARBY_SPRINTS = Path("~/.openclaw/workspace/skills/carby-studio/.carby-sprints")


def get_project_status_icon(status: str, current_stage: str, stages: dict) -> str:
    """Get status icon for legacy projects."""
    if status == "completed":
        return "🟢"
    elif status == "failed" or any(s.get("status") == "failed" for s in stages.values()):
        return "🔴"
    elif current_stage and current_stage != "discover":
        return "🟡"
    else:
        return "🔵"


def get_sprint_status_icon(status: str) -> str:
    """Get status icon for carby-sprint projects."""
    status_map = {
        "completed": "✅",
        "archived": "✅",
        "in-progress": "🔄",
        "failed": "❌",
        "paused": "⏸️",
        "pending": "⬜",
        "cancelled": "❌"
    }
    return status_map.get(status, "⬜")


def list_workspace_projects() -> List[Tuple[str, str, str]]:
    """List workspace projects with status icons.
    Returns: [(project_id, icon, type), ...]
    """
    entities = []

    if not WORKSPACE_PROJECTS.exists():
        return entities

    for item in WORKSPACE_PROJECTS.iterdir():
        # Skip non-directories and hidden files
        if item.name.startswith('.') or item.name.startswith('~'):
            continue

        # Check if it's a directory with a project
        if item.is_dir():
            project_id = item.name

            # Look for state file
            state_file = WORKSPACE_PROJECTS / f"{project_id}.json"
            if state_file.exists():
                try:
                    with open(state_file) as f:
                        data = json.load(f)

                    status = data.get("status", "")
                    current_stage = data.get("currentStage", "")
                    stages = data.get("stages", {})

                    icon = get_project_status_icon(status, current_stage, stages)
                    entities.append((project_id, icon, "project"))
                except Exception:
                    # If we can't read the state, show as pending
                    entities.append((project_id, "🔵", "project"))
            else:
                # Directory exists but no state file
                entities.append((project_id, "🔵", "project"))

    return sorted(entities)


def list_carby_sprints() -> List[Tuple[str, str, str]]:
    """List carby-sprint projects with status icons.
    Returns: [(sprint_id, icon, type), ...]
    """
    entities = []

    if not CARBY_SPRINTS.exists():
        return entities

    for item in CARBY_SPRINTS.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            sprint_id = item.name

            # Check for metadata.json
            metadata_file = item / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        data = json.load(f)

                    status = data.get("status", "pending")
                    icon = get_sprint_status_icon(status)
                    entities.append((sprint_id, icon, "sprint"))
                except Exception:
                    entities.append((sprint_id, "⬜", "sprint"))
            else:
                # Directory exists but no metadata yet
                entities.append((sprint_id, "⬜", "sprint"))

    return sorted(entities)


def build_project_menu() -> Dict:
    """Build interactive project menu for OpenClaw message tool."""
    projects = list_workspace_projects()
    sprints = list_carby_sprints()
    all_entities = projects + sprints

    if not all_entities:
        return {
            "text": "📋 No projects or sprints found.\n\nCreate one with: `carby-sprint init <name>`"
        }

    # Build button rows (2 buttons per row)
    button_rows = []
    for i in range(0, len(all_entities), 2):
        row = []
        # First button
        entity_id, icon, entity_type = all_entities[i]
        row.append({
            "label": f"{icon} {entity_id}",
            "value": f"view:{entity_type}:{entity_id}"
        })
        # Second button if exists
        if i + 1 < len(all_entities):
            entity_id2, icon2, entity_type2 = all_entities[i + 1]
            row.append({
                "label": f"{icon2} {entity_id2}",
                "value": f"view:{entity_type2}:{entity_id2}"
            })
        button_rows.append(row)

    # Add back button
    button_rows.append([{
        "label": "← Back to Main Menu",
        "value": "back:main"
    }])

    # Flatten buttons for interactive block
    buttons = []
    for row in button_rows:
        buttons.extend(row)

    return {
        "text": f"📋 Your Projects & Sprints ({len(all_entities)})\n\nTap a project to view details:",
        "interactive": {
            "blocks": [
                {"type": "text", "text": f"📋 Your Projects & Sprints ({len(all_entities)})\n\nTap a project to view details:"},
                {"type": "buttons", "buttons": buttons}
            ]
        }
    }


def get_project_details(project_id: str, entity_type: str = "project") -> str:
    """Get detailed info about a project or sprint."""
    if entity_type == "sprint":
        # Read carby-sprint metadata
        metadata_file = CARBY_SPRINTS / project_id / "metadata.json"
        if metadata_file.exists():
            try:
                with open(metadata_file) as f:
                    data = json.load(f)

                status = data.get("status", "pending")
                goal = data.get("goal", "No goal set")
                current_phase = data.get("current_phase", "N/A")

                return (
                    f"🔄 *{project_id}* (Sprint)\n\n"
                    f"📌 Status: {status}\n"
                    f"🎯 Goal: {goal}\n"
                    f"📍 Current Phase: {current_phase}\n\n"
                    f"Use `carby-sprint status {project_id}` for full details."
                )
            except Exception as e:
                return f"❌ Error reading sprint: {e}"
        else:
            return f"⚠️ Sprint '{project_id}' found but no metadata available."

    else:
        # Read legacy project state
        state_file = WORKSPACE_PROJECTS / f"{project_id}.json"
        if state_file.exists():
            try:
                with open(state_file) as f:
                    data = json.load(f)

                status = data.get("status", "unknown")
                goal = data.get("goal", "No goal set")
                current_stage = data.get("currentStage", "N/A")
                stages = data.get("stages", {})

                # Build stage summary
                stage_summary = []
                for stage_name in ["discover", "design", "build", "verify", "deliver"]:
                    stage = stages.get(stage_name, {})
                    stage_status = stage.get("status", "pending")
                    if stage_status == "done":
                        stage_summary.append(f"✅ {stage_name}")
                    elif stage_status == "in-progress":
                        stage_summary.append(f"🔄 {stage_name}")
                    elif stage_status == "failed":
                        stage_summary.append(f"❌ {stage_name}")
                    else:
                        stage_summary.append(f"⬜ {stage_name}")

                return (
                    f"📁 *{project_id}* (Project)\n\n"
                    f"📌 Status: {status}\n"
                    f"🎯 Goal: {goal}\n"
                    f"📍 Current Stage: {current_stage}\n\n"
                    f"*Pipeline:*\n" + "\n".join(stage_summary) + "\n\n"
                    f"Use `carby-studio resume {project_id}` to continue."
                )
            except Exception as e:
                return f"❌ Error reading project: {e}"
        else:
            return f"⚠️ Project '{project_id}' found but no state file available."


def get_project_detail_buttons(project_id: str, entity_type: str = "project") -> List[Dict]:
    """Get action buttons for project detail view."""
    buttons = []

    # Add Resume button
    if entity_type == "project":
        buttons.append({"label": "▶️ Resume Project", "value": f"resume:project:{project_id}"})
    else:
        buttons.append({"label": "▶️ Resume Sprint", "value": f"resume:sprint:{project_id}"})

    # Add back button
    buttons.append({"label": "← Back to Projects", "value": "back:projects"})

    return buttons


def handle_callback(callback_data: str) -> Dict:
    """Handle button callback from interactive menu."""
    if callback_data.startswith("view:project:"):
        project_id = callback_data.replace("view:project:", "")
        details = get_project_details(project_id, "project")
        buttons = get_project_detail_buttons(project_id, "project")
        return {
            "text": details,
            "interactive": {
                "blocks": [
                    {"type": "text", "text": details},
                    {"type": "buttons", "buttons": buttons}
                ]
            }
        }

    elif callback_data.startswith("view:sprint:"):
        sprint_id = callback_data.replace("view:sprint:", "")
        details = get_project_details(sprint_id, "sprint")
        buttons = get_project_detail_buttons(sprint_id, "sprint")
        return {
            "text": details,
            "interactive": {
                "blocks": [
                    {"type": "text", "text": details},
                    {"type": "buttons", "buttons": buttons}
                ]
            }
        }

    elif callback_data.startswith("resume:project:"):
        project_id = callback_data.replace("resume:project:", "")
        return {
            "text": f"▶️ Resuming project: {project_id}\n\nI'll help you continue working on this project. What would you like to do?",
            "interactive": {
                "blocks": [
                    {"type": "text", "text": f"▶️ Resuming project: {project_id}\n\nI'll help you continue working on this project. What would you like to do?"},
                    {"type": "buttons", "buttons": [
                        {"label": "📊 Check Status", "value": f"status:project:{project_id}"},
                        {"label": "📝 View Tasks", "value": f"tasks:project:{project_id}"},
                        {"label": "← Back to Project", "value": f"view:project:{project_id}"}
                    ]}
                ]
            }
        }

    elif callback_data.startswith("resume:sprint:"):
        sprint_id = callback_data.replace("resume:sprint:", "")
        return {
            "text": f"▶️ Resuming sprint: {sprint_id}\n\nI'll help you continue working on this sprint. What would you like to do?",
            "interactive": {
                "blocks": [
                    {"type": "text", "text": f"▶️ Resuming sprint: {sprint_id}\n\nI'll help you continue working on this sprint. What would you like to do?"},
                    {"type": "buttons", "buttons": [
                        {"label": "📊 Check Status", "value": f"status:sprint:{sprint_id}"},
                        {"label": "📝 View Gates", "value": f"gates:sprint:{sprint_id}"},
                        {"label": "← Back to Sprint", "value": f"view:sprint:{sprint_id}"}
                    ]}
                ]
            }
        }

    elif callback_data.startswith("status:project:"):
        project_id = callback_data.replace("status:project:", "")
        return {
            "text": f"📊 Project Status: {project_id}\n\nRun `carby-studio status {project_id}` for full details, or tell me what you'd like to work on."
        }

    elif callback_data.startswith("status:sprint:"):
        sprint_id = callback_data.replace("status:sprint:", "")
        return {
            "text": f"📊 Sprint Status: {sprint_id}\n\nRun `carby-sprint status {sprint_id}` for full details, or tell me what you'd like to work on."
        }

    elif callback_data.startswith(("tasks:project:", "gates:sprint:")):
        if callback_data.startswith("tasks:project:"):
            project_id = callback_data.replace("tasks:project:", "")
            return {
                "text": f"📝 Tasks for {project_id}\n\nWhat task would you like to work on? Or tell me what you need help with."
            }
        else:
            sprint_id = callback_data.replace("gates:sprint:", "")
            return {
                "text": f"📝 Gates for {sprint_id}\n\nWhich gate would you like to work on? Or tell me what you need help with."
            }

    elif callback_data == "back:projects":
        return build_project_menu()

    elif callback_data == "back:main":
        return {
            "text": "🏠 Main Menu\n\nWhat would you like to do?",
            "interactive": {
                "blocks": [
                    {"type": "text", "text": "🏠 Main Menu\n\nWhat would you like to do?"},
                    {"type": "buttons", "buttons": [
                        {"label": "📋 View Projects", "value": "menu:projects"},
                        {"label": "➕ New Sprint", "value": "menu:new"},
                        {"label": "❓ Help", "value": "menu:help"}
                    ]}
                ]
            }
        }

    elif callback_data == "menu:projects":
        return build_project_menu()

    elif callback_data == "menu:new":
        return {
            "text": "➕ Create New Sprint\n\nUse the command:\n`carby-sprint init <name> --goal \"Your goal\"`"
        }

    elif callback_data == "menu:help":
        return {
            "text": (
                "❓ Carby Studio Help\n\n"
                "*Commands:*\n"
                "• `/projects` - View all projects\n"
                "• `carby-sprint init <name>` - Create new sprint\n"
                "• `carby-sprint status <name>` - Check sprint status\n"
                "• `carby-sprint start <name>` - Start a sprint\n\n"
                "*Navigation:*\n"
                "• Click project buttons to view details\n"
                "• Use ← Back buttons to return"
            )
        }

    else:
        return {"text": f"⚠️ Unknown action: {callback_data}"}


# Convenience function for direct use
def show_projects():
    """Get the project menu payload for message tool."""
    return build_project_menu()