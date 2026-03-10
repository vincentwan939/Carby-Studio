"""Error handling with actionable guidance."""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ErrorInfo:
    """Structured error information."""
    message: str
    explanation: str
    action: str
    error_code: str
    severity: str  # "info", "warning", "error", "critical"


# Error code registry
ERROR_CODES = {
    # Project errors
    "E1001": "Project not found",
    "E1002": "Project already exists",
    "E1003": "Project in progress",
    "E1004": "Project completed",
    "E1005": "Project failed",
    
    # Validation errors
    "E2001": "Invalid project name",
    "E2002": "Invalid stage name",
    "E2003": "Invalid mode",
    
    # Operation errors
    "E3001": "Dispatch failed",
    "E3002": "Stop failed",
    "E3003": "Retry failed",
    "E3004": "Skip failed",
    "E3005": "Rename failed",
    "E3006": "Delete failed",
    
    # System errors
    "E4001": "CLI not found",
    "E4002": "CLI timeout",
    "E4003": "File not found",
    "E4004": "Permission denied",
    "E4005": "Disk full",
    
    # Safety errors
    "E5001": "Safety check failed",
    "E5002": "Confirmation required",
    "E5003": "Operation not allowed",
}


# Error guidance database
ERROR_GUIDANCE: Dict[str, Dict] = {
    "E1001": {
        "explanation": "The project you're looking for doesn't exist.",
        "action": "Check the project name or view all projects with 📋 Projects.",
        "severity": "warning"
    },
    "E1002": {
        "explanation": "A project with that name already exists.",
        "action": "Choose a different name or delete the existing project first.",
        "severity": "warning"
    },
    "E1003": {
        "explanation": "The project has a running agent that must be stopped first.",
        "action": "Stop the agent with 🛑 Stop Agent, then try again.",
        "severity": "warning"
    },
    "E1004": {
        "explanation": "The project is already completed.",
        "action": "You can archive it or create a new project.",
        "severity": "info"
    },
    "E1005": {
        "explanation": "The project has failed stages that need attention.",
        "action": "View the project and retry or skip the failed stage.",
        "severity": "warning"
    },
    "E2001": {
        "explanation": "Project names must be lowercase letters, numbers, and hyphens only.",
        "action": "Try: my-project, project123, new-project-2024",
        "severity": "warning"
    },
    "E2002": {
        "explanation": "The stage name is not valid.",
        "action": "Valid stages: discover, design, build, verify, deliver",
        "severity": "warning"
    },
    "E3001": {
        "explanation": "Failed to dispatch the agent for this stage.",
        "action": "Check that the CLI is installed and try again. If it persists, check logs.",
        "severity": "error"
    },
    "E3002": {
        "explanation": "Failed to stop the running agent.",
        "action": "The agent may have already stopped. Check the project status.",
        "severity": "warning"
    },
    "E3005": {
        "explanation": "Failed to rename the project.",
        "action": "Ensure the new name is valid and not already in use.",
        "severity": "warning"
    },
    "E3006": {
        "explanation": "Failed to delete the project.",
        "action": "Check that you have permission to delete files in the projects directory.",
        "severity": "error"
    },
    "E4001": {
        "explanation": "The carby-studio CLI command was not found.",
        "action": "Ensure carby-studio is installed and in your PATH. Run: which carby-studio",
        "severity": "critical"
    },
    "E4002": {
        "explanation": "The operation timed out after 60 seconds.",
        "action": "The system may be busy. Try again in a moment.",
        "severity": "warning"
    },
    "E4004": {
        "explanation": "Permission denied when accessing project files.",
        "action": "Check file permissions or run with appropriate privileges.",
        "severity": "error"
    },
    "E5001": {
        "explanation": "A safety check prevented this operation.",
        "action": "Review the safety message and ensure the operation is safe to proceed.",
        "severity": "warning"
    },
    "E5002": {
        "explanation": "This operation requires explicit confirmation.",
        "action": "Follow the confirmation instructions to proceed.",
        "severity": "info"
    },
}


def get_error_info(error_code: str, context: Optional[Dict] = None) -> ErrorInfo:
    """
    Get error information for an error code.
    
    Args:
        error_code: The error code (e.g., "E1001")
        context: Optional context for formatting
        
    Returns:
        ErrorInfo with message, explanation, action, and severity
    """
    context = context or {}
    
    # Get base error name
    error_name = ERROR_CODES.get(error_code, "Unknown error")
    
    # Get guidance
    guidance = ERROR_GUIDANCE.get(error_code, {
        "explanation": "An unexpected error occurred.",
        "action": "Please try again or contact support if the issue persists.",
        "severity": "error"
    })
    
    # Format with context
    message = error_name
    if context.get("project"):
        message = f"{error_name}: {context['project']}"
    
    explanation = guidance["explanation"].format(**context)
    action = guidance["action"].format(**context)
    
    return ErrorInfo(
        message=message,
        explanation=explanation,
        action=action,
        error_code=error_code,
        severity=guidance["severity"]
    )


def format_error_message(error_info: ErrorInfo, include_code: bool = True) -> str:
    """
    Format error info for Telegram display.
    
    Args:
        error_info: ErrorInfo object
        include_code: Whether to include error code
        
    Returns:
        Formatted error message
    """
    lines = []
    
    # Header with emoji based on severity
    emoji = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "critical": "🚨"
    }.get(error_info.severity, "❌")
    
    if include_code:
        lines.append(f"{emoji} *{error_info.message}* `[{error_info.error_code}]`")
    else:
        lines.append(f"{emoji} *{error_info.message}*")
    
    lines.append("")
    lines.append(f"_{error_info.explanation}_")
    lines.append("")
    lines.append(f"💡 *What to do:* {error_info.action}")
    
    return "\n".join(lines)


def classify_error(error_text: str) -> Tuple[str, str]:
    """
    Classify an error message to an error code.
    
    Args:
        error_text: Raw error text
        
    Returns:
        Tuple of (error_code, error_name)
    """
    error_lower = error_text.lower()
    
    # Project errors
    if "not found" in error_lower:
        return "E1001", ERROR_CODES["E1001"]
    if "already exists" in error_lower:
        return "E1002", ERROR_CODES["E1002"]
    if "in progress" in error_lower or "running agent" in error_lower:
        return "E1003", ERROR_CODES["E1003"]
    if "completed" in error_lower:
        return "E1004", ERROR_CODES["E1004"]
    if "failed" in error_lower:
        return "E1005", ERROR_CODES["E1005"]
    
    # Validation errors
    if "invalid" in error_lower and "name" in error_lower:
        return "E2001", ERROR_CODES["E2001"]
    if "invalid" in error_lower and "stage" in error_lower:
        return "E2002", ERROR_CODES["E2002"]
    
    # CLI errors
    if "command not found" in error_lower or "not found" in error_lower:
        return "E4001", ERROR_CODES["E4001"]
    if "timeout" in error_lower or "timed out" in error_lower:
        return "E4002", ERROR_CODES["E4002"]
    if "permission" in error_lower:
        return "E4004", ERROR_CODES["E4004"]
    
    # Safety errors
    if "safety" in error_lower or "not allowed" in error_lower:
        return "E5001", ERROR_CODES["E5001"]
    if "confirmation" in error_lower:
        return "E5002", ERROR_CODES["E5002"]
    
    # Default
    return "E0000", "Unknown error"


def handle_cli_error(result) -> str:
    """
    Handle CLI error result and return formatted message.
    
    Args:
        result: CLIResult object with success, stderr, etc.
        
    Returns:
        Formatted error message for user
    """
    if result.success:
        return ""
    
    # Classify the error
    error_code, error_name = classify_error(result.stderr)
    
    # Get error info
    error_info = get_error_info(error_code)
    
    # Override message with actual error if available
    if result.stderr:
        error_info.message = result.stderr[:100]  # Truncate long errors
    
    return format_error_message(error_info)


# Severity colors for logging
SEVERITY_COLORS = {
    "info": "\033[94m",      # Blue
    "warning": "\033[93m",   # Yellow
    "error": "\033[91m",     # Red
    "critical": "\033[95m",  # Magenta
    "reset": "\033[0m"
}


def log_error(error_info: ErrorInfo, exc_info: bool = False):
    """
    Log error with appropriate level and formatting.
    
    Args:
        error_info: ErrorInfo object
        exc_info: Whether to include exception info
    """
    log_func = {
        "info": logger.info,
        "warning": logger.warning,
        "error": logger.error,
        "critical": logger.critical
    }.get(error_info.severity, logger.error)
    
    message = f"[{error_info.error_code}] {error_info.message}: {error_info.explanation}"
    log_func(message, exc_info=exc_info)
