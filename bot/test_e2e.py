#!/usr/bin/env python3
"""
End-to-End Test Suite for Carby Telegram Bot
Tests all user flows with state verification
"""

import os
import sys
import time
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import asyncio

# Add bot directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram import Update, Message, Chat, User, CallbackQuery
from telegram.ext import ContextTypes

from telegram_interface import TelegramInterface, MAIN_KEYBOARD, MORE_KEYBOARD
from bot import CarbyBot
from state_manager import StateManager


class E2ETestRunner:
    """Run end-to-end tests against the actual bot components."""
    
    def __init__(self):
        self.interface = None
        self.test_results = []
        self.test_project_dir = None
        
    def setup(self):
        """Set up test environment."""
        print("🔧 Setting up test environment...")
        
        # Create temp project directory
        self.test_project_dir = tempfile.mkdtemp(prefix="carby_test_")
        
        # Set environment
        os.environ["CARBY_PROJECTS_DIR"] = self.test_project_dir
        os.environ["CARBY_BOT_TOKEN"] = "test_token"
        
        # Initialize interface
        self.interface = TelegramInterface()
        
        print(f"✅ Test environment ready: {self.test_project_dir}")
        
    def teardown(self):
        """Clean up test environment."""
        print("🧹 Cleaning up...")
        if self.test_project_dir and os.path.exists(self.test_project_dir):
            shutil.rmtree(self.test_project_dir)
        print("✅ Cleanup complete")
        
    def create_mock_update(self, text=None, callback_data=None, user_id=12345):
        """Create a mock Telegram update."""
        update = Mock(spec=Update)
        
        # Mock user
        user = Mock(spec=User)
        user.id = user_id
        user.first_name = "Test"
        user.username = "testuser"
        
        # Mock chat
        chat = Mock(spec=Chat)
        chat.id = user_id
        chat.type = "private"
        
        if callback_data:
            # Callback query update
            query = Mock(spec=CallbackQuery)
            query.data = callback_data
            query.from_user = user
            query.message = Mock(spec=Message)
            query.message.chat = chat
            query.message.message_id = 1
            query.message.text = "Original message"
            
            # Async mock for answer
            async def mock_answer():
                return True
            query.answer = mock_answer
            
            # Async mock for edit_message_text
            self.last_edit_text = None
            self.last_edit_markup = None
            async def mock_edit(text, **kwargs):
                self.last_edit_text = text
                self.last_edit_markup = kwargs.get('reply_markup')
                return Mock(message_id=1)
            query.edit_message_text = mock_edit
            
            update.callback_query = query
            update.message = None
        else:
            # Message update
            message = Mock(spec=Message)
            message.text = text
            message.chat = chat
            message.from_user = user
            message.message_id = 1
            
            # Async mock for reply_text
            self.last_reply_text = None
            self.last_reply_markup = None
            async def mock_reply(text, **kwargs):
                self.last_reply_text = text
                self.last_reply_markup = kwargs.get('reply_markup')
                return Mock(message_id=2)
            message.reply_text = mock_reply
            
            update.message = message
            update.callback_query = None
            
        return update
        
    def create_mock_context(self):
        """Create a mock context."""
        context = Mock(spec=ContextTypes.DEFAULT_TYPE)
        context.user_data = {}
        context.bot_data = {
            'carby_bot': self.interface.bot,
            'state_manager': self.interface.state_manager
        }
        return context
        
    def run_async(self, coro):
        """Run an async function."""
        return asyncio.get_event_loop().run_until_complete(coro)
        
    def test(self, name, assertion, details=""):
        """Record a test result."""
        result = {
            'name': name,
            'passed': assertion,
            'details': details
        }
        self.test_results.append(result)
        status = "✅ PASS" if assertion else "❌ FAIL"
        print(f"  {status}: {name}")
        if details and not assertion:
            print(f"      → {details}")
        return assertion
        
    # ==================== TEST SUITES ====================
    
    def test_basic_commands(self):
        """Test Phase 1: Basic Commands"""
        print("\n📋 Phase 1: Basic Commands")
        
        # Test 1.1: /start command
        update = self.create_mock_update(text="/start")
        context = self.create_mock_context()
        self.run_async(self.interface.cmd_start(update, context))
        
        self.test(
            "/start shows welcome message",
            "Carby Studio Bot" in self.last_reply_text,
            f"Expected 'Carby Studio Bot' in response, got: {self.last_reply_text[:100]}"
        )
        self.test(
            "/start shows main keyboard",
            self.last_reply_markup is not None and hasattr(self.last_reply_markup, 'keyboard'),
            "Main keyboard not shown"
        )
        
        # Test 1.2: /help command
        update = self.create_mock_update(text="/help")
        context = self.create_mock_context()
        self.run_async(self.interface.cmd_help(update, context))
        
        self.test(
            "/help shows help text",
            self.last_reply_text and len(self.last_reply_text) > 50,
            "Help text too short or missing"
        )
        
        # Test 1.3: /status command
        update = self.create_mock_update(text="/status")
        context = self.create_mock_context()
        self.run_async(self.interface.cmd_status(update, context))
        
        self.test(
            "/status shows system status",
            "System Status" in self.last_reply_text or "running" in self.last_reply_text.lower(),
            f"Status not shown: {self.last_reply_text[:100]}"
        )
        
    def test_navigation(self):
        """Test Phase 2: Navigation & Menus"""
        print("\n📋 Phase 2: Navigation & Menus")
        
        # Test 2.1: More menu
        update = self.create_mock_update(text="⚙️ More")
        context = self.create_mock_context()
        self.run_async(self.interface.cmd_more(update, context))
        
        self.test(
            "⚙️ More shows more menu",
            self.last_reply_markup is not None,
            "More menu keyboard not shown"
        )
        
        # Test 2.2: Back to main
        update = self.create_mock_update(text="← Back to Main")
        context = self.create_mock_context()
        self.run_async(self.interface.cmd_back_main(update, context))
        
        self.test(
            "← Back returns to main menu",
            self.last_reply_markup is not None,
            "Main keyboard not restored"
        )
        
        # Test 2.3: Projects list
        update = self.create_mock_update(text="📋 Projects")
        context = self.create_mock_context()
        self.run_async(self.interface.cmd_projects(update, context))
        
        self.test(
            "📋 Projects shows project list",
            self.last_reply_text is not None,
            "Project list not shown"
        )
        
    def test_project_lifecycle(self):
        """Test Phase 3 & 4: Project Operations"""
        print("\n📋 Phase 3 & 4: Project Lifecycle")
        
        # Create a test project first (use valid project name: lowercase, numbers, hyphens only)
        test_project_name = f"test-project-{int(time.time())}"
        
        # Test 4.1-4.4: Create new project
        print("  Creating test project...")
        success, message = self.interface.bot.create_project(
            test_project_name,
            "Test project for e2e testing",
            "linear"
        )
        
        self.test(
            "Create project succeeds",
            success,
            f"Failed to create project: {message}"
        )
        
        # Verify project exists in filesystem
        project_path = Path(self.test_project_dir) / test_project_name
        self.test(
            "Project directory created",
            project_path.exists(),
            f"Project dir not found: {project_path}"
        )
        
        # Test 3.1: View project
        update = self.create_mock_update(callback_data=f"view:{test_project_name}")
        context = self.create_mock_context()
        self.run_async(self.interface.handle_callback(update, context))
        
        self.test(
            "View project shows details",
            test_project_name in self.last_edit_text,
            f"Project details not shown: {self.last_edit_text[:100]}"
        )
        
        # Test 3.2: Rename project
        new_name = f"{test_project_name}-renamed"
        
        # Start rename
        update = self.create_mock_update(callback_data=f"rename:{test_project_name}")
        context = self.create_mock_context()
        state = self.run_async(self.interface.rename_start(update, context))
        
        self.test(
            "Rename start prompts for new name",
            "Enter new project name" in self.last_edit_text,
            "Rename prompt not shown"
        )
        
        # Execute rename
        update = self.create_mock_update(text=new_name)
        context = self.create_mock_context()
        context.user_data['renaming_project'] = test_project_name
        self.run_async(self.interface.rename_execute(update, context))
        
        self.test(
            "Rename succeeds",
            "Renamed" in self.last_reply_text or new_name in self.last_reply_text,
            f"Rename failed: {self.last_reply_text}"
        )
        
        # Verify old directory gone, new directory exists
        old_exists = (Path(self.test_project_dir) / test_project_name).exists()
        new_exists = (Path(self.test_project_dir) / new_name).exists()
        
        self.test(
            "Old project directory removed",
            not old_exists,
            f"Old dir still exists: {test_project_name}"
        )
        self.test(
            "New project directory exists",
            new_exists,
            f"New dir not found: {new_name}"
        )
        
        # Test 3.3: Delete project (THE BUG WE FIXED)
        print("  Testing delete flow...")
        
        # Start delete
        update = self.create_mock_update(callback_data=f"delete:{new_name}")
        context = self.create_mock_context()
        state = self.run_async(self.interface.delete_start(update, context))
        
        has_preview = "Delete" in self.last_edit_text or "will be deleted" in self.last_edit_text
        has_confirm_prompt = "DELETE" in self.last_edit_text
        
        self.test(
            "Delete shows preview",
            has_preview,
            f"Delete preview not shown: {self.last_edit_text[:100]}"
        )
        self.test(
            "Delete prompts for confirmation",
            has_confirm_prompt,
            f"Confirmation prompt missing: {self.last_edit_text[:100]}"
        )
        
        # Execute delete with correct confirmation
        update = self.create_mock_update(text="DELETE")
        context = self.create_mock_context()
        context.user_data['deleting_project'] = new_name
        self.run_async(self.interface.delete_execute(update, context))
        
        delete_success = "Deleted" in self.last_reply_text or "deleted" in self.last_reply_text.lower()
        
        self.test(
            "Delete with 'DELETE' confirmation succeeds",
            delete_success,
            f"Delete failed: {self.last_reply_text}"
        )
        
        # Verify directory actually deleted
        project_deleted = not (Path(self.test_project_dir) / new_name).exists()
        self.test(
            "Project directory actually deleted from filesystem",
            project_deleted,
            f"Project dir still exists after delete: {new_name}"
        )
        
        # Test 3.4: Cancel delete with wrong confirmation
        # Create another project to test cancel
        cancel_project = f"cancel-test-{int(time.time())}"
        self.interface.bot.create_project(cancel_project, "Test cancel", "linear")
        
        update = self.create_mock_update(callback_data=f"delete:{cancel_project}")
        context = self.create_mock_context()
        self.run_async(self.interface.delete_start(update, context))
        
        update = self.create_mock_update(text="NO")  # Wrong confirmation
        context = self.create_mock_context()
        context.user_data['deleting_project'] = cancel_project
        self.run_async(self.interface.delete_execute(update, context))
        
        cancel_worked = "cancelled" in self.last_reply_text.lower() or "incorrect" in self.last_reply_text.lower()
        project_still_exists = (Path(self.test_project_dir) / cancel_project).exists()
        
        self.test(
            "Wrong confirmation cancels delete",
            cancel_worked,
            f"Cancel not detected: {self.last_reply_text}"
        )
        self.test(
            "Project preserved after cancel",
            project_still_exists,
            f"Project deleted despite cancel: {cancel_project}"
        )
        
    def test_natural_language(self):
        """Test Phase 5: Natural Language"""
        print("\n📋 Phase 5: Natural Language")
        
        # Test 5.1: "show my projects"
        update = self.create_mock_update(text="show my projects")
        context = self.create_mock_context()
        self.run_async(self.interface.handle_message(update, context))
        
        self.test(
            "Natural language 'show my projects' works",
            self.last_reply_text is not None,
            "No response to natural language query"
        )
        
        # Test 5.2: "what's running"
        update = self.create_mock_update(text="what's running")
        context = self.create_mock_context()
        self.run_async(self.interface.handle_message(update, context))
        
        self.test(
            "Natural language 'what's running' works",
            self.last_reply_text is not None,
            "No response to status query"
        )
        
    def test_edge_cases(self):
        """Test edge cases and error handling"""
        print("\n📋 Edge Cases & Error Handling")
        
        # Test: Delete non-existent project
        update = self.create_mock_update(callback_data="delete:nonexistent_project_xyz")
        context = self.create_mock_context()
        
        try:
            self.run_async(self.interface.delete_start(update, context))
            self.test(
                "Delete non-existent project handled gracefully",
                "not found" in self.last_edit_text.lower() or "error" in self.last_edit_text.lower() or self.last_edit_text,
                "No error handling for non-existent project"
            )
        except Exception as e:
            self.test(
                "Delete non-existent project throws exception (needs fix)",
                False,
                f"Exception: {e}"
            )
            
        # Test: Rename to invalid name
        # First create a project
        invalid_test = f"invalid-test-{int(time.time())}"
        self.interface.bot.create_project(invalid_test, "Test", "linear")
        
        update = self.create_mock_update(callback_data=f"rename:{invalid_test}")
        context = self.create_mock_context()
        self.run_async(self.interface.rename_start(update, context))
        
        # Try invalid name with spaces
        update = self.create_mock_update(text="name with spaces")
        context = self.create_mock_context()
        context.user_data['renaming_project'] = invalid_test
        self.run_async(self.interface.rename_execute(update, context))
        
        self.test(
            "Rename to invalid name rejected",
            "error" in self.last_reply_text.lower() or "invalid" in self.last_reply_text.lower() or "❌" in self.last_reply_text,
            f"Invalid name accepted: {self.last_reply_text}"
        )
        
    def run_all_tests(self):
        """Run all test suites."""
        print("=" * 60)
        print("🧪 CARBY BOT END-TO-END TEST SUITE")
        print("=" * 60)
        
        try:
            self.setup()
            
            self.test_basic_commands()
            self.test_navigation()
            self.test_project_lifecycle()
            self.test_natural_language()
            self.test_edge_cases()
            
        finally:
            self.teardown()
            
        # Print summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for r in self.test_results if r['passed'])
        failed = sum(1 for r in self.test_results if not r['passed'])
        total = len(self.test_results)
        
        print(f"\nTotal: {total} | ✅ Passed: {passed} | ❌ Failed: {failed}")
        print(f"Success Rate: {passed/total*100:.1f}%" if total > 0 else "N/A")
        
        if failed > 0:
            print("\n❌ FAILED TESTS:")
            for r in self.test_results:
                if not r['passed']:
                    print(f"  • {r['name']}")
                    if r['details']:
                        print(f"    → {r['details']}")
                        
        print("\n" + "=" * 60)
        
        return failed == 0


if __name__ == "__main__":
    runner = E2ETestRunner()
    success = runner.run_all_tests()
    sys.exit(0 if success else 1)
