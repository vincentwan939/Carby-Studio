"""
Security Configuration for Carby Studio Telegram Bot

This module provides security hardening features including:
- User authentication via ALLOWED_USERS environment variable
- Input validation for project IDs
- Log sanitization to prevent token leakage
- Rate limiting for flood protection
"""

import os
import re
import time
import hashlib
import logging
from typing import Optional, List, Dict
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration Loading
# =============================================================================

# Load allowed users from environment variable (comma-separated list)
# Format: CARBY_ALLOWED_USERS=123456789,987654321
ALLOWED_USERS_STR = os.getenv("CARBY_ALLOWED_USERS", "")
ALLOWED_USERS: List[int] = []
if ALLOWED_USERS_STR:
    try:
        ALLOWED_USERS = [int(uid.strip()) for uid in ALLOWED_USERS_STR.split(",") if uid.strip()]
    except ValueError:
        logger.error("Invalid CARBY_ALLOWED_USERS format. Expected comma-separated integers.")
        ALLOWED_USERS = []

# Bot token for sanitization checks
BOT_TOKEN = os.getenv("CARBY_BOT_TOKEN", "")

# Project ID validation pattern
# Allows: lowercase letters, numbers, hyphens, underscores
# Must start with a letter or number, 3-50 characters
PROJECT_NAME_PATTERN = re.compile(r'^[a-z0-9][a-z0-9_-]{2,49}$')

# Rate limiting configuration
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30  # Max requests per window per user

# =============================================================================
# User Authentication
# =============================================================================

def is_authorized(user_id: int) -> bool:
    """
    Check if a user ID is authorized to use the bot.
    
    If ALLOWED_USERS is empty, all users are allowed (development mode).
    In production, always set CARBY_ALLOWED_USERS.
    
    Args:
        user_id: The Telegram user ID to check
        
    Returns:
        True if authorized, False otherwise
    """
    if not ALLOWED_USERS:
        # No restrictions set - allow all (log warning for production)
        return True
    return user_id in ALLOWED_USERS


async def check_authorization(update: Update) -> bool:
    """
    Check if the user sending the update is authorized.
    Sends an unauthorized message if not.
    
    Args:
        update: The Telegram update object
        
    Returns:
        True if authorized, False otherwise
    """
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id:
        logger.warning("Received update without user information")
        return False
    
    if not is_authorized(user_id):
        logger.warning(f"Unauthorized access attempt by user {user_id}")
        if update.message:
            await update.message.reply_text(
                "⛔ *Access Denied*\n\n"
                "You are not authorized to use this bot.",
                parse_mode="Markdown"
            )
        elif update.callback_query:
            await update.callback_query.answer("Access denied", show_alert=True)
        return False
    
    return True


# =============================================================================
# Input Validation
# =============================================================================

def validate_project_id(project_id: str) -> tuple[bool, Optional[str]]:
    """
    Validate a project ID against the allowed pattern.
    
    Args:
        project_id: The project ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
        - is_valid: True if valid, False otherwise
        - error_message: Description of the error if invalid, None if valid
    """
    if not project_id:
        return False, "Project ID cannot be empty"
    
    if len(project_id) < 3:
        return False, f"Project ID too short (min 3 chars): '{sanitize_log_message(project_id)}'"
    
    if len(project_id) > 50:
        return False, f"Project ID too long (max 50 chars): '{sanitize_log_message(project_id[:20])}...'"
    
    if not PROJECT_NAME_PATTERN.match(project_id):
        return False, (
            f"Invalid project ID format: '{sanitize_log_message(project_id)}'. "
            "Must start with lowercase letter or number, contain only lowercase letters, "
            "numbers, hyphens, and underscores."
        )
    
    return True, None


def validate_callback_data(data: str, expected_parts: int = 2) -> tuple[bool, List[str], Optional[str]]:
    """
    Validate and parse callback data with bounds checking.
    
    Args:
        data: The callback data string
        expected_parts: Minimum number of colon-separated parts expected
        
    Returns:
        Tuple of (is_valid, parts_list, error_message)
    """
    if not data:
        return False, [], "Callback data is empty"
    
    parts = data.split(":")
    
    if len(parts) < expected_parts:
        return False, parts, f"Invalid callback data format: expected {expected_parts} parts, got {len(parts)}"
    
    return True, parts, None


# =============================================================================
# Log Sanitization
# =============================================================================

def sanitize_log_message(message: str) -> str:
    """
    Sanitize a message to prevent sensitive data leakage in logs.
    
    Removes or masks:
    - Bot tokens
    - API keys (basic patterns)
    - Long hex strings that might be tokens
    
    Args:
        message: The message to sanitize
        
    Returns:
        Sanitized message safe for logging
    """
    if not message:
        return message
    
    sanitized = message
    
    # Mask bot token if present
    if BOT_TOKEN and BOT_TOKEN in sanitized:
        sanitized = sanitized.replace(BOT_TOKEN, "[BOT_TOKEN_REDACTED]")
    
    # Mask Telegram bot token pattern (numbers:alphanumeric)
    # Pattern: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz
    token_pattern = re.compile(r'\d{9,}:[A-Za-z0-9_-]{30,}')
    sanitized = token_pattern.sub("[TOKEN_REDACTED]", sanitized)
    
    # Mask potential API keys (common patterns)
    # Generic key patterns
    key_patterns = [
        (re.compile(r'(api[_-]?key[:\s=]+)[\w-]{16,}', re.IGNORECASE), r'\1[API_KEY_REDACTED]'),
        (re.compile(r'(token[:\s=]+)[\w-]{16,}', re.IGNORECASE), r'\1[TOKEN_REDACTED]'),
        (re.compile(r'(secret[:\s=]+)[\w-]{16,}', re.IGNORECASE), r'\1[SECRET_REDACTED]'),
        (re.compile(r'(password[:\s=]+)[^\s&]+', re.IGNORECASE), r'\1[PASSWORD_REDACTED]'),
    ]
    
    for pattern, replacement in key_patterns:
        sanitized = pattern.sub(replacement, sanitized)
    
    return sanitized


# =============================================================================
# Rate Limiting
# =============================================================================

class RateLimiter:
    """
    Simple in-memory rate limiter for flood protection.
    
    Tracks request counts per user within a time window.
    Note: This is reset on bot restart. For persistent rate limiting,
    consider using Redis or a database.
    """
    
    def __init__(self, window_seconds: int = RATE_LIMIT_WINDOW_SECONDS, 
                 max_requests: int = RATE_LIMIT_MAX_REQUESTS):
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._requests: Dict[int, List[float]] = {}
    
    def is_allowed(self, user_id: int) -> tuple[bool, int, int]:
        """
        Check if a user is allowed to make a request.
        
        Args:
            user_id: The Telegram user ID
            
        Returns:
            Tuple of (is_allowed, current_count, max_allowed)
        """
        now = time.time()
        
        # Get or create request history for this user
        if user_id not in self._requests:
            self._requests[user_id] = []
        
        # Remove old requests outside the window
        self._requests[user_id] = [
            timestamp for timestamp in self._requests[user_id]
            if now - timestamp < self.window_seconds
        ]
        
        # Check if under limit
        current_count = len(self._requests[user_id])
        if current_count >= self.max_requests:
            return False, current_count, self.max_requests
        
        # Record this request
        self._requests[user_id].append(now)
        return True, current_count + 1, self.max_requests
    
    def get_wait_time(self, user_id: int) -> int:
        """
        Get seconds until user can make another request.
        
        Args:
            user_id: The Telegram user ID
            
        Returns:
            Seconds to wait (0 if not rate limited)
        """
        if user_id not in self._requests or not self._requests[user_id]:
            return 0
        
        now = time.time()
        oldest_allowed = now - self.window_seconds
        
        # Find the oldest request that's still within the window
        oldest_timestamp = min(self._requests[user_id])
        if oldest_timestamp <= oldest_allowed:
            return 0
        
        return int(oldest_timestamp - oldest_allowed) + 1


# Global rate limiter instance
rate_limiter = RateLimiter()


async def check_rate_limit(update: Update) -> bool:
    """
    Check if user has exceeded rate limit.
    Sends a rate limit message if exceeded.
    
    Args:
        update: The Telegram update object
        
    Returns:
        True if allowed, False if rate limited
    """
    user_id = update.effective_user.id if update.effective_user else None
    if not user_id:
        return False
    
    allowed, current, max_allowed = rate_limiter.is_allowed(user_id)
    
    if not allowed:
        wait_seconds = rate_limiter.get_wait_time(user_id)
        logger.warning(f"Rate limit exceeded for user {user_id}. Wait {wait_seconds}s.")
        
        message = (
            f"⏱️ *Rate Limit Exceeded*\n\n"
            f"You've made {max_allowed} requests in the last {RATE_LIMIT_WINDOW_SECONDS} seconds.\n"
            f"Please wait {wait_seconds} seconds before trying again."
        )
        
        if update.message:
            await update.message.reply_text(message, parse_mode="Markdown")
        elif update.callback_query:
            await update.callback_query.answer(
                f"Rate limit exceeded. Wait {wait_seconds}s.",
                show_alert=True
            )
        return False
    
    return True


# =============================================================================
# User Isolation
# =============================================================================

def get_user_project_prefix(user_id: int) -> str:
    """
    Generate a user-specific prefix for project IDs.
    
    This ensures users can only see/access their own projects
    by prefixing project IDs with a user-specific hash.
    
    Args:
        user_id: The Telegram user ID
        
    Returns:
        A prefix string for this user's projects
    """
    # Create a short hash of the user ID
    hash_input = f"carby-studio-{user_id}"
    hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
    return f"u{user_id}-{hash_digest}"


def isolate_project_id(project_id: str, user_id: int) -> str:
    """
    Prefix a project ID with user-specific identifier for isolation.
    
    Args:
        project_id: The base project ID
        user_id: The Telegram user ID
        
    Returns:
        Isolated project ID
    """
    prefix = get_user_project_prefix(user_id)
    return f"{prefix}-{project_id}"


def extract_base_project_id(isolated_id: str, user_id: int) -> Optional[str]:
    """
    Extract the base project ID from an isolated ID.
    
    Args:
        isolated_id: The potentially isolated project ID
        user_id: The Telegram user ID
        
    Returns:
        The base project ID if valid, None if not owned by this user
    """
    prefix = get_user_project_prefix(user_id)
    
    # Check if this is an isolated ID
    if isolated_id.startswith(f"{prefix}-"):
        return isolated_id[len(prefix) + 1:]
    
    # Check if this belongs to another user
    if isolated_id.startswith("u") and "-" in isolated_id:
        # Extract the user ID from the prefix
        try:
            parts = isolated_id.split("-")
            if len(parts) >= 2 and parts[0][1:].isdigit():
                return None  # Belongs to another user
        except (IndexError, ValueError):
            pass
    
    # Not isolated - return as-is (for backwards compatibility)
    return isolated_id


def belongs_to_user(project_id: str, user_id: int) -> bool:
    """
    Check if a project ID belongs to the given user.
    
    Args:
        project_id: The project ID to check
        user_id: The Telegram user ID
        
    Returns:
        True if the project belongs to the user, False otherwise
    """
    prefix = get_user_project_prefix(user_id)
    
    # If not prefixed with any user prefix, it's public/legacy
    if not project_id.startswith("u"):
        return True
    
    # Check if it starts with this user's prefix
    return project_id.startswith(f"{prefix}-")


# =============================================================================
# Decorators
# =============================================================================

def require_auth(func):
    """
    Decorator to require authentication for a handler.
    """
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_authorization(update):
            return
        return await func(self, update, context)
    return wrapper


def require_rate_limit(func):
    """
    Decorator to apply rate limiting to a handler.
    """
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_rate_limit(update):
            return
        return await func(self, update, context)
    return wrapper


def secure_handler(func):
    """
    Decorator that applies both authentication and rate limiting.
    """
    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not await check_authorization(update):
            return
        if not await check_rate_limit(update):
            return
        return await func(self, update, context)
    return wrapper