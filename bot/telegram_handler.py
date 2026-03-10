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

from carby_bot import get_bot, ProjectStatus

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
    ["📋 Projects", "➕ New Project", "⚙️ More"]
], resize_keyboard=True)

MORE_KEYBOARD = ReplyKeyboardMarkup([
    ["🔐 Credentials", "📊 System Status"],
    ["🗄️ Archived Projects", "❓ Help"],
    ["← Back to Main"]
], resize_keyboard=True)


class TelegramHandler:
    """Handles all Telegram bot interactions."""
    
    def __init__(self):
        self.bot = get_bot()
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
        
        # Main menu handler
        application.add_handler(MessageHandler(filters.Regex("^📋 Projects$"), self.cmd_projects))
        application.add_handler(MessageHandler(filters.Regex("^⚙️ More$"), self.cmd_more))
        application.add_handler(MessageHandler(filters.Regex("^← Back to Main$"), self.cmd_back_main))
        application.add_handler(MessageHandler(filters.Regex("^🔐 Credentials$"), self.cmd_credentials))
        application.add_handler(MessageHandler(filters.Regex("^📊 System Status$"), self.cmd_system_status))
        application.add_handler(MessageHandler(filters.Regex("^🗄️ Archived Projects$"), self.cmd_archived))
        application.add_handler(MessageHandler(filters.Regex("^❓ Help$"), self.cmd_help))
        
        # Natural language handler
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        logger.info("Starting Carby Bot...")
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "🤖 *Carby Studio*\n\n"
            "Your AI development team.\n\n"
            "What would you like to do?",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
        
    async def cmd_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle projects list."""
        projects = self.bot.list_projects(ProjectStatus.ACTIVE)
        text = self.bot.format_projects_list(projects)
        
        # Add inline buttons for each project
        keyboard = []
        for p in projects:
            current = p.stages.get(p.current_stage)
            if current.status.value == "done":
                # Pending approval
                keyboard.append([
                    InlineKeyboardButton(f"Review {p.id}", callback_data=f"review:{p.id}"),
                    InlineKeyboardButton("Approve", callback_data=f"approve:{p.id}"),
                    InlineKeyboardButton("Reject", callback_data=f"reject:{p.id}")
                ])
            elif current.status.value == "failed":
                # Failed
                keyboard.append([
                    InlineKeyboardButton(f"View {p.id}", callback_data=f"view:{p.id}"),
                    InlineKeyboardButton("Retry", callback_data=f"retry:{p.id}"),
                    InlineKeyboardButton("Skip", callback_data=f"skip:{p.id}")
                ])
            else:
                # Normal
                keyboard.append([
                    InlineKeyboardButton(f"View {p.id}", callback_data=f"view:{p.id}"),
                    InlineKeyboardButton("Stop", callback_data=f"stop:{p.id}")
                ])
                
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        
        await update.message.reply_text(
            text,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle status command."""
        projects = self.bot.list_projects(ProjectStatus.ACTIVE)
        
        in_progress = sum(1 for p in projects 
                         if p.stages.get(p.current_stage).status.value == "in_progress")
        pending_approval = sum(1 for p in projects 
                              if p.stages.get(p.current_stage).status.value == "done")
        failed = sum(1 for p in projects 
                    if p.stages.get(p.current_stage).status.value == "failed")
        
        text = (
            "📊 *System Status*\n\n"
            f"Active projects: {len(projects)}\n"
            f"🟢 In progress: {in_progress}\n"
            f"🟡 Pending approval: {pending_approval}\n"
            f"🔴 Failed: {failed}\n\n"
            "Gateway: 🟢 Running\n"
            "All systems operational."
        )
        
        await update.message.reply_text(text, parse_mode="Markdown")
        
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
        # TODO: Implement credential management
        await update.message.reply_text(
            "🔐 *Credentials*\n\n"
            "Shared credentials:\n"
            "✅ synology-nas\n"
            "✅ icloud-api\n"
            "⬜ sony-wifi\n\n"
            "[Setup Sony WiFi] — coming soon",
            parse_mode="Markdown",
            reply_markup=MORE_KEYBOARD
        )
        
    async def cmd_system_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show system status."""
        await self.cmd_status(update, context)
        
    async def cmd_archived(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show archived projects."""
        projects = self.bot.list_projects(ProjectStatus.ARCHIVED)
        if not projects:
            text = "🗄️ No archived projects."
        else:
            text = "🗄️ *Archived Projects*\n\n"
            for p in projects:
                text += f"• {p.id}\n"
                
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=MORE_KEYBOARD)
        
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
            
            # Create project
            project = self.bot.create_project(project_id, goal)
            
            if approach == "quick":
                await query.edit_message_text(
                    f"✅ Project created: `{project_id}`\n"
                    f"Mode: Quick (single agent)\n\n"
                    f"Starting now...",
                    parse_mode="Markdown"
                )
                # TODO: Spawn quick agent
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Yes, Start Discover", callback_data=f"start:{project_id}")],
                    [InlineKeyboardButton("Later", callback_data="cancel")]
                ])
                await query.edit_message_text(
                    f"✅ Project created: `{project_id}`\n"
                    f"Mode: Full Pipeline\n\n"
                    f"Start Discover stage?",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
                
        elif action == "start":
            project_id = parts[1]
            project = self.bot.start_stage(project_id)
            if project:
                await query.edit_message_text(
                    f"🚀 Started *{project.current_stage}* stage\n"
                    f"Project: `{project_id}`\n"
                    f"Agent: {project.stages[project.current_stage].agent}",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("❌ Failed to start stage")
                
        elif action == "view":
            project_id = parts[1]
            project = self.bot.load_project(project_id)
            if project:
                text = self.bot.format_project_detail(project)
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🛑 Stop", callback_data=f"stop:{project_id}"),
                        InlineKeyboardButton("📋 Logs", callback_data=f"logs:{project_id}")
                    ],
                    [InlineKeyboardButton("← Back to Projects", callback_data="back:projects")]
                ])
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
            else:
                await query.edit_message_text("❌ Project not found")
                
        elif action == "review":
            project_id = parts[1]
            project = self.bot.load_project(project_id)
            if project:
                text = self.bot.format_approval_screen(project)
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve:{project_id}"),
                        InlineKeyboardButton("📝 Reject", callback_data=f"reject:{project_id}")
                    ],
                    [InlineKeyboardButton("View Full Design", callback_data=f"view:{project_id}")]
                ])
                await query.edit_message_text(text, parse_mode="Markdown", reply_markup=keyboard)
            else:
                await query.edit_message_text("❌ Project not found")
                
        elif action == "approve":
            project_id = parts[1]
            project = self.bot.approve_stage(project_id)
            if project:
                await query.edit_message_text(
                    f"✅ Approved *{project.stages[project.current_stage].name}* stage\n\n"
                    f"Next: *{project.current_stage.capitalize()}* starting...",
                    parse_mode="Markdown"
                )
                # TODO: Auto-start next stage or notify user
            else:
                await query.edit_message_text("❌ Failed to approve")
                
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
            project = self.bot.retry_stage(project_id)
            if project:
                await query.edit_message_text(
                    f"🔄 Retrying *{project.current_stage}* stage\n"
                    f"Project: `{project_id}`",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("❌ Failed to retry")
                
        elif action == "skip":
            project_id = parts[1]
            project = self.bot.skip_stage(project_id)
            if project:
                await query.edit_message_text(
                    f"⏭️ Skipped *{project.stages[project.current_stage].name}* stage\n\n"
                    f"Next: *{project.current_stage.capitalize()}*",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("❌ Failed to skip")
                
        elif action == "stop":
            project_id = parts[1]
            # TODO: Implement stop
            await query.edit_message_text(
                f"🛑 Stopped *{project_id}*\n\n"
                f"Agent terminated.",
                parse_mode="Markdown"
            )
            
        elif action == "back":
            if parts[1] == "projects":
                await self.cmd_projects(update, context)
                
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
            projects = self.bot.list_projects(ProjectStatus.ACTIVE)
            if projects:
                project = projects[0]
                await update.message.reply_text(
                    f"Continuing *{project.id}*...",
                    parse_mode="Markdown"
                )
                # Show project detail
                text = self.bot.format_project_detail(project)
                await update.message.reply_text(text, parse_mode="Markdown")
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
