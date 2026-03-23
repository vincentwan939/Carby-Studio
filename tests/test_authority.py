"""Tests for carby-sprint authority module."""

import json
import tempfile
from pathlib import Path

import pytest

import sys
sys.path.insert(0, '/Users/wants01/.openclaw/workspace/skills/carby-studio')

from carby_sprint.authority import (
    DecisionAuthority,
    AuthorityRule,
    AuthorityConfig,
    AuthorityManager
)


class TestDecisionAuthority:
    """Test DecisionAuthority enum."""

    def test_authority_levels_exist(self):
        """Test that all authority levels exist."""
        assert hasattr(DecisionAuthority, 'HUMAN_REQUIRED')
        assert hasattr(DecisionAuthority, 'AGENT_RECOMMENDS')
        assert hasattr(DecisionAuthority, 'AGENT_AUTONOMOUS')

        # Test values
        assert DecisionAuthority.HUMAN_REQUIRED.value == 'human_required'
        assert DecisionAuthority.AGENT_RECOMMENDS.value == 'agent_recommends'
        assert DecisionAuthority.AGENT_AUTONOMOUS.value == 'agent_autonomous'


class TestAuthorityRule:
    """Test AuthorityRule dataclass."""

    def test_authority_rule_creation(self):
        """Test AuthorityRule creation."""
        rule = AuthorityRule(
            decision_type='security_change',
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            description='Security changes require approval',
            priority=10
        )

        assert rule.decision_type == 'security_change'
        assert rule.authority_level == DecisionAuthority.HUMAN_REQUIRED
        assert rule.description == 'Security changes require approval'
        assert rule.priority == 10

    def test_authority_rule_defaults(self):
        """Test AuthorityRule default values."""
        rule = AuthorityRule(
            decision_type='test',
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS
        )

        assert rule.context_pattern is None
        assert rule.description is None
        assert rule.priority == 0


class TestAuthorityConfig:
    """Test AuthorityConfig class."""

    def test_config_creation(self):
        """Test AuthorityConfig creation."""
        config = AuthorityConfig(
            sprint_id='test-sprint',
            default_authority=DecisionAuthority.AGENT_RECOMMENDS
        )

        assert config.sprint_id == 'test-sprint'
        assert config.default_authority == DecisionAuthority.AGENT_RECOMMENDS
        assert config.rules == []
        assert config.enabled is True

    def test_add_rule(self):
        """Test adding rules to config."""
        config = AuthorityConfig(sprint_id='test-sprint')

        rule = AuthorityRule(
            decision_type='test',
            authority_level=DecisionAuthority.HUMAN_REQUIRED
        )
        config.add_rule(rule)

        assert len(config.rules) == 1
        assert config.rules[0] == rule

    def test_get_authority_for_decision(self):
        """Test getting authority for decision."""
        config = AuthorityConfig(sprint_id='test-sprint')

        # Add a specific rule
        rule = AuthorityRule(
            decision_type='security_change',
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            priority=10
        )
        config.add_rule(rule)

        # Test specific rule match
        authority = config.get_authority_for_decision('security_change')
        assert authority == DecisionAuthority.HUMAN_REQUIRED

        # Test default for unknown decision type
        authority = config.get_authority_for_decision('unknown_type')
        assert authority == DecisionAuthority.AGENT_RECOMMENDS  # default

    def test_context_matching(self):
        """Test context pattern matching."""
        config = AuthorityConfig(sprint_id='test-sprint')

        # Add rule with context pattern
        rule = AuthorityRule(
            decision_type='dependency_update',
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            context_pattern='critical',
            priority=8
        )
        config.add_rule(rule)

        # Test context matching
        context = {'package': 'critical-package', 'severity': 'high'}
        authority = config.get_authority_for_decision('dependency_update', context)
        assert authority == DecisionAuthority.HUMAN_REQUIRED

        # Test non-matching context
        context = {'package': 'normal-package', 'severity': 'low'}
        authority = config.get_authority_for_decision('dependency_update', context)
        assert authority == DecisionAuthority.AGENT_RECOMMENDS  # default


class TestAuthorityManager:
    """Test AuthorityManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Provide a temporary directory for tests."""
        with tempfile.TemporaryDirectory() as tmp:
            yield Path(tmp)

    def test_manager_initialization(self, temp_dir):
        """Test AuthorityManager initialization."""
        manager = AuthorityManager(str(temp_dir))

        assert manager.project_dir == temp_dir
        assert manager.sprint_dir == temp_dir / '.carby-sprints'

    def test_create_default_config(self, temp_dir):
        """Test creating default configuration."""
        manager = AuthorityManager(str(temp_dir))
        config = manager.create_default_config('test-sprint')

        assert config.sprint_id == 'test-sprint'
        assert config.default_authority == DecisionAuthority.AGENT_RECOMMENDS
        assert len(config.rules) > 0  # Should have default rules

        # Check for expected default rules
        rule_types = [rule.decision_type for rule in config.rules]
        assert 'security_change' in rule_types
        assert 'infrastructure_change' in rule_types
        assert 'documentation' in rule_types

    def test_load_and_save_config(self, temp_dir):
        """Test loading and saving configuration."""
        manager = AuthorityManager(str(temp_dir))

        # Create config with custom rules
        config = AuthorityConfig(sprint_id='test-sprint')
        rule = AuthorityRule(
            decision_type='custom_rule',
            authority_level=DecisionAuthority.HUMAN_REQUIRED
        )
        config.add_rule(rule)

        # Save config
        manager.save_config(config)

        # Load config
        loaded_config = manager.load_config('test-sprint')

        assert loaded_config.sprint_id == 'test-sprint'
        assert len(loaded_config.rules) == 1
        assert loaded_config.rules[0].decision_type == 'custom_rule'
        assert loaded_config.rules[0].authority_level == DecisionAuthority.HUMAN_REQUIRED

    def test_should_require_approval(self, temp_dir):
        """Test should_require_approval method."""
        manager = AuthorityManager(str(temp_dir))

        # Create and save default config which includes standard rules
        config = manager.create_default_config('test-sprint')
        manager.save_config(config)

        # By default, security changes should require approval
        requires_approval = manager.should_require_approval(
            'test-sprint',
            'security_change'
        )
        assert requires_approval is True

        # Documentation changes should not require approval by default
        requires_approval = manager.should_require_approval(
            'test-sprint',
            'documentation'
        )
        assert requires_approval is False

    def test_get_approval_recommendation(self, temp_dir):
        """Test get_approval_recommendation method."""
        manager = AuthorityManager(str(temp_dir))
        
        # Create and save default config which includes standard rules
        config = manager.create_default_config('test-sprint')
        manager.save_config(config)
        
        # Security changes should require approval
        recommendation = manager.get_approval_recommendation(
            'test-sprint',
            'security_change'
        )
        assert 'REQUIRES APPROVAL' in recommendation

        # Documentation changes should be autonomous
        recommendation = manager.get_approval_recommendation(
            'test-sprint',
            'documentation'
        )
        assert 'AUTONOMOUS' in recommendation