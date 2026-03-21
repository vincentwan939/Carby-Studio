"""
Security Changes for telegram_handler.py

This file documents all the security-related changes needed in telegram_handler.py.
Apply these changes to integrate the security features from security_config.py.
"""

# =============================================================================
# STEP 1: Add imports at the top of telegram_handler.py
# =============================================================================

IMPORTS_TO_ADD = '''
# Add these imports after the existing imports
from security_config import (
    is_authorized,
    check_authorization,
    validate_project_id,
    validate_callback_data,
    sanitize_log_message,
    check_rate_limit,
    isolate_project_id,
    extract_base_project_id,
    belongs_to_user,
    secure_handler,
    ALLOWED_USERS,
)
'''


# =============================================================================
# STEP 2: Modify __init__ method to add security checks
# =============================================================================

INIT_CHANGES = '''
# In __init__, add after token validation:
if ALLOWED_USERS:
    logger.info(f"Bot configured with {len(ALLOWED_USERS)} authorized users")
else:
    logger.warning("No ALLOWED_USERS set - bot is open to all users (development mode)")
'''


# =============================================================================
# STEP 3: Add user isolation helper method
# =============================================================================

USER_ISOLATION_METHOD = '''
    def _get_user_id(self, update: Update) -> Optional[int]:
        """Safely extract user ID from update."""
        return update.effective_user.id if update.effective_user else None
    
    def _get_isolated_project_id(self, project_id: str, user_id: int) -> str:
        """Create user-isolated project ID."""
        return isolate_project_id(project_id, user_id)
    
    def _extract_project_id(self, isolated_id: str, user_id: int) -> Optional[str]:
        """Extract base project ID from isolated ID."""
        return extract_base_project_id(isolated_id, user_id)
'''


# =============================================================================
# STEP 4: Secure cmd_start method
# =============================================================================

CMD_START_CHANGES = '''
    @secure_handler
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command with security checks."""
        # secure_handler decorator handles auth and rate limiting
        await update.message.reply_text(
            "🤖 *Carby Studio*\n\n"
            "Your AI development team.\n\n"
            "What would you like to do?",
            parse_mode="Markdown",
            reply_markup=MAIN_KEYBOARD
        )
'''


# =============================================================================
# STEP 5: Secure cmd_projects method with user isolation
# =============================================================================

CMD_PROJECTS_CHANGES = '''
    @secure_handler
    async def cmd_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle projects list with user isolation."""
        user_id = self._get_user_id(update)
        
        projects = self.bot.list_projects(ProjectStatus.ACTIVE)
        
        # Filter projects to only show user's own projects
        user_projects = [p for p in projects if belongs_to_user(p.id, user_id)]
        
        text = self.bot.format_projects_list(user_projects)
        
        # Add inline buttons for each project
        keyboard = []
        for p in user_projects:
            current = p.stages.get(p.current_stage)
            if current.status.value == "done":
                keyboard.append([
                    InlineKeyboardButton(f"Review {p.id}", callback_data=f"review:{p.id}"),
                    InlineKeyboardButton("Approve", callback_data=f"approve:{p.id}"),
                    InlineKeyboardButton("Reject", callback_data=f"reject:{p.id}")
                ])
            elif current.status.value == "failed":
                keyboard.append([
                    InlineKeyboardButton(f"View {p.id}", callback_data=f"view:{p.id}"),
                    InlineKeyboardButton("Retry", callback_data=f"retry:{p.id}"),
                    InlineKeyboardButton("Skip", callback_data=f"skip:{p.id}")
                ])
            else:
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
'''


# =============================================================================
# STEP 6: Secure cmd_status method
# =============================================================================

CMD_STATUS_CHANGES = '''
    @secure_handler
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle status command with user isolation."""
        user_id = self._get_user_id(update)
        
        projects = self.bot.list_projects(ProjectStatus.ACTIVE)
        user_projects = [p for p in projects if belongs_to_user(p.id, user_id)]
        
        in_progress = sum(1 for p in user_projects 
                         if p.stages.get(p.current_stage).status.value == "in_progress")
        pending_approval = sum(1 for p in user_projects 
                              if p.stages.get(p.current_stage).status.value == "done")
        failed = sum(1 for p in user_projects 
                    if p.stages.get(p.current_stage).status.value == "failed")
        
        text = (
            "📊 *System Status*\n\n"
            f"Your active projects: {len(user_projects)}\n"
            f"🟢 In progress: {in_progress}\n"
            f"🟡 Pending approval: {pending_approval}\n"
            f"🔴 Failed: {failed}\n\n"
            "Gateway: 🟢 Running\n"
            "All systems operational."
        )
        
        await update.message.reply_text(text, parse_mode="Markdown")
'''


# =============================================================================
# STEP 7: Secure new_project_start with input validation
# =============================================================================

NEW_PROJECT_START_CHANGES = '''
    @secure_handler
    async def new_project_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start new project conversation with security checks."""
        await update.message.reply_text(
            "➕ *New Project*\n\n"
            "What are you building?\n"
            "(Describe in one sentence)",
            parse_mode="Markdown"
        )
        return NEW_PROJECT_GOAL
'''


# =============================================================================
# STEP 8: Secure new_project_goal with project ID validation
# =============================================================================

NEW_PROJECT_GOAL_CHANGES = '''
    @secure_handler
    async def new_project_goal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle project goal with validation."""
        goal = update.message.text
        context.user_data['project_goal'] = goal
        
        # Generate project ID from goal
        base_project_id = goal.lower().replace(" ", "-")[:30]
        
        # Validate the project ID
        is_valid, error_msg = validate_project_id(base_project_id)
        if not is_valid:
            logger.warning(sanitize_log_message(f"Invalid project ID attempt: {error_msg}"))
            await update.message.reply_text(
                f"❌ *Invalid Project Name*\n\n{error_msg}\n\n"
                f"Please try again with a valid name (lowercase letters, numbers, hyphens).",
                parse_mode="Markdown"
            )
            return NEW_PROJECT_GOAL
        
        # Apply user isolation
        user_id = self._get_user_id(update)
        project_id = self._get_isolated_project_id(base_project_id, user_id)
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
            f"Project ID: `{base_project_id}`\n\n"
            f"Choose approach:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        
        return ConversationHandler.END
'''


# =============================================================================
# STEP 9: Secure handle_callback with bounds checking
# =============================================================================

HANDLE_CALLBACK_CHANGES = '''
    @secure_handler
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks with bounds checking and validation."""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        # Validate callback data with bounds checking
        is_valid, parts, error_msg = validate_callback_data(data, expected_parts=1)
        if not is_valid:
            logger.warning(sanitize_log_message(f"Invalid callback data: {error_msg}"))
            await query.edit_message_text("❌ Invalid request. Please try again.")
            return
        
        action = parts[0]
        
        # Bounds checking for each action type
        if action == "approach":
            # Expected: approach:quick|full:project_id
            if len(parts) < 3:
                logger.warning(sanitize_log_message(f"Invalid approach callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            approach = parts[1]
            project_id = parts[2]
            
            # Validate project ownership
            user_id = self._get_user_id(update)
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to access project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
            goal = context.user_data.get('project_goal', 'Unknown project')
            
            # Validate approach value
            if approach not in ('quick', 'full'):
                logger.warning(sanitize_log_message(f"Invalid approach: {approach}"))
                await query.edit_message_text("❌ Invalid approach selected.")
                return
            
            # Create project
            project = self.bot.create_project(project_id, goal)
            
            if approach == "quick":
                await query.edit_message_text(
                    f"✅ Project created: `{project_id}`\n"
                    f"Mode: Quick (single agent)\n\n"
                    f"Starting now...",
                    parse_mode="Markdown"
                )
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
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid start callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            project_id = parts[1]
            user_id = self._get_user_id(update)
            
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to start project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
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
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid view callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            project_id = parts[1]
            user_id = self._get_user_id(update)
            
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to view project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
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
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid review callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            project_id = parts[1]
            user_id = self._get_user_id(update)
            
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to review project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
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
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid approve callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            project_id = parts[1]
            user_id = self._get_user_id(update)
            
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to approve project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
            project = self.bot.approve_stage(project_id)
            if project:
                await query.edit_message_text(
                    f"✅ Approved *{project.stages[project.current_stage].name}* stage\n\n"
                    f"Next: *{project.current_stage.capitalize()}* starting...",
                    parse_mode="Markdown"
                )
            else:
                await query.edit_message_text("❌ Failed to approve")
                
        elif action == "reject":
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid reject callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            project_id = parts[1]
            user_id = self._get_user_id(update)
            
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to reject project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
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
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid retry callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            project_id = parts[1]
            user_id = self._get_user_id(update)
            
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to retry project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
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
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid skip callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            project_id = parts[1]
            user_id = self._get_user_id(update)
            
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to skip project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
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
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid stop callback: {data}"))
                await query.edit_message_text("❌ Invalid request format.")
                return
            
            project_id = parts[1]
            user_id = self._get_user_id(update)
            
            if not belongs_to_user(project_id, user_id):
                logger.warning(f"User {user_id} attempted to stop project {project_id}")
                await query.edit_message_text("⛔ Access denied: Project not found.")
                return
            
            await query.edit_message_text(
                f"🛑 Stopped *{project_id}*\n\n"
                f"Agent terminated.",
                parse_mode="Markdown"
            )
            
        elif action == "back":
            if len(parts) < 2:
                logger.warning(sanitize_log_message(f"Invalid back callback: {data}"))
                return
            
            if parts[1] == "projects":
                await self.cmd_projects(update, context)
                
        elif action == "cancel":
            await query.edit_message_text("Cancelled.")
        else:
            logger.warning(sanitize_log_message(f"Unknown callback action: {action}"))
            await query.edit_message_text("❌ Unknown action.")
'''


# =============================================================================
# STEP 10: Secure handle_message method
# =============================================================================

HANDLE_MESSAGE_CHANGES = '''
    @secure_handler
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle natural language messages with security checks."""
        text = update.message.text.lower()
        
        # Natural language patterns
        if any(word in text for word in ["projects", "list", "my projects"]):
            await self.cmd_projects(update, context)
        elif any(word in text for word in ["status", "what's running", "what is running"]):
            await self.cmd_status(update, context)
        elif any(word in text for word in ["continue", "resume"]):
            # Continue last active project
            user_id = self._get_user_id(update)
            projects = self.bot.list_projects(ProjectStatus.ACTIVE)
            user_projects = [p for p in projects if belongs_to_user(p.id, user_id)]
            
            if user_projects:
                project = user_projects[0]
                await update.message.reply_text(
                    f"Continuing *{project.id}*...",
                    parse_mode="Markdown"
                )
                text = self.bot.format_project_detail(project)
                await update.message.reply_text(text, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    "No active projects. Start one with ➕ New Project"
                )
        elif any(word in text for word in ["help", "how to", "how do i"]):
            await self.cmd_help(update, context)
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 View Projects", callback_data="back:projects")],
                [InlineKeyboardButton("➕ New Project", callback_data="new_project")],
                [InlineKeyboardButton("❓ Help", callback_data="help")]
            ])
            await update.message.reply_text(
                "I'm not sure what you mean. Did you want to:",
                reply_markup=keyboard
            )
'''


# =============================================================================
# STEP 11: Update logging to use sanitization
# =============================================================================

LOGGING_CHANGES = '''
# Replace the logging configuration at the top of the file with:
class SanitizingLogFilter(logging.Filter):
    """Filter that sanitizes log messages to prevent token leakage."""
    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = sanitize_log_message(record.msg)
        if record.args:
            record.args = tuple(
                sanitize_log_message(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.addFilter(SanitizingLogFilter())
'''


# =============================================================================
# SUMMARY OF CHANGES
# =============================================================================

SUMMARY = """
SECURITY HARDENING SUMMARY
==========================

1. USER AUTHENTICATION
   - Added ALLOWED_USERS check from CARBY_ALLOWED_USERS env var
   - @secure_handler decorator on all command handlers
   - Unauthorized users get access denied message

2. INPUT VALIDATION
   - Project IDs validated against PROJECT_NAME_PATTERN regex
   - Callback data validated with bounds checking
   - Invalid inputs logged with sanitized messages

3. BOUNDS CHECKING
   - All callback data parts checked before accessing indices
   - Minimum parts validated for each action type
   - Graceful error handling for malformed callbacks

4. TOKEN SANITIZATION
   - sanitize_log_message() masks bot tokens and API keys
   - Custom logging filter applies sanitization automatically
   - Tokens won't appear in logs even in error messages

5. RATE LIMITING
   - 30 requests per 60 seconds per user
   - Rate limit exceeded message with wait time
   - In-memory storage (resets on restart)

6. USER ISOLATION
   - Projects prefixed with user-specific hash
   - Users can only see/access their own projects
   - belongs_to_user() check on all project operations

ENVIRONMENT VARIABLES REQUIRED:
- CARBY_BOT_TOKEN: Your Telegram bot token
- CARBY_ALLOWED_USERS: Comma-separated list of authorized Telegram user IDs
  (e.g., "123456789,987654321") - if empty, all users allowed (dev mode)
"""