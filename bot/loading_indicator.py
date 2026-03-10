"""Loading indicators for async operations."""

import logging
from typing import Optional, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class LoadingState(Enum):
    """Loading states for operations."""
    IDLE = "idle"
    LOADING = "loading"
    SUCCESS = "success"
    ERROR = "error"


@dataclass
class LoadingConfig:
    """Configuration for loading indicators."""
    initial_text: str = "⏳ Processing..."
    loading_emoji: str = "🔄"
    success_emoji: str = "✅"
    error_emoji: str = "❌"
    dots: bool = True


class LoadingIndicator:
    """
    Manages loading indicators for async Telegram operations.
    
    Provides consistent loading UX across all bot operations.
    """
    
    def __init__(self, config: Optional[LoadingConfig] = None):
        self.config = config or LoadingConfig()
        self._states: dict = {}  # message_id -> state
    
    def get_loading_text(self, operation: str, detail: Optional[str] = None) -> str:
        """
        Generate loading text for an operation.
        
        Args:
            operation: Name of the operation (e.g., "Resuming", "Dispatching")
            detail: Optional detail to show
            
        Returns:
            Formatted loading text
        """
        emoji = self.config.loading_emoji
        
        if detail:
            return f"{emoji} *{operation}...*\n\n_{detail}_"
        else:
            return f"{emoji} *{operation}...*"
    
    def get_success_text(self, operation: str, result: Optional[str] = None) -> str:
        """Generate success text."""
        emoji = self.config.success_emoji
        
        if result:
            return f"{emoji} *{operation}*\n\n{result}"
        else:
            return f"{emoji} *{operation}*"
    
    def get_error_text(self, operation: str, error: str) -> str:
        """Generate error text."""
        emoji = self.config.error_emoji
        return f"{emoji} *{operation} Failed*\n\n{error}"


# Global loading indicator instance
_loading_indicator: Optional[LoadingIndicator] = None


def get_loading_indicator() -> LoadingIndicator:
    """Get or create global loading indicator."""
    global _loading_indicator
    if _loading_indicator is None:
        _loading_indicator = LoadingIndicator()
    return _loading_indicator


# Predefined loading messages for common operations
LOADING_MESSAGES = {
    "resume": {
        "initial": "🔄 *Resuming Project...*\n\n_Contacting Carby Studio agent..._",
        "loading": "🔄 *Resuming Project...*\n\n_Gathering context..._",
        "success": "✅ *Resume Request Sent*",
        "error": "❌ *Resume Failed*"
    },
    "dispatch": {
        "initial": "🚀 *Dispatching Stage...*\n\n_Preparing agent..._",
        "loading": "🚀 *Dispatching Stage...*\n\n_Starting execution..._",
        "success": "✅ *Stage Dispatched*",
        "error": "❌ *Dispatch Failed*"
    },
    "retry": {
        "initial": "🔄 *Retrying Stage...*\n\n_Preparing retry..._",
        "success": "✅ *Retry Initiated*",
        "error": "❌ *Retry Failed*"
    },
    "skip": {
        "initial": "⏭️ *Skipping Stage...*",
        "success": "✅ *Stage Skipped*",
        "error": "❌ *Skip Failed*"
    },
    "stop": {
        "initial": "🛑 *Stopping Agent...*\n\n_Sending stop signal..._",
        "success": "✅ *Agent Stopped*",
        "error": "❌ *Stop Failed*"
    },
    "delete": {
        "initial": "🗑️ *Deleting Project...*",
        "success": "✅ *Project Deleted*",
        "error": "❌ *Delete Failed*"
    },
    "rename": {
        "initial": "✏️ *Renaming Project...*",
        "success": "✅ *Project Renamed*",
        "error": "❌ *Rename Failed*"
    },
    "logs": {
        "initial": "📋 *Fetching Logs...*\n\n_Retrieving output..._",
        "success": "📋 *Logs Retrieved*",
        "error": "❌ *Failed to Fetch Logs*"
    }
}


def get_loading_message(operation: str, state: str = "initial", 
                        detail: Optional[str] = None) -> str:
    """
    Get predefined loading message.
    
    Args:
        operation: Operation name (resume, dispatch, retry, etc.)
        state: State (initial, loading, success, error)
        detail: Optional detail to append
        
    Returns:
        Formatted message
    """
    messages = LOADING_MESSAGES.get(operation, {})
    message = messages.get(state, f"{state.capitalize()}...")
    
    if detail and state in ("success", "error"):
        message += f"\n\n{detail}"
    
    return message
