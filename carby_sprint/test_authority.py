"""
Test suite for authority module.

Tests the permission/authorization framework including:
- User permission checks
- Role-based access control
- Authorization decorators
- Permission validation
- Admin vs user permissions
- Permission inheritance
"""

import pytest
import tempfile
import shutil
import os
from pathlib import Path
from datetime import datetime
import json

from carby_sprint.authority import (
    DecisionAuthority,
    AuthorityRule,
    AuthorityConfig,
    AuthorityManager,
)
from carby_sprint.user_context import get_current_user, is_system_user


class TestDecisionAuthority:
    """Tests for DecisionAuthority enum."""

    def test_authority_levels_exist(self):
        """Test that all authority levels are defined."""
        assert DecisionAuthority.HUMAN_REQUIRED.value == "human_required"
        assert DecisionAuthority.AGENT_RECOMMENDS.value == "agent_recommends"
        assert DecisionAuthority.AGENT_AUTONOMOUS.value == "agent_autonomous"

    def test_authority_comparison(self):
        """Test that authority levels can be compared."""
        assert DecisionAuthority.HUMAN_REQUIRED != DecisionAuthority.AGENT_AUTONOMOUS
        assert DecisionAuthority.AGENT_RECOMMENDS == DecisionAuthority.AGENT_RECOMMENDS


class TestAuthorityRule:
    """Tests for AuthorityRule dataclass."""

    def test_rule_creation_basic(self):
        """Test basic rule creation."""
        rule = AuthorityRule(
            decision_type="security_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED
        )
        assert rule.decision_type == "security_change"
        assert rule.authority_level == DecisionAuthority.HUMAN_REQUIRED
        assert rule.context_pattern is None
        assert rule.description is None
        assert rule.priority == 0

    def test_rule_creation_full(self):
        """Test rule creation with all fields."""
        rule = AuthorityRule(
            decision_type="dependency_update",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS,
            context_pattern="minor",
            description="Minor dependency updates can be handled autonomously",
            priority=8
        )
        assert rule.decision_type == "dependency_update"
        assert rule.authority_level == DecisionAuthority.AGENT_AUTONOMOUS
        assert rule.context_pattern == "minor"
        assert rule.description == "Minor dependency updates can be handled autonomously"
        assert rule.priority == 8


class TestAuthorityConfig:
    """Tests for AuthorityConfig class."""

    def test_default_config_creation(self):
        """Test default config creation."""
        config = AuthorityConfig(sprint_id="test-sprint")
        assert config.sprint_id == "test-sprint"
        assert config.default_authority == DecisionAuthority.AGENT_RECOMMENDS
        assert config.rules == []
        assert config.enabled is True

    def test_add_rule(self):
        """Test adding rules to config."""
        config = AuthorityConfig(sprint_id="test-sprint")
        rule = AuthorityRule(
            decision_type="security_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            priority=10
        )
        config.add_rule(rule)
        assert len(config.rules) == 1
        assert config.rules[0].decision_type == "security_change"

    def test_get_authority_no_rules(self):
        """Test getting authority when no rules match."""
        config = AuthorityConfig(sprint_id="test-sprint")
        authority = config.get_authority_for_decision("unknown_type")
        assert authority == DecisionAuthority.AGENT_RECOMMENDS

    def test_get_authority_simple_match(self):
        """Test getting authority with simple rule match."""
        config = AuthorityConfig(sprint_id="test-sprint")
        config.add_rule(AuthorityRule(
            decision_type="security_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED
        ))
        authority = config.get_authority_for_decision("security_change")
        assert authority == DecisionAuthority.HUMAN_REQUIRED

    def test_get_authority_priority_order(self):
        """Test that higher priority rules take precedence."""
        config = AuthorityConfig(sprint_id="test-sprint")
        config.add_rule(AuthorityRule(
            decision_type="dependency_update",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS,
            priority=5
        ))
        config.add_rule(AuthorityRule(
            decision_type="dependency_update",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            priority=10
        ))
        authority = config.get_authority_for_decision("dependency_update")
        assert authority == DecisionAuthority.HUMAN_REQUIRED

    def test_get_authority_with_context_match(self):
        """Test getting authority with context pattern matching."""
        config = AuthorityConfig(sprint_id="test-sprint")
        config.add_rule(AuthorityRule(
            decision_type="dependency_update",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            context_pattern="critical",
            priority=8
        ))
        # Should match when context contains "critical"
        authority = config.get_authority_for_decision(
            "dependency_update",
            context={"severity": "critical", "package": "django"}
        )
        assert authority == DecisionAuthority.HUMAN_REQUIRED

    def test_get_authority_with_context_no_match(self):
        """Test getting authority when context doesn't match pattern."""
        config = AuthorityConfig(sprint_id="test-sprint")
        config.add_rule(AuthorityRule(
            decision_type="dependency_update",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            context_pattern="critical",
            priority=8
        ))
        # Should not match when context doesn't contain "critical"
        authority = config.get_authority_for_decision(
            "dependency_update",
            context={"severity": "minor", "package": "django"}
        )
        assert authority == DecisionAuthority.AGENT_RECOMMENDS  # Default

    def test_context_matches_empty_context(self):
        """Test context matching with empty context."""
        config = AuthorityConfig(sprint_id="test-sprint")
        result = config._context_matches(None, "pattern")
        assert result is False

    def test_context_matches_case_insensitive(self):
        """Test that context matching is case insensitive."""
        config = AuthorityConfig(sprint_id="test-sprint")
        result = config._context_matches(
            {"severity": "CRITICAL"},
            "critical"
        )
        assert result is True


class TestAuthorityManager:
    """Tests for AuthorityManager class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        yield str(project_path)
        shutil.rmtree(temp_dir)

    def test_manager_initialization(self, temp_project):
        """Test authority manager initialization."""
        manager = AuthorityManager(temp_project)
        assert manager.project_dir == Path(temp_project)
        assert manager.sprint_dir == Path(temp_project) / ".carby-sprints"
        assert manager.sprint_dir.exists()

    def test_load_config_nonexistent(self, temp_project):
        """Test loading config when file doesn't exist."""
        manager = AuthorityManager(temp_project)
        config = manager.load_config("nonexistent-sprint")
        assert config.sprint_id == "nonexistent-sprint"
        assert config.default_authority == DecisionAuthority.AGENT_RECOMMENDS
        assert config.rules == []

    def test_save_and_load_config(self, temp_project):
        """Test saving and loading config."""
        manager = AuthorityManager(temp_project)
        
        # Create config with rules
        config = AuthorityConfig(sprint_id="test-sprint")
        config.add_rule(AuthorityRule(
            decision_type="security_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            description="Security changes need approval",
            priority=10
        ))
        
        # Save config
        manager.save_config(config)
        
        # Load config
        loaded = manager.load_config("test-sprint")
        assert loaded.sprint_id == "test-sprint"
        assert loaded.default_authority == DecisionAuthority.AGENT_RECOMMENDS
        assert len(loaded.rules) == 1
        assert loaded.rules[0].decision_type == "security_change"
        assert loaded.rules[0].authority_level == DecisionAuthority.HUMAN_REQUIRED

    def test_create_default_config(self, temp_project):
        """Test creating default configuration."""
        manager = AuthorityManager(temp_project)
        config = manager.create_default_config("test-sprint")
        
        assert config.sprint_id == "test-sprint"
        assert config.default_authority == DecisionAuthority.AGENT_RECOMMENDS
        assert len(config.rules) >= 5  # Should have default rules
        
        # Check for expected default rules
        rule_types = [r.decision_type for r in config.rules]
        assert "security_change" in rule_types
        assert "infrastructure_change" in rule_types
        assert "documentation" in rule_types
        assert "testing" in rule_types

    def test_should_require_approval_human_required(self, temp_project):
        """Test should_require_approval returns True for human_required."""
        manager = AuthorityManager(temp_project)
        config = manager.create_default_config("test-sprint")
        manager.save_config(config)
        
        # Security changes should require approval
        result = manager.should_require_approval("test-sprint", "security_change")
        assert result is True

    def test_should_require_approval_agent_autonomous(self, temp_project):
        """Test should_require_approval returns False for agent_autonomous."""
        manager = AuthorityManager(temp_project)
        config = manager.create_default_config("test-sprint")
        manager.save_config(config)
        
        # Documentation changes should not require approval
        result = manager.should_require_approval("test-sprint", "documentation")
        assert result is False

    def test_should_require_approval_disabled(self, temp_project):
        """Test should_require_approval when authority is disabled."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint", enabled=False)
        manager.save_config(config)
        
        # Should return False when disabled
        result = manager.should_require_approval("test-sprint", "security_change")
        assert result is False

    def test_get_approval_recommendation_human_required(self, temp_project):
        """Test recommendation for human_required decisions."""
        manager = AuthorityManager(temp_project)
        config = manager.create_default_config("test-sprint")
        manager.save_config(config)
        
        result = manager.get_approval_recommendation("test-sprint", "security_change")
        assert "REQUIRES APPROVAL" in result
        assert "security_change" in result

    def test_get_approval_recommendation_agent_recommends(self, temp_project):
        """Test recommendation for agent_recommends decisions."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint")
        config.add_rule(AuthorityRule(
            decision_type="code_review",
            authority_level=DecisionAuthority.AGENT_RECOMMENDS
        ))
        manager.save_config(config)
        
        result = manager.get_approval_recommendation("test-sprint", "code_review")
        assert "RECOMMENDATION" in result
        assert "code_review" in result

    def test_get_approval_recommendation_agent_autonomous(self, temp_project):
        """Test recommendation for agent_autonomous decisions."""
        manager = AuthorityManager(temp_project)
        config = manager.create_default_config("test-sprint")
        manager.save_config(config)
        
        result = manager.get_approval_recommendation("test-sprint", "documentation")
        assert "AUTONOMOUS" in result
        assert "documentation" in result

    def test_get_approval_recommendation_disabled(self, temp_project):
        """Test recommendation when authority is disabled."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint", enabled=False)
        manager.save_config(config)
        
        result = manager.get_approval_recommendation("test-sprint", "security_change")
        assert "AUTONOMOUS" in result
        assert "disabled" in result.lower()

    def test_update_sprint_metadata_with_authority(self, temp_project):
        """Test updating sprint metadata with authority info."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint")
        config.add_rule(AuthorityRule(
            decision_type="test",
            authority_level=DecisionAuthority.HUMAN_REQUIRED
        ))
        manager.save_config(config)
        
        metadata = {}
        updated = manager.update_sprint_metadata_with_authority("test-sprint", metadata)
        
        assert "authority_rules" in updated
        assert updated["authority_rules"]["authority_enabled"] is True
        assert updated["authority_rules"]["authority_default"] == "agent_recommends"
        assert updated["authority_rules"]["authority_rules_count"] == 1


class TestPermissionChecks:
    """Tests for permission check scenarios."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        yield str(project_path)
        shutil.rmtree(temp_dir)

    def test_permission_check_works_correctly(self, temp_project):
        """Test that permission checks work correctly for different decision types."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint")
        
        # Add various permission rules
        config.add_rule(AuthorityRule(
            decision_type="deploy_production",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            priority=10
        ))
        config.add_rule(AuthorityRule(
            decision_type="run_tests",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS,
            priority=5
        ))
        config.add_rule(AuthorityRule(
            decision_type="merge_pr",
            authority_level=DecisionAuthority.AGENT_RECOMMENDS,
            priority=7
        ))
        
        manager.save_config(config)
        
        # Verify permissions
        assert manager.should_require_approval("test-sprint", "deploy_production") is True
        assert manager.should_require_approval("test-sprint", "run_tests") is False
        assert manager.should_require_approval("test-sprint", "merge_pr") is False  # AGENT_RECOMMENDS doesn't require approval

    def test_unauthorized_access_blocked(self, temp_project):
        """Test that unauthorized access is properly blocked."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint")
        
        # Set up a rule that requires human approval
        config.add_rule(AuthorityRule(
            decision_type="delete_database",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            priority=100
        ))
        
        manager.save_config(config)
        
        # Verify that destructive action requires approval
        result = manager.should_require_approval("test-sprint", "delete_database")
        assert result is True, "Destructive operations should require human approval"

    def test_role_based_permissions(self, temp_project):
        """Test role-based permission scenarios."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint")
        
        # Simulate different roles with different permissions
        # Admin role - can approve security changes
        config.add_rule(AuthorityRule(
            decision_type="security_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            context_pattern="admin",
            priority=10
        ))
        
        # Developer role - can handle minor changes autonomously
        config.add_rule(AuthorityRule(
            decision_type="code_refactor",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS,
            context_pattern="developer",
            priority=5
        ))
        
        manager.save_config(config)
        
        # Admin context
        admin_auth = config.get_authority_for_decision(
            "security_change",
            context={"role": "admin", "scope": "production"}
        )
        assert admin_auth == DecisionAuthority.HUMAN_REQUIRED
        
        # Developer context
        dev_auth = config.get_authority_for_decision(
            "code_refactor",
            context={"role": "developer", "scope": "feature-branch"}
        )
        assert dev_auth == DecisionAuthority.AGENT_AUTONOMOUS

    def test_admin_vs_user_permissions(self, temp_project):
        """Test admin vs regular user permission differences."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint")
        
        # Regular users require approval for infrastructure changes
        config.add_rule(AuthorityRule(
            decision_type="infrastructure_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            context_pattern="regular",
            priority=10
        ))
        
        # Admins can act autonomously (higher priority rule)
        config.add_rule(AuthorityRule(
            decision_type="infrastructure_change",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS,
            context_pattern="admin",
            priority=11  # Higher priority
        ))
        
        manager.save_config(config)
        
        # Non-admin requires approval
        non_admin_auth = config.get_authority_for_decision(
            "infrastructure_change",
            context={"user_type": "regular"}
        )
        assert non_admin_auth == DecisionAuthority.HUMAN_REQUIRED
        
        # Admin can act autonomously (higher priority rule)
        admin_auth = config.get_authority_for_decision(
            "infrastructure_change",
            context={"user_type": "admin"}
        )
        assert admin_auth == DecisionAuthority.AGENT_AUTONOMOUS

    def test_permission_inheritance(self, temp_project):
        """Test permission inheritance through context patterns."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint")
        
        # Base rule for all changes
        config.add_rule(AuthorityRule(
            decision_type="any_change",
            authority_level=DecisionAuthority.AGENT_RECOMMENDS,
            priority=1
        ))
        
        # More specific rule for production
        config.add_rule(AuthorityRule(
            decision_type="any_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            context_pattern="production",
            priority=10
        ))
        
        # Even more specific for production security
        config.add_rule(AuthorityRule(
            decision_type="any_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            context_pattern="production-security",
            priority=20
        ))
        
        manager.save_config(config)
        
        # Development environment - uses base rule
        dev_auth = config.get_authority_for_decision(
            "any_change",
            context={"environment": "development"}
        )
        assert dev_auth == DecisionAuthority.AGENT_RECOMMENDS
        
        # Production environment - higher priority rule
        prod_auth = config.get_authority_for_decision(
            "any_change",
            context={"environment": "production"}
        )
        assert prod_auth == DecisionAuthority.HUMAN_REQUIRED
        
        # Production security - highest priority
        prod_sec_auth = config.get_authority_for_decision(
            "any_change",
            context={"environment": "production-security"}
        )
        assert prod_sec_auth == DecisionAuthority.HUMAN_REQUIRED


class TestUserContextIntegration:
    """Tests for user context integration with authority."""

    def test_system_user_detection(self):
        """Test detection of system users."""
        assert is_system_user("system") is True
        assert is_system_user("github-action") is True
        assert is_system_user("ci") is True
        assert is_system_user("jenkins") is True
        assert is_system_user("bot") is True
        assert is_system_user("automation:cron") is True
        assert is_system_user("human-user") is False
        assert is_system_user("vincent") is False

    def test_current_user_with_env_override(self, monkeypatch):
        """Test getting current user with environment override."""
        monkeypatch.setenv("CARBY_SPRINT_USER", "test-admin")
        user = get_current_user()
        assert user == "test-admin"

    def test_user_with_context(self):
        """Test getting user with context."""
        from carby_sprint.user_context import get_user_with_context
        
        # Without context
        user = get_user_with_context()
        assert ":" not in user or user.count(":") <= 1  # May have context from env
        
        # With context
        user_with_ctx = get_user_with_context("github-action")
        assert "github-action" in user_with_ctx


class TestAuthorityPersistence:
    """Tests for authority configuration persistence."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir) / "test-project"
        project_path.mkdir()
        yield str(project_path)
        shutil.rmtree(temp_dir)

    def test_config_file_format(self, temp_project):
        """Test that config is saved in correct format."""
        manager = AuthorityManager(temp_project)
        config = AuthorityConfig(sprint_id="test-sprint")
        config.add_rule(AuthorityRule(
            decision_type="test_rule",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            context_pattern="test",
            description="Test rule",
            priority=5
        ))
        manager.save_config(config)
        
        # Read the file directly
        config_path = Path(temp_project) / ".carby-sprints" / "authority-test-sprint.json"
        assert config_path.exists()
        
        with open(config_path) as f:
            data = json.load(f)
        
        assert data["sprint_id"] == "test-sprint"
        assert data["default_authority"] == "agent_recommends"
        assert data["enabled"] is True
        assert len(data["rules"]) == 1
        assert data["rules"][0]["decision_type"] == "test_rule"
        assert data["rules"][0]["authority_level"] == "human_required"

    def test_invalid_config_fallback(self, temp_project):
        """Test fallback to default config when file is invalid."""
        manager = AuthorityManager(temp_project)
        
        # Create an invalid config file
        config_path = Path(temp_project) / ".carby-sprints" / "authority-invalid.json"
        config_path.write_text("not valid json")
        
        # Should return default config
        config = manager.load_config("invalid")
        assert config.sprint_id == "invalid"
        assert config.default_authority == DecisionAuthority.AGENT_RECOMMENDS

    def test_multiple_sprint_configs(self, temp_project):
        """Test that different sprints have separate configs."""
        manager = AuthorityManager(temp_project)
        
        # Create config for sprint-1
        config1 = AuthorityConfig(sprint_id="sprint-1")
        config1.add_rule(AuthorityRule(
            decision_type="security_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED
        ))
        manager.save_config(config1)
        
        # Create config for sprint-2
        config2 = AuthorityConfig(sprint_id="sprint-2")
        config2.add_rule(AuthorityRule(
            decision_type="security_change",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS
        ))
        manager.save_config(config2)
        
        # Verify configs are separate
        loaded1 = manager.load_config("sprint-1")
        loaded2 = manager.load_config("sprint-2")
        
        assert loaded1.rules[0].authority_level == DecisionAuthority.HUMAN_REQUIRED
        assert loaded2.rules[0].authority_level == DecisionAuthority.AGENT_AUTONOMOUS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
