"""
Comprehensive test suite for Phase Lock module.

Tests:
1. Phase sequence enforcement
2. State transitions
3. Error handling
4. File persistence
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from carby_sprint.phase_lock import (
    PHASE_ORDER,
    _load,
    _save,
    _lock_path,
    get_phase_status,
    wait_for_previous_phase,
    mark_phase_complete,
    approve_phase,
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


def run_tests():
    """Run all Phase Lock tests."""
    results = TestResults()

    # Create temp directory for test isolation
    test_dir = tempfile.mkdtemp(prefix="phase_lock_test_")
    print(f"Using test directory: {test_dir}\n")

    try:
        # ============================================================
        # TEST SUITE 1: Phase Sequence Enforcement
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 1: Phase Sequence Enforcement")
        print("="*60)

        sprint_id = "test-sprint-seq"

        # Test 1.1: First phase (discover) should be allowed immediately
        try:
            result = wait_for_previous_phase(sprint_id, "discover", output_dir=test_dir)
            if result["ready"]:
                results.add_pass("First phase (discover) is ready without dependency")
            else:
                results.add_fail("First phase (discover) is ready without dependency",
                               "Expected ready=True")
        except Exception as e:
            results.add_fail("First phase (discover) is ready without dependency", e)

        # Test 1.2: Try to start design before discover is approved
        try:
            result = wait_for_previous_phase(sprint_id, "design", output_dir=test_dir)
            results.add_fail("Design blocked before discover approved",
                           "Expected RuntimeError but got success")
        except RuntimeError as e:
            error_msg = str(e)
            if "blocked" in error_msg.lower() and "discover" in error_msg.lower():
                results.add_pass("Design blocked before discover approved")
            else:
                results.add_fail("Design blocked before discover approved",
                               f"Wrong error message: {error_msg}")
        except Exception as e:
            results.add_fail("Design blocked before discover approved", e)

        # Test 1.3: Verify error message is clear and helpful
        try:
            wait_for_previous_phase(sprint_id, "design", output_dir=test_dir)
        except RuntimeError as e:
            error_msg = str(e)
            has_blocked = "blocked" in error_msg.lower()
            has_previous = "previous phase" in error_msg.lower()
            if has_blocked and has_previous:
                results.add_pass("Error message contains 'blocked' and 'previous phase'")
            else:
                results.add_fail("Error message contains 'blocked' and 'previous phase'",
                               f"Missing info in: {error_msg}")

        # ============================================================
        # TEST SUITE 2: State Transitions
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 2: State Transitions")
        print("="*60)

        sprint_id = "test-sprint-state"

        # Test 2.1: Mark discover as complete
        try:
            result = mark_phase_complete(sprint_id, "discover", "Requirements gathered", output_dir=test_dir)
            if result["state"] == "awaiting_approval":
                results.add_pass("Mark discover complete → awaiting_approval")
            else:
                results.add_fail("Mark discover complete → awaiting_approval",
                               f"Expected awaiting_approval, got {result['state']}")
        except Exception as e:
            results.add_fail("Mark discover complete → awaiting_approval", e)

        # Test 2.2: Verify status shows awaiting_approval
        try:
            status = get_phase_status(sprint_id, "discover", output_dir=test_dir)
            if status["state"] == "awaiting_approval":
                results.add_pass("Status shows awaiting_approval after marking complete")
            else:
                results.add_fail("Status shows awaiting_approval after marking complete",
                               f"Expected awaiting_approval, got {status['state']}")
        except Exception as e:
            results.add_fail("Status shows awaiting_approval after marking complete", e)

        # Test 2.3: Approve discover
        try:
            result = approve_phase(sprint_id, "discover", output_dir=test_dir)
            if result["state"] == "approved":
                results.add_pass("Approve discover → approved")
            else:
                results.add_fail("Approve discover → approved",
                               f"Expected approved, got {result['state']}")
        except Exception as e:
            results.add_fail("Approve discover → approved", e)

        # Test 2.4: Verify status shows approved
        try:
            status = get_phase_status(sprint_id, "discover", output_dir=test_dir)
            if status["state"] == "approved":
                results.add_pass("Status shows approved after approval")
            else:
                results.add_fail("Status shows approved after approval",
                               f"Expected approved, got {status['state']}")
        except Exception as e:
            results.add_fail("Status shows approved after approval", e)

        # Test 2.5: Verify design can now start
        try:
            result = wait_for_previous_phase(sprint_id, "design", output_dir=test_dir)
            if result["ready"]:
                results.add_pass("Design can start after discover approved")
            else:
                results.add_fail("Design can start after discover approved",
                               "Expected ready=True")
        except Exception as e:
            results.add_fail("Design can start after discover approved", e)

        # Test 2.6: Verify approve returns next phase info
        try:
            sprint_id_next = "test-sprint-next-info"
            mark_phase_complete(sprint_id_next, "discover", "Done", output_dir=test_dir)
            result = approve_phase(sprint_id_next, "discover", output_dir=test_dir)
            if result.get("next_phase") == "design" and "next_command" in result:
                results.add_pass("Approve returns next phase info")
            else:
                results.add_fail("Approve returns next phase info",
                               f"Missing next_phase or next_command in: {result}")
        except Exception as e:
            results.add_fail("Approve returns next phase info", e)

        # Test 2.7: Verify last phase (deliver) has no next phase
        try:
            sprint_id_last = "test-sprint-last-phase"
            # Complete all phases up to deliver
            for phase in PHASE_ORDER[:-1]:
                mark_phase_complete(sprint_id_last, phase, f"{phase} done", output_dir=test_dir)
                approve_phase(sprint_id_last, phase, output_dir=test_dir)
            mark_phase_complete(sprint_id_last, "deliver", "Delivered", output_dir=test_dir)
            result = approve_phase(sprint_id_last, "deliver", output_dir=test_dir)
            if "next_phase" not in result:
                results.add_pass("Last phase (deliver) has no next_phase")
            else:
                results.add_fail("Last phase (deliver) has no next_phase",
                               f"Unexpected next_phase: {result.get('next_phase')}")
        except Exception as e:
            results.add_fail("Last phase (deliver) has no next_phase", e)

        # ============================================================
        # TEST SUITE 3: Error Handling
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 3: Error Handling")
        print("="*60)

        # Test 3.1: Invalid sprint ID (non-existent should create new)
        try:
            sprint_id_new = "brand-new-sprint-12345"
            status = get_phase_status(sprint_id_new, "discover", output_dir=test_dir)
            if status["state"] == "pending":
                results.add_pass("Non-existent sprint ID creates new sprint")
            else:
                results.add_fail("Non-existent sprint ID creates new sprint",
                               f"Expected pending state, got {status['state']}")
        except Exception as e:
            results.add_fail("Non-existent sprint ID creates new sprint", e)

        # Test 3.2: Invalid phase ID
        try:
            status = get_phase_status(sprint_id, "invalid_phase", output_dir=test_dir)
            results.add_fail("Invalid phase ID raises ValueError",
                           "Expected ValueError but got success")
        except ValueError as e:
            if "invalid phase" in str(e).lower():
                results.add_pass("Invalid phase ID raises ValueError with clear message")
            else:
                results.add_pass("Invalid phase ID raises ValueError")
        except Exception as e:
            results.add_fail("Invalid phase ID raises ValueError", e)

        # Test 3.3: Approving already-approved phase
        try:
            sprint_id_approved = "test-already-approved"
            mark_phase_complete(sprint_id_approved, "discover", "Done", output_dir=test_dir)
            approve_phase(sprint_id_approved, "discover", output_dir=test_dir)
            # Try to approve again
            approve_phase(sprint_id_approved, "discover", output_dir=test_dir)
            results.add_fail("Approving already-approved phase raises error",
                           "Expected ValueError but succeeded")
        except ValueError as e:
            if "not awaiting_approval" in str(e).lower():
                results.add_pass("Approving already-approved phase raises clear error")
            else:
                results.add_pass("Approving already-approved phase raises error")
        except Exception as e:
            results.add_fail("Approving already-approved phase raises error", e)

        # Test 3.4: Approving pending phase (not completed)
        try:
            sprint_id_pending = "test-approve-pending"
            # Don't mark complete, just try to approve
            approve_phase(sprint_id_pending, "discover", output_dir=test_dir)
            results.add_fail("Approving pending phase raises error",
                           "Expected ValueError but succeeded")
        except ValueError as e:
            if "not awaiting_approval" in str(e).lower():
                results.add_pass("Approving pending phase raises clear error")
            else:
                results.add_pass("Approving pending phase raises error")
        except Exception as e:
            results.add_fail("Approving pending phase raises error", e)

        # ============================================================
        # TEST SUITE 4: File Persistence
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 4: File Persistence")
        print("="*60)

        sprint_id_persist = "test-persistence"

        # Test 4.1: JSON state file is created
        try:
            mark_phase_complete(sprint_id_persist, "discover", "Test summary", output_dir=test_dir)
            lock_file = _lock_path(sprint_id_persist, test_dir)
            if lock_file.exists():
                results.add_pass("JSON state file is created")
            else:
                results.add_fail("JSON state file is created",
                               f"File not found: {lock_file}")
        except Exception as e:
            results.add_fail("JSON state file is created", e)

        # Test 4.2: State file contains correct data
        try:
            with open(lock_file) as f:
                data = json.load(f)
            if (data["sprint_id"] == sprint_id_persist and
                data["phases"]["discover"]["state"] == "awaiting_approval" and
                data["phases"]["discover"]["summary"] == "Test summary"):
                results.add_pass("State file contains correct data")
            else:
                results.add_fail("State file contains correct data",
                               f"Unexpected data: {data}")
        except Exception as e:
            results.add_fail("State file contains correct data", e)

        # Test 4.3: State survives process restart (simulated by reloading)
        try:
            # Reload data using _load
            data = _load(sprint_id_persist, test_dir)
            if (data["phases"]["discover"]["state"] == "awaiting_approval" and
                data["phases"]["discover"]["summary"] == "Test summary"):
                results.add_pass("State survives process restart (reload)")
            else:
                results.add_fail("State survives process restart (reload)",
                               f"Data lost or corrupted: {data}")
        except Exception as e:
            results.add_fail("State survives process restart (reload)", e)

        # Test 4.4: Atomic writes (no corruption during write)
        try:
            # Write multiple times rapidly
            for i in range(10):
                data = _load(sprint_id_persist, test_dir)
                data["phases"]["discover"]["iteration"] = i
                _save(data, sprint_id_persist, test_dir)
            
            # Verify file is valid JSON
            with open(lock_file) as f:
                final_data = json.load(f)
            
            if "iteration" in final_data["phases"]["discover"]:
                results.add_pass("Atomic writes (no corruption)")
            else:
                results.add_fail("Atomic writes (no corruption)",
                               "Data corrupted during rapid writes")
        except json.JSONDecodeError as e:
            results.add_fail("Atomic writes (no corruption)",
                           f"File corrupted: {e}")
            results.add_bug("File corruption possible during concurrent writes")
        except Exception as e:
            results.add_fail("Atomic writes (no corruption)", e)

        # Test 4.5: Verify all phases exist in new sprint
        try:
            sprint_id_all = "test-all-phases"
            data = _load(sprint_id_all, test_dir)
            all_exist = all(p in data["phases"] for p in PHASE_ORDER)
            all_pending = all(data["phases"][p]["state"] == "pending" for p in PHASE_ORDER)
            if all_exist and all_pending:
                results.add_pass("All phases exist in new sprint with pending state")
            else:
                results.add_fail("All phases exist in new sprint with pending state",
                               f"Missing or wrong state: {data['phases']}")
        except Exception as e:
            results.add_fail("All phases exist in new sprint with pending state", e)

        # Test 4.6: Directory structure is created
        try:
            sprint_id_dir = "test-dir-structure"
            mark_phase_complete(sprint_id_dir, "discover", "Test", output_dir=test_dir)
            sprint_dir = Path(test_dir) / sprint_id_dir
            if sprint_dir.exists() and sprint_dir.is_dir():
                results.add_pass("Directory structure created correctly")
            else:
                results.add_fail("Directory structure created correctly",
                               f"Directory not found: {sprint_dir}")
        except Exception as e:
            results.add_fail("Directory structure created correctly", e)

    finally:
        # Cleanup
        shutil.rmtree(test_dir, ignore_errors=True)
        print(f"\nCleaned up test directory: {test_dir}")

    # Print summary
    success = results.summary()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(run_tests())
