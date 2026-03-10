"""Tests for loading indicators."""

import unittest
from loading_indicator import (
    LoadingIndicator,
    LoadingConfig,
    get_loading_message,
    LOADING_MESSAGES
)


class TestLoadingIndicator(unittest.TestCase):
    """Test loading indicator functionality."""
    
    def test_loading_config_defaults(self):
        """Test default loading config."""
        config = LoadingConfig()
        self.assertEqual(config.loading_emoji, "🔄")
        self.assertEqual(config.success_emoji, "✅")
        self.assertEqual(config.error_emoji, "❌")
    
    def test_get_loading_text(self):
        """Test loading text generation."""
        indicator = LoadingIndicator()
        text = indicator.get_loading_text("Resuming", "Contacting agent...")
        
        self.assertIn("🔄", text)
        self.assertIn("Resuming", text)
        self.assertIn("Contacting agent...", text)
    
    def test_get_success_text(self):
        """Test success text generation."""
        indicator = LoadingIndicator()
        text = indicator.get_success_text("Resume", "Project resumed successfully")
        
        self.assertIn("✅", text)
        self.assertIn("Resume", text)
        self.assertIn("Project resumed successfully", text)
    
    def test_get_error_text(self):
        """Test error text generation."""
        indicator = LoadingIndicator()
        text = indicator.get_error_text("Resume", "Connection failed")
        
        self.assertIn("❌", text)
        self.assertIn("Resume Failed", text)
        self.assertIn("Connection failed", text)
    
    def test_predefined_messages_exist(self):
        """Test that predefined messages exist for all operations."""
        operations = ["resume", "dispatch", "retry", "skip", "stop", "delete", "rename", "logs"]
        states = ["initial", "success", "error"]
        
        for op in operations:
            self.assertIn(op, LOADING_MESSAGES)
            for state in states:
                self.assertIn(state, LOADING_MESSAGES[op])
    
    def test_get_loading_message_resume(self):
        """Test getting resume loading message."""
        text = get_loading_message("resume", "initial")
        self.assertIn("🔄", text)
        self.assertIn("Resuming", text)
    
    def test_get_loading_message_with_detail(self):
        """Test getting loading message with detail."""
        text = get_loading_message("resume", "success", detail="Project: test-project")
        self.assertIn("✅", text)
        self.assertIn("Project: test-project", text)
    
    def test_get_loading_message_unknown_operation(self):
        """Test getting message for unknown operation."""
        text = get_loading_message("unknown_op", "initial")
        self.assertEqual(text, "Initial...")
    
    def test_custom_config(self):
        """Test custom loading config."""
        config = LoadingConfig(
            loading_emoji="⏳",
            success_emoji="🎉",
            error_emoji="💥"
        )
        indicator = LoadingIndicator(config)
        
        loading = indicator.get_loading_text("Test")
        success = indicator.get_success_text("Test")
        error = indicator.get_error_text("Test", "Error")
        
        self.assertIn("⏳", loading)
        self.assertIn("🎉", success)
        self.assertIn("💥", error)


class TestLoadingMessageContent(unittest.TestCase):
    """Test content of predefined loading messages."""
    
    def test_resume_messages(self):
        """Test resume operation messages."""
        initial = get_loading_message("resume", "initial")
        self.assertIn("🔄", initial)
        self.assertIn("Resuming", initial)
        
        success = get_loading_message("resume", "success")
        self.assertIn("✅", success)
        
        error = get_loading_message("resume", "error")
        self.assertIn("❌", error)
    
    def test_dispatch_messages(self):
        """Test dispatch operation messages."""
        initial = get_loading_message("dispatch", "initial")
        self.assertIn("🚀", initial)
        self.assertIn("Dispatching", initial)
    
    def test_stop_messages(self):
        """Test stop operation messages."""
        initial = get_loading_message("stop", "initial")
        self.assertIn("🛑", initial)
        self.assertIn("Stopping", initial)
    
    def test_delete_messages(self):
        """Test delete operation messages."""
        initial = get_loading_message("delete", "initial")
        self.assertIn("🗑️", initial)
        self.assertIn("Deleting", initial)


if __name__ == "__main__":
    unittest.main()
