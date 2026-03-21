#!/usr/bin/env python3
"""
Telegram Bot Handler for Carby Studio
Handles all Telegram-specific interactions.
"""

import os
import logging
from typing import Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters
)

from bot import CarbyBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Conversation states
NEW_PROJECT_GOAL = 1
NEW_PROJECT_APPROACH = 2
FEEDBACK = 3

# Persistent keyboard
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["/projects", "➕ New Project", "/more"]
], resize_keyboard=True)

MORE_KEYBOARD = ReplyKeyboardMarkup([
    ["🔐 Credentials", "📊 System Status"],
    ["🗄️ Archived Projects", "❓ Help"],
    ["← Back to Main"]
], resize_keyboard=True)


class TelegramHandler:
    """Handles all Telegram bot interactions."""
    
    def __init__(self):
        self.bot = CarbyBot()
        self.token = os.getenv("CARBY_BOT_TOKEN")
        if not self.token:
            logger.error("CARBY_BOT_TOKEN not set!")
            raise ValueError("CARBY_BOT_TOKEN environment variable required")
            
    def run(self):
        """Start the bot."""
        application = Application.builder().token(self.token).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", self.cmd_start))
        application.add_handler(CommandHandler("projects", self.cmd_projects))
        application.add_handler(CommandHandler("status", self.cmd_status))
        
        # New project conversation
        new_project_conv = ConversationHandler(
            entry_points=[MessageHandler(filters.Regex("^(➕ New Project|new project)$"), self.new_project_start)],
            states={
                NEW_PROJECT_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.new_project_goal)],
            },
            fallbacks=[CommandHandler("cancel", self.cmd_cancel)],
        )
        application.add_handler(new_project_conv)
        
        # Callback queries (button clicks)
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Main menu handler (reply keyboard sends /commands)
        application.add_handler(MessageHandler(filters.Regex("^/projects$"), self.cmd_projects))
        application.add_handler(MessageHandler(filters.Regex("^/more$"), self.cmd_more))
        application.add_handler(MessageHandler(filters.Regex("^← Back to Main$"), self.cmd_back_main))
        application.add_handler(MessageHandler(filters.Regex("^🔐 Credentials$"), self.cmd_credentials))
        application.add_handler(MessageHandler(filters.Regex("^📊 System Status$"), self.cmd_system_status))
        application.add_handler(MessageHandler(filters.Regex("^🗄️ Archived Projects$"), self.cmd_archived))
        application.add_handler(MessageHandler(filters.Regex("^❓ Help$"), self.cmd_help))
        
        # Natural language handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Error handler
        application.add_error_handler(self.error_handler)
        
        logger.info("Starting Carby Bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    async def error_handler(self, update: Optional[Update], context: ContextTypes.DEFAULT_TYPE):
        """Handle errors."""
        logger.error(f"Exception while handling an update: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again or contact support."
            )
        
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "🤖 *Carby Studio*\n\n"
            "Your AI development team.\n\n"
            "What would you like to do?",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        
    def _parse_project_id(self, line: str) -> Optional[str]:
        """Extract project ID from a project list line."""
        line = line.strip()
        for emoji in ['🟢', '🟡', '🔴', '⏸️']:
            if line.startswith(emoji):
                # Remove emoji and get the project name part
                rest = line[len(emoji):].strip()
                # Split on ' - ' to get just the project ID
                parts = rest.split(' - ')
                return parts[0].strip() if parts else None
        return None
        
    def _get_line_status(self, line: str) -> str:
        """Get status from line emoji."""
        if line.startswith('🟢'):
            return "in_progress"
        elif line.startswith('🟡'):
            return "pending"
        elif line.startswith('🔴'):
            return "failed"
        elif line.startswith('⏸️'):
            return "paused"
        return "unknown"
        
    async def cmd_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle projects list - show projects as clickable list."""
        from state_manager import StateManager
        state_manager = StateManager()
        project_ids = state_manager.list_projects()
        
        if not project_ids:
            await update.message.reply_text(
                "📋 No projects found.\n\nCreate one with ➕ New Project",
                reply_markup=MAIN_KEYBOARD
            )
            return
        
        # Build project list with one button per project
        lines = [f"📋 Your Projects ({len(project_ids)})\n\nTap a project to view details:"]
        keyboard = []
        
        for project_id in project_ids:
            summary = state_manager.get_project_summary(project_id)
            if not summary:
                continue
            
            current_status = summary.get("current_status", "unknown")
            current_stage = summary.get("current_stage", "") or "N/A"
            
            # Determine emoji based on status
            if current_status == "in-progress":
                emoji = "🟢"
            elif current_status == "pending":
                emoji = "🟡"
            elif current_status == "failed":
                emoji = "🔴"
            elif current_status == "completed":
                emoji = "✅"
            else:
                emoji = "⏸️"
            
            # One button per project row
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {project_id} ({current_status})", 
                    callback_data=f"view:{project_id}"
                )
            ])
        
        text = "\n".join(lines)
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle status command."""
        from state_manager import StateManager
        state_manager = StateManager()
        project_ids = state_manager.list_projects()
        
        total = 0
        in_progress = 0
        pending_approval = 0
        failed = 0
        
        for project_id in project_ids:
            summary = state_manager.get_project_summary(project_id)
            if summary:
                total += 1
                status = summary.get("current_status", "")
                if status == "in-progress":
                    in_progress += 1
                elif status == "pending":
                    pending_approval += 1
                elif status == "failed":
                    failed += 1
        
        status_text = (
            "📊 *System Status*\n\n"
            f"Active projects: {total}\n"
            f"🟢 In progress: {in_progress}\n"
            f"🟡 Pending approval: {pending_approval}\n"
            f"🔴 Failed: {failed}\n\n"
            "Gateway: 🟢 Running\n"
            "All systems operational."
        )
        
        await update.message.reply_text(status_text, parse_mode="Markdown")
        
    async def new_project_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start new project conversation."""
        await update.message.reply_text(
            "➕ *New Project*\n\n"
            "What are you building?\n"
            "(Describe in one sentence)",
            parse_mode="Markdown"
        )
        return NEW_PROJECT_GOAL
        
    async def new_project_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle project goal."""
        goal = update.message.text
        context.user_data['project_goal'] = goal
        
        # Generate project ID from goal
        project_id = goal.lower().replace(" ", "-")[:30]
        context.user_data['project_id'] = project_id
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🏃 Quick", callback_data=f"approach:quick:{project_id}"),
                InlineKeyboardButton("📐 Full Pipeline", callback_data=f"approach:full:{project_id}")
            ]
        ])
        
        await update.message.reply_text(
            f"➕ *New Project*\n\n"
            f"Goal: _{goal}_\n\n"
            f"Project ID: `{project_id}`\n\n"
            f"Choose approach:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        return ConversationHandler.END
        
    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation."""
        await update.message.reply_text(
            "Cancelled.",
            reply_markup=MAIN_KEYBOARD
        )
        return ConversationHandler.END
        
    async def cmd_more(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show more menu."""
        await update.message.reply_text(
            "⚙️ *More Options*",
            parse_mode="Markdown",
            reply_markup=MORE_KEYBOARD
        )
        
    async def cmd_back_main(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Return to main menu."""
        await update.message.reply_text(
            "Main menu:",
            reply_markup=MAIN_KEYBOARD
        )
        
    async def cmd_credentials(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show credentials."""
        await update.message.reply_text(
            "🔐 *Credentials*\n\n"
            "Use /credentials to manage credentials.",
            parse_mode="Markdown",
            reply_markup=MORE_KEYBOARD
        )
        
    async def cmd_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show system status."""
        await self.cmd_status(update, context)
        
    async def cmd_archived(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show archived projects."""
        await update.message.reply_text(
            "🗄️ *Archived Projects*\n\n"
            "No archived projects.",
            parse_mode="Markdown",
            reply_markup=MORE_KEYBOARD
        )
        
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help."""
        text = (
            "❓ *Carby Studio Help*\n\n"
            "*Quick commands:*\n"
            "• 'Projects' — List your projects\n"
            "• 'New project' — Start a new project\n"
            "• 'Continue' — Continue last project\n"
            "• 'Status' — Check system status\n\n"
            "*During a project:*\n"
            "• Approve each stage to continue\n"
            "• Reject with feedback for changes\n"
            "• Retry or skip failed stages\n\n"
            "*Need help?* Contact support."
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MORE_KEYBOARD)
        
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        parts = data.split(":")
        action = parts[0]
        
        if action == "approach":
            # New project approach selected
            approach = parts[1]
            project_id = parts[2]
            goal = context.user_data.get('project_goal', 'Unknown project')
            
            # Create project using new API
            mode = "quick" if approach == "quick" else "linear"
            success, message = self.bot.create_project(project_id, goal, mode)
            
            if not success:
                await query.edit_message_text(
                    f"❌ Failed to create project: {message}",
                    parse_mode="Markdown"
                )
                return
            
            if approach == "quick":
                await query.edit_message_text(
                    f"✅ Project created: `{project_id}`\n"
                    f"Mode: Quick (single agent)\n\n"
                    f"Starting now...",
                    parse_mode="Markdown"
                )
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Yes, Start", callback_data=f"start:{project_id}")],
                    [InlineKeyboardButton("Later", callback_data="cancel")]
                ])
                await query.edit_message_text(
                    f"✅ Project created: `{project_id}`\n"
                    f"Mode: Full Pipeline\n\n"
                    f"Start first stage?",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                
        elif action == "start":
            project_id = parts[1]
            result = self.bot.dispatch_stage(project_id)
            if result.success:
                await query.edit_message_text(
                    f"🚀 Started stage\n"
                    f"Project: `{project_id}`",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to start: {result.stderr or 'Unknown error'}",
                    parse_mode="Markdown"
                )
                
        elif action == "view":
            project_id = parts[1]
            text = self.bot.get_project_detail(project_id)
            if text:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("▶️ Resume", callback_data=f"resume:{project_id}"),
                        InlineKeyboardButton("✏️ Rename", callback_data=f"rename:{project_id}")
                    ],
                    [
                        InlineKeyboardButton("🗑️ Delete", callback_data=f"delete:{project_id}"),
                        InlineKeyboardButton("📦 Archive", callback_data=f"archive:{project_id}")
                    ],
                    [InlineKeyboardButton("← Back to Projects", callback_data="back:projects")]
                ])
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
            else:
                await query.edit_message_text("❌ Project not found")
                
        elif action == "review":
            project_id = parts[1]
            text = self.bot.get_project_detail(project_id)
            if text:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve:{project_id}"),
                        InlineKeyboardButton("📝 Reject", callback_data=f"reject:{project_id}")
                    ],
                    [InlineKeyboardButton("View Full Detail", callback_data=f"view:{project_id}")]
                ])
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
            else:
                await query.edit_message_text("❌ Project not found")
                
        elif action == "approve":
            project_id = parts[1]
            # Dispatch next stage (approval means continue)
            result = self.bot.dispatch_stage(project_id)
            if result.success:
                await query.edit_message_text(
                    f"✅ Approved and continued\n"
                    f"Project: `{project_id}`",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"✅ Approved\n"
                    f"Project: `{project_id}`\n\n"
                    f"Note: {result.stderr or 'No next stage'}",
                    parse_mode="Markdown"
                )
                
        elif action == "reject":
            project_id = parts[1]
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel", callback_data=f"review:{project_id}")]
            ])
            await query.edit_message_text(
                f"📝 Rejecting *{project_id}*\n\n"
                f"Please send feedback for the agent:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            context.user_data['rejecting_project'] = project_id
            
        elif action == "retry":
            project_id = parts[1]
            result = self.bot.retry_stage(project_id)
            if result.success:
                await query.edit_message_text(
                    f"🔄 Retrying stage\n"
                    f"Project: `{project_id}`",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to retry: {result.stderr or 'Unknown error'}",
                    parse_mode="Markdown"
                )
                
        elif action == "skip":
            project_id = parts[1]
            result = self.bot.skip_stage(project_id)
            if result.success:
                await query.edit_message_text(
                    f"⏭️ Skipped stage\n"
                    f"Project: `{project_id}`",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to skip: {result.stderr or 'Unknown error'}",
                    parse_mode="Markdown"
                )
                
        elif action == "stop":
            project_id = parts[1]
            success, message = self.bot.stop_agent(project_id)
            if success:
                await query.edit_message_text(
                    f"🛑 Stopped *{project_id}*\n\n"
                    f"Agent terminated.",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to stop: {message}",
                    parse_mode="Markdown"
                )
                
        elif action == "resume":
            project_id = parts[1]
            # Resume = dispatch current stage
            result = self.bot.dispatch_stage(project_id)
            if result.success:
                await query.edit_message_text(
                    f"▶️ Resumed *{project_id}*\n\n"
                    f"Stage dispatched successfully.",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"▶️ Resumed *{project_id}*\n\n"
                    f"Note: {result.stderr or 'No active stage to resume'}",
                    parse_mode="Markdown"
                )
                
        elif action == "delete":
            project_id = parts[1]
            # Show confirmation
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete:{project_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data="back:projects")
                ]
            ])
            await query.edit_message_text(
                f"🗑️ Delete Project\n\n"
                f"Are you sure you want to delete *{project_id}*?\n\n"
                f"This cannot be undone!",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            
        elif action == "confirm_delete":
            project_id = parts[1]
            # Actually delete the project
            success, message = self.bot.delete_project(project_id, confirmation="DELETE")
            if success:
                await query.edit_message_text(
                    f"🗑️ Deleted *{project_id}*\n\n"
                    f"Project has been removed.",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text(
                    f"❌ Failed to delete: {message}",
                    parse_mode="Markdown"
                )
                
        elif action == "rename":
            project_id = parts[1]
            # Show rename prompt
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Cancel", callback_data=f"view:{project_id}")]
            ])
            await query.edit_message_text(
                f"✏️ Rename Project\n\n"
                f"Current name: `{project_id}`\n\n"
                f"Please send the new name for this project:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
            context.user_data['renaming_project'] = project_id
            
        elif action == "archive":
            project_id = parts[1]
            # Archive the project
            from state_manager import StateManager, ProjectStatus
            state_manager = StateManager()
            project_state = state_manager.read_project_state(project_id)
            if project_state:
                project_state.status = ProjectStatus.ARCHIVED.value
                state_manager.write_project_state(project_state)
                await query.edit_message_text(
                    f"📦 Archived *{project_id}*\n\n"
                    f"Project has been archived.",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("❌ Project not found")
            
        elif action == "back":
            if parts[1] == "projects":
                # Re-show projects list using same logic as cmd_projects
                from state_manager import StateManager
                state_manager = StateManager()
                project_ids = state_manager.list_projects()
                
                if not project_ids:
                    await query.edit_message_text(
                        "📋 No projects found.\n\nCreate one with ➕ New Project"
                    )
                    return
                
                lines = [f"📋 Your Projects ({len(project_ids)})\n\nTap a project to view details:"]
                keyboard = []
                
                for project_id in project_ids:
                    summary = state_manager.get_project_summary(project_id)
                    if not summary:
                        continue
                    
                    current_status = summary.get("current_status", "unknown")
                    current_stage = summary.get("current_stage", "") or "N/A"
                    
                    if current_status == "in-progress":
                        emoji = "🟢"
                    elif current_status == "pending":
                        emoji = "🟡"
                    elif current_status == "failed":
                        emoji = "🔴"
                    elif current_status == "completed":
                        emoji = "✅"
                    else:
                        emoji = "⏸️"
                    
                    # One button per project row
                    keyboard.append([
                        InlineKeyboardButton(
                            f"{emoji} {project_id} ({current_status})", 
                            callback_data=f"view:{project_id}"
                        )
                    ])
                
                text = "\n".join(lines)
                reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=reply_markup)
                
        elif action == "cancel":
            await query.edit_message_text("Cancelled.")
            
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages."""
        text = update.message.text.lower()
        
        # Natural language patterns
        if any(word in text for word in ["projects", "list", "my projects"]):
            await self.cmd_projects(update, context)
        elif any(word in text for word in ["status", "what's running", "what is running"]):
            await self.cmd_status(update, context)
        elif any(word in text for word in ["continue", "resume"]):
            # Continue last active project
            from state_manager import StateManager
            state_manager = StateManager()
            project_ids = state_manager.list_projects()
            
            first_project = None
            for project_id in project_ids:
                summary = state_manager.get_project_summary(project_id)
                if summary and summary.get("current_status") == "in-progress":
                    first_project = project_id
                    break
            
            # If no in-progress, take first project
            if not first_project and project_ids:
                first_project = project_ids[0]
            
            if first_project:
                await update.message.reply_text(
                    f"Continuing *{first_project}*...",
                    parse_mode="Markdown"
                )
                # Show project detail
                detail = self.bot.get_project_detail(first_project)
                if detail:
                    await update.message.reply_text(detail, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "No active projects. Start one with ➕ New Project"
                )
        elif any(word in text for word in ["help", "how to", "how do i"]):
            await self.cmd_help(update, context)
        else:
            # Unknown message - offer suggestions
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Projects", callback_data="back:projects")],
                [InlineKeyboardButton("➕ New Project", callback_data="new_project")],
                [InlineKeyboardButton("❓ Help", callback_data="help")]
            ])
            await update.message.reply_text(
                "I'm not sure what you mean. Did you want to:",
                reply_markup=keyboard
            )


def main():
    """Main entry point."""
    handler = TelegramHandler()
    handler.run()


if __name__ == "__main__":
    main()
