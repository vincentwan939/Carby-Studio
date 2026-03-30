"""
User context utilities for audit trail attribution.

Provides functions to identify the current user performing actions,
supporting both CLI/manual actions and automated/system actions.
"""

from __future__ import annotations

import os
import getpass
from typing import Optional


def get_current_user() -> str:
    """
    Get the current user identifier for audit trail attribution.

    Resolution order:
    1. CARBY_SPRINT_USER environment variable (explicit override)
    2. USER environment variable (standard Unix/Linux)
    3. USERNAME environment variable (Windows)
    4. LOGNAME environment variable (Unix fallback)
    5. getpass.getuser() (system call fallback)
    6. "system" (ultimate fallback for automated actions)

    Returns:
        User identifier string
    """
    # Check environment variables in order of preference
    for env_var in ["CARBY_SPRINT_USER", "USER", "USERNAME", "LOGNAME"]:
        user = os.environ.get(env_var)
        if user:
            return user

    # Fallback to system call
    try:
        return getpass.getuser()
    except Exception:
        pass

    # Ultimate fallback for automated/system actions
    return "system"


def get_user_with_context(context: Optional[str] = None) -> str:
    """
    Get user with additional context for automated actions.

    Args:
        context: Optional context string (e.g., "github-action", "cron", "ci")

    Returns:
        User identifier with context if provided
    """
    user = get_current_user()

    if context:
        return f"{user}:{context}"

    return user


def is_system_user(user_id: str) -> bool:
    """
    Check if the user ID represents a system/automated action.

    Args:
        user_id: User identifier to check

    Returns:
        True if this is a system user
    """
    system_indicators = [
        "system",
        "github-action",
        "ci",
        "jenkins",
        "gitlab-runner",
        "automation",
        "bot",
    ]

    user_lower = user_id.lower()

    # Check for exact matches
    if user_lower in system_indicators:
        return True

    # Check for context suffixes
    if ":" in user_id:
        base_user = user_id.split(":")[0]
        if base_user.lower() in system_indicators:
            return True

    return False
