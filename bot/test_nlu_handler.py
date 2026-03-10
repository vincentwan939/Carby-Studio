"""Tests for NLU handler."""

import unittest
from nlu_handler import (
    NLUHandler,
    match_intent,
    extract_project_name,
    get_nlu_handler,
    Intent
)


class TestNLUHandler(unittest.TestCase):
    """Test NLU handler functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.nlu = NLUHandler()
    
    def test_match_intent_projects_exact(self):
        """Test exact match for projects intent."""
        intent, confidence = self.nlu.match_intent("show my projects")
        self.assertEqual(intent, Intent.PROJECTS)
        self.assertEqual(confidence, 1.0)
    
    def test_match_intent_projects_variations(self):
        """Test various project-related phrases."""
        variations = [
            "projects",
            "my projects",
            "list projects",
            "view projects",
            "what projects do i have",
            "show my work",
            "what am i working on"
        ]
        for text in variations:
            intent, confidence = self.nlu.match_intent(text)
            self.assertEqual(intent, Intent.PROJECTS, f"Failed for: {text}")
            self.assertGreater(confidence, 0)
    
    def test_match_intent_status(self):
        """Test status intent matching."""
        variations = [
            "status",
            "what's running",
            "what is running",
            "system status",
            "check status",
            "what's going on"
        ]
        for text in variations:
            intent, confidence = self.nlu.match_intent(text)
            self.assertEqual(intent, Intent.STATUS, f"Failed for: {text}")
    
    def test_match_intent_continue(self):
        """Test continue intent matching."""
        variations = [
            "continue",
            "resume",
            "where was i",
            "what was i doing",
            "let's continue",
            "carry on"
        ]
        for text in variations:
            intent, confidence = self.nlu.match_intent(text)
            self.assertEqual(intent, Intent.CONTINUE, f"Failed for: {text}")
    
    def test_match_intent_help(self):
        """Test help intent matching."""
        variations = [
            "help",
            "how to",
            "how do i",
            "what can you do",
            "instructions",
            "what is this"
        ]
        for text in variations:
            intent, confidence = self.nlu.match_intent(text)
            self.assertEqual(intent, Intent.HELP, f"Failed for: {text}")
    
    def test_match_intent_create(self):
        """Test create intent matching."""
        variations = [
            "create",
            "start",
            "begin",
            "init",
            "i want to create"
        ]
        for text in variations:
            intent, confidence = self.nlu.match_intent(text)
            self.assertEqual(intent, Intent.CREATE, f"Failed for: {text}")
    
    def test_match_intent_stop(self):
        """Test stop intent matching."""
        variations = [
            "stop",
            "cancel",
            "stop agent",
            "abort"
        ]
        for text in variations:
            intent, confidence = self.nlu.match_intent(text)
            self.assertEqual(intent, Intent.STOP, f"Failed for: {text}")
    
    def test_match_intent_unknown(self):
        """Test unknown intent."""
        intent, confidence = self.nlu.match_intent("xyz abc 123")
        self.assertEqual(intent, Intent.UNKNOWN)
        self.assertEqual(confidence, 0.0)
    
    def test_fuzzy_matching_typo(self):
        """Test fuzzy matching for typos."""
        # Common typos should still match
        typos = [
            ("projcts", Intent.PROJECTS),  # Missing 'e'
            ("statu", Intent.STATUS),      # Missing 's'
            ("continu", Intent.CONTINUE),  # Missing 'e'
            ("helo", Intent.HELP),         # Missing 'p'
        ]
        for text, expected_intent in typos:
            intent, confidence = self.nlu.match_intent(text)
            self.assertEqual(intent, expected_intent, f"Failed for typo: {text}")
            self.assertGreater(confidence, 0)
    
    def test_extract_project_name(self):
        """Test project name extraction."""
        test_cases = [
            ("show project my-app", "my-app"),
            ('what about "my-project"', "my-project"),
            ("project123 status", "project123"),
        ]
        for text, expected in test_cases:
            result = self.nlu.extract_project_name(text)
            self.assertEqual(result, expected, f"Failed for: {text}")
    
    def test_extract_project_name_none(self):
        """Test when no project name is found."""
        result = self.nlu.extract_project_name("show me something")
        self.assertIsNone(result)
    
    def test_get_suggestions(self):
        """Test suggestion generation."""
        suggestions = self.nlu.get_suggestions("proj")
        self.assertIn(Intent.PROJECTS, suggestions)
    
    def test_format_suggestions(self):
        """Test suggestion formatting."""
        suggestions = [Intent.PROJECTS, Intent.STATUS]
        text = self.nlu.format_suggestions(suggestions)
        self.assertIn("📋", text)
        self.assertIn("📊", text)
    
    def test_case_insensitive(self):
        """Test case insensitivity."""
        variations = [
            "PROJECTS",
            "Projects",
            "PrOjEcTs"
        ]
        for text in variations:
            intent, confidence = self.nlu.match_intent(text)
            self.assertEqual(intent, Intent.PROJECTS)


class TestConvenienceFunctions(unittest.TestCase):
    """Test convenience functions."""
    
    def test_match_intent_convenience(self):
        """Test match_intent convenience function."""
        intent, confidence = match_intent("help me")
        self.assertEqual(intent, Intent.HELP)
    
    def test_extract_project_name_convenience(self):
        """Test extract_project_name convenience function."""
        result = extract_project_name("project test-123")
        self.assertEqual(result, "test-123")
    
    def test_get_nlu_handler_singleton(self):
        """Test NLU handler singleton."""
        handler1 = get_nlu_handler()
        handler2 = get_nlu_handler()
        self.assertIs(handler1, handler2)


if __name__ == "__main__":
    unittest.main()
