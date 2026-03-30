#!/usr/bin/env python3
"""
Demonstration of state file tamper detection.

This script shows how the HMAC-based integrity protection prevents
direct modification of state files.
"""

import tempfile
import json
from pathlib import Path
from carby_sprint.gate_state import GateStateManager, StateTamperError


def demonstrate_tamper_detection():
    """Demonstrate how tamper detection works."""
    print("=== State File Tamper Detection Demo ===\n")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        project_path = Path(temp_dir) / "demo-project"
        project_path.mkdir()
        
        print(f"1. Creating project at: {project_path}")
        manager = GateStateManager(str(project_path))
        
        print("\n2. Setting initial gate status...")
        manager.set_current_gate("demo-sprint", "discovery")
        print(f"   Current gate: {manager.get_current_gate('demo-sprint')}")
        
        print("\n3. Recording gate completion...")
        manager.record_gate_completion("demo-sprint", "discovery", "demo-token-123")
        print(f"   Completed gates: {manager.get_completed_gates('demo-sprint')}")
        
        print("\n4. Marking token as used...")
        manager.mark_token_used("demo-token-123", "demo-sprint", "discovery", "demo-user")
        print(f"   Token used: {manager.is_token_used('demo-token-123')}")
        
        print("\n5. Verifying all state integrity...")
        results = manager.verify_state_integrity()
        print(f"   Verified files: {results['verified']}")
        print(f"   Failed files: {results['failed']}")
        
        # Now demonstrate tampering detection
        print("\n6. Attempting to tamper with gate-status.json...")
        status_file = project_path / ".carby-sprints" / "gate-status.json"
        
        # Read the current file
        raw_data = json.loads(status_file.read_text())
        print(f"   Original current_gate: {raw_data['data']['demo-sprint']['current_gate']}")
        
        # Tamper with the data
        raw_data['data']['demo-sprint']['current_gate'] = 'delivery'  # Bypass all gates!
        status_file.write_text(json.dumps(raw_data))
        print("   Tampered current_gate to 'delivery'")
        
        print("\n7. Attempting to read tampered file (should fail)...")
        try:
            current_gate = manager.get_current_gate("demo-sprint")
            print(f"   ERROR: Got gate: {current_gate} - tamper detection failed!")
        except StateTamperError as e:
            print(f"   SUCCESS: Tamper detected! Error: {e}")
        
        print("\n8. Attempting to tamper with token registry...")
        registry_file = project_path / ".carby-sprints" / "token-registry.json"
        
        # Read the current file
        raw_registry = json.loads(registry_file.read_text())
        print(f"   Original token registry size: {len(raw_registry['data'])}")
        
        # Tamper by clearing the registry to allow token replay
        raw_registry['data'] = {}
        registry_file.write_text(json.dumps(raw_registry))
        print("   Cleared token registry (would allow token replay)")
        
        print("\n9. Attempting to check tampered token registry (should fail)...")
        try:
            is_used = manager.is_token_used("demo-token-123")
            print(f"   ERROR: Token check succeeded: {is_used} - tamper detection failed!")
        except StateTamperError as e:
            print(f"   SUCCESS: Tamper detected! Error: {e}")
        
        print("\n=== Demo Complete ===")
        print("The state file protection successfully prevented:")
        print("- Bypassing gates by directly modifying gate-status.json")
        print("- Token replay attacks by modifying token-registry.json")


if __name__ == "__main__":
    demonstrate_tamper_detection()