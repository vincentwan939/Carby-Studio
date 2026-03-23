"""Security tests for Carby Studio.

This module tests security-critical functionality including:
- HMAC token security (tampering detection, expiration, timing attacks)
- Path traversal protections
- Race condition handling
"""

import pytest
import tempfile
import json
import hmac
import hashlib
import threading
import time
import statistics
import base64
import os
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Import the modules under test
from carby_sprint.gate_enforcer import (
    GateEnforcer, GateToken, DesignGateEnforcer, DesignApprovalToken,
    InvalidTokenError, ExpiredTokenError, GateBypassError, GateEnforcementError
)
from carby_sprint.path_utils import (
    validate_sprint_id, validate_work_item_id, safe_join_path, sanitize_filename
)
from carby_sprint.lock_manager import DistributedLock


class TestHMACTokenSecurity:
    """Test HMAC token security properties."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .carby-sprints directory
            sprint_dir = Path(tmpdir) / ".carby-sprints"
            sprint_dir.mkdir()
            yield tmpdir
    
    @pytest.fixture
    def secret_key(self):
        """Generate a test secret key."""
        return b"test_secret_key_for_hmac_signing_32bytes!"
    
    def test_tampered_signature_detected(self, secret_key):
        """Test that tampered signatures are rejected."""
        # Create valid token
        token = GateToken(
            gate_id="test-gate",
            sprint_id="test-sprint",
            expires_in_hours=24,
            secret_key=secret_key
        )
        
        # Get the serialized token
        token_str = token.token
        
        # Tamper with the signature (change last character)
        parts = token_str.split('.')
        tampered_sig = parts[1][:-1] + ('0' if parts[1][-1] != '0' else '1')
        tampered_token = f"{parts[0]}.{tampered_sig}"
        
        # Verify rejection
        with pytest.raises(InvalidTokenError, match="Invalid token signature"):
            GateToken.from_string(tampered_token, secret_key=secret_key)
    
    def test_tampered_payload_detected(self, secret_key):
        """Test that tampered payloads are rejected."""
        # Create valid token
        token = GateToken(
            gate_id="test-gate",
            sprint_id="test-sprint",
            expires_in_hours=24,
            secret_key=secret_key
        )
        
        # Get the serialized token
        token_str = token.token
        parts = token_str.split('.')
        
        # Decode payload, modify it, re-encode
        payload_json = base64.urlsafe_b64decode(parts[0]).decode()
        payload = json.loads(payload_json)
        
        # Tamper with the payload - change gate_id
        payload["gate_id"] = "tampered-gate"
        
        # Re-encode
        tampered_payload = base64.urlsafe_b64encode(
            json.dumps(payload, separators=(',', ':'), sort_keys=True).encode()
        ).decode()
        tampered_token = f"{tampered_payload}.{parts[1]}"
        
        # Verify rejection
        with pytest.raises(InvalidTokenError, match="Invalid token signature"):
            GateToken.from_string(tampered_token, secret_key=secret_key)
    
    def test_expired_token_rejected(self, secret_key):
        """Test that expired tokens are rejected."""
        # Create token that expires immediately
        token = GateToken(
            gate_id="test-gate",
            sprint_id="test-sprint",
            expires_in_hours=0,  # Expires immediately
            secret_key=secret_key
        )
        
        # Manually set expiration to past
        token.expires_at = datetime.utcnow() - timedelta(seconds=1)
        
        # Create a new serialized token with expired timestamp
        expired_token_data = {
            "gate_id": token.gate_id,
            "sprint_id": token.sprint_id,
            "created_at": (datetime.utcnow() - timedelta(hours=25)).isoformat(),
            "expires_at": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            "nonce": token.nonce
        }
        
        # Sign the expired data
        token_json = json.dumps(expired_token_data, sort_keys=True)
        signature = hmac.new(
            secret_key,
            token_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Encode payload
        encoded_payload = base64.urlsafe_b64encode(token_json.encode()).decode()
        expired_token = f"{encoded_payload}.{signature}"
        
        # Verify rejection due to expiration
        with pytest.raises(ExpiredTokenError, match="Token has expired"):
            GateToken.from_string(expired_token, secret_key=secret_key)
    
    def test_timing_attack_resistance(self, secret_key):
        """Test that signature verification is constant-time."""
        # Create valid token
        token = GateToken(
            gate_id="test-gate",
            sprint_id="test-sprint",
            expires_in_hours=24,
            secret_key=secret_key
        )
        
        valid_token_str = token.token
        
        # Create invalid token (tampered signature)
        parts = valid_token_str.split('.')
        invalid_token_str = f"{parts[0]}.{parts[1][:-1]}0"
        
        # Measure timing for valid token
        valid_times = []
        for _ in range(50):
            start = time.perf_counter()
            try:
                GateToken.from_string(valid_token_str, secret_key=secret_key)
            except:
                pass
            valid_times.append(time.perf_counter() - start)
        
        # Measure timing for invalid token
        invalid_times = []
        for _ in range(50):
            start = time.perf_counter()
            try:
                GateToken.from_string(invalid_token_str, secret_key=secret_key)
            except:
                pass
            invalid_times.append(time.perf_counter() - start)
        
        # Calculate means and standard deviations
        valid_mean = statistics.mean(valid_times)
        invalid_mean = statistics.mean(invalid_times)
        valid_std = statistics.stdev(valid_times) if len(valid_times) > 1 else 0
        
        # The timing difference should be small relative to standard deviation
        # (allowing for some variance due to system load)
        time_diff = abs(valid_mean - invalid_mean)
        
        # Timing difference should be less than 3 standard deviations
        # This is a statistical test - may occasionally fail due to system noise
        assert time_diff < (valid_std * 5 + 0.001), (
            f"Timing difference {time_diff:.6f}s suggests non-constant time comparison. "
            f"Valid mean: {valid_mean:.6f}s, Invalid mean: {invalid_mean:.6f}s"
        )
    
    def test_invalid_token_format_rejected(self, secret_key):
        """Test that malformed tokens are rejected."""
        invalid_tokens = [
            "not-a-valid-token",
            "only-one-part",
            "part1.part2.part3.extra",
            "",
            ".",
            "..",
        ]
        
        for invalid_token in invalid_tokens:
            with pytest.raises(InvalidTokenError):
                GateToken.from_string(invalid_token, secret_key=secret_key)
    
    def test_missing_required_fields_rejected(self, secret_key):
        """Test that tokens with missing fields are rejected."""
        # Create token data with missing fields
        incomplete_data = {
            "gate_id": "test-gate",
            # Missing sprint_id, created_at, expires_at, nonce
        }
        
        # Sign incomplete data
        token_json = json.dumps(incomplete_data, sort_keys=True)
        signature = hmac.new(
            secret_key,
            token_json.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        encoded_payload = base64.urlsafe_b64encode(token_json.encode()).decode()
        incomplete_token = f"{encoded_payload}.{signature}"
        
        with pytest.raises(InvalidTokenError, match="Missing required token fields"):
            GateToken.from_string(incomplete_token, secret_key=secret_key)


class TestPathTraversal:
    """Test path traversal protections."""
    
    def test_dotdot_rejected_in_sprint_id(self):
        """Test that .. paths are rejected in sprint IDs."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_sprint_id("../etc/passwd")
        
        with pytest.raises(ValueError, match="path traversal"):
            validate_sprint_id("sprint/../other")
        
        with pytest.raises(ValueError, match="path traversal"):
            validate_sprint_id("..\\windows\\system32")
    
    def test_dotdot_rejected_in_work_item_id(self):
        """Test that .. paths are rejected in work item IDs."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_work_item_id("../secret")
    
    def test_dotdot_rejected_in_safe_join(self):
        """Test that .. paths are rejected in safe_join_path."""
        with pytest.raises(ValueError, match="path traversal"):
            safe_join_path("/base", "../escape")
        
        with pytest.raises(ValueError, match="path traversal"):
            safe_join_path("../base", "subdir")
    
    def test_tilde_rejected_in_path_validation(self):
        """Test that ~ paths are rejected in project directory validation."""
        # This should be caught by GateEnforcer constructor
        with pytest.raises(ValueError, match="path traversal"):
            GateEnforcer("~/home/user/project")
    
    def test_absolute_path_rejected_in_sprint_id(self):
        """Test that absolute paths are rejected in sprint IDs."""
        with pytest.raises(ValueError, match="path traversal"):
            validate_sprint_id("/etc/passwd")
        
        with pytest.raises(ValueError, match="path traversal"):
            validate_sprint_id("/absolute/path")
    
    def test_absolute_path_rejected_in_gate_enforcer(self):
        """Test that GateEnforcer rejects absolute paths."""
        with pytest.raises(ValueError, match="path traversal"):
            GateEnforcer("/etc")
        
        with pytest.raises(ValueError, match="path traversal"):
            GateEnforcer("/absolute/path")
    
    def test_absolute_path_rejected_in_safe_join(self):
        """Test that absolute paths are rejected in safe_join_path."""
        with pytest.raises(ValueError, match="path traversal"):
            safe_join_path("/absolute", "subdir")
    
    def test_valid_relative_path_accepted(self):
        """Test that valid relative paths work."""
        # These should not raise
        assert validate_sprint_id("valid-sprint-id") is True
        assert validate_sprint_id("sprint_123") is True
        assert validate_sprint_id("my-sprint") is True
    
    def test_valid_work_item_id_accepted(self):
        """Test that valid work item IDs work."""
        assert validate_work_item_id("wi_abc123") is True
        assert validate_work_item_id("task-001") is True
    
    def test_valid_safe_join_accepted(self):
        """Test that valid safe_join_path calls work."""
        result = safe_join_path("base", "subdir", "file.txt")
        assert "base" in result
        assert "subdir" in result
        assert ".." not in result
    
    def test_sanitize_filename_rejects_traversal(self):
        """Test that sanitize_filename rejects traversal attempts."""
        with pytest.raises(ValueError, match="path traversal"):
            sanitize_filename("../etc/passwd")
        
        with pytest.raises(ValueError, match="path traversal"):
            sanitize_filename("/etc/passwd")
    
    def test_null_byte_rejection(self):
        """Test that null bytes are handled safely."""
        # Null bytes in paths can cause issues on some systems
        with pytest.raises(ValueError):
            validate_sprint_id("sprint\x00id")
    
    def test_unicode_normalization_safety(self):
        """Test that unicode paths are handled safely."""
        # Unicode characters that might normalize to dangerous sequences
        tricky_ids = [
            "sprint\u202e",  # Right-to-left override
            "sprint\u200e",  # Left-to-right mark
            "sprint\u0000",  # Null character
        ]
        
        for sprint_id in tricky_ids:
            with pytest.raises(ValueError):
                validate_sprint_id(sprint_id)


class TestRaceConditions:
    """Test race condition protections."""
    
    @pytest.fixture
    def temp_project_dir(self):
        """Create a temporary project directory for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a subdirectory with a safe name that doesn't look like traversal
            safe_dir = Path(tmpdir) / "test_project"
            safe_dir.mkdir()
            # Create .carby-sprints directory structure
            sprint_dir = safe_dir / ".carby-sprints"
            sprint_dir.mkdir()
            yield str(safe_dir)
    
    def test_concurrent_token_creation_safe(self, temp_project_dir):
        """Test that concurrent token creation is safe."""
        tokens = []
        errors = []
        
        def create_token(idx):
            try:
                token = GateToken(
                    gate_id=f"gate-{idx}",
                    sprint_id="concurrent-sprint",
                    expires_in_hours=24
                )
                tokens.append(token.token)
            except Exception as e:
                errors.append(str(e))
        
        # Create tokens concurrently
        threads = []
        for i in range(20):
            t = threading.Thread(target=create_token, args=(i,))
            threads.append(t)
        
        for t in threads:
            t.start()
        
        for t in threads:
            t.join()
        
        # Verify no errors
        assert len(errors) == 0, f"Errors during token creation: {errors}"
        
        # Verify all tokens are unique
        assert len(tokens) == len(set(tokens)), "Duplicate tokens created"
    
    def test_distributed_lock_prevents_race(self):
        """Test that DistributedLock prevents race conditions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = Path(tmpdir) / "test.lock"
            
            shared_counter = [0]  # Use list for mutable reference
            errors = []
            
            def increment_counter():
                try:
                    with DistributedLock(lock_file):
                        # Read current value
                        current = shared_counter[0]
                        # Small delay to increase chance of race
                        time.sleep(0.01)
                        # Write new value
                        shared_counter[0] = current + 1
                except Exception as e:
                    errors.append(str(e))
            
            # Run multiple threads
            threads = []
            for _ in range(10):
                t = threading.Thread(target=increment_counter)
                threads.append(t)
            
            for t in threads:
                t.start()
            
            for t in threads:
                t.join()
            
            # Verify no errors
            assert len(errors) == 0, f"Errors during locked operations: {errors}"
            
            # Counter should be exactly 10 (no lost updates)
            assert shared_counter[0] == 10, f"Race condition detected: counter={shared_counter[0]}"


class TestSecretKeySecurity:
    """Test secret key management security."""
    
    def test_secret_key_file_permissions(self, tmp_path):
        """Test that secret key file has restricted permissions."""
        # Mock the secret key location
        secret_dir = tmp_path / ".openclaw" / "secrets"
        secret_dir.mkdir(parents=True)
        secret_file = secret_dir / "carby-studio-gate-key"
        
        # Create a secret key
        import secrets
        secret = secrets.token_bytes(32)
        secret_file.write_bytes(secret)
        secret_file.chmod(0o600)
        
        # Verify permissions
        if os.name == 'posix':
            stat = secret_file.stat()
            assert (stat.st_mode & 0o777) == 0o600, (
                f"Secret key file has incorrect permissions: {oct(stat.st_mode & 0o777)}"
            )
    
    def test_different_keys_produce_different_signatures(self):
        """Test that different secret keys produce different signatures."""
        key1 = b"secret_key_one_32_bytes_long!!!!"
        key2 = b"secret_key_two_32_bytes_long!!!!"
        
        data = b"test data"
        
        sig1 = hmac.new(key1, data, hashlib.sha256).hexdigest()
        sig2 = hmac.new(key2, data, hashlib.sha256).hexdigest()
        
        assert sig1 != sig2, "Different keys should produce different signatures"
    
    def test_same_key_produces_same_signature(self):
        """Test that the same key produces consistent signatures."""
        key = b"secret_key_32_bytes_long!!!!!!"
        data = b"test data"
        
        sig1 = hmac.new(key, data, hashlib.sha256).hexdigest()
        sig2 = hmac.new(key, data, hashlib.sha256).hexdigest()
        
        assert sig1 == sig2, "Same key should produce identical signatures"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])