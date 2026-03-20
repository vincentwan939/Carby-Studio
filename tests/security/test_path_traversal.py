"""
Security Tests for Path Traversal Prevention in Carby Sprint Framework.

Tests that validate the path traversal prevention mechanisms in the framework.
"""

import tempfile
import pytest
from pathlib import Path
import json

from carby_sprint.sprint_repository import SprintRepository
from carby_sprint.path_utils import validate_sprint_id, validate_work_item_id, safe_join_path


def test_sprint_id_validation():
    """Test that sprint ID validation prevents path traversal."""
    # Valid sprint IDs should pass
    assert validate_sprint_id("valid-sprint-id")
    assert validate_sprint_id("valid_sprint_id")
    assert validate_sprint_id("validSprint123")
    
    # Invalid sprint IDs should raise ValueError
    with pytest.raises(ValueError, match="path traversal characters"):
        validate_sprint_id("../invalid")
    
    with pytest.raises(ValueError, match="path traversal characters"):
        validate_sprint_id("invalid/..")
    
    with pytest.raises(ValueError, match="path traversal characters"):
        validate_sprint_id("invalid\\..")
    
    with pytest.raises(ValueError, match="path traversal characters"):
        validate_sprint_id("..\\invalid")
    
    with pytest.raises(ValueError, match="Contains invalid characters"):
        validate_sprint_id("invalid<sprint>")
    
    with pytest.raises(ValueError, match="Contains invalid characters"):
        validate_sprint_id("invalid|sprint")


def test_work_item_id_validation():
    """Test that work item ID validation prevents path traversal."""
    # Valid work item IDs should pass
    assert validate_work_item_id("valid-work-item-id")
    assert validate_work_item_id("valid_work_item_id")
    assert validate_work_item_id("validWorkItem123")
    
    # Invalid work item IDs should raise ValueError
    with pytest.raises(ValueError, match="path traversal characters"):
        validate_work_item_id("../invalid")
    
    with pytest.raises(ValueError, match="path traversal characters"):
        validate_work_item_id("invalid/..")
    
    with pytest.raises(ValueError, match="path traversal characters"):
        validate_work_item_id("invalid\\..")


def test_safe_join_path():
    """Test safe path joining functionality."""
    # Valid paths should work
    result = safe_join_path("base", "subdir", "file.txt")
    assert result == "base/subdir/file.txt" or result == "base\\subdir\\file.txt"  # OS dependent
    
    # Path traversal should be prevented (at path traversal check)
    with pytest.raises(ValueError, match="path traversal characters"):
        safe_join_path("../base", "subdir", "file.txt")
    
    with pytest.raises(ValueError, match="path traversal characters"):
        safe_join_path("base", "../subdir", "file.txt")
    
    with pytest.raises(ValueError, match="path traversal characters"):
        safe_join_path("base", "subdir", "../../file.txt")


def test_repository_path_traversal_protection():
    """Test that SprintRepository prevents path traversal attacks."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = SprintRepository(temp_dir)
        
        # Attempt to access a sprint with path traversal - should raise ValueError
        with pytest.raises(ValueError, match="path traversal characters"):
            repo.exists("../../etc/passwd")
        
        with pytest.raises(ValueError, match="path traversal characters"):
            repo.get_sprint_path("../sensitive_directory")
        
        # Valid sprint operations should still work
        valid_sprint_id = "test-sprint-123"
        assert repo.get_sprint_path(valid_sprint_id) == Path(temp_dir) / valid_sprint_id


def test_work_item_path_traversal_protection():
    """Test that work item operations prevent path traversal."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = SprintRepository(temp_dir)
        
        # Create a valid sprint first
        valid_sprint_id = "test-sprint"
        sprint_data, paths = repo.create(valid_sprint_id, "Test Project", "Test Goal")
        
        # Try to load work item with path traversal - should raise ValueError
        with pytest.raises(ValueError, match="path traversal characters"):
            repo.load_work_item(paths, "../../../etc/passwd")
        
        with pytest.raises(ValueError, match="path traversal characters"):
            repo.delete_work_item(paths, "../../../etc/passwd")


def test_metadata_file_creation_safe():
    """Test that metadata files are created safely."""
    with tempfile.TemporaryDirectory() as temp_dir:
        repo = SprintRepository(temp_dir)
        
        # Create a valid sprint
        sprint_id = "safe-test-sprint"
        sprint_data, paths = repo.create(sprint_id, "Test Project", "Test Goal")
        
        # Verify the metadata file exists in the correct location
        expected_metadata_path = Path(temp_dir) / sprint_id / "metadata.json"
        assert expected_metadata_path.exists()
        
        # Verify that no adjacent directories were affected
        assert not (Path(temp_dir) / ".." / sprint_id / "metadata.json").exists()


if __name__ == "__main__":
    # Run the tests
    test_sprint_id_validation()
    test_work_item_id_validation()
    test_safe_join_path()
    test_repository_path_traversal_protection()
    test_work_item_path_traversal_protection()
    test_metadata_file_creation_safe()
    print("All path traversal security tests passed!")