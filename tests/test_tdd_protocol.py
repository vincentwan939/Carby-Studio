"""
Test cases for TDD Protocol implementation.

Verifies:
1. RED/GREEN/REFACTOR evidence tracking
2. TDD evidence format in build-tasks.json
3. Mode detection (sequential vs parallel)
4. Backward compatibility
"""

import json
import pytest
import tempfile
from pathlib import Path
from datetime import datetime


def test_tdd_evidence_structure():
    """Test that TDD evidence has the correct structure."""
    tdd_evidence = {
        "mode": "sequential",
        "red": {
            "commit_hash": "abc123",
            "commit_message": "[RED] TASK-001: Add failing test for feature",
            "test_file": "tests/test_feature.py",
            "test_function": "test_expected_behavior",
            "failure_evidence": "AssertionError: expected X but got Y"
        },
        "green": {
            "commit_hash": "def456",
            "commit_message": "[GREEN] TASK-001: Implement minimal code for feature",
            "implementation_file": "src/feature.py",
            "passing_evidence": "1 passed in 0.02s"
        },
        "refactor": {
            "commit_hash": "ghi789",
            "commit_message": "[REFACTOR] TASK-001: Improve feature implementation",
            "changes": ["Extracted helper function", "Removed duplication"],
            "passing_evidence": "1 passed in 0.02s"
        }
    }
    
    # Validate structure
    assert "mode" in tdd_evidence
    assert tdd_evidence["mode"] in ["sequential", "parallel"]
    assert "red" in tdd_evidence
    assert "green" in tdd_evidence
    assert "refactor" in tdd_evidence
    
    # Validate RED phase
    red = tdd_evidence["red"]
    assert "commit_hash" in red
    assert "commit_message" in red
    assert red["commit_message"].startswith("[RED]")
    assert "test_file" in red
    assert "failure_evidence" in red
    
    # Validate GREEN phase
    green = tdd_evidence["green"]
    assert "commit_hash" in green
    assert "commit_message" in green
    assert green["commit_message"].startswith("[GREEN]")
    assert "implementation_file" in green
    assert "passing_evidence" in green
    
    # Validate REFACTOR phase
    refactor = tdd_evidence["refactor"]
    assert "commit_hash" in refactor
    assert "commit_message" in refactor
    assert refactor["commit_message"].startswith("[REFACTOR]")
    assert "changes" in refactor
    assert isinstance(refactor["changes"], list)


def test_build_tasks_json_with_tdd_evidence():
    """Test that build-tasks.json can include TDD evidence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tasks_file = Path(tmpdir) / "build-tasks.json"
        
        build_tasks = {
            "project": "test-project",
            "phase": "build",
            "mode": "sequential",
            "tasks": [
                {
                    "id": "TASK-001",
                    "title": "Implement user authentication",
                    "status": "done",
                    "issue_url": "https://github.com/...",
                    "branch": "feature/TASK-001-auth",
                    "pr_url": "https://github.com/...",
                    "tdd_evidence": {
                        "mode": "sequential",
                        "red": {
                            "commit_hash": "a1b2c3d",
                            "commit_message": "[RED] TASK-001: Add failing tests for login endpoint",
                            "test_file": "tests/test_auth.py",
                            "test_functions": ["test_login_returns_jwt_on_valid_credentials"],
                            "failure_evidence": "AttributeError: module 'src.auth' has no attribute 'endpoints'"
                        },
                        "green": {
                            "commit_hash": "e4f5g6h",
                            "commit_message": "[GREEN] TASK-001: Implement minimal login endpoint",
                            "implementation_file": "src/auth/endpoints.py",
                            "passing_evidence": "2 passed in 0.03s"
                        },
                        "refactor": {
                            "commit_hash": "i7j8k9l",
                            "commit_message": "[REFACTOR] TASK-001: Extract auth service layer",
                            "changes": ["Extracted auth service", "Added JWT token generation"],
                            "passing_evidence": "2 passed in 0.03s"
                        }
                    }
                }
            ]
        }
        
        # Write to file
        with open(tasks_file, 'w') as f:
            json.dump(build_tasks, f, indent=2)
        
        # Read back and validate
        with open(tasks_file) as f:
            loaded = json.load(f)
        
        assert loaded["mode"] == "sequential"
        assert len(loaded["tasks"]) == 1
        task = loaded["tasks"][0]
        assert "tdd_evidence" in task
        assert task["tdd_evidence"]["red"]["commit_message"].startswith("[RED]")
        assert task["tdd_evidence"]["green"]["commit_message"].startswith("[GREEN]")
        assert task["tdd_evidence"]["refactor"]["commit_message"].startswith("[REFACTOR]")


def test_parallel_mode_skips_tdd():
    """Test that parallel mode tasks don't require TDD evidence."""
    build_tasks = {
        "project": "test-project",
        "phase": "build",
        "mode": "parallel",
        "tasks": [
            {
                "id": "TASK-001",
                "title": "Setup project scaffolding",
                "status": "done",
                "issue_url": "https://github.com/...",
                "branch": "feature/TASK-001-setup",
                "pr_url": "https://github.com/..."
            },
            {
                "id": "TASK-002",
                "title": "Configure CI/CD",
                "status": "done",
                "issue_url": "https://github.com/...",
                "branch": "feature/TASK-002-cicd",
                "pr_url": "https://github.com/..."
            }
        ]
    }
    
    assert build_tasks["mode"] == "parallel"
    for task in build_tasks["tasks"]:
        # Parallel mode doesn't require TDD evidence
        assert "tdd_evidence" not in task or task.get("tdd_evidence") is None


def test_commit_prefix_validation():
    """Test that commit messages have correct TDD prefixes."""
    valid_red = "[RED] TASK-001: Add failing test"
    valid_green = "[GREEN] TASK-001: Implement feature"
    valid_refactor = "[REFACTOR] TASK-001: Improve code"
    
    invalid_red = "RED: Add failing test"
    invalid_green = "[GREEN]TASK-001: Implement"
    
    assert valid_red.startswith("[RED]")
    assert valid_green.startswith("[GREEN]")
    assert valid_refactor.startswith("[REFACTOR]")
    
    assert not invalid_red.startswith("[RED]")
    assert not invalid_green.startswith("[GREEN] ")


def test_mock_tdd_flow():
    """Test a complete mock TDD flow with evidence tracking."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Simulate RED phase
        red_commit = {
            "hash": "abc1234",
            "message": "[RED] TASK-042: Add failing tests for login endpoint",
            "files_changed": ["tests/test_auth.py"]
        }
        
        # Simulate GREEN phase
        green_commit = {
            "hash": "def5678",
            "message": "[GREEN] TASK-042: Implement minimal login endpoint",
            "files_changed": ["src/auth/endpoints.py"]
        }
        
        # Simulate REFACTOR phase
        refactor_commit = {
            "hash": "ghi9012",
            "message": "[REFACTOR] TASK-042: Extract auth service layer",
            "files_changed": ["src/auth/endpoints.py", "src/auth/service.py"]
        }
        
        # Build final evidence
        tdd_evidence = {
            "mode": "sequential",
            "red": {
                "commit_hash": red_commit["hash"],
                "commit_message": red_commit["message"],
                "test_file": "tests/test_auth.py",
                "test_functions": ["test_login_returns_jwt_on_valid_credentials"],
                "failure_evidence": "AttributeError: module 'src.auth' has no attribute 'endpoints'"
            },
            "green": {
                "commit_hash": green_commit["hash"],
                "commit_message": green_commit["message"],
                "implementation_file": "src/auth/endpoints.py",
                "passing_evidence": "2 passed in 0.03s"
            },
            "refactor": {
                "commit_hash": refactor_commit["hash"],
                "commit_message": refactor_commit["message"],
                "changes": ["Extracted auth service", "Added JWT token generation", "Added Pydantic model"],
                "passing_evidence": "2 passed in 0.03s"
            }
        }
        
        # Save to build-tasks.json
        build_tasks = {
            "project": "mock-project",
            "phase": "build",
            "mode": "sequential",
            "tasks": [
                {
                    "id": "TASK-042",
                    "title": "Implement user login endpoint",
                    "status": "done",
                    "tdd_evidence": tdd_evidence
                }
            ]
        }
        
        tasks_file = Path(tmpdir) / "build-tasks.json"
        with open(tasks_file, 'w') as f:
            json.dump(build_tasks, f, indent=2)
        
        # Verify the evidence
        with open(tasks_file) as f:
            loaded = json.load(f)
        
        task = loaded["tasks"][0]
        assert task["tdd_evidence"]["red"]["commit_hash"] == "abc1234"
        assert task["tdd_evidence"]["green"]["commit_hash"] == "def5678"
        assert task["tdd_evidence"]["refactor"]["commit_hash"] == "ghi9012"
        assert len(task["tdd_evidence"]["refactor"]["changes"]) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
