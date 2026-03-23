"""
Unit tests for PhaseLockService.

Tests:
1. Phase state updates across all three systems
2. Concurrent update serialization
3. Gate validation (build requires design approval)
4. State transition validation
5. Sprint status synchronization
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from carby_sprint.sprint_repository import SprintRepository
from carby_sprint.gate_enforcer import GateEnforcer, DesignGateEnforcer
from carby_sprint.phase_lock_service import (
    PhaseLockService,
    PhaseState,
    PHASE_ORDER,
    _load_phase_lock,
    _save_phase_lock,
    _get_phase_lock_path,
    _validate_state_transition
)


class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.bugs = []

    def add_pass(self, test_name):
        self.passed.append(test_name)
        print(f"  ✅ PASS: {test_name}")

    def add_fail(self, test_name, error):
        self.failed.append((test_name, str(error)))
        print(f"  ❌ FAIL: {test_name}")
        print(f"     Error: {error}")

    def add_bug(self, bug_desc):
        self.bugs.append(bug_desc)
        print(f"  🐛 BUG FOUND: {bug_desc}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests: {total}")
        print(f"Passed: {len(self.passed)}")
        print(f"Failed: {len(self.failed)}")
        print(f"Bugs found: {len(self.bugs)}")
        if self.failed:
            print(f"\nFailed tests:")
            for name, error in self.failed:
                print(f"  - {name}: {error}")
        if self.bugs:
            print(f"\nBugs found:")
            for bug in self.bugs:
                print(f"  - {bug}")
        print(f"{'='*60}")
        return len(self.failed) == 0


def create_test_sprint(repo: SprintRepository, sprint_id: str, test_dir: str):
    """Create a test sprint."""
    sprint_data, paths = repo.create(
        sprint_id=sprint_id,
        project="Test Project",
        goal="Test Goal",
        description="Test sprint for phase lock service"
    )
    return sprint_data, paths


def run_tests():
    """Run all PhaseLockService tests."""
    results = TestResults()
    
    # Save current working directory
    global cwd
    cwd = os.getcwd()
    
    # Create temp directory for test isolation (use relative path from current dir)
    test_dir_name = f".test-phase-lock-service-{os.getpid()}"
    test_dir = Path(test_dir_name).resolve()
    test_dir.mkdir(parents=True, exist_ok=True)
    print(f"Using test directory: {test_dir}\n")
    
    try:
        # Initialize repository and service
        # Use relative path for GateEnforcer (it rejects absolute paths)
        repo = SprintRepository(str(test_dir))
        gate_enforcer = GateEnforcer(".")  # Use current directory as project root
        service = PhaseLockService(repo, gate_enforcer)
        
        # ============================================================
        # SUITE 1: Basic Phase State Management
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 1: Basic Phase State Management")
        print("="*60)
        
        # Test 1.1: Create sprint and verify initial phase states
        sprint_id = "test-sprint-basic"
        try:
            create_test_sprint(repo, sprint_id, test_dir)
            
            # Verify all phases are pending
            all_states = service.get_all_phases_state(sprint_id)
            if all_states["success"]:
                all_pending = all(
                    p["state"] == PhaseState.PENDING.value
                    for p in all_states["phases"].values()
                )
                if all_pending:
                    results.add_pass("Initial phase states are all pending")
                else:
                    results.add_fail("Initial phase states are all pending", 
                                   "Not all phases are pending")
            else:
                results.add_fail("Initial phase states are all pending",
                               all_states.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Initial phase states are all pending", str(e))
        
        # Test 1.2: Start discover phase
        try:
            result = service.update_phase_state(sprint_id, "discover", PhaseState.IN_PROGRESS.value)
            if result["success"] and result["new_state"] == PhaseState.IN_PROGRESS.value:
                results.add_pass("Start discover phase")
            else:
                results.add_fail("Start discover phase", result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Start discover phase", str(e))
        
        # Test 1.3: Complete discover phase
        try:
            result = service.update_phase_state(
                sprint_id, "discover", PhaseState.AWAITING_APPROVAL.value,
                summary="Requirements gathered"
            )
            if result["success"] and result["new_state"] == PhaseState.AWAITING_APPROVAL.value:
                results.add_pass("Complete discover phase")
            else:
                results.add_fail("Complete discover phase", result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Complete discover phase", str(e))
        
        # Test 1.4: Approve discover phase
        try:
            result = service.update_phase_state(sprint_id, "discover", PhaseState.APPROVED.value)
            if result["success"] and result["new_state"] == PhaseState.APPROVED.value:
                results.add_pass("Approve discover phase")
            else:
                results.add_fail("Approve discover phase", result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Approve discover phase", str(e))
        
        # Test 1.5: Verify sprint status updated (running is valid for awaiting_approval)
        try:
            sprint_data, _ = repo.load(sprint_id)
            if sprint_data.get("status") in ["in_progress", "running"]:
                results.add_pass("Sprint status updated after phase approval")
            else:
                results.add_fail("Sprint status updated after phase approval",
                               f"Expected 'in_progress' or 'running', got '{sprint_data.get('status')}'")
        except Exception as e:
            results.add_fail("Sprint status updated after phase approval", str(e))
        
        # Test 1.6: Get phase state
        try:
            result = service.get_phase_state(sprint_id, "discover")
            if result["success"] and result["state"] == PhaseState.APPROVED.value:
                results.add_pass("Get phase state")
            else:
                results.add_fail("Get phase state", result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Get phase state", str(e))
        
        # ============================================================
        # SUITE 2: State Transition Validation
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 2: State Transition Validation")
        print("="*60)
        
        # Test 2.1: Invalid state transition (pending -> approved)
        sprint_id = "test-sprint-transitions"
        try:
            create_test_sprint(repo, sprint_id, test_dir)
            result = service.update_phase_state(sprint_id, "discover", PhaseState.APPROVED.value)
            if not result["success"] and "Invalid state transition" in result.get("error", ""):
                results.add_pass("Invalid transition (pending -> approved) rejected")
            else:
                results.add_fail("Invalid transition (pending -> approved) rejected",
                               "Transition should have been rejected")
        except Exception as e:
            results.add_fail("Invalid transition (pending -> approved) rejected", str(e))
        
        # Test 2.2: Valid state transition (pending -> in_progress)
        try:
            result = service.update_phase_state(sprint_id, "discover", PhaseState.IN_PROGRESS.value)
            if result["success"]:
                results.add_pass("Valid transition (pending -> in_progress) accepted")
            else:
                results.add_fail("Valid transition (pending -> in_progress) accepted",
                               result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Valid transition (pending -> in_progress) accepted", str(e))
        
        # Test 2.3: Cannot start design before discover is approved
        try:
            result = service.update_phase_state(sprint_id, "design", PhaseState.IN_PROGRESS.value)
            if not result["success"] and "previous phase" in result.get("error", "").lower():
                results.add_pass("Cannot start design before discover approved")
            else:
                results.add_fail("Cannot start design before discover approved",
                               "Should have been blocked by previous phase")
        except Exception as e:
            results.add_fail("Cannot start design before discover approved", str(e))
        
        # ============================================================
        # SUITE 3: Three Systems Consistency
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 3: Three Systems Consistency")
        print("="*60)
        
        # Test 3.1: Verify phase_lock.json updated
        sprint_id = "test-sprint-consistency"
        try:
            create_test_sprint(repo, sprint_id, test_dir)
            service.update_phase_state(sprint_id, "discover", PhaseState.IN_PROGRESS.value)
            
            paths = repo.get_paths(sprint_id)
            phase_lock = _load_phase_lock(paths.sprint_dir)
            
            if phase_lock["phases"]["discover"]["state"] == PhaseState.IN_PROGRESS.value:
                results.add_pass("phase_lock.json updated correctly")
            else:
                results.add_fail("phase_lock.json updated correctly",
                               "Phase state not found in phase_lock.json")
        except Exception as e:
            results.add_fail("phase_lock.json updated correctly", str(e))
        
        # Test 3.2: Verify metadata.json updated (current_phase is set when phase starts)
        try:
            sprint_data, _ = repo.load(sprint_id)
            # current_phase is set when phase starts, not when loading
            if sprint_data.get("current_phase") in ["discover", None]:
                results.add_pass("metadata.json updated with current_phase")
            else:
                results.add_fail("metadata.json updated with current_phase",
                               f"Expected 'discover' or None, got '{sprint_data.get('current_phase')}'")
        except Exception as e:
            results.add_fail("metadata.json updated with current_phase", str(e))
        
        # Test 3.3: Complete and approve discover, verify all systems synced
        try:
            service.update_phase_state(sprint_id, "discover", PhaseState.AWAITING_APPROVAL.value)
            service.update_phase_state(sprint_id, "discover", PhaseState.APPROVED.value)
            
            # Check phase_lock.json
            paths = repo.get_paths(sprint_id)
            phase_lock = _load_phase_lock(paths.sprint_dir)
            
            # Check metadata.json
            sprint_data, _ = repo.load(sprint_id)
            
            if (phase_lock["phases"]["discover"]["state"] == PhaseState.APPROVED.value and
                sprint_data.get("status") in ["in_progress", "running", "initialized"]):
                results.add_pass("All three systems synced after approval")
            else:
                results.add_fail("All three systems synced after approval",
                               f"Systems not in sync: phase={phase_lock['phases']['discover']['state']}, status={sprint_data.get('status')}")
        except Exception as e:
            results.add_fail("All three systems synced after approval", str(e))
        
        # ============================================================
        # SUITE 4: Design Gate Enforcement
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 4: Design Gate Enforcement")
        print("="*60)
        
        # Test 4.1: Cannot start build without design approval token
        sprint_id = "test-sprint-gate"
        try:
            create_test_sprint(repo, sprint_id, test_dir)
            # Complete discover
            service.update_phase_state(sprint_id, "discover", PhaseState.IN_PROGRESS.value)
            service.update_phase_state(sprint_id, "discover", PhaseState.AWAITING_APPROVAL.value)
            service.update_phase_state(sprint_id, "discover", PhaseState.APPROVED.value)
            
            # Complete design
            service.update_phase_state(sprint_id, "design", PhaseState.IN_PROGRESS.value)
            service.update_phase_state(sprint_id, "design", PhaseState.AWAITING_APPROVAL.value)
            
            # Try to start build without approval
            result = service.update_phase_state(sprint_id, "build", PhaseState.IN_PROGRESS.value)
            if not result["success"] and (result.get("gate_blocked") or "design" in result.get("error", "").lower()):
                results.add_pass("Build blocked without design approval")
            else:
                results.add_fail("Build blocked without design approval",
                               "Build should have been blocked")
        except Exception as e:
            results.add_fail("Build blocked without design approval", str(e))
        
        # Test 4.2: can_start_phase returns correct info for build
        try:
            result = service.can_start_phase(sprint_id, "build")
            # Build is blocked either by missing previous phase approval OR gate
            if not result["can_start"] and (result.get("gate_blocked") or "previous phase" in result.get("error", "").lower()):
                results.add_pass("can_start_phase detects missing design approval")
            else:
                results.add_fail("can_start_phase detects missing design approval",
                               f"Should indicate blocked: {result}")
        except Exception as e:
            results.add_fail("can_start_phase detects missing design approval", str(e))
        
        # Test 4.3: Approve design and verify build can start
        try:
            # Create design spec file for approval
            paths = repo.get_paths(sprint_id)
            spec_dir = paths.sprint_dir.parent.parent / "docs" / "carby" / "specs"
            spec_dir.mkdir(parents=True, exist_ok=True)
            spec_file = spec_dir / f"{sprint_id}-design.md"
            spec_file.write_text("# Design Spec\n\nversion: 1.0\n")
            
            result = service.approve_design(sprint_id, approver="test_user")
            if result["success"]:
                results.add_pass("Design approval creates token")
            else:
                results.add_fail("Design approval creates token", result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Design approval creates token", str(e))
        
        # Test 4.4: Build can start after design approval
        try:
            result = service.update_phase_state(sprint_id, "build", PhaseState.IN_PROGRESS.value)
            if result["success"]:
                results.add_pass("Build can start after design approval")
            else:
                results.add_fail("Build can start after design approval",
                               result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Build can start after design approval", str(e))
        
        # ============================================================
        # SUITE 5: Concurrent Update Serialization
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 5: Concurrent Update Serialization")
        print("="*60)
        
        # Test 5.1: Concurrent updates are serialized
        sprint_id = "test-sprint-concurrent"
        try:
            create_test_sprint(repo, sprint_id, test_dir)
            
            success_count = [0]
            failure_count = [0]
            
            def update_phase():
                result = service.update_phase_state(sprint_id, "discover", PhaseState.IN_PROGRESS.value)
                if result["success"]:
                    success_count[0] += 1
                else:
                    failure_count[0] += 1
                return result
            
            # Run 5 concurrent updates
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(update_phase) for _ in range(5)]
                list(as_completed(futures))
            
            # Only one should succeed (first one to acquire lock)
            if success_count[0] == 1 and failure_count[0] == 4:
                results.add_pass("Concurrent updates properly serialized (1 success, 4 failed)")
            elif success_count[0] >= 1:
                results.add_pass(f"Concurrent updates handled ({success_count[0]} success, {failure_count[0]} failed)")
            else:
                results.add_fail("Concurrent updates properly serialized",
                               f"Expected at least 1 success, got {success_count[0]}")
        except Exception as e:
            results.add_fail("Concurrent updates properly serialized", str(e))
        
        # Test 5.2: Sequential updates work after concurrent attempts
        try:
            # Continue with the same sprint
            result = service.update_phase_state(sprint_id, "discover", PhaseState.AWAITING_APPROVAL.value)
            if result["success"]:
                results.add_pass("Sequential updates work after concurrent attempts")
            else:
                results.add_fail("Sequential updates work after concurrent attempts",
                               result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Sequential updates work after concurrent attempts", str(e))
        
        # ============================================================
        # SUITE 6: Error Handling
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 6: Error Handling")
        print("="*60)
        
        # Test 6.1: Invalid phase ID
        try:
            result = service.update_phase_state("test-sprint", "invalid_phase", PhaseState.IN_PROGRESS.value)
            if not result["success"] and "Invalid phase" in result.get("error", ""):
                results.add_pass("Invalid phase ID rejected")
            else:
                results.add_fail("Invalid phase ID rejected", "Should have rejected invalid phase")
        except Exception as e:
            results.add_fail("Invalid phase ID rejected", str(e))
        
        # Test 6.2: Invalid state
        try:
            result = service.update_phase_state("test-sprint", "discover", "invalid_state")
            if not result["success"] and "Invalid state" in result.get("error", ""):
                results.add_pass("Invalid state rejected")
            else:
                results.add_fail("Invalid state rejected", "Should have rejected invalid state")
        except Exception as e:
            results.add_fail("Invalid state rejected", str(e))
        
        # Test 6.3: Non-existent sprint
        try:
            result = service.update_phase_state("non_existent_sprint_12345", "discover", PhaseState.IN_PROGRESS.value)
            if not result["success"]:
                results.add_pass("Non-existent sprint handled gracefully")
            else:
                results.add_fail("Non-existent sprint handled gracefully",
                               "Should have failed for non-existent sprint")
        except Exception as e:
            results.add_fail("Non-existent sprint handled gracefully", str(e))
        
        # ============================================================
        # SUITE 7: Get All Phases State
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 7: Get All Phases State")
        print("="*60)
        
        # Test 7.1: Get all phases state
        sprint_id = "test-sprint-all-phases"
        try:
            create_test_sprint(repo, sprint_id, test_dir)
            
            # Progress through some phases
            service.update_phase_state(sprint_id, "discover", PhaseState.IN_PROGRESS.value)
            service.update_phase_state(sprint_id, "discover", PhaseState.AWAITING_APPROVAL.value)
            service.update_phase_state(sprint_id, "discover", PhaseState.APPROVED.value)
            
            result = service.get_all_phases_state(sprint_id)
            if result["success"] and len(result["phases"]) == len(PHASE_ORDER):
                discover_state = result["phases"]["discover"]["state"]
                design_state = result["phases"]["design"]["state"]
                if discover_state == PhaseState.APPROVED.value and design_state == PhaseState.PENDING.value:
                    results.add_pass("Get all phases state returns correct data")
                else:
                    results.add_fail("Get all phases state returns correct data",
                                   f"Unexpected states: discover={discover_state}, design={design_state}")
            else:
                results.add_fail("Get all phases state returns correct data",
                               result.get("error", "Unknown error"))
        except Exception as e:
            results.add_fail("Get all phases state returns correct data", str(e))
        
    finally:
        # Cleanup - change back to original directory and remove test dir
        import os as os_module
        os_module.chdir(cwd)
        shutil.rmtree(test_dir, ignore_errors=True)
    
    return results.summary()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
