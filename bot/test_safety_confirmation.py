"""Tests for safety confirmation (race condition fix)."""

import unittest
from safety import SafetyManager
from state_manager import StateManager


class TestDeleteConfirmation(unittest.TestCase):
    """Test delete confirmation behavior."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock state manager
        self.state_manager = StateManager.__new__(StateManager)
        self.state_manager._cache = {}
        self.safety = SafetyManager(self.state_manager)
    
    def test_confirmation_persists_on_mismatch(self):
        """Test that confirmation persists when user types wrong code."""
        project = "test-project"
        
        # Request confirmation
        code = self.safety.request_delete_confirmation(project)
        self.assertEqual(code, "DELETE")
        
        # Verify with wrong code
        result = self.safety.verify_delete_confirmation(project, "WRONG")
        self.assertFalse(result)
        
        # Confirmation should still exist (allowing retry)
        self.assertIn(project, self.safety._delete_confirmations)
        
        # Verify with correct code
        result = self.safety.verify_delete_confirmation(project, "DELETE")
        self.assertTrue(result)
        
        # Now confirmation should be removed
        self.assertNotIn(project, self.safety._delete_confirmations)
    
    def test_confirmation_removed_on_success(self):
        """Test that confirmation is removed on successful verification."""
        project = "test-project"
        
        # Request confirmation
        self.safety.request_delete_confirmation(project)
        self.assertIn(project, self.safety._delete_confirmations)
        
        # Verify with correct code
        result = self.safety.verify_delete_confirmation(project, "DELETE")
        self.assertTrue(result)
        
        # Confirmation should be removed
        self.assertNotIn(project, self.safety._delete_confirmations)
    
    def test_multiple_retries_allowed(self):
        """Test that multiple retries are allowed."""
        project = "test-project"
        
        # Request confirmation
        self.safety.request_delete_confirmation(project)
        
        # Multiple wrong attempts
        for _ in range(3):
            result = self.safety.verify_delete_confirmation(project, "WRONG")
            self.assertFalse(result)
            self.assertIn(project, self.safety._delete_confirmations)
        
        # Finally correct
        result = self.safety.verify_delete_confirmation(project, "DELETE")
        self.assertTrue(result)
    
    def test_no_confirmation_returns_false(self):
        """Test that verification fails when no confirmation exists."""
        project = "test-project"
        
        # Try to verify without requesting first
        result = self.safety.verify_delete_confirmation(project, "DELETE")
        self.assertFalse(result)
    
    def test_confirmation_case_insensitive(self):
        """Test that confirmation is case-insensitive."""
        project = "test-project"
        
        # Request confirmation
        self.safety.request_delete_confirmation(project)
        
        # Verify with lowercase
        result = self.safety.verify_delete_confirmation(project, "delete")
        self.assertTrue(result)
    
    def test_confirmation_whitespace_insensitive(self):
        """Test that confirmation ignores whitespace."""
        project = "test-project"
        
        # Request confirmation
        self.safety.request_delete_confirmation(project)
        
        # Verify with whitespace
        result = self.safety.verify_delete_confirmation(project, "  DELETE  ")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
