"""
Test suite for gate enforcement functionality.

Tests the server-side gate enforcement system with HMAC-signed tokens,
expiration validation, and bypass prevention mechanisms.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import json

from carby_sprint.gate_enforcer import GateEnforcer, GateToken, InvalidTokenError, ExpiredTokenError, GateBypassError


def test_gate_token_creation():
    """Test basic gate token creation and serialization."""
    token = GateToken(gate_id="test-gate", sprint_id="test-sprint")
    
    assert token.gate_id == "test-gate"
    assert token.sprint_id == "test-sprint"
    assert token.is_valid() is True
    assert token.token is not None
    assert len(token.token) > 0


def test_gate_token_serialization():
    """Test token serialization and deserialization."""
    original_token = GateToken(gate_id="test-gate", sprint_id="test-sprint")
    token_str = original_token.token
    
    # Deserialize the token
    restored_token = GateToken.from_string(token_str)
    
    assert restored_token.gate_id == original_token.gate_id
    assert restored_token.sprint_id == original_token.sprint_id
    assert restored_token.nonce == original_token.nonce


def test_gate_token_verification():
    """Test that tokens can be verified correctly."""
    token = GateToken(gate_id="test-gate", sprint_id="test-sprint")
    
    # Verify the token using the GateEnforcer method
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        enforcer = GateEnforcer(str(project_path))
        is_valid, gate_id, sprint_id = enforcer.validate_gate_token(token.token)
        
        assert is_valid is True
        assert gate_id == "test-gate"
        assert sprint_id == "test-sprint"


def test_gate_token_tampering():
    """Test that tampered tokens are rejected."""
    token = GateToken(gate_id="test-gate", sprint_id="test-sprint")
    
    # Tamper with the token by modifying the signature part
    parts = token.token.split('.', 1)  # Split into payload and signature only
    original_payload = parts[0]
    original_signature = parts[1]
    
    # Create a tampered token by changing the payload
    import base64
    import json
    decoded_payload = base64.urlsafe_b64decode(original_payload).decode()
    payload_data = json.loads(decoded_payload)
    
    # Modify one field in the payload
    payload_data['gate_id'] = 'tampered-gate'
    
    # Re-encode the modified payload
    modified_payload_json = json.dumps(payload_data, separators=(',', ':'), sort_keys=True)
    modified_payload = base64.urlsafe_b64encode(modified_payload_json.encode()).decode()
    
    # Use the original signature with the modified payload (this should fail verification)
    tampered_token = f"{modified_payload}.{original_signature}"
    
    # Should fail validation
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        enforcer = GateEnforcer(str(project_path))
        is_valid, _, _ = enforcer.validate_gate_token(tampered_token)
        assert is_valid is False


def test_expired_token():
    """Test that expired tokens are rejected."""
    # Create a token with very short expiration
    token = GateToken(gate_id="test-gate", sprint_id="test-sprint", expires_in_hours=0)
    
    # The token should be expired immediately
    assert token.is_valid() is False


def test_gate_enforcer_initialization():
    """Test gate enforcer initialization."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        enforcer = GateEnforcer(str(project_path))
        
        assert enforcer.project_dir == project_path
        assert enforcer.sprint_dir.exists()


def test_gate_sequence_enforcement():
    """Test that gate sequence is enforced."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        enforcer = GateEnforcer(str(project_path))
        sprint_id = "test-sprint"
        
        # Initially, should be at first gate
        current_gate = enforcer._get_current_gate(sprint_id)
        assert current_gate == "discovery"
        
        # Request token for first gate
        token = enforcer.request_gate_token(sprint_id, "discovery")
        
        # Complete the first gate
        enforcer._record_gate_completion(sprint_id, "discovery", token.token)
        
        # Now we should be able to advance to next gate
        can_advance = enforcer.can_advance(sprint_id, "discovery", "design")
        assert can_advance is True
        
        # But not to a later gate
        can_advance_later = enforcer.can_advance(sprint_id, "discovery", "build")
        assert can_advance_later is False


def test_gate_advancement():
    """Test that gate advancement works correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        enforcer = GateEnforcer(str(project_path))
        sprint_id = "test-sprint"
        
        # Request token for design gate
        token = enforcer.request_gate_token(sprint_id, "design")
        
        # Complete discovery first
        discovery_token = enforcer.request_gate_token(sprint_id, "discovery")
        enforcer._record_gate_completion(sprint_id, "discovery", discovery_token.token)
        
        # Now advance to design
        result = enforcer.advance_gate(sprint_id, "design", token.token)
        assert result is True
        
        # Check that the current gate is now design
        status = enforcer.get_gate_status(sprint_id)
        assert status["current_gate"] == "design"


def test_gate_bypass_prevention():
    """Test that gate bypass attempts are prevented."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        enforcer = GateEnforcer(str(project_path))
        sprint_id = "test-sprint"
        
        # Request token for build gate
        token = enforcer.request_gate_token(sprint_id, "build")
        
        # Try to advance to build without completing discovery and design
        # This should fail because prerequisites aren't met
        try:
            enforcer.advance_gate(sprint_id, "build", token.token)
            assert False, "Should have raised GateBypassError"
        except GateBypassError:
            # Expected behavior
            pass


def test_invalid_token_rejection():
    """Test that invalid tokens are rejected."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        enforcer = GateEnforcer(str(project_path))
        sprint_id = "test-sprint"
        
        # Try to advance with an invalid token
        try:
            enforcer.advance_gate(sprint_id, "design", "invalid-token")
            assert False, "Should have raised GateBypassError"
        except GateBypassError:
            # Expected behavior
            pass


def test_gate_status():
    """Test gate status reporting."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        enforcer = GateEnforcer(str(project_path))
        sprint_id = "test-sprint"
        
        # Get initial status
        status = enforcer.get_gate_status(sprint_id)
        
        assert status["sprint_id"] == sprint_id
        assert status["current_gate"] == "discovery"
        assert status["next_gate"] == "design"
        assert status["project_dir"] == str(project_path)
        assert len(status["completed_gates"]) == 0


if __name__ == "__main__":
    # Run tests
    test_gate_token_creation()
    test_gate_token_serialization()
    test_gate_token_verification()
    test_gate_token_tampering()
    test_expired_token()
    test_gate_enforcer_initialization()
    test_gate_sequence_enforcement()
    test_gate_advancement()
    test_gate_bypass_prevention()
    test_invalid_token_rejection()
    test_gate_status()
    
    print("All gate enforcement tests passed!")