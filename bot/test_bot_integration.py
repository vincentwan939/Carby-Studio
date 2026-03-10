#!/usr/bin/env python3
"""
Integration Tests for Telegram Bot
Tests actual bot workflows without Telegram API
"""

import os
import sys
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock

os.environ["CARBY_BOT_TOKEN"] = "test_token_12345"
os.environ["CARBY_WORKSPACE"] = "/Users/wants01/.openclaw/workspace/projects"

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

from telegram_interface import TelegramInterface
from bot import CarbyBot
from state_manager import StateManager

class AsyncTestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
    
    async def test(self, name, func):
        try:
            await func()
            self.passed += 1
            print(f"✅ {name}")
        except Exception as e:
            self.failed += 1
            print(f"❌ {name}: {e}")
    
    def summary(self):
        print(f"\n{'='*50}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print(f"{'='*50}")
        return self.failed == 0

async def run_tests():
    runner = AsyncTestRunner()
    
    print("🔬 Integration Testing\n")
    
    # Test 1: Project list formatting
    async def test_project_list():
        sm = StateManager()
        interface = TelegramInterface()
        interface.state_manager = sm
        interface.bot = CarbyBot()
        
        # Mock update
        update = Mock()
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        
        await interface.cmd_projects(update, Mock())
        assert update.message.reply_text.called
    
    await runner.test("Project list command", test_project_list)
    
    # Test 2: Start command
    async def test_start():
        interface = TelegramInterface()
        
        update = Mock()
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        
        await interface.cmd_start(update, Mock())
        assert update.message.reply_text.called
        call_args = update.message.reply_text.call_args
        assert "Welcome" in call_args[0][0] or "Carby" in call_args[0][0]
    
    await runner.test("Start command", test_start)
    
    # Test 3: View project
    async def test_view_project():
        interface = TelegramInterface()
        
        query = Mock()
        query.edit_message_text = AsyncMock()
        
        await interface.handle_view(query, "test-dummy-bot")
        assert query.edit_message_text.called
        call_args = query.edit_message_text.call_args
        text = call_args[1].get('text') or call_args[0][0]
        assert "test-dummy-bot" in text
    
    await runner.test("View project", test_view_project)
    
    # Test 4: View nonexistent project
    async def test_view_nonexistent():
        interface = TelegramInterface()
        
        query = Mock()
        query.edit_message_text = AsyncMock()
        
        await interface.handle_view(query, "nonexistent-project-xyz")
        assert query.edit_message_text.called
        call_args = query.edit_message_text.call_args
        text = call_args[1].get('text') or call_args[0][0]
        assert "not found" in text.lower()
    
    await runner.test("View nonexistent project", test_view_nonexistent)
    
    # Test 5: Help command
    async def test_help():
        interface = TelegramInterface()
        
        update = Mock()
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        
        await interface.cmd_help(update, Mock())
        assert update.message.reply_text.called
    
    await runner.test("Help command", test_help)
    
    # Test 6: Status command
    async def test_status():
        interface = TelegramInterface()
        
        update = Mock()
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        
        await interface.cmd_status(update, Mock())
        assert update.message.reply_text.called
    
    await runner.test("Status command", test_status)
    
    # Test 7: More menu
    async def test_more():
        interface = TelegramInterface()
        
        update = Mock()
        update.message = Mock()
        update.message.reply_text = AsyncMock()
        
        await interface.cmd_more(update, Mock())
        assert update.message.reply_text.called
    
    await runner.test("More menu", test_more)
    
    # Test 8: Dispatch completed project
    async def test_dispatch_completed():
        interface = TelegramInterface()
        
        query = Mock()
        query.edit_message_text = AsyncMock()
        
        # Try to dispatch "hihi" which is completed
        await interface.handle_dispatch(query, "hihi")
        assert query.edit_message_text.called
        call_args = query.edit_message_text.call_args
        text = call_args[1].get('text') or call_args[0][0]
        # Should show error or info about no pending stages
        assert "hihi" in text
    
    await runner.test("Dispatch completed project", test_dispatch_completed)
    
    # Test 9: Rename flow start
    async def test_rename_start():
        interface = TelegramInterface()
        
        query = Mock()
        query.data = "rename:test-dummy-bot"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        context = Mock()
        context.user_data = {}
        
        result = await interface.rename_start(
            Mock(callback_query=query, effective_user=Mock(id=123)), 
            context
        )
        assert query.answer.called
    
    await runner.test("Rename flow start", test_rename_start)
    
    # Test 10: Delete flow start
    async def test_delete_start():
        interface = TelegramInterface()
        
        query = Mock()
        query.data = "delete:test-dummy-bot"
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        
        context = Mock()
        context.user_data = {}
        
        result = await interface.delete_start(
            Mock(callback_query=query, effective_user=Mock(id=123)),
            context
        )
        assert query.answer.called
        assert query.edit_message_text.called
        # Check that confirmation was requested
        call_args = query.edit_message_text.call_args
        text = call_args[1].get('text') or call_args[0][0]
        assert "DELETE" in text
    
    await runner.test("Delete flow start", test_delete_start)
    
    return runner.summary()

if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
