"""
Tests for Atomic Transactions in Carby Sprint Framework.

Tests the atomic_sprint_update and atomic_work_item_update context managers
to ensure data integrity under various conditions including failure scenarios.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

from carby_sprint.transaction import (
    atomic_sprint_update,
    atomic_work_item_update,
    TransactionError,
    validate_gate_transition,
    validate_work_item_exists,
    ensure_directory_structure
)


def test_atomic_sprint_update_success():
    """Test successful atomic sprint update."""
    with tempfile.TemporaryDirectory() as temp_dir:
        sprint_path = Path(temp_dir) / "test_sprint"
        sprint_path.mkdir()
        
        # Create initial metadata
        metadata_path = sprint_path / "metadata.json"
        initial_data = {"sprint_id": "test", "status": "initial"}
        with open(metadata_path, "w") as f:
            json.dump(initial_data, f)
        
        # Perform atomic update
        with atomic_sprint_update(sprint_path) as data:
            data["status"] = "updated"
            data["new_field"] = "value"
        
        # Verify the update was applied
        with open(metadata_path, "r") as f:
            result = json.load(f)
        
        assert result["status"] == "updated"
        assert result["new_field"] == "value"
        assert result["sprint_id"] == "test"


def test_atomic_sprint_update_failure_rollback():
    """Test that atomic sprint update rolls back on failure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        sprint_path = Path(temp_dir) / "test_sprint"
        sprint_path.mkdir()
        
        # Create initial metadata
        metadata_path = sprint_path / "metadata.json"
        initial_data = {"sprint_id": "test", "status": "initial"}
        with open(metadata_path, "w") as f:
            json.dump(initial_data, f)
        
        # Get initial file stats to compare later
        initial_stat = metadata_path.stat()
        
        # Perform atomic update that fails
        try:
            with atomic_sprint_update(sprint_path) as data:
                data["status"] = "updated"
                raise RuntimeError("Simulated failure")
        except TransactionError:
            pass  # Expected
        
        # Verify the update was rolled back
        with open(metadata_path, "r") as f:
            result = json.load(f)
        
        assert result["status"] == "initial"
        assert "new_field" not in result


def test_atomic_sprint_update_new_sprint():
    """Test atomic sprint update for new sprint (no initial file)."""
    with tempfile.TemporaryDirectory() as temp_dir:
        sprint_path = Path(temp_dir) / "new_sprint"
        sprint_path.mkdir()
        
        # Perform atomic update on non-existent file
        with atomic_sprint_update(sprint_path) as data:
            data.update({"sprint_id": "new_test", "status": "created"})
        
        # Verify the file was created
        metadata_path = sprint_path / "metadata.json"
        assert metadata_path.exists()
        
        with open(metadata_path, "r") as f:
            result = json.load(f)
        
        assert result["sprint_id"] == "new_test"
        assert result["status"] == "created"


def test_atomic_work_item_update_success():
    """Test successful atomic work item update."""
    with tempfile.TemporaryDirectory() as temp_dir:
        work_items_dir = Path(temp_dir)
        
        # Create initial work item
        work_item_path = work_items_dir / "test_wi.json"
        initial_data = {"id": "test_wi", "status": "initial", "content": "original"}
        with open(work_item_path, "w") as f:
            json.dump(initial_data, f)
        
        # Perform atomic update
        with atomic_work_item_update(work_items_dir, "test_wi") as data:
            data["status"] = "updated"
            data["content"] = "modified"
        
        # Verify the update was applied
        with open(work_item_path, "r") as f:
            result = json.load(f)
        
        assert result["status"] == "updated"
        assert result["content"] == "modified"
        assert result["id"] == "test_wi"


def test_atomic_work_item_update_failure_rollback():
    """Test that atomic work item update rolls back on failure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        work_items_dir = Path(temp_dir)
        
        # Create initial work item
        work_item_path = work_items_dir / "test_wi.json"
        initial_data = {"id": "test_wi", "status": "initial", "content": "original"}
        with open(work_item_path, "w") as f:
            json.dump(initial_data, f)
        
        # Perform atomic update that fails
        try:
            with atomic_work_item_update(work_items_dir, "test_wi") as data:
                data["status"] = "updated"
                raise RuntimeError("Simulated failure")
        except TransactionError:
            pass  # Expected
        
        # Verify the update was rolled back
        with open(work_item_path, "r") as f:
            result = json.load(f)
        
        assert result["status"] == "initial"
        assert result["content"] == "original"


def test_atomic_work_item_update_new_item():
    """Test atomic work item update for new work item."""
    with tempfile.TemporaryDirectory() as temp_dir:
        work_items_dir = Path(temp_dir)
        
        # Perform atomic update on non-existent work item
        with atomic_work_item_update(work_items_dir, "new_wi") as data:
            data.update({"id": "new_wi", "status": "created", "content": "new"})
        
        # Verify the file was created
        work_item_path = work_items_dir / "new_wi.json"
        assert work_item_path.exists()
        
        with open(work_item_path, "r") as f:
            result = json.load(f)
        
        assert result["id"] == "new_wi"
        assert result["status"] == "created"
        assert result["content"] == "new"


def test_validate_gate_transition():
    """Test gate transition validation."""
    # Valid transitions
    assert validate_gate_transition("pending", "in_progress") is True
    assert validate_gate_transition("pending", "skipped") is True
    assert validate_gate_transition("in_progress", "passed") is True
    assert validate_gate_transition("in_progress", "failed") is True
    assert validate_gate_transition("in_progress", "blocked") is True
    assert validate_gate_transition("blocked", "in_progress") is True
    assert validate_gate_transition("blocked", "failed") is True
    assert validate_gate_transition("failed", "in_progress") is True
    assert validate_gate_transition("failed", "skipped") is True
    
    # Invalid transitions
    assert validate_gate_transition("passed", "in_progress") is False
    assert validate_gate_transition("skipped", "in_progress") is False
    assert validate_gate_transition("pending", "passed") is False  # Can't skip in_progress
    assert validate_gate_transition("invalid_status", "passed") is False


def test_validate_work_item_exists():
    """Test work item existence validation."""
    with tempfile.TemporaryDirectory() as temp_dir:
        work_items_dir = Path(temp_dir)
        
        # Create a work item
        work_item_path = work_items_dir / "existing_wi.json"
        with open(work_item_path, "w") as f:
            json.dump({"id": "existing_wi"}, f)
        
        # Test existing work item
        assert validate_work_item_exists(work_items_dir, "existing_wi") is True
        
        # Test non-existing work item
        assert validate_work_item_exists(work_items_dir, "non_existing_wi") is False


def test_ensure_directory_structure():
    """Test ensuring directory structure exists."""
    with tempfile.TemporaryDirectory() as temp_dir:
        sprint_path = Path(temp_dir) / "test_sprint"
        
        # Initially directories don't exist
        assert not sprint_path.exists()
        
        # Create structure
        ensure_directory_structure(sprint_path)
        
        # Verify all directories exist
        assert sprint_path.exists()
        assert (sprint_path / "work_items").exists()
        assert (sprint_path / "gates").exists()
        assert (sprint_path / "logs").exists()


if __name__ == "__main__":
    # Run tests manually if executed directly
    test_atomic_sprint_update_success()
    print("✓ test_atomic_sprint_update_success passed")
    
    test_atomic_sprint_update_failure_rollback()
    print("✓ test_atomic_sprint_update_failure_rollback passed")
    
    test_atomic_sprint_update_new_sprint()
    print("✓ test_atomic_sprint_update_new_sprint passed")
    
    test_atomic_work_item_update_success()
    print("✓ test_atomic_work_item_update_success passed")
    
    test_atomic_work_item_update_failure_rollback()
    print("✓ test_atomic_work_item_update_failure_rollback passed")
    
    test_atomic_work_item_update_new_item()
    print("✓ test_atomic_work_item_update_new_item passed")
    
    test_validate_gate_transition()
    print("✓ test_validate_gate_transition passed")
    
    test_validate_work_item_exists()
    print("✓ test_validate_work_item_exists passed")
    
    test_ensure_directory_structure()
    print("✓ test_ensure_directory_structure passed")
    
    print("\nAll transaction tests passed! ✓")