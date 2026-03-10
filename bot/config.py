"""Configuration for Carby Studio Bot."""

import os
from pathlib import Path

# Base directories
HOME = Path.home()
DEFAULT_WORKSPACE = HOME / ".openclaw" / "workspace" / "projects"
DEFAULT_CACHE_DIR = HOME / ".openclaw" / "carby-bot"

# Configuration
class Config:
    """Bot configuration."""
    
    # Telegram
    BOT_TOKEN = os.getenv("CARBY_BOT_TOKEN", "")
    
    # Paths
    PROJECTS_DIR = Path(os.getenv("CARBY_WORKSPACE", DEFAULT_WORKSPACE))
    CACHE_DIR = Path(os.getenv("CARBY_CACHE_DIR", DEFAULT_CACHE_DIR))
    CACHE_FILE = CACHE_DIR / "cache.json"
    
    # Polling
    POLL_INTERVAL = int(os.getenv("CARBY_POLL_INTERVAL", "30"))
    ACTIVE_POLL_INTERVAL = int(os.getenv("CARBY_ACTIVE_POLL_INTERVAL", "10"))
    
    # Logging
    DEBUG = os.getenv("CARBY_DEBUG", "false").lower() == "true"
    LOG_FILE = CACHE_DIR / "bot.log"
    
    # Validation
    PROJECT_NAME_PATTERN = r'^[a-z0-9-]+$'
    PROJECT_NAME_MAX_LEN = 50
    
    @classmethod
    def validate(cls) -> list:
        """Validate configuration. Returns list of errors."""
        errors = []
        
        if not cls.BOT_TOKEN:
            errors.append("CARBY_BOT_TOKEN not set")
        
        if not cls.PROJECTS_DIR.exists():
            errors.append(f"Projects directory does not exist: {cls.PROJECTS_DIR}")
        
        return errors
    
    @classmethod
    def ensure_directories(cls):
        """Create necessary directories."""
        cls.CACHE_DIR.mkdir(parents=True, exist_ok=True)

# CLI Commands
CLI_COMMANDS = {
    "dispatch": ["carby-studio", "dispatch", "{project}", "{stage}"],
    "skip": ["carby-studio", "skip", "{project}", "{stage}"],
    "retry": ["carby-studio", "retry", "{project}", "{stage}"],
    "status": ["carby-studio", "status", "{project}"],
    "init": ["carby-studio", "init", "{project}", "-g", "{goal}"],
}

# Status icons
STATUS_ICONS = {
    "pending": "⬜",
    "in-progress": "🟢",
    "done": "⏸️",
    "failed": "🔴",
    "skipped": "⏭️",
    "archived": "🗄️",
    "completed": "✅",
    "unknown": "❓",
}

# Notification templates
NOTIFICATION_TEMPLATES = {
    "started": "🚀 *{project}*: {stage} started",
    "completed": "✅ *{project}*: {stage} complete",
    "failed": "❌ *{project}*: {stage} failed",
    "skipped": "⏭️ *{project}*: {stage} skipped",
}
