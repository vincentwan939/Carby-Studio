#!/usr/bin/env python3
"""
Comprehensive Bot Testing Script
Tests all bot functions without requiring Telegram
"""

import os
import sys
import asyncio
from unittest.mock import Mock, patch, MagicMock

# Set up environment
os.environ["CARBY_BOT_TOKEN"] = "test_token_12345"
os.environ["CARBY_WORKSPACE"] = "/Users/wants01/.openclaw/workspace/projects"

# Mock telegram before importing
sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()

from telegram_interface import TelegramInterface, MAIN_KEYBOARD, MORE_KEYBOARD
from bot import CarbyBot
from state_manager import StateManager
from cli_executor import CLIExecutor

class TestRunner:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []
    
    def test(self, name, func):
        """Run a test and track results."""
        try:
            func()
            self.passed += 1
            self.tests.append(("✅", name))
            print(f"✅ {name}")
        except Exception as e:
            self.failed += 1
            self.tests.append(("❌", f"{name}: {e}"))
            print(f"❌ {name}: {e}")
    
    def summary(self):
        print(f"\n{'='*50}")
        print(f"Results: {self.passed} passed, {self.failed} failed")
        print(f"{'='*50}")
        return self.failed == 0

def run_tests():
    runner = TestRunner()
    
    print("🧪 Comprehensive Bot Testing\n")
    
    # Test 1: Bot Initialization
    def test_bot_init():
        bot = CarbyBot()
        assert bot.state_manager is not None
        assert bot.safety_manager is not None
    runner.test("Bot initialization", test_bot_init)
    
    # Test 2: State Manager
    def test_state_manager():
        sm = StateManager()
        projects = sm.list_projects()
        assert isinstance(projects, list)
    runner.test("State manager list projects", test_state_manager)
    
    # Test 3: Project Summary
    def test_project_summary():
        sm = StateManager()
        projects = sm.list_projects()
        if projects:
            summary = sm.get_project_summary(projects[0])
            assert summary is not None
            assert "status" in summary
    runner.test("Project summary retrieval", test_project_summary)
    
    # Test 4: CLI Executor - Rename
    def test_cli_rename():
        cli = CLIExecutor()
        # Test validation
        valid, msg = cli.validate_project_name("test-project")
        assert valid is True
    runner.test("CLI rename validation", test_cli_rename)
    
    # Test 5: CLI Executor - Invalid name
    def test_cli_invalid_name():
        cli = CLIExecutor()
        valid, msg = cli.validate_project_name("Test Project!")
        assert valid is False
    runner.test("CLI invalid name rejection", test_cli_invalid_name)
    
    # Test 6: Safety Manager - Delete confirmation
    def test_safety_delete():
        sm = StateManager()
        bot = CarbyBot()
        
        # Store confirmation
        code = bot.safety_manager.request_delete_confirmation("test-project")
        assert code == "DELETE"
        
        # Verify correct
        result = bot.safety_manager.verify_delete_confirmation("test-project", "DELETE")
        assert result is True
    runner.test("Safety delete confirmation", test_safety_delete)
    
    # Test 7: Safety Manager - Wrong confirmation
    def test_safety_wrong_confirm():
        sm = StateManager()
        bot = CarbyBot()
        
        bot.safety_manager.request_delete_confirmation("test-project2")
        result = bot.safety_manager.verify_delete_confirmation("test-project2", "WRONG")
        assert result is False
    runner.test("Safety wrong confirmation rejected", test_safety_wrong_confirm)
    
    # Test 8: Bot dispatch_stage with no stage
    def test_dispatch_no_stage():
        bot = CarbyBot()
        # Should handle missing stage gracefully
        result = bot.dispatch_stage("nonexistent-project-12345")
        assert result.success is False
    runner.test("Dispatch handles missing project", test_dispatch_no_stage)
    
    # Test 9: Check dummy project exists
    def test_dummy_project():
        sm = StateManager()
        summary = sm.get_project_summary("test-dummy-bot")
        assert summary is not None
        assert summary.get("status") == "active"
    runner.test("Dummy project exists", test_dummy_project)
    
    # Test 10: Dummy project stages (read full state)
    def test_dummy_stages():
        sm = StateManager()
        state = sm.read_project("test-dummy-bot")
        assert state is not None
        stages = state.get("stages", {})
        assert "discover" in stages
        assert "design" in stages
        assert "build" in stages
    runner.test("Dummy project has correct stages", test_dummy_stages)
    
    # Test 11: Project status detection
    def test_project_status():
        sm = StateManager()
        summary = sm.get_project_summary("test-dummy-bot")
        status = summary.get("status")
        assert status in ["active", "completed", "failed", "blocked"]
    runner.test("Project status detection", test_project_status)
    
    # Test 12: Current stage detection
    def test_current_stage():
        sm = StateManager()
        summary = sm.get_project_summary("test-dummy-bot")
        current = summary.get("current_stage") or summary.get("currentStage")
        # Should have a current stage or we can find pending
        assert current is not None or summary.get("stages")
    runner.test("Current stage detection", test_current_stage)
    
    # Test 13: TelegramInterface initialization
    def test_telegram_init():
        with patch('telegram_interface.Application'):
            interface = TelegramInterface()
            assert interface.bot is not None
            assert interface.state_manager is not None
    runner.test("TelegramInterface initialization", test_telegram_init)
    
    # Test 14: Keyboard layouts
    def test_keyboards():
        assert MAIN_KEYBOARD is not None
        assert MORE_KEYBOARD is not None
    runner.test("Keyboard layouts defined", test_keyboards)
    
    # Test 15: carby-studio CLI available
    def test_carby_cli():
        import subprocess
        result = subprocess.run(["carby-studio", "--help"], capture_output=True, text=True)
        assert result.returncode == 0
        assert "Usage" in result.stdout
    runner.test("carby-studio CLI available", test_carby_cli)
    
    return runner.summary()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
