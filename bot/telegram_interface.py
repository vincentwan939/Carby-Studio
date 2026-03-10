#!/usr/bin/env python3
"""
Telegram Bot Interface for Carby Studio
Phase 3: Integrated with Phase 2 core components
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
from state_manager import StateManager
from loading_indicator import get_loading_message
from nlu_handler import match_intent, extract_project_name, get_nlu_handler, Intent
from error_handler import handle_cli_error, get_error_info, format_error_message

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Conversation states
RENAME_PROJECT = 1
RENAME_CONFIRM = 2
DELETE_CONFIRM = 3
FEEDBACK = 4

# Persistent keyboard
MAIN_KEYBOARD = ReplyKeyboardMarkup([
    ["📋 Projects", "⚙️ More"]
], resize_keyboard=True)

MORE_KEYBOARD = ReplyKeyboardMarkup([
    ["🔐 Credentials", "📊 System Status"],
    ["🗄️ Archived Projects", "❓ Help"],
    ["← Back to Main"]
], resize_keyboard=True)


class TelegramInterface:
    """Telegram bot interface using Phase 2 core components."""
    
    def __init__(self):
        self.token = os.getenv("CARBY_BOT_TOKEN")
        if not self.token:
            logger.error("CARBY_BOT_TOKEN not set!")
            raise ValueError("CARBY_BOT_TOKEN environment variable required")
        
        # Initialize Phase 2 components
        self.bot = CarbyBot()
        self.state_manager = StateManager()
        
        # Track user state for conversations
        self.user_data = {}
        
        # Track active resume requests to prevent spam
        self._active_resumes = set()
        
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Global error handler for unhandled exceptions.
        
        Logs the error and notifies the user gracefully.
        """
        logger.error(f"Exception while handling update: {context.error}", exc_info=context.error)
        
        # Get error details
        error_message = str(context.error)
        error_type = type(context.error).__name__
        
        # Log full traceback for debugging
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Full traceback:\n{tb}")
        
        # Notify user if possible
        if update and update.effective_message:
            try:
                # Don't expose internal details to user
                user_message = (
                    "❌ *An error occurred*\n\n"
                    "The bot encountered an unexpected issue. "
                    "The error has been logged for investigation.\n\n"
                    "Please try again or contact support if the issue persists."
                )
                
                await update.effective_message.reply_text(
                    user_message,
                    parse_mode="Markdown",
                    reply_markup=MAIN_KEYBOARD
                )
            except (telegram.error.TelegramError, telegram.error.NetworkError) as notify_error:
                logger.error(f"Failed to send error notification: {notify_error}")
        
        # Could also send alert to admin here if configured
        # admin_id = os.getenv("CARBY_ADMIN_CHAT_ID")
        # if admin_id:
        #     await context.bot.send_message(
        #         chat_id=admin_id,
        #         text=f"Bot error: {error_type}: {error_message}"
        #     )
    
    def run(self):
        """Start the bot."""
        application = Application.builder().token(self.token).build()
        self.application = application
        
        # Add global error handler FIRST (before other handlers)
        application.add_error_handler(self._error_handler)
        
        # Store bot instance in application context
        application.bot_data['carby_bot'] = self.bot
        application.bot_data['state_manager'] = self.state_manager
        
        # Command handlers
        application.add_handler(CommandHandler("start", self.cmd_start))
        application.add_handler(CommandHandler("projects", self.cmd_projects))
        application.add_handler(CommandHandler("status", self.cmd_status))
        
        # Conversation handlers
        rename_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.rename_start, pattern="^rename:")],
            states={
                RENAME_PROJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.rename_confirm)],
                RENAME_CONFIRM: [CallbackQueryHandler(self.rename_execute, pattern="^confirm_rename:|^cancel_rename")],
            },
            fallbacks=[CommandHandler("cancel", self.cmd_cancel)],
        )
        application.add_handler(rename_conv)
        
        delete_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(self.delete_start, pattern="^delete:")],
            states={
                DELETE_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, self.delete_execute)],
            },
            fallbacks=[CommandHandler("cancel", self.cmd_cancel)],
        )
        application.add_handler(delete_conv)
        
        # Callback queries (button clicks)
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Main menu handlers
        application.add_handler(MessageHandler(filters.Regex("^📋 Projects$"), self.cmd_projects))
        application.add_handler(MessageHandler(filters.Regex("^⚙️ More$"), self.cmd_more))
        application.add_handler(MessageHandler(filters.Regex("^← Back to Main$"), self.cmd_back_main))
        application.add_handler(MessageHandler(filters.Regex("^🔐 Credentials$"), self.cmd_credentials))
        application.add_handler(MessageHandler(filters.Regex("^📊 System Status$"), self.cmd_system_status))
        application.add_handler(MessageHandler(filters.Regex("^🗄️ Archived Projects$"), self.cmd_archived))
        application.add_handler(MessageHandler(filters.Regex("^❓ Help$"), self.cmd_help))
        
        # New project handler

        
        # Natural language handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Start the bot and polling
        logger.info("Starting Carby Bot with Phase 2 components...")
        self.bot.start()
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        # Get project stats
        projects = self.state_manager.list_projects()
        active_count = 0
        completed_count = 0
        
        for pid in projects:
            summary = self.state_manager.get_project_summary(pid)
            if summary:
                status = summary.get("status", "")
                if status == "completed":
                    completed_count += 1
                else:
                    active_count += 1
        
        welcome_text = (
            "🤖 *Welcome to Carby Studio Bot!*\n\n"
            "Your AI-powered development assistant.\n\n"
            f"📊 *Current Status:*\n"
            f"• {len(projects)} total projects\n"
            f"• {active_count} active\n"
            f"• {completed_count} completed\n\n"
            "*Quick Actions:*\n"
            "• 📋 Projects — View all projects\n"
            "• ⚙️ More — System status & help\n\n"
            "Tap a button below to get started! 👇"
        )
        
        await update.message.reply_text(
            welcome_text,
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        
    async def cmd_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle projects list - 2 per row, in-progress first, then completed."""
        projects = self.state_manager.list_projects()
        
        if not projects:
            await update.message.reply_text(
                "📋 No projects found.\n\nCreate one with: `carby-studio init <name>`",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
            return
        
        # Sort projects: in-progress first, then completed
        in_progress = []
        completed = []
        
        for project_id in projects:
            summary = self.state_manager.get_project_summary(project_id)
            if not summary:
                continue
            
            project_status = summary.get("status", "")
            current_status = summary.get("current_status", "")
            
            if project_status == "completed" or current_status == "completed":
                completed.append((project_id, "🟢"))
            else:
                in_progress.append((project_id, "🟡"))
        
        # Header text
        text = f"📋 Your Projects ({len(projects)})\n\nTap a project to view details:"
        
        # Build keyboard: 2 buttons per row
        keyboard = []
        all_projects = in_progress + completed  # In-progress first, then completed
        
        for i in range(0, len(all_projects), 2):
            row = []
            # First button in row
            pid1, icon1 = all_projects[i]
            row.append(InlineKeyboardButton(f"{icon1} {pid1}", callback_data=f"view:{pid1}"))
            # Second button in row (if exists)
            if i + 1 < len(all_projects):
                pid2, icon2 = all_projects[i + 1]
                row.append(InlineKeyboardButton(f"{icon2} {pid2}", callback_data=f"view:{pid2}"))
            keyboard.append(row)
        
        # Add back to main menu button
        keyboard.append([InlineKeyboardButton("← Back to Main Menu", callback_data="back:main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(
            text,
            reply_markup=reply_markup
        )
        
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle status command."""
        projects = self.state_manager.list_projects()
        
        in_progress = 0
        pending = 0
        failed = 0
        completed = 0
        
        for project_id in projects:
            summary = self.state_manager.get_project_summary(project_id)
            if summary:
                current_status = summary.get("current_status", "")
                project_status = summary.get("status", "")
                
                if project_status == "completed" or current_status == "completed":
                    completed += 1
                elif current_status == "in-progress":
                    in_progress += 1
                elif current_status == "done":
                    pending += 1
                elif current_status == "failed":
                    failed += 1
        
        text = (
            "📊 *System Status*\n\n"
            f"Total projects: {len(projects)}\n"
            f"🟢 In progress: {in_progress}\n"
            f"🟡 Pending approval: {pending}\n"
            f"🔴 Failed: {failed}\n"
            f"✅ Completed: {completed}\n\n"
            "Gateway: 🟢 Running\n"
            "Bot: 🟢 Active"
        )
        
        await update.message.reply_text(text, parse_mode="Markdown")
        
    async def cmd_new_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle new project - guide user through CLI creation."""
        # Show helper with clear instructions
        await update.message.reply_text(
            "➕ *Create New Project*\n\n"
            "To create a project, run this command in your terminal:\n\n"
            "```\n"
            "carby init <project-name>\n"
            "```\n\n"
            "*Example:*\n"
            "```\n"
            "carby init my-awesome-project\n"
            "```\n\n"
            "Then return here and tap 📋 Projects to see it!",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        
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
            "Shared credentials:\n"
            "✅ synology-nas\n"
            "✅ icloud-api\n"
            "⬜ sony-wifi\n\n"
            "Use the `carby-credentials` skill to manage.",
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
            "No archived projects yet.",
            parse_mode="Markdown",
            reply_markup=MORE_KEYBOARD
        )
        
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help."""
        text = (
            "❓ *Carby Studio Bot Help*\n\n"
            "*Quick commands:*\n"
            "• 'Projects' — List your projects\n"
            "• 'Status' — Check system status\n"
            "• 'Continue' — View last active project\n\n"
            "*Project actions:*\n"
            "• Tap project to view details\n"
            "• ✅ Approve — Continue to next stage\n"
            "• 📝 Reject — Send back for changes\n"
            "• 🔄 Retry — Retry failed stage\n"
            "• ⏭️ Skip — Skip to next stage\n"
            "• 🛑 Stop — Stop current agent\n\n"
            "*Project management:*\n"
            "In project detail view:\n"
            "• ✏️ Rename — Change project name\n"
            "• 🗑️ Delete — Remove project\n\n"
            "*Need help?* Contact support."
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MORE_KEYBOARD)
        
    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel conversation."""
        await update.message.reply_text(
            "Cancelled.",
            reply_markup=MAIN_KEYBOARD
        )
        return ConversationHandler.END
        
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        parts = data.split(":")
        action = parts[0]
        
        if action == "view":
            await self.handle_view(query, parts[1])
        elif action == "resume":
            await self.handle_resume(query, parts[1])
        elif action == "dispatch":
            await self.handle_dispatch(query, parts[1])
        elif action == "approve":
            await self.handle_approve(query, parts[1])
        elif action == "reject":
            await self.handle_reject(query, parts[1])
        elif action == "retry":
            await self.handle_retry(query, parts[1])
        elif action == "skip":
            await self.handle_skip(query, parts[1])
        elif action == "stop":
            await self.handle_stop(query, parts[1])
        elif action == "back":
            if parts[1] == "projects":
                await self.handle_back_to_projects(query)
            elif parts[1] == "main":
                await self.handle_back_to_main(query)
        elif action == "confirm_delete":
            await self.handle_confirm_delete(query, parts[1])
        elif action == "logs":
            await self.handle_logs(query, parts[1])
            
    async def handle_view(self, query, project_id: str):
        """View project detail with improved status display."""
        # Read full project state for detailed view
        full_state = self.state_manager.read_project(project_id)
        summary = self.state_manager.get_project_summary(project_id)
        
        if not full_state or not summary:
            await query.edit_message_text("❌ Project not found")
            return
        
        # Build detailed project view
        goal = full_state.get("goal", "No goal set")
        mode = full_state.get("mode", "linear")
        project_status = full_state.get("status", "active")
        created = full_state.get("created", "Unknown")[:10]  # Just date part
        
        # Escape markdown characters
        def escape_md(text):
            return text.replace('\\', '\\\\').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
        
        safe_project_id = escape_md(project_id)
        safe_goal = escape_md(goal)
        
        lines = [
            f"📁 *{safe_project_id}*",
            f"🎯 {safe_goal}",
            f"📅 Created: {created}",
            f"⚙️ Mode: {mode}",
            ""
        ]
        
        # Show stages/tasks
        stages = full_state.get("stages", {})
        pipeline = full_state.get("pipeline", [])
        
        if pipeline:
            lines.append("📊 *Stages:*")
            for stage in pipeline:
                stage_info = stages.get(stage, {})
                stage_status = stage_info.get("status", "pending")
                agent = stage_info.get("agent", "unknown")
                
                # Status icons
                icon = {
                    "done": "✅",
                    "in-progress": "🔄",
                    "failed": "❌",
                    "skipped": "⏭️",
                    "pending": "⬜"
                }.get(stage_status, "⬜")
                
                lines.append(f"{icon} {stage} ({agent})")
        elif stages:
            # DAG mode - show all stages
            lines.append("📊 *Stages:*")
            for stage, stage_info in stages.items():
                stage_status = stage_info.get("status", "pending")
                agent = stage_info.get("agent", "unknown")
                
                icon = {
                    "done": "✅",
                    "in-progress": "🔄",
                    "failed": "❌",
                    "skipped": "⏭️",
                    "pending": "⬜"
                }.get(stage_status, "⬜")
                
                lines.append(f"{icon} {stage} ({agent})")
        
        lines.append("")
        
        # Overall status
        if project_status == "completed":
            lines.append("✅ *Project Complete!*")
        elif project_status == "failed":
            lines.append("❌ *Project Failed*")
        else:
            current = full_state.get("currentStage") or full_state.get("current_stage")
            if current:
                lines.append(f"▶️ *Current:* {current}")
            else:
                # Find first pending
                for stage in pipeline or list(stages.keys()):
                    stage_data = stages.get(stage, {})
                    if stage_data.get("status") == "pending":
                        lines.append(f"⏸️ *Ready:* {stage}")
                        break
        
        text = "\n".join(lines)
        
        # Build action buttons - Resume for ALL projects
        buttons = []
        
        # Primary action: Resume with Carby
        buttons.append([
            InlineKeyboardButton("🔄 Resume with Carby", callback_data=f"resume:{project_id}")
        ])
        
        # Secondary actions based on status
        if project_status == "completed":
            buttons.append([InlineKeyboardButton("🗄️ Archive", callback_data=f"archive:{project_id}")])
        elif project_status == "failed":
            buttons.append([
                InlineKeyboardButton("🔄 Retry Stage", callback_data=f"retry:{project_id}"),
                InlineKeyboardButton("⏭️ Skip Stage", callback_data=f"skip:{project_id}")
            ])
        elif project_status == "active":
            # Active project - check current stage status
            current_stage = summary.get("current_stage") or summary.get("currentStage")
            if current_stage and stages.get(current_stage, {}).get("status") == "in-progress":
                buttons.append([
                    InlineKeyboardButton("🛑 Stop Agent", callback_data=f"stop:{project_id}"),
                    InlineKeyboardButton("📋 View Logs", callback_data=f"logs:{project_id}")
                ])
        
        # Project management buttons
        buttons.append([
            InlineKeyboardButton("✏️ Rename", callback_data=f"rename:{project_id}"),
            InlineKeyboardButton("🗑️ Delete", callback_data=f"delete:{project_id}")
        ])
        
        buttons.append([InlineKeyboardButton("← Back to Projects", callback_data="back:projects")])
        
        keyboard = InlineKeyboardMarkup(buttons)
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
        
    async def handle_dispatch(self, query, project_id: str):
        """Dispatch next stage with loading indicator."""
        # Show loading
        await query.answer("🚀 Dispatching...")
        loading_text = get_loading_message("dispatch", "initial", detail=f"Project: {project_id}")
        await query.edit_message_text(
            loading_text,
            parse_mode="Markdown"
        )
        
        # Perform operation
        result = self.bot.dispatch_stage(project_id)
        
        if result.success:
            success_text = get_loading_message(
                "dispatch", 
                "success",
                detail=f"Project: *{project_id}*\n\n```{result.stdout}```"
            )
            await query.edit_message_text(
                success_text,
                parse_mode="Markdown"
            )
        else:
            error_text = get_loading_message(
                "dispatch",
                "error",
                detail=f"Project: *{project_id}*\n\n```{result.stderr}```"
            )
            await query.edit_message_text(
                error_text,
                parse_mode="Markdown"
            )
            
    async def handle_resume(self, query, project_id: str):
        """Handle resume request - notify Carby to gather context."""
        # Debounce: prevent spam
        if project_id in self._active_resumes:
            await query.answer("Already resuming this project!")
            return
        
        self._active_resumes.add(project_id)
        
        try:
            # Show loading indicator immediately
            await query.answer("⏳ Resuming...")
            loading_text = get_loading_message("resume", "initial")
            await query.edit_message_text(
                loading_text,
                parse_mode="Markdown"
            )
            
            # Get project info
            summary = self.state_manager.get_project_summary(project_id)
            goal = summary.get("goal", "No goal set") if summary else "Unknown"
            status = summary.get("status", "unknown") if summary else "unknown"
            
            # Show success
            success_text = get_loading_message(
                "resume", 
                "success",
                detail=f"Project: *{project_id}*\nStatus: {status}\nGoal: {goal}\n\n"
                       f"✅ Carby has been notified and will message you shortly with:\n"
                       f"• Project context summary\n"
                       f"• Where you left off\n"
                       f"• Suggested next steps\n\n"
                       f"_Check your messages for Carby's brief._"
            )
            await query.edit_message_text(
                success_text,
                parse_mode="Markdown"
            )
            
            # Notify Carby
            await self._notify_carby_resume(query, project_id, goal, status)
            
        except (telegram.error.TelegramError, telegram.error.NetworkError, ValueError, KeyError) as e:
            logger.error(f"Resume failed: {e}")
            error_text = get_loading_message("resume", "error", detail="Please try again.")
            await query.edit_message_text(
                error_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Back", callback_data=f"view:{project_id}")
                ]])
            )
        finally:
            self._active_resumes.discard(project_id)

    async def _notify_carby_resume(self, query, project_id: str, goal: str, status: str):
        """Send resume notification to Carby (main agent) via OpenClaw sessions_send."""
        try:
            # Get project path
            project_path = os.path.join(
                os.path.expanduser("~/.openclaw/workspace/projects"),
                project_id
            )
            
            # Build resume request message for Carby
            carby_message = (
                f"🔄 **RESUME REQUEST**\n\n"
                f"From: Vincent\n"
                f"Project: **{project_id}**\n"
                f"Status: {status}\n"
                f"Goal: {goal}\n\n"
                f"📂 Project Location:\n"
                f"`{project_path}/`\n\n"
                f"📝 Please do the following:\n"
                f"1. Search your memory for this project\n"
                f"2. Read: README.md, requirements.md, design.md, task.md\n"
                f"3. Check git log for recent changes\n"
                f"4. Review Carby Studio status\n"
                f"5. Write a brief summary for Vincent\n\n"
                f"Reply here when ready with your summary."
            )
            
            # Send to Carby's main session using openclaw CLI
            # Use message send command to route to the user's main session
            import subprocess
            result = subprocess.run(
                ["openclaw", "message", "send", "--channel", "telegram", "--target", "8394363673", "--message", carby_message],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                logger.info(f"Resume request sent to Carby for {project_id}")
                success_text = (
                    f"✅ Resume Requested: {project_id}\n\n"
                    f"Carby has been notified and will send you a summary shortly."
                )
            else:
                logger.error(f"Failed to send resume request: {result.stderr}")
                success_text = (
                    f"✅ Resume Requested: {project_id}\n\n"
                    f"Carby notification failed. Please message @tintinwan_bot directly:\n"
                    f"Resume project {project_id}"
                )
            
            await query.edit_message_text(
                success_text,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Failed to handle resume: {e}")
            # Don't fail the user request if notification fails
            
    async def handle_approve(self, query, project_id: str):
        """Approve current stage."""
        # Approve via CLI
        result = self.bot.cli_executor.approve(project_id)
        
        if result.success:
            await query.edit_message_text(
                f"✅ *{project_id}*\n\n"
                f"Stage approved.\n\n"
                f"```{result.stdout}```",
                parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"❌ *{project_id}*\n\n"
                f"Failed to approve:\n"
                f"```{result.stderr}```",
                parse_mode="Markdown"
            )
            
    async def handle_reject(self, query, project_id: str):
        """Reject current stage."""
        await query.edit_message_text(
            f"📝 *Reject {project_id}*\n\n"
            f"Please send feedback for the agent:",
            parse_mode="Markdown"
        )
        # Store state for feedback handler
        # TODO: Implement feedback flow
        
    async def handle_retry(self, query, project_id: str):
        """Retry failed stage with loading indicator."""
        # Show loading
        await query.answer("🔄 Retrying...")
        loading_text = get_loading_message("retry", "initial", detail=f"Project: {project_id}")
        await query.edit_message_text(
            loading_text,
            parse_mode="Markdown"
        )
        
        # Perform operation
        result = self.bot.retry_stage(project_id)
        
        if result.success:
            success_text = get_loading_message(
                "retry",
                "success",
                detail=f"Project: *{project_id}*\n\n```{result.stdout}```"
            )
            await query.edit_message_text(
                success_text,
                parse_mode="Markdown"
            )
        else:
            error_text = get_loading_message(
                "retry",
                "error",
                detail=f"Project: *{project_id}*\n\n```{result.stderr}```"
            )
            await query.edit_message_text(
                error_text,
                parse_mode="Markdown"
            )
            
    async def handle_skip(self, query, project_id: str):
        """Skip current stage with loading indicator."""
        # Show loading
        await query.answer("⏭️ Skipping...")
        loading_text = get_loading_message("skip", "initial", detail=f"Project: {project_id}")
        await query.edit_message_text(
            loading_text,
            parse_mode="Markdown"
        )
        
        # Perform operation
        result = self.bot.skip_stage(project_id)
        
        if result.success:
            success_text = get_loading_message(
                "skip",
                "success",
                detail=f"Project: *{project_id}*\n\n```{result.stdout}```"
            )
            await query.edit_message_text(
                success_text,
                parse_mode="Markdown"
            )
        else:
            error_text = get_loading_message(
                "skip",
                "error",
                detail=f"Project: *{project_id}*\n\n```{result.stderr}```"
            )
            await query.edit_message_text(
                error_text,
                parse_mode="Markdown"
            )
            
    async def handle_stop(self, query, project_id: str):
        """Stop current stage with loading indicator."""
        # Show loading
        await query.answer("🛑 Stopping...")
        loading_text = get_loading_message("stop", "initial", detail=f"Project: {project_id}")
        await query.edit_message_text(
            loading_text,
            parse_mode="Markdown"
        )
        
        # Perform operation
        success, message = self.bot.stop_agent(project_id)
        
        if success:
            success_text = get_loading_message(
                "stop",
                "success",
                detail=f"Project: *{project_id}*\n\n{message}"
            )
            await query.edit_message_text(
                success_text,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Back", callback_data=f"view:{project_id}")
                ]])
            )
        else:
            error_text = get_loading_message(
                "stop",
                "error",
                detail=f"Project: *{project_id}*\n\n{message}"
            )
            await query.edit_message_text(
                error_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Back", callback_data=f"view:{project_id}")
                ]])
            )
            
    async def handle_logs(self, query, project_id: str):
        """View project logs with loading indicator."""
        # Show loading
        await query.answer("📋 Fetching logs...")
        loading_text = get_loading_message("logs", "initial", detail=f"Project: {project_id}")
        await query.edit_message_text(
            loading_text,
            parse_mode="Markdown"
        )
        
        # Perform operation
        result = self.bot.cli_executor.logs(project_id)
        
        if result.success:
            # Truncate if too long
            logs = result.stdout[:3000] if len(result.stdout) > 3000 else result.stdout
            success_text = get_loading_message(
                "logs",
                "success",
                detail=f"*{project_id} Logs*\n\n```\n{logs}\n```"
            )
            await query.edit_message_text(
                success_text,
                parse_mode="Markdown"
            )
        else:
            error_text = get_loading_message(
                "logs",
                "error",
                detail=f"Project: *{project_id}*\n\n```{result.stderr}```"
            )
            await query.edit_message_text(
                error_text,
                parse_mode="Markdown"
            )
            
    async def handle_back_to_projects(self, query):
        """Return to projects list - 2 per row, in-progress first, then completed."""
        projects = self.state_manager.list_projects()
        
        # Sort projects: in-progress first, then completed
        in_progress = []
        completed = []
        
        for project_id in projects:
            summary = self.state_manager.get_project_summary(project_id)
            if not summary:
                continue
            
            project_status = summary.get("status", "")
            current_status = summary.get("current_status", "")
            
            if project_status == "completed" or current_status == "completed":
                completed.append((project_id, "🟢"))
            else:
                in_progress.append((project_id, "🟡"))
        
        # Header text
        text = f"📋 Your Projects ({len(projects)})\n\nTap a project to view details:"
        
        # Build keyboard: 2 buttons per row
        keyboard = []
        all_projects = in_progress + completed  # In-progress first, then completed
        
        for i in range(0, len(all_projects), 2):
            row = []
            # First button in row
            pid1, icon1 = all_projects[i]
            row.append(InlineKeyboardButton(f"{icon1} {pid1}", callback_data=f"view:{pid1}"))
            # Second button in row (if exists)
            if i + 1 < len(all_projects):
                pid2, icon2 = all_projects[i + 1]
                row.append(InlineKeyboardButton(f"{icon2} {pid2}", callback_data=f"view:{pid2}"))
            keyboard.append(row)
        
        # Add back to main menu button
        keyboard.append([InlineKeyboardButton("← Back to Main Menu", callback_data="back:main")])
        
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    async def handle_back_to_main(self, query):
        """Return to main menu - send new message with reply keyboard."""
        await query.answer()
        welcome_text = (
            "🤖 *Welcome to Carby Studio Bot!*\n\n"
            "Your AI-powered development assistant.\n\n"
            "*Quick Actions:*\n"
            "• 📋 Projects — View all projects\n"
            "• ⚙️ More — System status & help\n\n"
            "Tap a button below to get started! 👇"
        )
        # Delete the inline keyboard message and send a new one with reply keyboard
        await query.delete_message()
        await self.application.bot.send_message(
            chat_id=query.from_user.id,
            text=welcome_text,
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        
    async def rename_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start rename conversation."""
        query = update.callback_query
        await query.answer()
        
        project_id = query.data.split(":")[1]
        context.user_data['renaming_project'] = project_id
        
        await query.edit_message_text(
            f"✏️ *Rename {project_id}*\n\n"
            f"Enter new project name:",
            parse_mode="Markdown"
        )
        return RENAME_PROJECT
    
    async def rename_confirm(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show rename confirmation dialog."""
        old_name = context.user_data.get('renaming_project')
        new_name = update.message.text.strip()
        
        if not old_name:
            await update.message.reply_text("Error: No project selected.", reply_markup=MAIN_KEYBOARD)
            return ConversationHandler.END
        
        # Validate new name format
        import re
        if not re.match(r'^[a-z0-9-]+$', new_name):
            await update.message.reply_text(
                "❌ *Invalid Project Name*\n\n"
                "Names must contain only:\n"
                "• Lowercase letters (a-z)\n"
                "• Numbers (0-9)\n"
                "• Hyphens (-)\n\n"
                "Examples: my-project, project123, new-app",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
            return ConversationHandler.END
        
        # Store new name for confirmation
        context.user_data['rename_new_name'] = new_name
        
        # Show confirmation dialog
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Rename", callback_data=f"confirm_rename:{new_name}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_rename")]
        ])
        
        await update.message.reply_text(
            f"⚠️ *Confirm Rename*\n\n"
            f"From: `{old_name}`\n"
            f"To: `{new_name}`\n\n"
            f"This cannot be undone.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return RENAME_CONFIRM
        
    async def rename_execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Execute rename with loading indicator."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "cancel_rename":
            await query.edit_message_text(
                "❌ Rename cancelled.",
                reply_markup=MAIN_KEYBOARD
            )
            return ConversationHandler.END
        
        # Extract new name from callback data
        if not data.startswith("confirm_rename:"):
            await query.edit_message_text(
                "Error: Invalid confirmation.",
                reply_markup=MAIN_KEYBOARD
            )
            return ConversationHandler.END
        
        new_name = data.split(":", 1)[1]
        old_name = context.user_data.get('renaming_project')
        
        if not old_name:
            await query.edit_message_text(
                "Error: No project selected.",
                reply_markup=MAIN_KEYBOARD
            )
            return ConversationHandler.END
        
        # Show loading
        loading_text = get_loading_message("rename", "initial", detail=f"From: {old_name}\nTo: {new_name}")
        await query.edit_message_text(
            loading_text,
            parse_mode="Markdown"
        )
        
        # Perform operation
        success, message = self.bot.rename_project(old_name, new_name)
        
        if success:
            success_text = get_loading_message(
                "rename",
                "success",
                detail=message
            )
            await query.edit_message_text(
                success_text,
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
        else:
            error_info = get_error_info("E3005", {"project": old_name})
            error_text = format_error_message(error_info)
            await query.edit_message_text(
                error_text,
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
        
        return ConversationHandler.END
        
    async def delete_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start delete conversation - show confirmation buttons."""
        query = update.callback_query
        await query.answer()
        
        project_id = query.data.split(":")[1]
        context.user_data['deleting_project'] = project_id
        
        # Get safety preview
        check = self.bot.safety_manager.check_delete(project_id)
        preview = self.bot.safety_manager.format_delete_preview(project_id, check.details or {})
        
        # Show confirmation with buttons
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete", callback_data=f"confirm_delete:{project_id}")],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"view:{project_id}")]
        ])
        
        await query.edit_message_text(
            f"{preview}\n\nAre you sure you want to delete this project?",
            reply_markup=keyboard
        )
        return ConversationHandler.END
        
    async def delete_execute(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Execute delete - no longer used with button flow."""
        pass
        
    async def handle_confirm_delete(self, query, project_id: str):
        """Handle delete confirmation with loading indicator."""
        # Show loading
        await query.answer("🗑️ Deleting...")
        loading_text = get_loading_message("delete", "initial", detail=f"Project: {project_id}")
        await query.edit_message_text(
            loading_text,
            parse_mode="Markdown"
        )
        
        # Perform operation
        success, message = self.bot.delete_project(project_id, "DELETE")
        
        if success:
            success_text = get_loading_message(
                "delete",
                "success",
                detail=f"{message}\n\nReturning to projects..."
            )
            await query.edit_message_text(success_text)
            # Show projects list after short delay
            await self.handle_back_to_projects(query)
        else:
            error_text = get_loading_message(
                "delete",
                "error",
                detail=message
            )
            await query.edit_message_text(
                error_text,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("← Back", callback_data=f"view:{project_id}")
                ]])
            )
        
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages with improved NLU."""
        text = update.message.text
        
        # Match intent using NLU
        intent, confidence = match_intent(text)
        
        logger.info(f"NLU: matched intent '{intent}' with confidence {confidence:.2f} for text: {text[:50]}")
        
        if intent == Intent.PROJECTS:
            await self.cmd_projects(update, context)
        
        elif intent == Intent.STATUS:
            await self.cmd_status(update, context)
        
        elif intent == Intent.CONTINUE:
            # Continue last active project
            projects = self.state_manager.list_projects()
            if projects:
                # Try to extract specific project name
                project_id = extract_project_name(text)
                if project_id and project_id in projects:
                    # User mentioned a specific project
                    pass
                else:
                    project_id = projects[0]  # Default to first
                
                summary = self.state_manager.get_project_summary(project_id)
                if summary:
                    detail = self.bot.get_project_detail(project_id)
                    await update.message.reply_text(
                        f"🔄 *Resuming {project_id}...*\n\n{detail}",
                        parse_mode="Markdown"
                    )
                    return
            await update.message.reply_text(
                "No active projects. Create one with: `carby-studio init <name>`",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
        
        elif intent == Intent.HELP:
            await self.cmd_help(update, context)
        
        elif intent == Intent.CREATE:
            # Project creation via bot removed - use CLI instead
            await update.message.reply_text(
                "➕ *Create New Project*\n\n"
                "Please use the CLI to create projects:\n"
                "```\n"
                "carby-studio init <project-name> -g 'Your goal'\n"
                "```",
                parse_mode="Markdown",
                reply_markup=MAIN_KEYBOARD
            )
        
        elif intent == Intent.STOP:
            # Stop the most recent active project
            projects = self.state_manager.list_projects()
            active_project = None
            for pid in projects:
                summary = self.state_manager.get_project_summary(pid)
                if summary and summary.get("current_status") == "in-progress":
                    active_project = pid
                    break
            
            if active_project:
                success, message = self.bot.stop_agent(active_project)
                if success:
                    await update.message.reply_text(
                        f"🛑 *Agent Stopped*\n\n{message}",
                        parse_mode="Markdown",
                        reply_markup=MAIN_KEYBOARD
                    )
                else:
                    error_info = get_error_info("E3002", {"project": active_project})
                    await update.message.reply_text(
                        format_error_message(error_info),
                        parse_mode="Markdown",
                        reply_markup=MAIN_KEYBOARD
                    )
            else:
                await update.message.reply_text(
                    "No running agents to stop.",
                    reply_markup=MAIN_KEYBOARD
                )
        
        else:
            # Unknown intent - offer smart suggestions
            nlu = get_nlu_handler()
            suggestions = nlu.get_suggestions(text)
            suggestion_text = nlu.format_suggestions(suggestions)
            
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Projects", callback_data="back:projects")],
                [InlineKeyboardButton("📊 System Status", callback_data="status")],
                [InlineKeyboardButton("❓ Help", callback_data="help")]
            ])
            await update.message.reply_text(
                f"I'm not sure what you mean. {suggestion_text}",
                reply_markup=keyboard
            )


def main():
    """Main entry point."""
    handler = TelegramInterface()
    handler.run()


if __name__ == "__main__":
    main()
