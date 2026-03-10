"""Notification service for Carby Studio Bot."""

import logging
import time
from typing import Optional
from dataclasses import dataclass
from collections import defaultdict

from state_manager import StateChange
from config import NOTIFICATION_TEMPLATES, STATUS_ICONS

logger = logging.getLogger(__name__)


@dataclass
class Notification:
    """A notification to send to the user."""
    project_id: str
    message: str
    buttons: list  # List of dicts: [{"text": "...", "callback": "..."}]
    priority: str = "normal"  # normal, high


class NotificationService:
    """Generates notifications from state changes with rate limiting."""
    
    # Rate limiting config
    RATE_LIMIT_WINDOW = 60  # seconds
    RATE_LIMIT_MAX = 5  # max notifications per window per project
    DEDUP_WINDOW = 300  # 5 minutes for deduplication
    
    def __init__(self):
        self._recent_notifications = set()  # For deduplication
        self._project_rate_limits = defaultdict(list)  # project_id -> [timestamps]
        self._notification_history = defaultdict(list)  # project_id -> [(message, timestamp)]
    
    def generate(self, change: StateChange) -> Optional[Notification]:
        """Generate notification from state change."""
        
        if change.change_type == "new":
            return self._new_project_notification(change)
        
        elif change.change_type == "stage_changed":
            return self._stage_change_notification(change)
        
        elif change.change_type == "deleted":
            return self._deleted_notification(change)
        
        return None
    
    def _new_project_notification(self, change: StateChange) -> Notification:
        """Generate notification for new project."""
        message = f"📁 *{change.project_id}*\nNew project created"
        
        buttons = [
            {"text": "📋 View Projects", "callback": f"view_projects"},
        ]
        
        return Notification(
            project_id=change.project_id,
            message=message,
            buttons=buttons,
            priority="normal"
        )
    
    def _stage_change_notification(self, change: StateChange) -> Optional[Notification]:
        """Generate notification for stage status change."""
        if not change.stage_name or not change.new_status:
            return None
        
        # Skip pending → in-progress (too noisy)
        if change.old_status == "pending" and change.new_status == "in-progress":
            return None
        
        template = NOTIFICATION_TEMPLATES.get(change.new_status)
        if not template:
            return None
        
        message = template.format(
            project=change.project_id,
            stage=change.stage_name
        )
        
        # Add context
        if change.new_status == "done":
            message += f"\n\n⏸️ Awaiting dispatch"
        elif change.new_status == "failed":
            message += f"\n\n❌ Needs attention"
        
        buttons = self._get_buttons_for_status(change)
        
        priority = "high" if change.new_status == "failed" else "normal"
        
        return Notification(
            project_id=change.project_id,
            message=message,
            buttons=buttons,
            priority=priority
        )
    
    def _get_buttons_for_status(self, change: StateChange) -> list:
        """Get appropriate buttons for status."""
        buttons = []
        
        if change.new_status == "done":
            # Stage completed, ready for next
            buttons = [
                {"text": "▶️ Dispatch Next", "callback": f"dispatch:{change.project_id}"},
                {"text": "⏭️ Skip", "callback": f"skip:{change.project_id}"},
                {"text": "📋 View", "callback": f"view:{change.project_id}"},
            ]
        
        elif change.new_status == "failed":
            # Stage failed, needs retry or skip
            buttons = [
                {"text": "🔄 Retry", "callback": f"retry:{change.project_id}:{change.stage_name}"},
                {"text": "⏭️ Skip", "callback": f"skip:{change.project_id}:{change.stage_name}"},
                {"text": "📋 Logs", "callback": f"logs:{change.project_id}:{change.stage_name}"},
            ]
        
        elif change.new_status == "skipped":
            buttons = [
                {"text": "▶️ Dispatch", "callback": f"dispatch:{change.project_id}"},
                {"text": "📋 View", "callback": f"view:{change.project_id}"},
            ]
        
        return buttons
    
    def _deleted_notification(self, change: StateChange) -> Notification:
        """Generate notification for deleted project."""
        message = f"🗑️ *{change.project_id}*\nProject deleted"
        
        return Notification(
            project_id=change.project_id,
            message=message,
            buttons=[],
            priority="normal"
        )
    
    def _check_rate_limit(self, project_id: str) -> bool:
        """
        Check if project has exceeded rate limit.
        
        Args:
            project_id: Project identifier
            
        Returns:
            True if under rate limit, False if exceeded
        """
        now = time.time()
        history = self._project_rate_limits[project_id]
        
        # Remove old entries outside window
        history[:] = [t for t in history if now - t < self.RATE_LIMIT_WINDOW]
        
        if len(history) >= self.RATE_LIMIT_MAX:
            logger.warning(
                f"Rate limit exceeded for {project_id}: "
                f"{len(history)} notifications in {self.RATE_LIMIT_WINDOW}s"
            )
            return False
        
        # Record this notification
        history.append(now)
        return True
    
    def _check_deduplication(self, notification: Notification) -> bool:
        """
        Check if this is a duplicate notification.
        
        Args:
            notification: Notification to check
            
        Returns:
            True if not a duplicate, False if duplicate
        """
        now = time.time()
        history = self._notification_history[notification.project_id]
        
        # Clean old history
        history[:] = [(msg, ts) for msg, ts in history if now - ts < self.DEDUP_WINDOW]
        
        # Check for similar recent notifications
        message_key = notification.message[:50]
        for msg, ts in history:
            if msg[:50] == message_key:
                logger.debug(f"Duplicate notification suppressed for {notification.project_id}")
                return False
        
        # Record this notification
        history.append((notification.message, now))
        
        # Also maintain legacy set for quick lookup
        key = f"{notification.project_id}:{message_key}"
        self._recent_notifications.add(key)
        if len(self._recent_notifications) > 100:
            self._recent_notifications.pop()
        
        return True
    
    def should_send(self, notification: Notification) -> bool:
        """
        Check if notification should be sent (rate limiting + deduplication).
        
        Args:
            notification: Notification to check
            
        Returns:
            True if should send, False if should suppress
        """
        # Check rate limit
        if not self._check_rate_limit(notification.project_id):
            return False
        
        # Check deduplication
        if not self._check_deduplication(notification):
            return False
        
        return True
    
    def get_rate_limit_status(self, project_id: str) -> dict:
        """
        Get current rate limit status for a project.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Dict with count, limit, window, and remaining
        """
        now = time.time()
        history = self._project_rate_limits[project_id]
        history[:] = [t for t in history if now - t < self.RATE_LIMIT_WINDOW]
        
        return {
            "count": len(history),
            "limit": self.RATE_LIMIT_MAX,
            "window": self.RATE_LIMIT_WINDOW,
            "remaining": max(0, self.RATE_LIMIT_MAX - len(history))
        }
    
    def format_project_detail(self, project_summary: dict) -> str:
        """Format project detail view for Telegram."""
        icon = STATUS_ICONS.get(project_summary["current_status"], "❓")
        
        lines = [
            f"*{project_summary['id']}*",
            f"🎯 {project_summary['goal']}",
            "",
            f"Current: {project_summary['current_stage']}",
            f"Status: {icon} {project_summary['current_status']}",
        ]
        
        if project_summary.get("agent"):
            lines.append(f"🤖 Agent: {project_summary['agent']}")
        
        lines.append(f"\nUpdated: {project_summary['updated_at'][:19]}")
        
        return "\n".join(lines)
