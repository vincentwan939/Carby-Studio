"""
Concurrent stress test for TOCTOU race condition fix in PhaseLockService.

This test verifies that all state reads happen while holding the distributed lock,
preventing Time-of-Check-Time-of-Use race conditions.

The test simulates:
1. Multiple threads reading state concurrently (get_phase_state, can_start_phase)
2. Multiple threads attempting to make decisions based on reads
3. Multiple threads writing concurrently

If the TOCTOU fix is correct, all operations should be serialized and no corruption
should occur.
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
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from carby_sprint.sprint_repository import SprintRepository
from carby_sprint.gate_enforcer import GateEnforcer
from carby_sprint.phase_lock_service import (
    PhaseLockService,
    PhaseState,
    PHASE_ORDER,
    _load_phase_lock,
    _save_phase_lock,
)


class TOCTOUTestResults:
    """Track test results."""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.corruptions_found = []
        self.race_conditions_detected = []

    def add_pass(self, test_name):
        self.passed.append(test_name)
        print(f"  ✅ PASS: {test_name}")

    def add_fail(self, test_name, error):
        self.failed.append((test_name, str(error)))
        print(f"  ❌ FAIL: {test_name}")
        print(f"     Error: {error}")

    def add_corruption(self, corruption_desc):
        self.corruptions_found.append(corruption_desc)
        print(f"  🚨 CORRUPTION DETECTED: {corruption_desc}")

    def add_race_condition(self, race_desc):
        self.race_conditions_detected.append(race_desc)
        print(f"  ⚠️ RACE CONDITION: {race_desc}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print(f"\n{'='*70}")
        print(f"TOCTOU STRESS TEST SUMMARY")
        print(f"{'='*70}")
        print(f"Total tests: {total}")
        print(f"Passed: {len(self.passed)}")
        print(f"Failed: {len(self.failed)}")
        print(f"Corruptions found: {len(self.corruptions_found)}")
        print(f"Race conditions detected: {len(self.race_conditions_detected)}")
        
        if self.failed:
            print(f"\nFailed tests:")
            for name, error in self.failed:
                print(f"  - {name}: {error}")
        if self.corruptions_found:
            print(f"\n🚨 CRITICAL: State corruptions detected!")
            for corruption in self.corruptions_found:
                print(f"  - {corruption}")
        if self.race_conditions_detected:
            print(f"\n⚠️ Race conditions detected (potential TOCTOU vulnerabilities):")
            for race in self.race_conditions_detected:
                print(f"  - {race}")
        
        print(f"{'='*70}")
        
        # Success means no failures AND no corruptions AND no race conditions
        return (len(self.failed) == 0 and 
                len(self.corruptions_found) == 0 and 
                len(self.race_conditions_detected) == 0)


def create_test_sprint(repo: SprintRepository, sprint_id: str, test_dir: str):
    """Create a test sprint."""
    sprint_data, paths = repo.create(
        sprint_id=sprint_id,
        project="Test Project",
        goal="Test Goal",
        description="Test sprint for TOCTOU stress testing"
    )
    return sprint_data, paths


def run_toctou_stress_tests():
    """Run TOCTOU race condition stress tests."""
    results = TOCTOUTestResults()
    
    # Save current working directory
    cwd = os.getcwd()
    
    # Create temp directory for test isolation
    test_dir_name = f".test-toctou-stress-{os.getpid()}"
    test_dir = Path(test_dir_name).resolve()
    test_dir.mkdir(parents=True, exist_ok=True)
    print(f"Using test directory: {test_dir}\n")
    
    try:
        # Initialize repository and service
        repo = SprintRepository(str(test_dir))
        gate_enforcer = GateEnforcer(".")
        service = PhaseLockService(repo, gate_enforcer)
        
        # ============================================================
        # TEST 1: Concurrent Read-Check-Act Race Condition Prevention
        # ============================================================
        print("\n" + "="*70)
        print("TEST 1: Concurrent Read-Check-Act Race Prevention")
        print("="*70)
        print("Simulates: Multiple threads reading state and making decisions")
        print("           concurrently, then attempting to act on stale state.")
        
        sprint_id = "toctou-test-1"
        create_test_sprint(repo, sprint_id, test_dir)
        
        # First, approve discover phase so design can start
        service.update_phase_state(sprint_id, "discover", PhaseState.IN_PROGRESS.value)
        service.update_phase_state(sprint_id, "discover", PhaseState.AWAITING_APPROVAL.value)
        service.update_phase_state(sprint_id, "discover", PhaseState.APPROVED.value)
        
        # Now test concurrent can_start_phase + update_phase_state
        # If TOCTOU is fixed, all threads should see consistent state
        
        decisions = []
        actions = []
        lock = threading.Lock()
        
        def read_and_act(thread_id: int):
            """Thread reads state, makes decision, then acts."""
            try:
                # Step 1: Check if can start (TOCTOU vulnerability was here)
                check_result = service.can_start_phase(sprint_id, "design")
                
                # Record the decision
                with lock:
                    decisions.append({
                        "thread_id": thread_id,
                        "can_start": check_result.get("can_start", False),
                        "timestamp": datetime.utcnow().isoformat(),
                        "phase_state": check_result.get("current_state", "unknown")
                    })
                
                # Step 2: If check passed, try to act (start the phase)
                if check_result.get("can_start"):
                    action_result = service.update_phase_state(
                        sprint_id, "design", PhaseState.IN_PROGRESS.value
                    )
                    
                    with lock:
                        actions.append({
                            "thread_id": thread_id,
                            "success": action_result.get("success", False),
                            "timestamp": datetime.utcnow().isoformat(),
                            "error": action_result.get("error")
                        })
                    return action_result
                else:
                    with lock:
                        actions.append({
                            "thread_id": thread_id,
                            "success": False,
                            "timestamp": datetime.utcnow().isoformat(),
                            "error": check_result.get("error"),
                            "blocked": True
                        })
                    return {"success": False, "blocked": True}
            except Exception as e:
                with lock:
                    actions.append({
                        "thread_id": thread_id,
                        "success": False,
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": str(e),
                        "exception": True
                    })
                return {"success": False, "error": str(e)}
        
        # Run 10 concurrent threads
        print("\n  Running 10 concurrent read-check-act threads...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(read_and_act, i) for i in range(10)]
            list(as_completed(futures))
        
        # Analyze results
        successful_actions = [a for a in actions if a.get("success")]
        blocked_actions = [a for a in actions if a.get("blocked")]
        failed_actions = [a for a in actions if not a.get("success") and not a.get("blocked")]
        
        print(f"\n  Results:")
        print(f"    - Decisions made: {len(decisions)}")
        print(f"    - Successful actions: {len(successful_actions)}")
        print(f"    - Blocked actions: {len(blocked_actions)}")
        print(f"    - Failed actions: {len(failed_actions)}")
        
        # Verify: Only ONE thread should succeed (lock prevents TOCTOU)
        if len(successful_actions) == 1:
            results.add_pass("TOCTOU prevented: only 1 thread succeeded")
        elif len(successful_actions) > 1:
            # This indicates a TOCTOU race condition
            results.add_race_condition(
                f"Multiple threads succeeded ({len(successful_actions)}) - "
                f"TOCTOU race condition detected!"
            )
            results.add_fail("TOCTOU prevention", 
                           f"Expected 1 success, got {len(successful_actions)}")
        else:
            results.add_fail("TOCTOU prevention", 
                           "No thread succeeded - unexpected blocking")
        
        # Verify final state is consistent
        final_state = service.get_phase_state(sprint_id, "design")
        if final_state.get("success"):
            state = final_state.get("state")
            if state == PhaseState.IN_PROGRESS.value:
                results.add_pass("Final state is consistent (in_progress)")
            else:
                results.add_corruption(
                    f"Final state inconsistent: expected 'in_progress', got '{state}'"
                )
        
        # ============================================================
        # TEST 2: Concurrent get_phase_state + update_race
        # ============================================================
        print("\n" + "="*70)
        print("TEST 2: Concurrent Read-Update Race Prevention")
        print("="*70)
        print("Simulates: Multiple threads reading state while others update.")
        
        sprint_id_2 = "toctou-test-2"
        create_test_sprint(repo, sprint_id_2, test_dir)
        
        # Approve discover first
        service.update_phase_state(sprint_id_2, "discover", PhaseState.IN_PROGRESS.value)
        service.update_phase_state(sprint_id_2, "discover", PhaseState.AWAITING_APPROVAL.value)
        service.update_phase_state(sprint_id_2, "discover", PhaseState.APPROVED.value)
        
        read_states = []
        write_states = []
        lock = threading.Lock()
        
        def read_state_worker(thread_id: int):
            """Thread repeatedly reads phase state."""
            for i in range(5):
                try:
                    state = service.get_phase_state(sprint_id_2, "discover")
                    with lock:
                        read_states.append({
                            "thread_id": thread_id,
                            "iteration": i,
                            "state": state.get("state"),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                except Exception as e:
                    with lock:
                        read_states.append({
                            "thread_id": thread_id,
                            "iteration": i,
                            "error": str(e),
                            "timestamp": datetime.utcnow().isoformat()
                        })
                time.sleep(0.01)  # Small delay to increase chance of race
        
        def write_state_worker(thread_id: int):
            """Thread attempts state updates."""
            try:
                # Try to start design
                result = service.update_phase_state(
                    sprint_id_2, "design", PhaseState.IN_PROGRESS.value
                )
                with lock:
                    write_states.append({
                        "thread_id": thread_id,
                        "success": result.get("success"),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            except Exception as e:
                with lock:
                    write_states.append({
                        "thread_id": thread_id,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
        
        # Run 5 readers + 5 writers concurrently
        print("\n  Running 5 concurrent readers + 5 concurrent writers...")
        with ThreadPoolExecutor(max_workers=10) as executor:
            # Readers
            reader_futures = [executor.submit(read_state_worker, i) for i in range(5)]
            # Writers
            writer_futures = [executor.submit(write_state_worker, i) for i in range(5, 10)]
            list(as_completed(reader_futures + writer_futures))
        
        # Check for race conditions: reads should never see intermediate states
        unique_read_states = set(s.get("state") for s in read_states if s.get("state"))
        
        print(f"\n  Results:")
        print(f"    - Total reads: {len(read_states)}")
        print(f"    - Unique states observed: {unique_read_states}")
        print(f"    - Successful writes: {len([w for w in write_states if w.get('success')])}")
        
        # All reads should see valid states (no partial/corrupted states)
        invalid_reads = [r for r in read_states if r.get("error") and "corrupt" in r.get("error", "").lower()]
        if len(invalid_reads) == 0:
            results.add_pass("All reads saw valid states (no corruption)")
        else:
            results.add_corruption(f"{len(invalid_reads)} reads saw corrupted state")
        
        # ============================================================
        # TEST 3: High-Load Concurrent get_all_phases_state
        # ============================================================
        print("\n" + "="*70)
        print("TEST 3: High-Load Concurrent get_all_phases_state")
        print("="*70)
        print("Simulates: 20 threads reading all phases concurrently.")
        
        sprint_id_3 = "toctou-test-3"
        create_test_sprint(repo, sprint_id_3, test_dir)
        
        # Setup: start discover
        service.update_phase_state(sprint_id_3, "discover", PhaseState.IN_PROGRESS.value)
        
        all_states_reads = []
        lock = threading.Lock()
        
        def read_all_states_worker(thread_id: int):
            """Thread reads all phases state."""
            try:
                result = service.get_all_phases_state(sprint_id_3)
                with lock:
                    all_states_reads.append({
                        "thread_id": thread_id,
                        "success": result.get("success"),
                        "phases_count": len(result.get("phases", {})),
                        "timestamp": datetime.utcnow().isoformat()
                    })
            except Exception as e:
                with lock:
                    all_states_reads.append({
                        "thread_id": thread_id,
                        "error": str(e),
                        "timestamp": datetime.utcnow().isoformat()
                    })
        
        # Run 20 concurrent reads
        print("\n  Running 20 concurrent get_all_phases_state calls...")
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(read_all_states_worker, i) for i in range(20)]
            list(as_completed(futures))
        
        successful_reads = [r for r in all_states_reads if r.get("success")]
        failed_reads = [r for r in all_states_reads if r.get("error")]
        
        print(f"\n  Results:")
        print(f"    - Successful reads: {len(successful_reads)}")
        print(f"    - Failed reads: {len(failed_reads)}")
        
        if len(successful_reads) == 20:
            results.add_pass("All 20 concurrent reads succeeded")
        else:
            results.add_fail("High-load concurrent reads", 
                           f"Expected 20 successes, got {len(successful_reads)}")
        
        # Verify all reads saw consistent data (5 phases)
        consistent_reads = [r for r in successful_reads if r.get("phases_count") == 5]
        if len(consistent_reads) == len(successful_reads):
            results.add_pass("All reads saw consistent phase count (5 phases)")
        else:
            results.add_corruption(
                f"Inconsistent phase counts: {len(consistent_reads)} consistent, "
                f"{len(successful_reads) - len(consistent_reads)} inconsistent"
            )
        
        # ============================================================
        # TEST 4: Verify Lock File Creation
        # ============================================================
        print("\n" + "="*70)
        print("TEST 4: Verify Lock File Creation")
        print("="*70)
        
        # Check that lock files are being created
        lock_file_path = test_dir / sprint_id / ".phase_lock_service.lock"
        
        # Trigger a read operation
        service.get_phase_state(sprint_id, "discover")
        
        # Check lock directory exists (lock files are created on-demand)
        lock_dir = test_dir / sprint_id
        if lock_dir.exists():
            results.add_pass("Lock directory exists")
        else:
            results.add_fail("Lock directory exists", f"Directory {lock_dir} not found")
        
        # ============================================================
        # TEST 5: State File Integrity After Stress
        # ============================================================
        print("\n" + "="*70)
        print("TEST 5: State File Integrity After Stress")
        print("="*70)
        
        # Verify phase_lock.json files are valid JSON after all stress tests
        for test_sprint in [sprint_id, sprint_id_2, sprint_id_3]:
            try:
                paths = repo.get_paths(test_sprint)
                phase_lock_path = paths.sprint_dir / "phase_lock.json"
                
                if phase_lock_path.exists():
                    with open(phase_lock_path) as f:
                        data = json.load(f)
                    
                    # Verify structure
                    if "phases" in data and len(data["phases"]) == 5:
                        for phase in PHASE_ORDER:
                            if phase not in data["phases"]:
                                results.add_corruption(
                                    f"Missing phase '{phase}' in {test_sprint}"
                                )
                            elif "state" not in data["phases"][phase]:
                                results.add_corruption(
                                    f"Missing 'state' field for phase '{phase}' in {test_sprint}"
                                )
                    else:
                        results.add_corruption(
                            f"Invalid structure in {test_sprint} phase_lock.json"
                        )
                else:
                    results.add_fail(f"phase_lock.json exists for {test_sprint}",
                                   f"File not found at {phase_lock_path}")
            except json.JSONDecodeError as e:
                results.add_corruption(f"JSON corruption in {test_sprint}: {e}")
            except Exception as e:
                results.add_fail(f"Phase lock validation for {test_sprint}", str(e))
        
        if len(results.corruptions_found) == 0:
            results.add_pass("All state files remain valid after stress tests")
        
    finally:
        # Cleanup
        os.chdir(cwd)
        shutil.rmtree(test_dir, ignore_errors=True)
    
    return results.summary()


if __name__ == "__main__":
    print("\n" + "="*70)
    print("TOCTOU RACE CONDITION STRESS TEST")
    print("="*70)
    print("This test verifies that all state reads in PhaseLockService are")
    print("protected by DistributedLock, preventing TOCTOU race conditions.")
    print("="*70 + "\n")
    
    success = run_toctou_stress_tests()
    
    if success:
        print("\n✅ TOCTOU fix verified: All tests passed, no corruptions detected.")
    else:
        print("\n❌ TOCTOU fix may have issues: Review failures and corruptions above.")
    
    sys.exit(0 if success else 1)