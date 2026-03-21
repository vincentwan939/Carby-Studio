"""
Test suite for Phase Lock CLI commands.

Tests:
1. approve command - Approve completed phases
2. phase-status command - Show phase statuses
3. phase-list command - List phases in various formats
4. Integration - Full workflow testing

Uses Click's CliRunner for testing CLI commands.
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from datetime import datetime

import pytest
from click.testing import CliRunner

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from carby_sprint.cli import cli
from carby_sprint.commands.phase import (
    PHASE_DEFINITIONS,
    STATUS_ICONS,
    load_sprint,
    save_sprint,
    initialize_phases,
    get_sprint_path,
    validate_phase_id,
    can_approve_phase,
    get_phase_status_display,
)


class TestPhaseCLI:
    """Test class for Phase Lock CLI commands."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
        self.test_dir = tempfile.mkdtemp(prefix="phase_cli_test_")
        self.sprint_id = "test-sprint-cli"
        self.sprint_path = Path(self.test_dir) / self.sprint_id
        self.sprint_path.mkdir(parents=True, exist_ok=True)

        # Create initial sprint metadata
        self.sprint_data = {
            "id": self.sprint_id,
            "name": "Test Sprint",
            "created_at": datetime.now().isoformat(),
            "execution_mode": "sequential",
            "phases": {}
        }

        # Initialize phases
        self.sprint_data = initialize_phases(self.sprint_data)

        # Save initial sprint
        metadata_path = self.sprint_path / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(self.sprint_data, f, indent=2)

        yield

        # Cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _update_phase_status(self, phase_id: str, status: str, approved: bool = False):
        """Helper to update phase status in sprint data."""
        metadata_path = self.sprint_path / "metadata.json"
        with open(metadata_path, "r") as f:
            data = json.load(f)

        data = initialize_phases(data)
        data["phases"][phase_id]["status"] = status
        data["phases"][phase_id]["approved"] = approved

        if status == "completed":
            data["phases"][phase_id]["completed_at"] = datetime.now().isoformat()
        if approved:
            data["phases"][phase_id]["approved_at"] = datetime.now().isoformat()

        with open(metadata_path, "w") as f:
            json.dump(data, f, indent=2)

    # ============================================================
    # TEST SUITE 1: approve command
    # ============================================================

    def test_approve_completed_phase_success(self):
        """Test approving a completed phase."""
        # Set phase 1 to completed
        self._update_phase_status("1", "completed", approved=False)

        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "1",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        assert "✓ Phase 1 approved" in result.output
        assert "Discovery" in result.output

    def test_approve_nonexistent_sprint_error(self):
        """Test error when sprint doesn't exist."""
        result = self.runner.invoke(cli, [
            "approve", "nonexistent-sprint", "1",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    def test_approve_nonexistent_phase_error(self):
        """Test error when phase doesn't exist."""
        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "99",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code != 0
        assert "Invalid phase" in result.output or "not found" in result.output.lower()

    def test_approve_phase_not_completed_error(self):
        """Test error when phase is not in completed state."""
        # Phase 1 is not_started by default
        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "1",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code != 0
        assert "not completed" in result.output.lower() or "Cannot approve" in result.output

    def test_approve_phase_sequential_enforcement(self):
        """Test sequential enforcement - can't approve phase 2 before phase 1."""
        # Set phase 2 to completed but don't approve phase 1
        self._update_phase_status("2", "completed", approved=False)

        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "2",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code != 0
        assert "phase 1" in result.output.lower() or "Previous phase" in result.output

    def test_approve_phase_after_previous_approved(self):
        """Test approving phase 2 after phase 1 is approved."""
        # Approve phase 1 first
        self._update_phase_status("1", "completed", approved=True)
        # Set phase 2 to completed
        self._update_phase_status("2", "completed", approved=False)

        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "2",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        assert "✓ Phase 2 approved" in result.output

    def test_approve_already_approved_phase(self):
        """Test error when phase is already approved."""
        # Approve phase 1
        self._update_phase_status("1", "completed", approved=True)

        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "1",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code != 0
        assert "already approved" in result.output.lower()

    # ============================================================
    # TEST SUITE 2: phase-status command
    # ============================================================

    def test_phase_status_show_all_phases(self):
        """Test showing all phase statuses."""
        result = self.runner.invoke(cli, [
            "phase-status", self.sprint_id,
            "--output-dir", self.test_dir
        ])

        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        assert "Phase Status for Sprint" in result.output
        assert self.sprint_id in result.output
        # Check all phases are listed
        for phase_id in PHASE_DEFINITIONS:
            assert phase_id in result.output or PHASE_DEFINITIONS[phase_id]["name"] in result.output

    def test_phase_status_visual_indicators(self):
        """Test visual indicators (✓, ⏳, 🔄) are displayed."""
        # Set up different phase states
        self._update_phase_status("1", "completed", approved=True)  # ✓ approved
        self._update_phase_status("2", "completed", approved=False)  # ⏳ pending_approval
        self._update_phase_status("3", "in_progress", approved=False)  # 🔄 in_progress

        result = self.runner.invoke(cli, [
            "phase-status", self.sprint_id,
            "--output-dir", self.test_dir
        ])

        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        # Check for visual indicators in output
        assert STATUS_ICONS["approved"] in result.output  # ✓
        assert STATUS_ICONS["pending_approval"] in result.output  # ⏳
        assert STATUS_ICONS["in_progress"] in result.output  # 🔄

    def test_phase_status_pending_only_flag(self):
        """Test --pending-only flag shows only phases pending approval."""
        # Set up phases with different states
        self._update_phase_status("1", "completed", approved=True)
        self._update_phase_status("2", "completed", approved=False)  # Pending approval
        self._update_phase_status("3", "in_progress", approved=False)

        result = self.runner.invoke(cli, [
            "phase-status", self.sprint_id,
            "--output-dir", self.test_dir,
            "--pending-only"
        ])

        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        # Should show phase 2 (pending approval)
        assert "Design" in result.output or "2" in result.output

    def test_phase_status_nonexistent_sprint_error(self):
        """Test error when sprint doesn't exist for phase-status."""
        result = self.runner.invoke(cli, [
            "phase-status", "nonexistent-sprint",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    # ============================================================
    # TEST SUITE 3: phase-list command
    # ============================================================

    def test_phase_list_table_format(self):
        """Test listing phases in table format (default)."""
        result = self.runner.invoke(cli, [
            "phase-list", self.sprint_id,
            "--output-dir", self.test_dir
        ])

        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        # Check table format elements
        assert "Phase" in result.output
        assert "Name" in result.output
        assert "Status" in result.output
        assert "Approved" in result.output
        # Check all phases are listed
        for phase_id in PHASE_DEFINITIONS:
            assert PHASE_DEFINITIONS[phase_id]["name"] in result.output

    def test_phase_list_json_format(self):
        """Test listing phases in JSON format."""
        result = self.runner.invoke(cli, [
            "phase-list", self.sprint_id,
            "--output-dir", self.test_dir,
            "--format", "json"
        ])

        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        # Parse JSON output
        output_data = json.loads(result.output)
        assert "sprint_id" in output_data
        assert output_data["sprint_id"] == self.sprint_id
        assert "phases" in output_data
        # Check all phases are present
        for phase_id in PHASE_DEFINITIONS:
            assert phase_id in output_data["phases"]

    def test_phase_list_compact_format(self):
        """Test listing phases in compact format."""
        result = self.runner.invoke(cli, [
            "phase-list", self.sprint_id,
            "--output-dir", self.test_dir,
            "--format", "compact"
        ])

        assert result.exit_code == 0, f"Exit code: {result.exit_code}\nOutput: {result.output}"
        # Check compact format elements
        assert f"Sprint: {self.sprint_id}" in result.output
        # Check all phases are listed with short format
        for phase_id in PHASE_DEFINITIONS:
            assert f"[{phase_id}]" in result.output

    def test_phase_list_nonexistent_sprint_error(self):
        """Test error when sprint doesn't exist for phase-list."""
        result = self.runner.invoke(cli, [
            "phase-list", "nonexistent-sprint",
            "--output-dir", self.test_dir
        ])

        assert result.exit_code != 0
        assert "not found" in result.output.lower() or "Error" in result.output

    # ============================================================
    # TEST SUITE 4: Integration - Full Workflow
    # ============================================================

    def test_full_workflow_create_complete_approve_check_status(self):
        """Test full workflow: create → complete → approve → check status."""
        # Step 1: Verify initial status (all phases not_started)
        result = self.runner.invoke(cli, [
            "phase-status", self.sprint_id,
            "--output-dir", self.test_dir
        ])
        assert result.exit_code == 0
        assert STATUS_ICONS["not_started"] in result.output

        # Step 2: Complete phase 1
        self._update_phase_status("1", "completed", approved=False)

        # Step 3: Check status shows phase 1 as completed (pending approval)
        result = self.runner.invoke(cli, [
            "phase-status", self.sprint_id,
            "--output-dir", self.test_dir
        ])
        assert result.exit_code == 0
        assert STATUS_ICONS["pending_approval"] in result.output

        # Step 4: Approve phase 1
        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "1",
            "--output-dir", self.test_dir
        ])
        assert result.exit_code == 0
        assert "✓ Phase 1 approved" in result.output

        # Step 5: Verify phase 1 is now approved
        result = self.runner.invoke(cli, [
            "phase-status", self.sprint_id,
            "--output-dir", self.test_dir
        ])
        assert result.exit_code == 0
        assert STATUS_ICONS["approved"] in result.output

        # Step 6: Complete and approve phase 2
        self._update_phase_status("2", "completed", approved=False)
        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "2",
            "--output-dir", self.test_dir
        ])
        assert result.exit_code == 0
        assert "✓ Phase 2 approved" in result.output

        # Step 7: Check final status with phase-list
        result = self.runner.invoke(cli, [
            "phase-list", self.sprint_id,
            "--output-dir", self.test_dir,
            "--format", "json"
        ])
        assert result.exit_code == 0
        output_data = json.loads(result.output)
        assert output_data["phases"]["1"]["approved"] is True
        assert output_data["phases"]["2"]["approved"] is True
        assert output_data["phases"]["3"]["approved"] is False

    def test_sequential_workflow_all_phases(self):
        """Test sequential workflow through all 5 phases."""
        # Progress through all phases sequentially
        for phase_id in ["1", "2", "3", "4", "5"]:
            # Complete the phase
            self._update_phase_status(phase_id, "completed", approved=False)

            # Approve the phase
            result = self.runner.invoke(cli, [
                "approve", self.sprint_id, phase_id,
                "--output-dir", self.test_dir
            ])
            assert result.exit_code == 0, f"Failed to approve phase {phase_id}"
            assert f"✓ Phase {phase_id} approved" in result.output

        # Verify all phases are approved
        result = self.runner.invoke(cli, [
            "phase-list", self.sprint_id,
            "--output-dir", self.test_dir,
            "--format", "json"
        ])
        output_data = json.loads(result.output)
        for phase_id in ["1", "2", "3", "4", "5"]:
            assert output_data["phases"][phase_id]["approved"] is True

    def test_cannot_skip_phases_in_approval(self):
        """Test that phases cannot be skipped in approval sequence."""
        # Try to approve phase 3 without approving phases 1 and 2
        self._update_phase_status("1", "completed", approved=False)
        self._update_phase_status("2", "completed", approved=False)
        self._update_phase_status("3", "completed", approved=False)

        # Should fail because phase 1 is not approved
        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "3",
            "--output-dir", self.test_dir
        ])
        assert result.exit_code != 0
        assert "phase 1" in result.output.lower() or "Previous phase" in result.output

        # Approve phase 1
        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "1",
            "--output-dir", self.test_dir
        ])
        assert result.exit_code == 0

        # Should still fail because phase 2 is not approved
        result = self.runner.invoke(cli, [
            "approve", self.sprint_id, "3",
            "--output-dir", self.test_dir
        ])
        assert result.exit_code != 0
        assert "phase 2" in result.output.lower() or "Previous phase" in result.output


# ============================================================
# Standalone test runner for environments without pytest
# ============================================================

class TestResults:
    """Track test results."""
    def __init__(self):
        self.passed = []
        self.failed = []

    def add_pass(self, test_name):
        self.passed.append(test_name)
        print(f"  ✅ PASS: {test_name}")

    def add_fail(self, test_name, error):
        self.failed.append((test_name, str(error)))
        print(f"  ❌ FAIL: {test_name}")
        print(f"     Error: {error}")

    def summary(self):
        total = len(self.passed) + len(self.failed)
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY")
        print(f"{'='*60}")
        print(f"Total tests: {total}")
        print(f"Passed: {len(self.passed)}")
        print(f"Failed: {len(self.failed)}")
        if self.failed:
            print(f"\nFailed tests:")
            for name, error in self.failed:
                print(f"  - {name}: {error}")
        print(f"{'='*60}")
        return len(self.failed) == 0


def run_tests():
    """Run all Phase CLI tests."""
    results = TestResults()
    runner = CliRunner()
    test_dir = tempfile.mkdtemp(prefix="phase_cli_test_")
    sprint_id = "test-sprint-cli"
    sprint_path = Path(test_dir) / sprint_id
    sprint_path.mkdir(parents=True, exist_ok=True)

    # Create initial sprint metadata
    sprint_data = {
        "id": sprint_id,
        "name": "Test Sprint",
        "created_at": datetime.now().isoformat(),
        "execution_mode": "sequential",
        "phases": {}
    }
    sprint_data = initialize_phases(sprint_data)
    metadata_path = sprint_path / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(sprint_data, f, indent=2)

    def update_phase_status(phase_id, status, approved=False):
        """Helper to update phase status."""
        with open(metadata_path, "r") as f:
            data = json.load(f)
        data = initialize_phases(data)
        data["phases"][phase_id]["status"] = status
        data["phases"][phase_id]["approved"] = approved
        if status == "completed":
            data["phases"][phase_id]["completed_at"] = datetime.now().isoformat()
        if approved:
            data["phases"][phase_id]["approved_at"] = datetime.now().isoformat()
        with open(metadata_path, "w") as f:
            json.dump(data, f, indent=2)

    try:
        # ============================================================
        # TEST SUITE 1: approve command
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 1: approve command")
        print("="*60)

        # Test 1.1: Approve completed phase success
        try:
            update_phase_status("1", "completed", approved=False)
            result = runner.invoke(cli, ["approve", sprint_id, "1", "--output-dir", test_dir])
            assert result.exit_code == 0, f"Exit code: {result.exit_code}"
            assert "✓ Phase 1 approved" in result.output
            results.add_pass("test_approve_completed_phase_success")
        except Exception as e:
            results.add_fail("test_approve_completed_phase_success", e)

        # Reset for next tests
        update_phase_status("1", "not_started", approved=False)

        # Test 1.2: Approve non-existent sprint error
        try:
            result = runner.invoke(cli, ["approve", "nonexistent-sprint", "1", "--output-dir", test_dir])
            assert result.exit_code != 0
            results.add_pass("test_approve_nonexistent_sprint_error")
        except Exception as e:
            results.add_fail("test_approve_nonexistent_sprint_error", e)

        # Test 1.3: Approve non-existent phase error
        try:
            result = runner.invoke(cli, ["approve", sprint_id, "99", "--output-dir", test_dir])
            assert result.exit_code != 0
            results.add_pass("test_approve_nonexistent_phase_error")
        except Exception as e:
            results.add_fail("test_approve_nonexistent_phase_error", e)

        # Test 1.4: Approve phase not completed error
        try:
            result = runner.invoke(cli, ["approve", sprint_id, "1", "--output-dir", test_dir])
            assert result.exit_code != 0
            results.add_pass("test_approve_phase_not_completed_error")
        except Exception as e:
            results.add_fail("test_approve_phase_not_completed_error", e)

        # Test 1.5: Sequential enforcement
        try:
            update_phase_status("2", "completed", approved=False)
            result = runner.invoke(cli, ["approve", sprint_id, "2", "--output-dir", test_dir])
            assert result.exit_code != 0
            assert "phase 1" in result.output.lower() or "Previous phase" in result.output
            results.add_pass("test_approve_phase_sequential_enforcement")
        except Exception as e:
            results.add_fail("test_approve_phase_sequential_enforcement", e)

        # ============================================================
        # TEST SUITE 2: phase-status command
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 2: phase-status command")
        print("="*60)

        # Test 2.1: Show all phases
        try:
            result = runner.invoke(cli, ["phase-status", sprint_id, "--output-dir", test_dir])
            assert result.exit_code == 0
            assert "Phase Status for Sprint" in result.output
            results.add_pass("test_phase_status_show_all_phases")
        except Exception as e:
            results.add_fail("test_phase_status_show_all_phases", e)

        # Test 2.2: Visual indicators
        try:
            update_phase_status("1", "completed", approved=True)
            update_phase_status("2", "completed", approved=False)
            update_phase_status("3", "in_progress", approved=False)
            result = runner.invoke(cli, ["phase-status", sprint_id, "--output-dir", test_dir])
            assert result.exit_code == 0
            assert STATUS_ICONS["approved"] in result.output
            assert STATUS_ICONS["pending_approval"] in result.output
            assert STATUS_ICONS["in_progress"] in result.output
            results.add_pass("test_phase_status_visual_indicators")
        except Exception as e:
            results.add_fail("test_phase_status_visual_indicators", e)

        # Test 2.3: Pending only flag
        try:
            result = runner.invoke(cli, ["phase-status", sprint_id, "--output-dir", test_dir, "--pending-only"])
            assert result.exit_code == 0
            results.add_pass("test_phase_status_pending_only_flag")
        except Exception as e:
            results.add_fail("test_phase_status_pending_only_flag", e)

        # ============================================================
        # TEST SUITE 3: phase-list command
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 3: phase-list command")
        print("="*60)

        # Test 3.1: Table format
        try:
            result = runner.invoke(cli, ["phase-list", sprint_id, "--output-dir", test_dir])
            assert result.exit_code == 0
            assert "Phase" in result.output
            assert "Name" in result.output
            results.add_pass("test_phase_list_table_format")
        except Exception as e:
            results.add_fail("test_phase_list_table_format", e)

        # Test 3.2: JSON format
        try:
            result = runner.invoke(cli, ["phase-list", sprint_id, "--output-dir", test_dir, "--format", "json"])
            assert result.exit_code == 0
            output_data = json.loads(result.output)
            assert output_data["sprint_id"] == sprint_id
            results.add_pass("test_phase_list_json_format")
        except Exception as e:
            results.add_fail("test_phase_list_json_format", e)

        # Test 3.3: Compact format
        try:
            result = runner.invoke(cli, ["phase-list", sprint_id, "--output-dir", test_dir, "--format", "compact"])
            assert result.exit_code == 0
            assert f"Sprint: {sprint_id}" in result.output
            results.add_pass("test_phase_list_compact_format")
        except Exception as e:
            results.add_fail("test_phase_list_compact_format", e)

        # ============================================================
        # TEST SUITE 4: Integration
        # ============================================================
        print("\n" + "="*60)
        print("SUITE 4: Integration - Full Workflow")
        print("="*60)

        # Test 4.1: Full workflow
        try:
            # Reset
            for i in ["1", "2", "3", "4", "5"]:
                update_phase_status(i, "not_started", approved=False)

            # Complete and approve phase 1
            update_phase_status("1", "completed", approved=False)
            result = runner.invoke(cli, ["approve", sprint_id, "1", "--output-dir", test_dir])
            assert result.exit_code == 0

            # Complete and approve phase 2
            update_phase_status("2", "completed", approved=False)
            result = runner.invoke(cli, ["approve", sprint_id, "2", "--output-dir", test_dir])
            assert result.exit_code == 0

            # Check status
            result = runner.invoke(cli, ["phase-list", sprint_id, "--output-dir", test_dir, "--format", "json"])
            output_data = json.loads(result.output)
            assert output_data["phases"]["1"]["approved"] is True
            assert output_data["phases"]["2"]["approved"] is True
            results.add_pass("test_full_workflow_create_complete_approve_check_status")
        except Exception as e:
            results.add_fail("test_full_workflow_create_complete_approve_check_status", e)

    finally:
        # Cleanup
        shutil.rmtree(test_dir, ignore_errors=True)

    return results.summary()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)