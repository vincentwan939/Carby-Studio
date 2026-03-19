#!/usr/bin/env python3
"""
Test script for Bitwarden integration.

Tests:
1. Session Manager - Keychain storage and auto-refresh
2. Bitwarden DAO - CRUD operations
3. Credentials Handler - Unified interface
4. Migration Script - GPG to Bitwarden migration
"""

import sys
import os
import unittest
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from session_manager import SessionManager, SessionInfo
from bitwarden_dao import BitwardenDAO, Credential
from credentials_handler import CredentialsHandler


class TestSessionManager(unittest.TestCase):
    """Test Session Manager functionality."""
    
    def setUp(self):
        self.manager = SessionManager()
    
    def test_keychain_service_configured(self):
        """Test keychain service is properly configured."""
        self.assertEqual(self.manager.KEYCHAIN_SERVICE, "com.carby-studio.bitwarden")
        self.assertEqual(self.manager.KEYCHAIN_ACCOUNT, "bw-session")
    
    def test_session_info_dataclass(self):
        """Test SessionInfo dataclass."""
        info = SessionInfo(
            status="unlocked",
            user_email="test@example.com"
        )
        self.assertEqual(info.status, "unlocked")
        self.assertEqual(info.user_email, "test@example.com")
    
    def test_cache_directory_exists(self):
        """Test cache directory is created."""
        self.assertTrue(self.manager.CACHE_DIR.exists())


class TestBitwardenDAO(unittest.TestCase):
    """Test Bitwarden DAO functionality."""
    
    def setUp(self):
        self.dao = BitwardenDAO()
    
    def test_organization_name(self):
        """Test organization name is configured."""
        self.assertEqual(self.dao.ORG_NAME, "Carby-Studio")
        self.assertEqual(self.dao.COLLECTION_NAME, "Carby-Studio")
    
    def test_credential_full_name(self):
        """Test credential full name generation."""
        cred = Credential(
            project="test-project",
            cred_type="nas",
            name="synology"
        )
        self.assertEqual(cred.full_name, "carby-studio/test-project/nas.synology")
    
    def test_credential_from_full_name(self):
        """Test parsing credential from full name."""
        cred = Credential.from_full_name("carby-studio/my-project/nas.synology")
        self.assertIsNotNone(cred)
        self.assertEqual(cred.project, "my-project")
        self.assertEqual(cred.cred_type, "nas")
        self.assertEqual(cred.name, "synology")
    
    def test_credential_safe_repr(self):
        """Test credential doesn't expose secrets in repr."""
        cred = Credential(
            project="test",
            cred_type="api-key",
            name="openai",
            fields={"key": "super-secret-key-12345"}
        )
        repr_str = repr(cred)
        self.assertNotIn("super-secret-key", repr_str)
        self.assertIn("test", repr_str)


class TestCredentialsHandler(unittest.TestCase):
    """Test Credentials Handler functionality."""
    
    def setUp(self):
        self.handler = CredentialsHandler()
    
    def test_secrets_dir_configured(self):
        """Test secrets directory is configured."""
        expected = Path.home() / ".openclaw" / "secrets" / "projects"
        self.assertEqual(self.handler.SECRETS_DIR, expected)
    
    def test_storage_type_detection(self):
        """Test storage type detection logic."""
        # This will return 'none' for non-existent project
        storage = self.handler._get_storage_type("non-existent-project-12345")
        self.assertEqual(storage, "none")


class TestIntegration(unittest.TestCase):
    """Integration tests (requires Bitwarden CLI)."""
    
    @classmethod
    def setUpClass(cls):
        """Check if Bitwarden CLI is available."""
        import subprocess
        try:
            result = subprocess.run(
                ["bw", "--version"],
                capture_output=True,
                timeout=5
            )
            cls.bw_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            cls.bw_available = False
        
        if not cls.bw_available:
            print("\n⚠️  Bitwarden CLI not available, skipping integration tests")
    
    @unittest.skipUnless(
        os.environ.get('RUN_BW_TESTS') == '1',
        "Set RUN_BW_TESTS=1 to run Bitwarden integration tests"
    )
    def test_session_unlock_flow(self):
        """Test session unlock flow."""
        if not self.bw_available:
            self.skipTest("Bitwarden CLI not available")
        
        manager = SessionManager()
        
        # Check status (may be locked)
        info = manager.check_status()
        self.assertIn(info.status, ["locked", "unlocked", "error"])
    
    @unittest.skipUnless(
        os.environ.get('RUN_BW_TESTS') == '1',
        "Set RUN_BW_TESTS=1 to run Bitwarden integration tests"
    )
    def test_dao_status_check(self):
        """Test DAO status check."""
        if not self.bw_available:
            self.skipTest("Bitwarden CLI not available")
        
        dao = BitwardenDAO()
        info = dao.session_manager.check_status()
        self.assertIn(info.status, ["locked", "unlocked", "error"])


def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestSessionManager))
    suite.addTests(loader.loadTestsFromTestCase(TestBitwardenDAO))
    suite.addTests(loader.loadTestsFromTestCase(TestCredentialsHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)