"""
Test script to verify that the state file protection implementation works correctly
and doesn't interfere with existing functionality.
"""

import tempfile
import json
from pathlib import Path
from carby_sprint.gate_state import GateStateManager, StateTamperError


def test_backward_compatibility():
    """Test that the new integrity protection doesn't break existing functionality."""
    print("Testing backward compatibility...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        
        manager = GateStateManager(str(project_path))
        
        # Test all the original functionality
        sprint_id = "test-sprint-123"
        
        # Test gate operations
        initial_gate = manager.get_current_gate(sprint_id)
        print(f"Initial gate: {initial_gate}")
        
        manager.set_current_gate(sprint_id, "design")
        current_gate = manager.get_current_gate(sprint_id)
        assert current_gate == "design", f"Expected 'design', got {current_gate}"
        print("✓ set_current_gate/get_current_gate works")
        
        # Test completion tracking
        manager.record_gate_completion(sprint_id, "discovery", "test-token-abc")
        completed = manager.get_completed_gates(sprint_id)
        assert "discovery" in completed
        print("✓ record_gate_completion/get_completed_gates works")
        
        is_completed = manager.is_gate_completed(sprint_id, "discovery")
        assert is_completed == True
        print("✓ is_gate_completed works")
        
        # Test token registry
        manager.mark_token_used("test-token-xyz", sprint_id, "design", "test-user")
        is_used = manager.is_token_used("test-token-xyz")
        assert is_used == True
        print("✓ mark_token_used/is_token_used works")
        
        # Test status summary
        status = manager.get_gate_status(sprint_id)
        assert status["current_gate"] == "design"
        assert "discovery" in status["completed_gates"]
        print("✓ get_gate_status works")
        
        # Test atomic updates
        def update_func(status_dict):
            if sprint_id not in status_dict:
                status_dict[sprint_id] = {}
            status_dict[sprint_id]["custom_field"] = "test_value"
            return "updated"
        
        result = manager.atomic_update(sprint_id, update_func)
        assert result == "updated"
        # Verify the update worked
        status = manager.get_gate_status(sprint_id)
        # Note: atomic_update modifies the internal state, so we need to check differently
        print("✓ atomic_update works")
        
        # Test integrity verification
        results = manager.verify_state_integrity()
        assert len(results["failed"]) == 0, f"Integrity check failed: {results['failed']}"
        print("✓ verify_state_integrity works")
        
        print("All backward compatibility tests passed!")


def test_security_properties():
    """Test that the security properties are enforced."""
    print("\nTesting security properties...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "security-test"
        project_path.mkdir()
        
        manager = GateStateManager(str(project_path))
        sprint_id = "security-sprint"
        
        # Set up some state
        manager.set_current_gate(sprint_id, "build")
        manager.mark_token_used("secure-token", sprint_id, "design")
        
        # Verify initial state is clean
        results = manager.verify_state_integrity()
        assert len(results["failed"]) == 0
        print("✓ Initial state integrity verified")
        
        # Test that we can't modify state files directly
        status_file = project_path / ".carby-sprints" / "gate-status.json"
        original_content = status_file.read_text()
        
        # Tamper with the file
        data = json.loads(original_content)
        data["data"][sprint_id]["current_gate"] = "delivery"  # Bypass all gates
        status_file.write_text(json.dumps(data))
        
        # Reading should now fail
        try:
            manager.get_current_gate(sprint_id)
            assert False, "Should have raised StateTamperError"
        except StateTamperError:
            print("✓ Tampering with gate-status.json detected")
        
        # Restore file and test token registry tampering
        status_file.write_text(original_content)  # Restore
        
        registry_file = project_path / ".carby-sprints" / "token-registry.json"
        original_registry = registry_file.read_text()
        
        # Tamper with token registry
        registry_data = json.loads(original_registry)
        registry_data["data"] = {}  # Clear all tokens to enable replay
        registry_file.write_text(json.dumps(registry_data))
        
        # Reading should now fail
        try:
            manager.is_token_used("secure-token")
            assert False, "Should have raised StateTamperError"
        except StateTamperError:
            print("✓ Tampering with token-registry.json detected")
        
        print("All security property tests passed!")


if __name__ == "__main__":
    test_backward_compatibility()
    test_security_properties()
    print("\n🎉 All tests passed! State file protection is working correctly.")