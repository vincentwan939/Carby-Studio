"""
Comprehensive verification script for token replay protection fix.

This script verifies:
1. Used tokens are rejected with TokenReplayError
2. Token registry persists across sessions
3. Concurrent replay attempts are blocked atomically
4. Tokens are hashed (SHA-256) in registry
"""
import tempfile
import threading
import time
import json
import hashlib
from pathlib import Path
import sys

# Add parent to path
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from carby_sprint.gate_enforcer import GateEnforcer
from carby_sprint.gate_state import GateStateManager
from carby_sprint.gate_token import GateToken
from carby_sprint.exceptions import TokenReplayError, GateBypassError


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'


def log_pass(msg):
    print(f"{Colors.GREEN}[PASS]{Colors.RESET} {msg}")


def log_fail(msg):
    print(f"{Colors.RED}[FAIL]{Colors.RESET} {msg}")


def log_info(msg):
    print(f"{Colors.YELLOW}[INFO]{Colors.RESET} {msg}")


def test_used_tokens_rejected():
    """Test that used tokens are rejected with TokenReplayError."""
    log_info("Testing: Used tokens rejected with TokenReplayError...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        enforcer = GateEnforcer(str(project_path))
        sprint_id = "test-sprint"
        
        # Setup: Complete discovery
        discovery_token = enforcer.request_gate_token(sprint_id, "discovery")
        enforcer._record_gate_completion(sprint_id, "discovery", discovery_token.token)
        
        # Get and use a design token
        design_token = enforcer.request_gate_token(sprint_id, "design")
        token_str = design_token.token
        enforcer.advance_gate(sprint_id, "design", token_str)
        
        # Test 1: validate_gate_token raises TokenReplayError
        try:
            enforcer.validate_gate_token(token_str)
            log_fail("validate_gate_token did not raise TokenReplayError for used token")
            return False
        except TokenReplayError:
            log_pass("validate_gate_token raises TokenReplayError for used token")
        
        # Test 2: advance_gate raises TokenReplayError
        try:
            enforcer.advance_gate(sprint_id, "build", token_str)
            log_fail("advance_gate did not raise TokenReplayError for used token")
            return False
        except TokenReplayError:
            log_pass("advance_gate raises TokenReplayError for used token")
        
        return True


def test_registry_persistence():
    """Test that token registry persists across sessions."""
    log_info("Testing: Token registry persistence across sessions...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        # First session
        manager1 = GateStateManager(str(project_path))
        sprint_id = "test-sprint"
        
        token = GateToken(gate_id="design", sprint_id=sprint_id)
        manager1.mark_token_used(token.token, sprint_id, "design")
        
        # Verify registry file exists
        registry_file = manager1.token_registry_file
        if not registry_file.exists():
            log_fail("Token registry file was not created")
            return False
        log_pass("Token registry file created")
        
        # Second session - new manager instance
        manager2 = GateStateManager(str(project_path))
        
        # Token should still be marked as used
        if not manager2.is_token_used(token.token):
            log_fail("Token did not persist across sessions")
            return False
        log_pass("Token persists across sessions")
        
        return True


def test_concurrent_blocking():
    """Test that concurrent replay attempts are blocked atomically."""
    log_info("Testing: Concurrent replay blocking...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        enforcer = GateEnforcer(str(project_path))
        sprint_id = "test-sprint"
        
        # Setup: Complete discovery
        discovery_token = enforcer.request_gate_token(sprint_id, "discovery")
        enforcer._record_gate_completion(sprint_id, "discovery", discovery_token.token)
        
        # Get token that will be contested
        design_token = enforcer.request_gate_token(sprint_id, "design")
        token_str = design_token.token
        
        results = []
        errors = []
        
        def attempt_advance():
            try:
                result = enforcer.advance_gate(sprint_id, "design", token_str)
                results.append(("success", result))
            except TokenReplayError as e:
                errors.append(("TokenReplayError", str(e)))
            except GateBypassError as e:
                errors.append(("GateBypassError", str(e)))
            except Exception as e:
                errors.append((type(e).__name__, str(e)))
        
        # Start multiple threads trying to use the same token
        threads = []
        for _ in range(5):
            t = threading.Thread(target=attempt_advance)
            threads.append(t)
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Exactly one should succeed
        if len(results) != 1:
            log_fail(f"Expected 1 success, got {len(results)}")
            return False
        log_pass("Exactly one concurrent attempt succeeded")
        
        # Others should fail with replay or bypass error
        if len(errors) != 4:
            log_fail(f"Expected 4 errors, got {len(errors)}")
            return False
        
        error_types = [e[0] for e in errors]
        if not all(e in ["TokenReplayError", "GateBypassError"] for e in error_types):
            log_fail(f"Unexpected error types: {error_types}")
            return False
        log_pass("All concurrent failures were TokenReplayError or GateBypassError")
        
        return True


def test_token_hashing():
    """Test that tokens are hashed (SHA-256) in registry."""
    log_info("Testing: Token hashing (SHA-256)...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = GateStateManager(temp_dir)
        
        token = GateToken(gate_id="design", sprint_id="test-sprint")
        token_str = token.token
        
        # Compute expected hash
        expected_hash = hashlib.sha256(token_str.encode()).hexdigest()
        
        # Get hash from manager
        actual_hash = manager._hash_token(token_str)
        
        # Verify SHA-256 properties
        if actual_hash != expected_hash:
            log_fail(f"Hash mismatch: expected {expected_hash}, got {actual_hash}")
            return False
        log_pass("Token hashing uses SHA-256 correctly")
        
        if len(actual_hash) != 64:
            log_fail(f"Hash length should be 64, got {len(actual_hash)}")
            return False
        log_pass("Hash is 64 hex characters (SHA-256)")
        
        # Mark token as used
        manager.mark_token_used(token_str, "test-sprint", "design")
        
        # Read raw registry file content
        registry_content = manager.token_registry_file.read_text()
        
        # Raw token should NOT be in file
        if token_str in registry_content:
            log_fail("Raw token appears in registry file (security risk)")
            return False
        log_pass("Raw token does not appear in registry file")
        
        # Hash should be in file
        if actual_hash not in registry_content:
            log_fail("Token hash not found in registry file")
            return False
        log_pass("Token hash appears in registry file")
        
        return True


def test_atomic_operations():
    """Test that token registry operations are atomic."""
    log_info("Testing: Atomic registry operations...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        manager = GateStateManager(temp_dir)
        
        # Test atomic read
        token = GateToken(gate_id="test", sprint_id="test-sprint")
        if manager.is_token_used(token.token):
            log_fail("New token incorrectly marked as used")
            return False
        log_pass("is_token_used returns False for new token")
        
        # Test atomic write
        manager.mark_token_used(token.token, "test-sprint", "test")
        if not manager.is_token_used(token.token):
            log_fail("Token not marked as used after marking")
            return False
        log_pass("is_token_used returns True after marking")
        
        return True


def main():
    """Run all verification tests."""
    print("=" * 70)
    print("TOKEN REPLAY PROTECTION VERIFICATION")
    print("=" * 70)
    print()
    
    results = []
    
    # Run all tests
    results.append(("Used tokens rejected", test_used_tokens_rejected()))
    print()
    
    results.append(("Registry persistence", test_registry_persistence()))
    print()
    
    results.append(("Concurrent blocking", test_concurrent_blocking()))
    print()
    
    results.append(("Token hashing (SHA-256)", test_token_hashing()))
    print()
    
    results.append(("Atomic operations", test_atomic_operations()))
    print()
    
    # Summary
    print("=" * 70)
    print("VERIFICATION SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
        print(f"  [{status}] {name}")
    
    print()
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print(f"{Colors.GREEN}OVERALL: PASS{Colors.RESET}")
        return 0
    else:
        print(f"{Colors.RED}OVERALL: FAIL{Colors.RESET}")
        return 1


if __name__ == "__main__":
    sys.exit(main())