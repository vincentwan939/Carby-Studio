"""Tests for carby-sprint init command."""

import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner

import sys
sys.path.insert(0, '/Users/wants01/.openclaw/workspace/skills/carby-studio')

from carby_sprint.cli import cli
from carby_sprint.sprint_repository import SprintRepository


class TestInitCommand:
    """Test sprint initialization command."""

    @pytest.fixture
    def temp_dir(self):
        """Provide a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def runner(self):
        """Provide a Click test runner."""
        return CliRunner()

    def test_init_creates_sprint_directory(self, temp_dir, runner):
        """Test that init creates sprint directory structure."""
        result = runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject',
            '--goal', 'Test Goal',
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code == 0

        sprint_dir = temp_dir / 'test-sprint'
        assert sprint_dir.exists()
        assert (sprint_dir / 'metadata.json').exists()
        assert (sprint_dir / 'work_items').exists()
        assert (sprint_dir / 'gates').exists()
        assert (sprint_dir / 'logs').exists()

    def test_init_creates_correct_metadata(self, temp_dir, runner):
        """Test that init creates correct metadata structure."""
        result = runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject',
            '--goal', 'Test Goal',
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code == 0

        metadata_path = temp_dir / 'test-sprint' / 'metadata.json'
        with open(metadata_path) as f:
            metadata = json.load(f)

        assert metadata['sprint_id'] == 'test-sprint'
        assert metadata['project'] == 'TestProject'
        assert metadata['goal'] == 'Test Goal'
        assert metadata['status'] == 'initialized'
        assert metadata['duration_days'] == 14

    def test_init_fails_if_sprint_exists(self, temp_dir, runner):
        """Test that init fails if sprint already exists."""
        result1 = runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject',
            '--goal', 'Test Goal',
            '--output-dir', str(temp_dir)
        ])
        assert result1.exit_code == 0
        
        result2 = runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject2',
            '--goal', 'Test Goal 2',
            '--output-dir', str(temp_dir)
        ])

        assert result2.exit_code != 0
        assert 'already exists' in result2.output.lower()

    def test_init_with_custom_duration(self, temp_dir, runner):
        """Test init with custom duration."""
        result = runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject',
            '--goal', 'Test Goal',
            '--duration', '7',
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code == 0

        metadata_path = temp_dir / 'test-sprint' / 'metadata.json'
        with open(metadata_path) as f:
            metadata = json.load(f)

        assert metadata['duration_days'] == 7

    def test_init_creates_all_gates(self, temp_dir, runner):
        """Test that init creates all 5 gates with pending status."""
        result = runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject',
            '--goal', 'Test Goal',
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code == 0

        metadata_path = temp_dir / 'test-sprint' / 'metadata.json'
        with open(metadata_path) as f:
            metadata = json.load(f)

        gates = metadata['gates']
        assert len(gates) == 5
        assert gates['1']['name'] == 'Planning Gate'
        assert gates['2']['name'] == 'Design Gate'
        assert gates['3']['name'] == 'Implementation Gate'
        assert gates['4']['name'] == 'Validation Gate'
        assert gates['5']['name'] == 'Release Gate'

    def test_init_missing_required_project(self, runner):
        """Test that init fails without required --project option."""
        result = runner.invoke(cli, [
            'init', 'test-sprint',
            '--goal', 'Test Goal'
        ])
        assert result.exit_code != 0

    def test_init_missing_required_goal(self, runner):
        """Test that init fails without required --goal option."""
        result = runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject'
        ])
        assert result.exit_code != 0