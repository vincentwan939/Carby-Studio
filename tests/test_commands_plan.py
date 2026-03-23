"""Tests for carby-sprint plan command."""

import json
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

import sys
sys.path.insert(0, '/Users/wants01/.openclaw/workspace/skills/carby-studio')

from carby_sprint.cli import cli
from carby_sprint.sprint_repository import SprintRepository


class TestPlanCommand:
    """Test sprint plan command."""

    @pytest.fixture
    def temp_dir(self):
        """Provide a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    @pytest.fixture
    def runner(self):
        """Provide a Click test runner."""
        return CliRunner()

    def _create_test_sprint(self, temp_dir, runner):
        """Helper to create a test sprint."""
        result = runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject',
            '--goal', 'Test Goal',
            '--output-dir', str(temp_dir)
        ])
        assert result.exit_code == 0
        return temp_dir / 'test-sprint'

    def test_plan_creates_work_items(self, temp_dir, runner):
        """Test that plan creates work item files."""
        self._create_test_sprint(temp_dir, runner)

        result = runner.invoke(cli, [
            'plan', 'test-sprint',
            '--work-items', 'Task1,Task2,Task3',
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code == 0

        # Check work items directory
        work_items_dir = temp_dir / 'test-sprint' / 'work_items'
        assert work_items_dir.exists()

        # Check individual work item files created
        assert (work_items_dir / 'WI-1.json').exists()
        assert (work_items_dir / 'WI-2.json').exists()
        assert (work_items_dir / 'WI-3.json').exists()

    def test_plan_updates_sprint_metadata(self, temp_dir, runner):
        """Test that plan updates sprint metadata with work items."""
        self._create_test_sprint(temp_dir, runner)

        result = runner.invoke(cli, [
            'plan', 'test-sprint',
            '--work-items', 'Task1,Task2',
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code == 0

        # Check metadata updated
        metadata_path = temp_dir / 'test-sprint' / 'metadata.json'
        with open(metadata_path) as f:
            metadata = json.load(f)

        assert metadata['status'] == 'planned'
        assert metadata['work_items'] == ['WI-1', 'WI-2']
        assert metadata['work_item_count'] == 2
        assert 'planned_at' in metadata

    def test_plan_work_item_content(self, temp_dir, runner):
        """Test that plan creates correct work item content."""
        self._create_test_sprint(temp_dir, runner)

        result = runner.invoke(cli, [
            'plan', 'test-sprint',
            '--work-items', 'Implement Feature,Write Tests',
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code == 0

        # Check work item content
        wi_path = temp_dir / 'test-sprint' / 'work_items' / 'WI-1.json'
        with open(wi_path) as f:
            work_item = json.load(f)

        assert work_item['id'] == 'WI-1'
        assert work_item['title'] == 'Implement Feature'
        assert work_item['status'] == 'planned'
        assert work_item['priority'] == 'medium'

    def test_plan_fails_for_nonexistent_sprint(self, temp_dir, runner):
        """Test that plan fails if sprint does not exist."""
        result = runner.invoke(cli, [
            'plan', 'nonexistent-sprint',
            '--work-items', 'Task1',
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code != 0
        assert 'not found' in result.output.lower()

    def test_plan_from_file(self, temp_dir, runner):
        """Test plan with work items from file."""
        self._create_test_sprint(temp_dir, runner)

        # Create work items file
        work_items_file = temp_dir / 'work_items.json'
        work_items_data = {
            'work_items': [
                {'id': 'TASK-001', 'title': 'First Task', 'priority': 'high'},
                {'id': 'TASK-002', 'title': 'Second Task', 'priority': 'low'}
            ]
        }
        with open(work_items_file, 'w') as f:
            json.dump(work_items_data, f)

        result = runner.invoke(cli, [
            'plan', 'test-sprint',
            '--work-items', 'dummy',  # Required but overridden by --from-file
            '--from-file', str(work_items_file),
            '--output-dir', str(temp_dir)
        ])

        assert result.exit_code == 0

        # Check work items created with custom IDs
        wi1_path = temp_dir / 'test-sprint' / 'work_items' / 'TASK-001.json'
        wi2_path = temp_dir / 'test-sprint' / 'work_items' / 'TASK-002.json'
        assert wi1_path.exists()
        assert wi2_path.exists()

        with open(wi1_path) as f:
            wi1 = json.load(f)
        assert wi1['title'] == 'First Task'
        assert wi1['priority'] == 'high'


class TestPlanIntegration:
    """Integration tests for plan command with SprintRepository."""
    
    @pytest.fixture
    def plan_temp_dir(self):
        """Provide a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)
    
    @pytest.fixture
    def plan_repo(self, plan_temp_dir):
        """Provide a SprintRepository instance."""
        return SprintRepository(str(plan_temp_dir))
    
    @pytest.fixture
    def plan_runner(self):
        """Provide a Click test runner."""
        return CliRunner()
    
    def test_plan_creates_work_items_accessible_via_repository(self, plan_temp_dir, plan_repo, plan_runner):
        """Test that work items created via CLI are accessible via repository."""
        # Create sprint via CLI
        plan_runner.invoke(cli, [
            'init', 'test-sprint',
            '--project', 'TestProject',
            '--goal', 'Test Goal',
            '--output-dir', str(plan_temp_dir)
        ])
        
        # Plan work items via CLI
        plan_runner.invoke(cli, [
            'plan', 'test-sprint',
            '--work-items', 'Task1,Task2',
            '--output-dir', str(plan_temp_dir)
        ])
        
        # Verify via repository
        sprint_data, paths = plan_repo.load('test-sprint')
        assert sprint_data['work_items'] == ['WI-1', 'WI-2']
        
        # Verify work item accessible
        wi = plan_repo.load_work_item(paths, 'WI-1')
        assert wi['title'] == 'Task1'