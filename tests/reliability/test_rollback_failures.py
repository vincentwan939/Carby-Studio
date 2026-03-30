"""
Test suite for Rollback Failure Handling (H4 Fix).

Tests that rollback failures are properly propagated and not silently logged.
This ensures transaction integrity during rollback scenarios.
"""

import json
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from carby_sprint.transaction import (
    atomic_sprint_update,
    atomic_work_item_update,
    TransactionError
)
from carby_sprint.two_phase_commit import (
    TwoPhaseCommitCoordinator,
    StateFileParticipant,
    Participant,
    ParticipantStatus
)


class TestAtomicSprintUpdateRollback:
    """Test rollback failure handling in atomic_sprint_update."""
    
    def test_rollback_failure_is_propagated(self):
        """Test that rollback failures are included in the raised exception."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir) / "test_sprint"
            sprint_path.mkdir()
            
            # Create initial metadata
            metadata_path = sprint_path / "metadata.json"
            initial_data = {"sprint_id": "test", "status": "initial"}
            with open(metadata_path, "w") as f:
                json.dump(initial_data, f)
            
            # Mock shutil.copy2 in the transaction module to fail during rollback
            original_copy2 = shutil.copy2
            call_count = [0]
            
            def failing_copy2(*args, **kwargs):
                call_count[0] += 1
                # Fail during rollback (when restoring from backup)
                if '.restore_tmp.' in str(args[1]) if len(args) > 1 else False:
                    raise IOError("Simulated rollback failure")
                return original_copy2(*args, **kwargs)
            
            with patch('carby_sprint.transaction.shutil.copy2', side_effect=failing_copy2):
                with pytest.raises(TransactionError) as exc_info:
                    with atomic_sprint_update(sprint_path) as data:
                        data["status"] = "updated"
                        raise RuntimeError("Simulated transaction failure")
            
            # Verify rollback failure is mentioned in error
            error_msg = str(exc_info.value)
            assert "CRITICAL" in error_msg
            assert "Rollback also failed" in error_msg
            assert "Data integrity may be compromised" in error_msg
    
    def test_successful_rollback_no_critical_message(self):
        """Test that successful rollback doesn't include CRITICAL message."""
        with tempfile.TemporaryDirectory() as temp_dir:
            sprint_path = Path(temp_dir) / "test_sprint"
            sprint_path.mkdir()
            
            # Create initial metadata
            metadata_path = sprint_path / "metadata.json"
            initial_data = {"sprint_id": "test", "status": "initial"}
            with open(metadata_path, "w") as f:
                json.dump(initial_data, f)
            
            with pytest.raises(TransactionError) as exc_info:
                with atomic_sprint_update(sprint_path) as data:
                    data["status"] = "updated"
                    raise RuntimeError("Simulated transaction failure")
            
            # Verify no CRITICAL message in error
            error_msg = str(exc_info.value)
            assert "CRITICAL" not in error_msg
            assert "Rollback also failed" not in error_msg
            
            # Verify data was rolled back
            with open(metadata_path, "r") as f:
                result = json.load(f)
            assert result["status"] == "initial"


class TestAtomicWorkItemUpdateRollback:
    """Test rollback failure handling in atomic_work_item_update."""
    
    def test_rollback_failure_is_propagated(self):
        """Test that rollback failures are included in the raised exception."""
        with tempfile.TemporaryDirectory() as temp_dir:
            work_items_dir = Path(temp_dir)
            
            # Create initial work item
            work_item_path = work_items_dir / "test_wi.json"
            initial_data = {"id": "test_wi", "status": "initial"}
            with open(work_item_path, "w") as f:
                json.dump(initial_data, f)
            
            # Mock shutil.copy2 to fail during rollback
            original_copy2 = shutil.copy2
            def failing_copy2(*args, **kwargs):
                if len(args) >= 2 and '.backup_' in str(args[0]):
                    raise IOError("Simulated rollback failure")
                return original_copy2(*args, **kwargs)
            
            with patch('shutil.copy2', side_effect=failing_copy2):
                with pytest.raises(TransactionError) as exc_info:
                    with atomic_work_item_update(work_items_dir, "test_wi") as data:
                        data["status"] = "updated"
                        raise RuntimeError("Simulated transaction failure")
            
            # Verify rollback failure is mentioned in error
            error_msg = str(exc_info.value)
            assert "CRITICAL" in error_msg
            assert "Rollback also failed" in error_msg
            assert "Data integrity may be compromised" in error_msg


class TestTwoPhaseCommitRollback:
    """Test rollback failure handling in TwoPhaseCommitCoordinator."""
    
    def test_phase1_rollback_failure_is_propagated(self):
        """Test that Phase 1 rollback failures are properly reported."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            coordinator = TwoPhaseCommitCoordinator(project_path)
            
            # Create test state file
            file1 = project_path / "test1.json"
            file1.write_text('{"value": 1}')
            
            # Create a participant that will fail prepare
            failing_participant = StateFileParticipant(
                name="failing",
                file_path=project_path / "nonexistent.json",
                update_fn=lambda data: (_ for _ in ()).throw(Exception("Prepare failed"))
            )
            
            # Create a participant that will succeed prepare but we need to test rollback
            file2 = project_path / "test2.json"
            file2.write_text('{"value": 2}')
            
            # Mock the rollback to fail
            def failing_rollback(data):
                raise IOError("Rollback failed")
            
            successful_participant = Participant(
                name="successful",
                file_path=file2,
                prepare_fn=lambda: (True, {"value": 999}, None),
                commit_fn=lambda data: True,
                rollback_fn=failing_rollback,
                status=ParticipantStatus.PREPARED,
                vote=True,
                vote_data={"value": 999}
            )
            
            participants = [
                failing_participant.to_participant(),
                successful_participant
            ]
            
            result = coordinator.execute_transaction(participants)
            
            # Verify rollback failure is reported
            assert result["success"] is False
            assert result["phase2_result"] == "rollback_failed"
            assert "critical" in result
            assert result["critical"] is True
            assert "CRITICAL" in result["error"]
            assert "Rollback also failed" in result["error"]