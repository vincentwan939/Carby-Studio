"""Unit tests for CLIExecutor class."""

import json
import os
import tempfile
import shutil
from pathlib import Path
import pytest
from unittest.mock import Mock, patch, MagicMock
import subprocess

from cli_executor import CLIExecutor, CLIResult, SecurityError


class TestCLIExecutor:
    """Test CLIExecutor class."""

    def test_validate_project_name_valid(self):
        """Test project name validation with valid names."""
        executor = CLIExecutor()
        valid_names = [
            "test-project",
            "my-project-123",
            "project1",
            "very-long-project-name-with-many-parts"
        ]

        for name in valid_names:
            executor._validate_project_name(name)  # Should not raise exception

    def test_validate_project_name_invalid(self):
        """Test project name validation with invalid names."""
        executor = CLIExecutor()
        invalid_names = [
            "",
            "test project",  # space
            "test_project",  # underscore
            "TestProject",  # uppercase
            "test@project",  # special character
            "a" * 51  # too long
        ]

        for name in invalid_names:
            with pytest.raises(SecurityError):
                executor._validate_project_name(name)

    def test_validate_gate_number_valid(self):
        """Test gate number validation with valid numbers."""
        executor = CLIExecutor()
        for gate in [1, 2, 3, 4, 5]:
            executor._validate_gate_number(gate)  # Should not raise exception

    def test_validate_gate_number_invalid(self):
        """Test gate number validation with invalid numbers."""
        executor = CLIExecutor()
        invalid_gates = [0, 6, -1, 10]

        for gate in invalid_gates:
            with pytest.raises(SecurityError):
                executor._validate_gate_number(gate)

    @patch('subprocess.run')
    def test_run_success(self, mock_run):
        """Test _run method with successful command."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "success output"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor._run(["echo", "test"])

        assert result.success is True
        assert result.stdout == "success output"
        assert result.stderr == ""
        assert result.return_code == 0
        mock_run.assert_called_once()

    @patch('subprocess.run')
    def test_run_failure(self, mock_run):
        """Test _run method with failed command."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error message"
        mock_run.return_value = mock_result

        result = executor._run(["fake", "command"])

        assert result.success is False
        assert result.stderr == "error message"
        assert result.return_code == 1

    @patch('subprocess.run')
    def test_run_timeout(self, mock_run):
        """Test _run method with timeout."""
        executor = CLIExecutor()
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["sleep", "100"], timeout=1)
    
        result = executor._run(["sleep", "100"])
    
        assert result.success is False
        assert "timed out" in result.stderr.lower()

    # NEW TESTS FOR CARBY-SPRINT COMMANDS

    @patch('subprocess.run')
    def test_sprint_init_success(self, mock_run):
        """Test sprint_init command success."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Sprint initialized successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor.sprint_init("test-sprint", "test-project", "Test goal")

        assert result.success is True
        assert result.stdout == "Sprint initialized successfully"
        # Note: The actual call includes cwd=None which is passed by the _run method
        mock_run.assert_called_once()
        # Verify the command is correct by checking the first argument
        called_args = mock_run.call_args
        assert called_args[0][0] == ["carby-sprint", "init", "test-sprint", "--project", "test-project", "--goal", "Test goal"]
        assert called_args[1]['capture_output'] is True
        assert called_args[1]['text'] is True
        assert called_args[1]['timeout'] == 60

    @patch('subprocess.run')
    def test_sprint_init_with_duration(self, mock_run):
        """Test sprint_init command with duration."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Sprint initialized successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor.sprint_init("test-sprint", "test-project", "Test goal", duration=7)

        assert result.success is True
        # Note: The actual call includes cwd=None which is passed by the _run method
        mock_run.assert_called_once()
        # Verify the command is correct by checking the first argument
        called_args = mock_run.call_args
        assert called_args[0][0] == ["carby-sprint", "init", "test-sprint", "--project", "test-project", "--goal", "Test goal", "--duration", "7"]
        assert called_args[1]['capture_output'] is True
        assert called_args[1]['text'] is True
        assert called_args[1]['timeout'] == 60

    def test_sprint_init_invalid_name(self):
        """Test sprint_init with invalid sprint name."""
        executor = CLIExecutor()
        result = executor.sprint_init("invalid name", "test-project", "Test goal")
        assert result.success is False
        assert "invalid" in result.stderr.lower() or "letters" in result.stderr.lower()

    def test_sprint_init_long_goal(self):
        """Test sprint_init with too long goal."""
        executor = CLIExecutor()
        long_goal = "A" * 600
        result = executor.sprint_init("test-sprint", "test-project", long_goal)
        assert result.success is False
        assert "500" in result.stderr

    @patch('subprocess.run')
    def test_sprint_start_success(self, mock_run):
        """Test sprint_start command success."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Sprint started successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor.sprint_start("test-sprint")

        assert result.success is True
        # Note: The actual call includes cwd=None which is passed by the _run method
        mock_run.assert_called_once()
        # Verify the command is correct by checking the first argument
        called_args = mock_run.call_args
        assert called_args[0][0] == ["carby-sprint", "start", "test-sprint", "--mode", "sequential"]
        assert called_args[1]['capture_output'] is True
        assert called_args[1]['text'] is True
        assert called_args[1]['timeout'] == 60

    @patch('subprocess.run')
    def test_sprint_start_parallel_mode(self, mock_run):
        """Test sprint_start command with parallel mode."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Sprint started successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor.sprint_start("test-sprint", mode="parallel")

        assert result.success is True
        # Note: The actual call includes cwd=None which is passed by the _run method
        mock_run.assert_called_once()
        # Verify the command is correct by checking the first argument
        called_args = mock_run.call_args
        assert called_args[0][0] == ["carby-sprint", "start", "test-sprint", "--mode", "parallel"]
        assert called_args[1]['capture_output'] is True
        assert called_args[1]['text'] is True
        assert called_args[1]['timeout'] == 60

    def test_sprint_start_invalid_mode(self):
        """Test sprint_start with invalid mode."""
        executor = CLIExecutor()
        result = executor.sprint_start("test-sprint", mode="invalid-mode")
        assert result.success is False
        assert "sequential" in result.stderr
        assert "parallel" in result.stderr

    @patch('subprocess.run')
    def test_sprint_gate_success(self, mock_run):
        """Test sprint_gate command success."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Gate advanced successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor.sprint_gate("test-sprint", 2)

        assert result.success is True
        # Note: The actual call includes cwd=None which is passed by the _run method
        mock_run.assert_called_once()
        # Verify the command is correct by checking the first argument
        called_args = mock_run.call_args
        assert called_args[0][0] == ["carby-sprint", "gate", "test-sprint", "2"]
        assert called_args[1]['capture_output'] is True
        assert called_args[1]['text'] is True
        assert called_args[1]['timeout'] == 60

    @patch('subprocess.run')
    def test_sprint_gate_with_flags(self, mock_run):
        """Test sprint_gate command with force and retry flags."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Gate advanced successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor.sprint_gate("test-sprint", 3, force=True, retry=True)

        assert result.success is True
        # Note: The actual call includes cwd=None which is passed by the _run method
        mock_run.assert_called_once()
        # Verify the command is correct by checking the first argument
        called_args = mock_run.call_args
        assert called_args[0][0] == ["carby-sprint", "gate", "test-sprint", "3", "--force", "--retry"]
        assert called_args[1]['capture_output'] is True
        assert called_args[1]['text'] is True
        assert called_args[1]['timeout'] == 60

    @patch('subprocess.run')
    def test_sprint_approve_success(self, mock_run):
        """Test sprint_approve command success."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Approved successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor.sprint_approve("test-sprint")

        assert result.success is True
        # Note: The actual call includes cwd=None which is passed by the _run method
        mock_run.assert_called_once()
        # Verify the command is correct by checking the first argument
        called_args = mock_run.call_args
        assert called_args[0][0] == ["carby-sprint", "approve", "test-sprint"]
        assert called_args[1]['capture_output'] is True
        assert called_args[1]['text'] is True
        assert called_args[1]['timeout'] == 60

    @patch('subprocess.run')
    def test_sprint_approve_with_phase_and_auto_advance(self, mock_run):
        """Test sprint_approve with phase ID and auto-advance."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Approved successfully"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = executor.sprint_approve("test-sprint", phase_id="phase-1", auto_advance=True)

        assert result.success is True
        # Note: The actual call includes cwd=None which is passed by the _run method
        mock_run.assert_called_once()
        # Verify the command is correct by checking the first argument
        called_args = mock_run.call_args
        assert called_args[0][0] == ["carby-sprint", "approve", "test-sprint", "phase-1", "--auto-advance"]
        assert called_args[1]['capture_output'] is True
        assert called_args[1]['text'] is True
        assert called_args[1]['timeout'] == 60

    def test_sprint_approve_invalid_phase_id(self):
        """Test sprint_approve with invalid phase ID."""
        executor = CLIExecutor()
        result = executor.sprint_approve("test-sprint", phase_id="invalid phase id")
        assert result.success is False
        assert "alphanumeric" in result.stderr

    # BACKWARD COMPATIBILITY TESTS

    @patch('subprocess.run')
    def test_dispatch_backward_compatibility(self, mock_run):
        """Test dispatch method backward compatibility."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Dispatched"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # This should map to sprint_gate for discover (gate 1)
        result = executor.dispatch("test-project", "discover")

        # Verify that the method works without throwing validation errors
        assert result.success is True

    @patch('subprocess.run')
    def test_skip_backward_compatibility(self, mock_run):
        """Test skip method backward compatibility."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Skipped"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # This should map to sprint_gate with force=True for discover (gate 1)
        result = executor.skip("test-project", "discover")

        assert result.success is True

    @patch('subprocess.run')
    def test_retry_backward_compatibility(self, mock_run):
        """Test retry method backward compatibility."""
        executor = CLIExecutor()
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Retried"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # This should map to sprint_gate with retry=True for discover (gate 1)
        result = executor.retry("test-project", "discover")

        assert result.success is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])