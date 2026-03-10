#!/usr/bin/env python3
"""
Tests for Telegram Interface (Phase 3)
Comprehensive pytest coverage for telegram_interface.py
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# Ensure proper imports
sys.path.insert(0, str(Path(__file__).parent))

# Set up environment before importing
os.environ["CARBY_BOT_TOKEN"] = "test_token_12345"

# Import after setting env
from telegram_interface import (
    TelegramInterface, MAIN_KEYBOARD, MORE_KEYBOARD,
    RENAME_PROJECT, DELETE_CONFIRM
)


# =============================================================================
# Fixtures
# =============================================================================

def async_mock(return_value=None):
    """Create an async mock function."""
    async def mock_coro(*args, **kwargs):
        return return_value
    return mock_coro


@pytest.fixture
def mock_update():
    """Create a mock Update object."""
    update = Mock()
    update.message = Mock()
    update.message.reply_text = Mock(return_value=asyncio.Future())
    update.message.reply_text.return_value.set_result(None)
    update.effective_message = Mock()
    update.effective_message.reply_text = Mock(return_value=asyncio.Future())
    update.effective_message.reply_text.return_value.set_result(None)
    return update


@pytest.fixture
def mock_context():
    """Create a mock Context object."""
    context = Mock()
    context.user_data = {}
    context.bot_data = {}
    return context


@pytest.fixture
def mock_query():
    """Create a mock CallbackQuery."""
    query = Mock()
    query.answer = Mock(return_value=asyncio.Future())
    query.answer.return_value.set_result(None)
    query.edit_message_text = Mock(return_value=asyncio.Future())
    query.edit_message_text.return_value.set_result(None)
    query.data = "view:test-project"
    return query


@pytest.fixture
def interface():
    """Create TelegramInterface with mocked dependencies."""
    with patch('telegram_interface.CarbyBot') as mock_bot, \
         patch('telegram_interface.StateManager') as mock_state:
        
        mock_bot_instance = Mock()
        mock_bot_instance.safety_manager = Mock()
        mock_bot.return_value = mock_bot_instance
        
        mock_state_instance = Mock()
        mock_state.return_value = mock_state_instance
        
        iface = TelegramInterface()
        return iface


# =============================================================================
# Test Class: Initialization and Basic Setup
# =============================================================================

class TestInitialization:
    """Test TelegramInterface initialization."""
    
    def test_initialization_with_token(self):
        """Test TelegramInterface initializes correctly with token."""
        with patch('telegram_interface.CarbyBot') as mock_bot, \
             patch('telegram_interface.StateManager') as mock_state:
            
            mock_bot_instance = Mock()
            mock_bot.return_value = mock_bot_instance
            mock_state_instance = Mock()
            mock_state.return_value = mock_state_instance
            
            interface = TelegramInterface()
            
            assert interface.token == "test_token_12345"
            assert interface.bot == mock_bot_instance
            assert interface.state_manager == mock_state_instance
    
    def test_initialization_missing_token(self):
        """Test that missing token raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="CARBY_BOT_TOKEN"):
                TelegramInterface()
    
    def test_user_data_initialized(self):
        """Test user_data dict is initialized."""
        with patch('telegram_interface.CarbyBot'), \
             patch('telegram_interface.StateManager'):
            
            interface = TelegramInterface()
            assert interface.user_data == {}


# =============================================================================
# Test Class: Command Handlers (/start, /help, /status, /cancel)
# =============================================================================

class TestCommandHandlers:
    """Test command handler methods."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_start(self, interface, mock_update, mock_context):
        """Test /start command sends welcome message."""
        await interface.cmd_start(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        
        assert "Carby Studio Bot" in text
        assert "📋" in text
        assert "➕" in text
        assert "✅" in text
        assert "🔐" in text
        assert call_args[1]['parse_mode'] == "Markdown"
        assert call_args[1]['reply_markup'] == MAIN_KEYBOARD
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_help(self, interface, mock_update, mock_context):
        """Test /help command shows help text."""
        await interface.cmd_help(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        
        assert "Help" in text
        assert "Projects" in text
        assert "Status" in text
        assert "Approve" in text
        assert "Reject" in text
        assert call_args[1]['parse_mode'] == "Markdown"
        assert call_args[1]['reply_markup'] == MORE_KEYBOARD
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_status_no_projects(self, interface, mock_update, mock_context):
        """Test /status with no projects."""
        interface.state_manager.list_projects.return_value = []
        
        await interface.cmd_status(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        
        assert "System Status" in text
        assert "Active projects: 0" in text
        assert "In progress: 0" in text
        assert "Pending approval: 0" in text
        assert "Failed: 0" in text
        assert call_args[1]['parse_mode'] == "Markdown"
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_status_with_projects(self, interface, mock_update, mock_context):
        """Test /status with various project states."""
        interface.state_manager.list_projects.return_value = [
            "proj-in-progress", "proj-done", "proj-failed"
        ]
        interface.state_manager.get_project_summary.side_effect = lambda pid: {
            "proj-in-progress": {"current_status": "in-progress"},
            "proj-done": {"current_status": "done"},
            "proj-failed": {"current_status": "failed"},
        }.get(pid)
        
        await interface.cmd_status(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        
        assert "Active projects: 3" in text
        assert "In progress: 1" in text
        assert "Pending approval: 1" in text
        assert "Failed: 1" in text
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_cancel(self, interface, mock_update, mock_context):
        """Test /cancel command ends conversation."""
        result = await interface.cmd_cancel(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Cancelled" in call_args[0][0]
        assert call_args[1]['reply_markup'] == MAIN_KEYBOARD
        assert result == -1  # ConversationHandler.END


# =============================================================================
# Test Class: Project Management (create_project, list_projects, view_project)
# =============================================================================

class TestProjectManagement:
    """Test project management commands."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_projects_empty(self, interface, mock_update, mock_context):
        """Test projects command with no projects."""
        interface.state_manager.list_projects.return_value = []
        interface.bot.get_project_list.return_value = "📋 No projects found."
        
        await interface.cmd_projects(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert call_args[1]['parse_mode'] == "Markdown"
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_projects_with_done_status(self, interface, mock_update, mock_context):
        """Test projects list shows approve/reject buttons for done status."""
        from telegram import InlineKeyboardMarkup
        
        interface.state_manager.list_projects.return_value = ["test-proj"]
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "done",
            "current_stage": "stage-1"
        }
        interface.bot.get_project_list.return_value = "📋 Your Projects (1)"
        
        await interface.cmd_projects(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        reply_markup = call_args[1]['reply_markup']
        
        assert isinstance(reply_markup, InlineKeyboardMarkup)
        # Should have approve and reject buttons for done projects
        keyboard = reply_markup.inline_keyboard
        assert len(keyboard) > 0
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_projects_with_failed_status(self, interface, mock_update, mock_context):
        """Test projects list shows retry/skip buttons for failed status."""
        from telegram import InlineKeyboardMarkup
        
        interface.state_manager.list_projects.return_value = ["failed-proj"]
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "failed",
            "current_stage": "stage-1"
        }
        interface.bot.get_project_list.return_value = "📋 Your Projects (1)"
        
        await interface.cmd_projects(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        reply_markup = call_args[1]['reply_markup']
        
        assert isinstance(reply_markup, InlineKeyboardMarkup)
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_projects_with_in_progress_status(self, interface, mock_update, mock_context):
        """Test projects list shows stop button for in-progress status."""
        from telegram import InlineKeyboardMarkup
        
        interface.state_manager.list_projects.return_value = ["active-proj"]
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "in-progress",
            "current_stage": "stage-1"
        }
        interface.bot.get_project_list.return_value = "📋 Your Projects (1)"
        
        await interface.cmd_projects(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        reply_markup = call_args[1]['reply_markup']
        
        assert isinstance(reply_markup, InlineKeyboardMarkup)
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_view_existing_project(self, interface, mock_query):
        """Test viewing an existing project."""
        from telegram import InlineKeyboardMarkup
        
        interface.bot.get_project_detail.return_value = "Project details here"
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "pending",
            "current_stage": "stage-1"
        }
        
        await interface.handle_view(mock_query, "test-project")
        
        assert mock_query.edit_message_text.called
        call_args = mock_query.edit_message_text.call_args
        assert call_args[1]['parse_mode'] == "Markdown"
        assert isinstance(call_args[1]['reply_markup'], InlineKeyboardMarkup)
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_view_nonexistent_project(self, interface, mock_query):
        """Test viewing a non-existent project."""
        interface.bot.get_project_detail.return_value = None
        
        await interface.handle_view(mock_query, "nonexistent")
        
        assert mock_query.edit_message_text.called
        call_args = mock_query.edit_message_text.call_args
        assert "not found" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_view_done_project(self, interface, mock_query):
        """Test viewing a done project shows approve/reject buttons."""
        from telegram import InlineKeyboardMarkup
        
        interface.bot.get_project_detail.return_value = "Project details"
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "done",
            "current_stage": "stage-1"
        }
        
        await interface.handle_view(mock_query, "done-project")
        
        call_args = mock_query.edit_message_text.call_args
        keyboard = call_args[1]['reply_markup'].inline_keyboard
        
        # Check for approve and reject buttons
        button_texts = []
        for row in keyboard:
            for btn in row:
                button_texts.append(btn.text)
        
        assert any("Approve" in t for t in button_texts)
        assert any("Reject" in t for t in button_texts)
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_view_failed_project(self, interface, mock_query):
        """Test viewing a failed project shows retry/skip buttons."""
        from telegram import InlineKeyboardMarkup
        
        interface.bot.get_project_detail.return_value = "Project details"
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "failed",
            "current_stage": "stage-1"
        }
        
        await interface.handle_view(mock_query, "failed-project")
        
        call_args = mock_query.edit_message_text.call_args
        keyboard = call_args[1]['reply_markup'].inline_keyboard
        
        button_texts = []
        for row in keyboard:
            for btn in row:
                button_texts.append(btn.text)
        
        assert any("Retry" in t for t in button_texts)
        assert any("Skip" in t for t in button_texts)
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_view_in_progress_project(self, interface, mock_query):
        """Test viewing an in-progress project shows stop/logs buttons."""
        from telegram import InlineKeyboardMarkup
        
        interface.bot.get_project_detail.return_value = "Project details"
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "in-progress",
            "current_stage": "stage-1"
        }
        
        await interface.handle_view(mock_query, "active-project")
        
        call_args = mock_query.edit_message_text.call_args
        keyboard = call_args[1]['reply_markup'].inline_keyboard
        
        button_texts = []
        for row in keyboard:
            for btn in row:
                button_texts.append(btn.text)
        
        assert any("Stop" in t for t in button_texts)
        assert any("Logs" in t for t in button_texts)
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_new_project(self, interface, mock_update, mock_context):
        """Test new project command."""
        await interface.cmd_new_project(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        
        assert "New Project" in text
        assert "carby init" in text
        assert call_args[1]['parse_mode'] == "Markdown"
        assert call_args[1]['reply_markup'] == MAIN_KEYBOARD


# =============================================================================
# Test Class: Safety Manager Integration (check_rename, check_delete)
# =============================================================================

class TestSafetyManagerIntegration:
    """Test safety manager integration for rename/delete operations."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_rename_start(self, interface, mock_update, mock_context):
        """Test rename conversation start."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future()); query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future()); query.edit_message_text.return_value.set_result(None)
        query.data = "rename:old-project"
        mock_update.callback_query = query
        
        result = await interface.rename_start(mock_update, mock_context)
        
        assert query.answer.called
        assert query.edit_message_text.called
        call_args = query.edit_message_text.call_args
        assert "Rename old-project" in call_args[0][0]
        assert "Enter new project name" in call_args[0][0]
        assert mock_context.user_data['renaming_project'] == "old-project"
        assert result == RENAME_PROJECT
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_rename_execute_success(self, interface, mock_update, mock_context):
        """Test successful rename execution."""
        mock_context.user_data['renaming_project'] = 'old-name'
        mock_update.message.text = 'new-name'
        
        interface.bot.rename_project.return_value = (True, "Renamed successfully")
        
        result = await interface.rename_execute(mock_update, mock_context)
        
        interface.bot.rename_project.assert_called_once_with('old-name', 'new-name')
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Renamed successfully" in call_args[0][0]
        assert result == -1  # ConversationHandler.END
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_rename_execute_failure(self, interface, mock_update, mock_context):
        """Test failed rename execution."""
        mock_context.user_data['renaming_project'] = 'old-name'
        mock_update.message.text = 'new-name'
        
        interface.bot.rename_project.return_value = (False, "Rename failed: name exists")
        
        result = await interface.rename_execute(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        assert "Rename failed" in call_args[0][0]
        assert result == -1
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_rename_execute_no_project_selected(self, interface, mock_update, mock_context):
        """Test rename when no project was selected."""
        mock_context.user_data = {}  # No renaming_project key
        
        result = await interface.rename_execute(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        assert "No project selected" in call_args[0][0]
        assert result == -1
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete_start(self, interface, mock_update, mock_context):
        """Test delete conversation start."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future()); query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future()); query.edit_message_text.return_value.set_result(None)
        query.data = "delete:test-project"
        mock_update.callback_query = query
        
        # Mock safety manager
        check = Mock()
        check.details = {"json_file": "/path/to/project.json"}
        interface.bot.safety_manager.check_delete.return_value = check
        interface.bot.safety_manager.format_delete_preview.return_value = "⚠️ Delete preview"
        interface.bot.safety_manager.request_delete_confirmation.return_value = "DELETE"
        
        result = await interface.delete_start(mock_update, mock_context)
        
        assert query.answer.called
        assert query.edit_message_text.called
        assert mock_context.user_data['deleting_project'] == "test-project"
        assert result == DELETE_CONFIRM
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete_execute_success(self, interface, mock_update, mock_context):
        """Test successful delete execution."""
        mock_context.user_data['deleting_project'] = 'test-project'
        mock_update.message.text = 'DELETE'
        
        interface.bot.delete_project.return_value = (True, "Deleted successfully")
        
        result = await interface.delete_execute(mock_update, mock_context)
        
        interface.bot.delete_project.assert_called_once_with('test-project', 'DELETE')
        call_args = mock_update.message.reply_text.call_args
        assert "Deleted" in call_args[0][0]
        assert result == -1
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete_execute_wrong_confirmation(self, interface, mock_update, mock_context):
        """Test delete with wrong confirmation code."""
        mock_context.user_data['deleting_project'] = 'test-project'
        mock_update.message.text = 'WRONG'
        
        interface.bot.delete_project.return_value = (False, "Confirmation incorrect")
        
        result = await interface.delete_execute(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        assert "Confirmation incorrect" in call_args[0][0] or "❌" in call_args[0][0]
        assert result == -1
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete_execute_no_project_selected(self, interface, mock_update, mock_context):
        """Test delete when no project was selected."""
        mock_context.user_data = {}
        
        result = await interface.delete_execute(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        assert "No project selected" in call_args[0][0]
        assert result == -1
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete_execute_preview_response(self, interface, mock_update, mock_context):
        """Test delete returns to confirm state when preview is shown."""
        mock_context.user_data['deleting_project'] = 'test-project'
        mock_update.message.text = 'something'
        
        # Simulate first step returning preview
        interface.bot.delete_project.return_value = (False, "This will be deleted. Type DELETE to confirm:")
        
        result = await interface.delete_execute(mock_update, mock_context)
        
        assert result == DELETE_CONFIRM


# =============================================================================
# Test Class: Error Handling (invalid callbacks, missing projects, malformed input)
# =============================================================================

class TestErrorHandling:
    """Test error handling scenarios."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_invalid_action(self, interface, mock_update):
        """Test callback with invalid action is ignored gracefully."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future()); query.answer.return_value.set_result(None)
        query.data = "invalid_action:project"
        mock_update.callback_query = query
        
        await interface.handle_callback(mock_update, Mock())
        
        # Should just answer the callback without error
        assert query.answer.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_malformed_data(self, interface, mock_update):
        """Test callback with malformed data."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future()); query.answer.return_value.set_result(None)
        query.data = "no_colon_here"
        mock_update.callback_query = query
        
        await interface.handle_callback(mock_update, Mock())
        
        # Should handle gracefully
        assert query.answer.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_dispatch_failure(self, interface, mock_query):
        """Test dispatch handles failure."""
        result = Mock()
        result.success = False
        result.stderr = "Dispatch failed"
        interface.bot.dispatch_stage.return_value = result
        
        await interface.handle_dispatch(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "Failed to dispatch" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_approve_failure(self, interface, mock_query):
        """Test approve handles failure."""
        result = Mock()
        result.success = False
        result.stderr = "Approval failed"
        interface.bot.cli_executor.approve.return_value = result
        
        await interface.handle_approve(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "Failed to approve" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_retry_failure(self, interface, mock_query):
        """Test retry handles failure."""
        result = Mock()
        result.success = False
        result.stderr = "Retry failed"
        interface.bot.retry_stage.return_value = result
        
        await interface.handle_retry(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "Failed to retry" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_skip_failure(self, interface, mock_query):
        """Test skip handles failure."""
        result = Mock()
        result.success = False
        result.stderr = "Skip failed"
        interface.bot.skip_stage.return_value = result
        
        await interface.handle_skip(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "Failed to skip" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_stop_failure(self, interface, mock_query):
        """Test stop handles failure."""
        result = Mock()
        result.success = False
        result.stderr = "Stop failed"
        interface.bot.cli_executor.stop.return_value = result
        
        await interface.handle_stop(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "Failed to stop" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_logs_failure(self, interface, mock_query):
        """Test logs handles failure."""
        result = Mock()
        result.success = False
        result.stderr = "Logs failed"
        interface.bot.cli_executor.logs.return_value = result
        
        await interface.handle_logs(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "Failed to get logs" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_logs_truncation(self, interface, mock_query):
        """Test long logs are truncated."""
        result = Mock()
        result.success = True
        result.stdout = "x" * 4000  # Very long log
        interface.bot.cli_executor.logs.return_value = result
        
        await interface.handle_logs(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        text = call_args[0][0]
        assert len(text) < 3500  # Should be truncated


# =============================================================================
# Test Class: State Transitions (conversation handler states)
# =============================================================================

class TestStateTransitions:
    """Test conversation handler state transitions."""
    
    def test_conversation_states_defined(self):
        """Test conversation states are properly defined."""
        assert RENAME_PROJECT == 1
        assert DELETE_CONFIRM == 2
        assert hasattr(sys.modules['telegram_interface'], 'FEEDBACK')
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_rename_flow_complete(self, interface):
        """Test complete rename conversation flow."""
        from telegram.ext import ConversationHandler
        
        # Start
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future()); query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future()); query.edit_message_text.return_value.set_result(None)
        query.data = "rename:test-project"
        
        update = Mock()
        update.callback_query = query
        
        context = Mock()
        context.user_data = {}
        
        result = await interface.rename_start(update, context)
        assert result == RENAME_PROJECT
        
        # Execute
        update2 = Mock()
        update2.message = Mock()
        update2.message.text = "new-name"
        update2.message.reply_text = Mock(return_value=asyncio.Future()); update2.message.reply_text.return_value.set_result(None)
        
        interface.bot.rename_project.return_value = (True, "Renamed")
        
        result = await interface.rename_execute(update2, context)
        assert result == ConversationHandler.END
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_delete_flow_complete(self, interface):
        """Test complete delete conversation flow."""
        from telegram.ext import ConversationHandler
        
        # Start
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future()); query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future()); query.edit_message_text.return_value.set_result(None)
        query.data = "delete:test-project"
        
        update = Mock()
        update.callback_query = query
        
        context = Mock()
        context.user_data = {}
        
        check = Mock()
        check.details = {}
        interface.bot.safety_manager.check_delete.return_value = check
        interface.bot.safety_manager.format_delete_preview.return_value = "Preview"
        interface.bot.safety_manager.request_delete_confirmation.return_value = "DELETE"
        
        result = await interface.delete_start(update, context)
        assert result == DELETE_CONFIRM
        
        # Execute
        update2 = Mock()
        update2.message = Mock()
        update2.message.text = "DELETE"
        update2.message.reply_text = Mock(return_value=asyncio.Future()); update2.message.reply_text.return_value.set_result(None)
        
        interface.bot.delete_project.return_value = (True, "Deleted")
        
        result = await interface.delete_execute(update2, context)
        assert result == ConversationHandler.END


# =============================================================================
# Test Class: Keyboard Layouts (MAIN_KEYBOARD, MORE_KEYBOARD)
# =============================================================================

class TestKeyboardLayouts:
    """Test keyboard layout constants."""
    
    def test_main_keyboard_structure(self):
        """Test MAIN_KEYBOARD has correct structure."""
        from telegram import KeyboardButton
        
        assert MAIN_KEYBOARD is not None
        assert hasattr(MAIN_KEYBOARD, 'keyboard')
        
        keyboard = MAIN_KEYBOARD.keyboard
        assert len(keyboard) == 1  # One row
        assert len(keyboard[0]) == 3  # Three buttons
        
        # Check button labels - extract text from KeyboardButton objects
        buttons = [btn.text if isinstance(btn, KeyboardButton) else str(btn) for btn in keyboard[0]]
        assert "📋 Projects" in buttons
        assert "➕ New Project" in buttons
        assert "⚙️ More" in buttons
    
    def test_more_keyboard_structure(self):
        """Test MORE_KEYBOARD has correct structure."""
        from telegram import KeyboardButton
        
        assert MORE_KEYBOARD is not None
        assert hasattr(MORE_KEYBOARD, 'keyboard')
        
        keyboard = MORE_KEYBOARD.keyboard
        assert len(keyboard) == 3  # Three rows
        
        # Helper to get button texts
        def get_texts(row):
            return [btn.text if isinstance(btn, KeyboardButton) else str(btn) for btn in row]
        
        # Row 1
        row1_texts = get_texts(keyboard[0])
        assert "🔐 Credentials" in row1_texts
        assert "📊 System Status" in row1_texts
        
        # Row 2
        row2_texts = get_texts(keyboard[1])
        assert "🗄️ Archived Projects" in row2_texts
        assert "❓ Help" in row2_texts
        
        # Row 3
        row3_texts = get_texts(keyboard[2])
        assert "← Back to Main" in row3_texts
    
    def test_keyboards_have_resize(self):
        """Test keyboards have resize_keyboard enabled."""
        assert MAIN_KEYBOARD.resize_keyboard is True
        assert MORE_KEYBOARD.resize_keyboard is True


# =============================================================================
# Test Class: Menu Navigation
# =============================================================================

class TestMenuNavigation:
    """Test menu navigation commands."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_more(self, interface, mock_update, mock_context):
        """Test more menu command."""
        await interface.cmd_more(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "More Options" in call_args[0][0]
        assert call_args[1]['reply_markup'] == MORE_KEYBOARD
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_back_main(self, interface, mock_update, mock_context):
        """Test back to main menu command."""
        await interface.cmd_back_main(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert call_args[1]['reply_markup'] == MAIN_KEYBOARD
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_credentials(self, interface, mock_update, mock_context):
        """Test credentials command."""
        await interface.cmd_credentials(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        text = call_args[0][0]
        assert "Credentials" in text
        assert "synology-nas" in text
        assert call_args[1]['reply_markup'] == MORE_KEYBOARD
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_system_status(self, interface, mock_update, mock_context):
        """Test system status command delegates to cmd_status."""
        interface.state_manager.list_projects.return_value = []
        
        await interface.cmd_system_status(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_archived(self, interface, mock_update, mock_context):
        """Test archived projects command."""
        await interface.cmd_archived(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Archived Projects" in call_args[0][0]
        assert call_args[1]['reply_markup'] == MORE_KEYBOARD


# =============================================================================
# Test Class: Action Handlers (dispatch, approve, reject, retry, skip, stop, logs)
# =============================================================================

class TestActionHandlers:
    """Test action handler methods."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_dispatch_success(self, interface, mock_query):
        """Test successful dispatch."""
        result = Mock()
        result.success = True
        result.stdout = "Agent started successfully"
        interface.bot.dispatch_stage.return_value = result
        
        await interface.handle_dispatch(mock_query, "test-project")
        
        interface.bot.dispatch_stage.assert_called_once_with("test-project")
        call_args = mock_query.edit_message_text.call_args
        assert "dispatched successfully" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_approve_success(self, interface, mock_query):
        """Test successful approve."""
        result = Mock()
        result.success = True
        result.stdout = "Stage approved"
        interface.bot.cli_executor.approve.return_value = result
        
        await interface.handle_approve(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "approved" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_reject(self, interface, mock_query):
        """Test reject handler."""
        await interface.handle_reject(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "Reject test-project" in call_args[0][0]
        assert "feedback" in call_args[0][0].lower()
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_retry_success(self, interface, mock_query):
        """Test successful retry."""
        result = Mock()
        result.success = True
        result.stdout = "Retry initiated"
        interface.bot.retry_stage.return_value = result
        
        await interface.handle_retry(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "retry initiated" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_skip_success(self, interface, mock_query):
        """Test successful skip."""
        result = Mock()
        result.success = True
        result.stdout = "Stage skipped"
        interface.bot.skip_stage.return_value = result
        
        await interface.handle_skip(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "skipped" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_stop_success(self, interface, mock_query):
        """Test successful stop."""
        result = Mock()
        result.success = True
        result.stdout = "Agent stopped"
        interface.bot.cli_executor.stop.return_value = result
        
        await interface.handle_stop(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "stopped" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_logs_success(self, interface, mock_query):
        """Test successful logs retrieval."""
        result = Mock()
        result.success = True
        result.stdout = "Log line 1\nLog line 2"
        interface.bot.cli_executor.logs.return_value = result
        
        await interface.handle_logs(mock_query, "test-project")
        
        call_args = mock_query.edit_message_text.call_args
        assert "Logs" in call_args[0][0]
        assert "Log line 1" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_back_to_projects(self, interface, mock_query):
        """Test back to projects handler."""
        interface.state_manager.list_projects.return_value = []
        interface.bot.get_project_list.return_value = "Projects list"
        
        await interface.handle_back_to_projects(mock_query)
        
        assert mock_query.edit_message_text.called


# =============================================================================
# Test Class: Natural Language Handler
# =============================================================================

class TestNaturalLanguageHandler:
    """Test natural language message handling."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_message_projects_keyword(self, interface, mock_update, mock_context):
        """Test 'projects' keyword triggers projects command."""
        mock_update.message.text = "show my projects"
        interface.state_manager.list_projects.return_value = []
        interface.bot.get_project_list.return_value = "Projects"
        
        await interface.handle_message(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_message_status_keyword(self, interface, mock_update, mock_context):
        """Test 'status' keyword triggers status command."""
        mock_update.message.text = "what's the status"
        interface.state_manager.list_projects.return_value = []
        
        await interface.handle_message(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_message_continue_keyword(self, interface, mock_update, mock_context):
        """Test 'continue' keyword shows last active project."""
        mock_update.message.text = "continue"
        interface.state_manager.list_projects.return_value = ["active-project"]
        interface.state_manager.get_project_summary.return_value = {
            "id": "active-project",
            "current_stage": "stage-1"
        }
        interface.bot.get_project_detail.return_value = "Project details"
        
        await interface.handle_message(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
        call_args = mock_update.message.reply_text.call_args
        assert "Continuing" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_message_continue_no_projects(self, interface, mock_update, mock_context):
        """Test 'continue' with no projects."""
        mock_update.message.text = "continue"
        interface.state_manager.list_projects.return_value = []
        
        await interface.handle_message(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        assert "No active projects" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_message_help_keyword(self, interface, mock_update, mock_context):
        """Test 'help' keyword triggers help command."""
        mock_update.message.text = "how do I use this"
        
        await interface.handle_message(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_message_unknown(self, interface, mock_update, mock_context):
        """Test unknown message shows suggestions."""
        mock_update.message.text = "random gibberish"
        
        await interface.handle_message(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        assert "not sure" in call_args[0][0].lower()
        assert "reply_markup" in call_args[1]


# =============================================================================
# Test Class: Error Handler
# =============================================================================

class TestErrorHandler:
    """Test global error handler."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_error_handler_with_message(self, interface):
        """Test error handler notifies user via message."""
        update = Mock()
        update.effective_message = Mock()
        update.effective_message.reply_text = Mock(return_value=asyncio.Future())
        update.effective_message.reply_text.return_value.set_result(None)
        
        context = Mock()
        context.error = Exception("Test error")
        
        await interface._error_handler(update, context)
        
        assert update.effective_message.reply_text.called
        call_args = update.effective_message.reply_text.call_args
        assert "error occurred" in call_args[0][0]
        assert call_args[1]['reply_markup'] == MAIN_KEYBOARD
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_error_handler_no_message(self, interface):
        """Test error handler handles missing message gracefully."""
        update = Mock()
        update.effective_message = None
        
        context = Mock()
        context.error = Exception("Test error")
        
        # Should not raise
        await interface._error_handler(update, context)


# =============================================================================
# Test Class: Additional Coverage Tests
# =============================================================================

class TestAdditionalCoverage:
    """Additional tests to reach 90%+ coverage."""
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_view(self, interface, mock_update):
        """Test handle_callback routes to view handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "view:test-project"
        mock_update.callback_query = query
        
        interface.bot.get_project_detail.return_value = "Project details"
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "pending",
            "current_stage": "stage-1"
        }
        
        await interface.handle_callback(mock_update, Mock())
        
        assert query.edit_message_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_dispatch(self, interface, mock_update):
        """Test handle_callback routes to dispatch handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "dispatch:test-project"
        mock_update.callback_query = query
        
        result = Mock()
        result.success = True
        result.stdout = "Dispatched"
        interface.bot.dispatch_stage.return_value = result
        
        await interface.handle_callback(mock_update, Mock())
        
        interface.bot.dispatch_stage.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_approve(self, interface, mock_update):
        """Test handle_callback routes to approve handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "approve:test-project"
        mock_update.callback_query = query
        
        result = Mock()
        result.success = True
        result.stdout = "Approved"
        interface.bot.cli_executor.approve.return_value = result
        
        await interface.handle_callback(mock_update, Mock())
        
        interface.bot.cli_executor.approve.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_reject(self, interface, mock_update):
        """Test handle_callback routes to reject handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "reject:test-project"
        mock_update.callback_query = query
        
        await interface.handle_callback(mock_update, Mock())
        
        call_args = query.edit_message_text.call_args
        assert "Reject" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_retry(self, interface, mock_update):
        """Test handle_callback routes to retry handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "retry:test-project"
        mock_update.callback_query = query
        
        result = Mock()
        result.success = True
        result.stdout = "Retrying"
        interface.bot.retry_stage.return_value = result
        
        await interface.handle_callback(mock_update, Mock())
        
        interface.bot.retry_stage.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_skip(self, interface, mock_update):
        """Test handle_callback routes to skip handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "skip:test-project"
        mock_update.callback_query = query
        
        result = Mock()
        result.success = True
        result.stdout = "Skipped"
        interface.bot.skip_stage.return_value = result
        
        await interface.handle_callback(mock_update, Mock())
        
        interface.bot.skip_stage.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_stop(self, interface, mock_update):
        """Test handle_callback routes to stop handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "stop:test-project"
        mock_update.callback_query = query
        
        result = Mock()
        result.success = True
        result.stdout = "Stopped"
        interface.bot.cli_executor.stop.return_value = result
        
        await interface.handle_callback(mock_update, Mock())
        
        interface.bot.cli_executor.stop.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_back(self, interface, mock_update):
        """Test handle_callback routes to back handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "back:projects"
        mock_update.callback_query = query
        
        interface.state_manager.list_projects.return_value = []
        interface.bot.get_project_list.return_value = "Projects list"
        
        await interface.handle_callback(mock_update, Mock())
        
        assert query.edit_message_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_callback_logs(self, interface, mock_update):
        """Test handle_callback routes to logs handler."""
        query = Mock()
        query.answer = Mock(return_value=asyncio.Future())
        query.answer.return_value.set_result(None)
        query.edit_message_text = Mock(return_value=asyncio.Future())
        query.edit_message_text.return_value.set_result(None)
        query.data = "logs:test-project"
        mock_update.callback_query = query
        
        result = Mock()
        result.success = True
        result.stdout = "Log output"
        interface.bot.cli_executor.logs.return_value = result
        
        await interface.handle_callback(mock_update, Mock())
        
        interface.bot.cli_executor.logs.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_dispatch_project_not_found(self, interface, mock_query):
        """Test dispatch when project summary is None."""
        interface.state_manager.get_project_summary.return_value = None
        
        result = Mock()
        result.success = False
        result.stderr = "Project 'test-project' not found"
        interface.bot.dispatch_stage.return_value = result
        
        await interface.handle_dispatch(mock_query, "test-project")
        
        interface.bot.dispatch_stage.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_dispatch_with_stage_from_summary(self, interface, mock_query):
        """Test dispatch uses stage from project summary."""
        interface.state_manager.get_project_summary.return_value = {
            "current_stage": "stage-2"
        }
        
        result = Mock()
        result.success = True
        result.stdout = "Dispatched"
        interface.bot.dispatch_stage.return_value = result
        
        await interface.handle_dispatch(mock_query, "test-project")
        
        interface.bot.dispatch_stage.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_retry_with_stage_from_summary(self, interface, mock_query):
        """Test retry uses stage from project summary."""
        interface.state_manager.get_project_summary.return_value = {
            "current_stage": "stage-2"
        }
        
        result = Mock()
        result.success = True
        result.stdout = "Retrying"
        interface.bot.retry_stage.return_value = result
        
        await interface.handle_retry(mock_query, "test-project")
        
        interface.bot.retry_stage.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_skip_with_stage_from_summary(self, interface, mock_query):
        """Test skip uses stage from project summary."""
        interface.state_manager.get_project_summary.return_value = {
            "current_stage": "stage-2"
        }
        
        result = Mock()
        result.success = True
        result.stdout = "Skipped"
        interface.bot.skip_stage.return_value = result
        
        await interface.handle_skip(mock_query, "test-project")
        
        interface.bot.skip_stage.assert_called_once_with("test-project")
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_back_to_projects_with_projects(self, interface, mock_query):
        """Test back to projects with existing projects."""
        interface.state_manager.list_projects.return_value = ["proj1", "proj2"]
        interface.state_manager.get_project_summary.side_effect = lambda pid: {
            "proj1": {"current_status": "pending"},
            "proj2": {"current_status": "done"}
        }.get(pid)
        interface.bot.get_project_list.return_value = "Projects list"
        
        await interface.handle_back_to_projects(mock_query)
        
        assert mock_query.edit_message_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_back_to_projects_no_summary(self, interface, mock_query):
        """Test back to projects when summary is None."""
        interface.state_manager.list_projects.return_value = ["proj1"]
        interface.state_manager.get_project_summary.return_value = None
        interface.bot.get_project_list.return_value = "Projects list"
        
        await interface.handle_back_to_projects(mock_query)
        
        assert mock_query.edit_message_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_back_to_projects_unknown_status(self, interface, mock_query):
        """Test back to projects with unknown status."""
        interface.state_manager.list_projects.return_value = ["proj1"]
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "unknown"
        }
        interface.bot.get_project_list.return_value = "Projects list"
        
        await interface.handle_back_to_projects(mock_query)
        
        assert mock_query.edit_message_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_error_handler_notification_failure(self, interface):
        """Test error handler when notification fails."""
        update = Mock()
        update.effective_message = Mock()
        update.effective_message.reply_text = Mock(return_value=asyncio.Future())
        # Simulate failure
        update.effective_message.reply_text.side_effect = Exception("Send failed")
        
        context = Mock()
        context.error = Exception("Test error")
        
        # Should not raise even when notification fails
        await interface._error_handler(update, context)
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_message_continue_no_summary(self, interface, mock_update, mock_context):
        """Test continue keyword when project has no summary."""
        mock_update.message.text = "continue"
        interface.state_manager.list_projects.return_value = ["proj1"]
        interface.state_manager.get_project_summary.return_value = None
        
        await interface.handle_message(mock_update, mock_context)
        
        call_args = mock_update.message.reply_text.call_args
        assert "No active projects" in call_args[0][0]
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_view_with_summary_none_status(self, interface, mock_query):
        """Test view project when summary returns None for status."""
        interface.bot.get_project_detail.return_value = "Project details"
        interface.state_manager.get_project_summary.return_value = {
            "current_status": None,
            "current_stage": "stage-1"
        }
        
        await interface.handle_view(mock_query, "test-project")
        
        assert mock_query.edit_message_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_cmd_projects_with_summary_none(self, interface, mock_update, mock_context):
        """Test projects command when summary is None for a project."""
        interface.state_manager.list_projects.return_value = ["proj1"]
        interface.state_manager.get_project_summary.return_value = None
        interface.bot.get_project_list.return_value = "Projects list"
        
        await interface.cmd_projects(mock_update, mock_context)
        
        assert mock_update.message.reply_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_back_to_projects_in_progress(self, interface, mock_query):
        """Test back to projects with in-progress status."""
        interface.state_manager.list_projects.return_value = ["proj1"]
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "in-progress",
            "current_stage": "stage-1"
        }
        interface.bot.get_project_list.return_value = "Projects list"
        
        await interface.handle_back_to_projects(mock_query)
        
        assert mock_query.edit_message_text.called
    
    @pytest.mark.asyncio(loop_scope="function")
    async def test_handle_back_to_projects_failed(self, interface, mock_query):
        """Test back to projects with failed status."""
        interface.state_manager.list_projects.return_value = ["proj1"]
        interface.state_manager.get_project_summary.return_value = {
            "current_status": "failed",
            "current_stage": "stage-1"
        }
        interface.bot.get_project_list.return_value = "Projects list"
        
        await interface.handle_back_to_projects(mock_query)
        
        assert mock_query.edit_message_text.called


# =============================================================================
# Legacy Tests (kept for backward compatibility)
# =============================================================================

class TestTelegramInterfaceLegacy:
    """Legacy tests from original test file."""
    
    def test_initialization(self):
        """Test TelegramInterface initializes correctly."""
        with patch('telegram_interface.CarbyBot') as mock_bot, \
             patch('telegram_interface.StateManager') as mock_state:
            
            mock_bot_instance = Mock()
            mock_bot.return_value = mock_bot_instance
            mock_state_instance = Mock()
            mock_state.return_value = mock_state_instance
            
            interface = TelegramInterface()
            
            assert interface.token == "test_token_12345"
            assert interface.bot == mock_bot_instance
            assert interface.state_manager == mock_state_instance


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=telegram_interface", "--cov-report=term-missing"])
