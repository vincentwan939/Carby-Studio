"""Tests for error handler."""

import unittest
from error_handler import (
    get_error_info,
    format_error_message,
    classify_error,
    handle_cli_error,
    ErrorInfo
)


class MockCLIResult:
    """Mock CLI result for testing."""
    def __init__(self, success, stdout="", stderr=""):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr


class TestErrorHandler(unittest.TestCase):
    """Test error handler functionality."""
    
    def test_get_error_info_project_not_found(self):
        """Test error info for project not found."""
        error_info = get_error_info("E1001", {"project": "test-project"})
        self.assertEqual(error_info.error_code, "E1001")
        self.assertIn("test-project", error_info.message)
        self.assertEqual(error_info.severity, "warning")
    
    def test_get_error_info_invalid_name(self):
        """Test error info for invalid name."""
        error_info = get_error_info("E2001")
        self.assertEqual(error_info.error_code, "E2001")
        self.assertIn("lowercase", error_info.explanation)
        self.assertIn("my-project", error_info.action)
    
    def test_get_error_info_cli_timeout(self):
        """Test error info for CLI timeout."""
        error_info = get_error_info("E4002")
        self.assertEqual(error_info.error_code, "E4002")
        self.assertEqual(error_info.severity, "warning")
    
    def test_format_error_message(self):
        """Test error message formatting."""
        error_info = ErrorInfo(
            message="Test error",
            explanation="This is what happened",
            action="Do this to fix it",
            error_code="E9999",
            severity="error"
        )
        formatted = format_error_message(error_info)
        
        self.assertIn("❌", formatted)
        self.assertIn("Test error", formatted)
        self.assertIn("E9999", formatted)
        self.assertIn("This is what happened", formatted)
        self.assertIn("Do this to fix it", formatted)
    
    def test_format_error_message_without_code(self):
        """Test error formatting without code."""
        error_info = ErrorInfo(
            message="Simple error",
            explanation="Explanation",
            action="Action",
            error_code="E0000",
            severity="warning"
        )
        formatted = format_error_message(error_info, include_code=False)
        
        self.assertIn("⚠️", formatted)
        self.assertNotIn("E0000", formatted)
    
    def test_classify_error_not_found(self):
        """Test error classification for not found."""
        code, name = classify_error("Project not found")
        self.assertEqual(code, "E1001")
    
    def test_classify_error_already_exists(self):
        """Test error classification for already exists."""
        code, name = classify_error("Project already exists")
        self.assertEqual(code, "E1002")
    
    def test_classify_error_in_progress(self):
        """Test error classification for in progress."""
        code, name = classify_error("Has running agent")
        self.assertEqual(code, "E1003")
    
    def test_classify_error_cli_not_found(self):
        """Test error classification for CLI not found."""
        code, name = classify_error("Command not found")
        self.assertEqual(code, "E4001")
    
    def test_classify_error_timeout(self):
        """Test error classification for timeout."""
        code, name = classify_error("Operation timed out")
        self.assertEqual(code, "E4002")
    
    def test_classify_error_permission(self):
        """Test error classification for permission denied."""
        code, name = classify_error("Permission denied")
        self.assertEqual(code, "E4004")
    
    def test_classify_error_safety(self):
        """Test error classification for safety check."""
        code, name = classify_error("Safety check failed")
        self.assertEqual(code, "E5001")
    
    def test_classify_error_confirmation(self):
        """Test error classification for confirmation required."""
        code, name = classify_error("Confirmation required")
        self.assertEqual(code, "E5002")
    
    def test_classify_error_unknown(self):
        """Test error classification for unknown error."""
        code, name = classify_error("Something weird happened")
        self.assertEqual(code, "E0000")
    
    def test_handle_cli_error_success(self):
        """Test handling successful CLI result."""
        result = MockCLIResult(success=True)
        message = handle_cli_error(result)
        self.assertEqual(message, "")
    
    def test_handle_cli_error_with_error(self):
        """Test handling CLI error result."""
        result = MockCLIResult(success=False, stderr="Project not found")
        message = handle_cli_error(result)
        
        self.assertIn("❌", message)
        self.assertIn("Project not found", message)
    
    def test_severity_emoji(self):
        """Test severity emoji selection."""
        severities = [
            ("info", "ℹ️"),
            ("warning", "⚠️"),
            ("error", "❌"),
            ("critical", "🚨")
        ]
        for severity, expected_emoji in severities:
            error_info = ErrorInfo(
                message="Test",
                explanation="Test",
                action="Test",
                error_code="E0000",
                severity=severity
            )
            formatted = format_error_message(error_info)
            self.assertIn(expected_emoji, formatted)


if __name__ == "__main__":
    unittest.main()
