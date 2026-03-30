"""
Test suite for state file integrity protection.

Tests HMAC-based tamper detection for gate-status.json and token-registry.json files.
"""

import pytest
import tempfile
import json
import os
from pathlib import Path
from datetime import datetime

from carby_sprint.gate_state import (
    GateStateManager, 
    StateIntegrityManager, 
    StateTamperError
)


class TestStateIntegrityManager:
    """Tests for the StateIntegrityManager class."""
    
    def test_key_generation(self):
        """Test that HMAC key is generated and stored securely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            
            # Key file should exist with restricted permissions
            key_file = project_path / ".carby-sprints" / ".state-key"
            assert key_file.exists()
            
            # Check permissions (owner read/write only = 0o600)
            stat_info = key_file.stat()
            assert stat_info.st_mode & 0o777 == 0o600
    
    def test_key_persistence(self):
        """Test that key persists across manager instances."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            # Create first manager
            integrity1 = StateIntegrityManager(project_path)
            
            # Create second manager for same project
            integrity2 = StateIntegrityManager(project_path)
            
            # Both should have the same key
            assert integrity1._key == integrity2._key
    
    def test_sign_and_verify(self):
        """Test signing and verifying state data."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            
            # Create test data
            test_data = {
                "sprint-123": {
                    "current_gate": "design",
                    "completed_gates": ["discovery"]
                }
            }
            
            state_file = project_path / ".carby-sprints" / "test-state.json"
            
            # Sign the data
            wrapped = integrity.sign_state(state_file, test_data)
            
            # Verify structure
            assert "_integrity" in wrapped
            assert "data" in wrapped
            assert wrapped["_integrity"]["algorithm"] == "HMAC-SHA256"
            assert wrapped["_integrity"]["version"] == 1
            assert "signature" in wrapped["_integrity"]
            
            # Verify the data
            verified_data = integrity.verify_state(state_file, wrapped)
            assert verified_data == test_data
    
    def test_tamper_detection_payload(self):
        """Test detection of payload tampering."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            
            # Create and sign test data
            test_data = {"key": "original_value"}
            state_file = project_path / ".carby-sprints" / "test-state.json"
            wrapped = integrity.sign_state(state_file, test_data)
            
            # Tamper with the data
            wrapped["data"]["key"] = "tampered_value"
            
            # Verification should fail
            with pytest.raises(StateTamperError) as exc_info:
                integrity.verify_state(state_file, wrapped)
            
            assert "tampered" in str(exc_info.value).lower()
    
    def test_tamper_detection_signature(self):
        """Test detection of signature tampering."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            
            # Create and sign test data
            test_data = {"key": "value"}
            state_file = project_path / ".carby-sprints" / "test-state.json"
            wrapped = integrity.sign_state(state_file, test_data)
            
            # Tamper with the signature
            wrapped["_integrity"]["signature"] = "fake_signature_12345"
            
            # Verification should fail
            with pytest.raises(StateTamperError) as exc_info:
                integrity.verify_state(state_file, wrapped)
            
            assert "tampered" in str(exc_info.value).lower()
    
    def test_legacy_unsigned_data_rejection(self):
        """Test that legacy unsigned data is rejected."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            
            # Create legacy unsigned data
            legacy_data = {"key": "value"}
            state_file = project_path / ".carby-sprints" / "test-state.json"
            
            # Verification should fail for unsigned data
            with pytest.raises(StateTamperError) as exc_info:
                integrity.verify_state(state_file, legacy_data)
            
            assert "no integrity protection" in str(exc_info.value).lower()
    
    def test_master_signature_file_creation(self):
        """Test that master signature file is created."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            
            # Create and sign test data
            test_data = {"key": "value"}
            state_file = project_path / ".carby-sprints" / "test-state.json"
            integrity.sign_state(state_file, test_data)
            
            # Master signature file should exist
            master_file = project_path / ".carby-sprints" / ".state-signatures.json"
            assert master_file.exists()
            
            # Check permissions
            stat_info = master_file.stat()
            assert stat_info.st_mode & 0o777 == 0o600
    
    def test_master_signature_cross_check(self):
        """Test that master signature is used for cross-verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            
            # Create and sign test data
            test_data = {"key": "value"}
            state_file = project_path / ".carby-sprints" / "test-state.json"
            wrapped = integrity.sign_state(state_file, test_data)
            
            # Tamper with master signature file
            master_file = project_path / ".carby-sprints" / ".state-signatures.json"
            master_data = json.loads(master_file.read_text())
            master_data["test-state.json"]["signature"] = "tampered_sig"
            master_file.write_text(json.dumps(master_data))
            
            # Verification should detect mismatch
            with pytest.raises(StateTamperError) as exc_info:
                integrity.verify_state(state_file, wrapped)
            
            assert "master record" in str(exc_info.value).lower()
    
    def test_verify_all_states(self):
        """Test batch verification of all state files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            sprint_dir = project_path / ".carby-sprints"
            
            # Create multiple state files
            for i in range(3):
                test_data = {"index": i}
                state_file = sprint_dir / f"state-{i}.json"
                wrapped = integrity.sign_state(state_file, test_data)
                state_file.write_text(json.dumps(wrapped))
            
            # Verify all states
            results = integrity.verify_all_states()
            
            assert len(results["verified"]) == 3
            assert len(results["failed"]) == 0
            assert len(results["missing"]) == 0
    
    def test_verify_all_states_with_failures(self):
        """Test batch verification with tampered files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            integrity = StateIntegrityManager(project_path)
            sprint_dir = project_path / ".carby-sprints"
            
            # Create valid state file
            wrapped1 = integrity.sign_state(sprint_dir / "valid.json", {"key": "value"})
            (sprint_dir / "valid.json").write_text(json.dumps(wrapped1))
            
            # Create tampered state file
            wrapped2 = integrity.sign_state(sprint_dir / "tampered.json", {"key": "value"})
            wrapped2["data"]["key"] = "tampered"
            (sprint_dir / "tampered.json").write_text(json.dumps(wrapped2))
            
            # Verify all states
            results = integrity.verify_all_states()
            
            assert "valid.json" in results["verified"]
            assert len(results["failed"]) == 1
            assert results["failed"][0]["file"] == "tampered.json"


class TestGateStateManagerIntegrity:
    """Tests for GateStateManager with integrity protection."""
    
    def test_gate_status_signed_on_save(self):
        """Test that gate status is signed when saved."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            manager = GateStateManager(str(project_path))
            
            # Set some gate status
            manager.set_current_gate("sprint-123", "design")
            
            # Read the file directly
            status_file = project_path / ".carby-sprints" / "gate-status.json"
            raw_data = json.loads(status_file.read_text())
            
            # Should have integrity wrapper
            assert "_integrity" in raw_data
            assert "data" in raw_data
            assert raw_data["_integrity"]["algorithm"] == "HMAC-SHA256"
    
    def test_gate_status_verified_on_load(self):
        """Test that gate status is verified when loaded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            manager = GateStateManager(str(project_path))
            
            # Set and retrieve gate status
            manager.set_current_gate("sprint-123", "design")
            current_gate = manager.get_current_gate("sprint-123")
            
            assert current_gate == "design"
    
    def test_gate_status_tamper_detection(self):
        """Test tamper detection on gate status file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            manager = GateStateManager(str(project_path))
            
            # Set some gate status
            manager.set_current_gate("sprint-123", "design")
            
            # Tamper with the file
            status_file = project_path / ".carby-sprints" / "gate-status.json"
            raw_data = json.loads(status_file.read_text())
            raw_data["data"]["sprint-123"]["current_gate"] = "delivery"
            status_file.write_text(json.dumps(raw_data))
            
            # Loading should fail with tamper error
            with pytest.raises(StateTamperError):
                manager.get_current_gate("sprint-123")
    
    def test_token_registry_signed_on_save(self):
        """Test that token registry is signed when saved."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            manager = GateStateManager(str(project_path))
            
            # Mark a token as used
            manager.mark_token_used("test-token-123", "sprint-123", "design", "user-456")
            
            # Read the file directly
            registry_file = project_path / ".carby-sprints" / "token-registry.json"
            raw_data = json.loads(registry_file.read_text())
            
            # Should have integrity wrapper
            assert "_integrity" in raw_data
            assert "data" in raw_data
    
    def test_token_registry_tamper_detection(self):
        """Test tamper detection on token registry file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            manager = GateStateManager(str(project_path))
            
            # Mark a token as used
            manager.mark_token_used("test-token-123", "sprint-123", "design", "user-456")
            
            # Tamper with the file - remove the token entry to allow replay
            registry_file = project_path / ".carby-sprints" / "token-registry.json"
            raw_data = json.loads(registry_file.read_text())
            raw_data["data"] = {}  # Clear all tokens
            registry_file.write_text(json.dumps(raw_data))
            
            # Checking token should fail with tamper error
            with pytest.raises(StateTamperError):
                manager.is_token_used("test-token-123")
    
    def test_verify_state_integrity_method(self):
        """Test the verify_state_integrity method."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            manager = GateStateManager(str(project_path))
            
            # Create some state
            manager.set_current_gate("sprint-1", "design")
            manager.set_current_gate("sprint-2", "build")
            manager.mark_token_used("token-1", "sprint-1", "design")
            
            # Verify all states
            results = manager.verify_state_integrity()
            
            assert len(results["verified"]) == 2  # gate-status and token-registry
            assert len(results["failed"]) == 0
    
    def test_concurrent_access_integrity(self):
        """Test integrity with concurrent access."""
        import threading
        
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir) / "test-project"
            project_path.mkdir()
            
            manager = GateStateManager(str(project_path))
            errors = []
            
            def worker(thread_id):
                try:
                    for i in range(10):
                        sprint_id = f"sprint-{thread_id}-{i}"
                        manager.set_current_gate(sprint_id, "design")
                        manager.record_gate_completion(sprint_id, "discovery", f"token-{i}")
                except Exception as e:
                    errors.append(e)
            
            # Run multiple threads concurrently
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            
            # No errors should occur
            assert len(errors) == 0
            
            # Verify all states are intact
            results = manager.verify_state_integrity()
            assert len(results["failed"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
            
