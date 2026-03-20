"""
Authority Framework for Carby Studio

Implements decision-making authority levels to determine whether
decisions require human input, agent recommendations, or can be fully autonomous.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path


class DecisionAuthority(Enum):
    """
    Authority levels for decision making in Carby Studio.
    """
    HUMAN_REQUIRED = "human_required"      # Requires explicit human approval
    AGENT_RECOMMENDS = "agent_recommends"  # Agent recommends, human can approve
    AGENT_AUTONOMOUS = "agent_autonomous"  # Agent can decide autonomously


@dataclass
class AuthorityRule:
    """
    Defines authority rules for specific decision types or contexts.
    """
    decision_type: str
    authority_level: DecisionAuthority
    context_pattern: Optional[str] = None  # Regex pattern or description
    description: Optional[str] = None
    priority: int = 0  # Higher priority rules take precedence


@dataclass
class AuthorityConfig:
    """
    Configuration for authority rules in a sprint.
    """
    sprint_id: str
    default_authority: DecisionAuthority = DecisionAuthority.AGENT_RECOMMENDS
    rules: list[AuthorityRule] = field(default_factory=list)
    enabled: bool = True
    
    def add_rule(self, rule: AuthorityRule) -> None:
        """Add a new authority rule."""
        self.rules.append(rule)
    
    def get_authority_for_decision(self, decision_type: str, context: Optional[Dict[str, Any]] = None) -> DecisionAuthority:
        """
        Determine the authority level for a specific decision.
        
        Args:
            decision_type: Type of decision being made
            context: Additional context for decision
        
        Returns:
            Appropriate DecisionAuthority level
        """
        # Sort rules by priority (highest first)
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)
        
        # Apply the highest priority matching rule
        for rule in sorted_rules:
            if rule.decision_type == decision_type:
                # If there's a context pattern, check if it matches
                if rule.context_pattern:
                    # Simple pattern matching (could be enhanced with regex)
                    if self._context_matches(context, rule.context_pattern):
                        return rule.authority_level
                else:
                    # If no context pattern, just match decision type
                    return rule.authority_level
        
        # Return default authority if no rules match
        return self.default_authority
    
    def _context_matches(self, context: Optional[Dict[str, Any]], pattern: str) -> bool:
        """
        Check if the given context matches the pattern.
        
        Args:
            context: Decision context
            pattern: Pattern to match against
        
        Returns:
            True if context matches pattern
        """
        if not context:
            return False
        
        # Simple implementation: check if pattern appears in any context value
        context_str = json.dumps(context, default=str).lower()
        return pattern.lower() in context_str


class AuthorityManager:
    """
    Manages authority configurations and enforces authority rules.
    """
    
    def __init__(self, project_dir: str):
        """
        Initialize the authority manager.
        
        Args:
            project_dir: Project directory path
        """
        self.project_dir = Path(project_dir)
        self.sprint_dir = self.project_dir / ".carby-sprints"
        self.authority_config_file = self.sprint_dir / "authority-config.json"
        
        # Create sprint directory if it doesn't exist
        self.sprint_dir.mkdir(exist_ok=True)
    
    def load_config(self, sprint_id: str) -> AuthorityConfig:
        """
        Load authority configuration for a sprint.
        
        Args:
            sprint_id: Sprint identifier
        
        Returns:
            AuthorityConfig instance
        """
        config_path = self.sprint_dir / f"authority-{sprint_id}.json"
        
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                
                # Convert rules from dict back to AuthorityRule objects
                rules = []
                for rule_data in data.get("rules", []):
                    rule = AuthorityRule(
                        decision_type=rule_data["decision_type"],
                        authority_level=DecisionAuthority(rule_data["authority_level"]),
                        context_pattern=rule_data.get("context_pattern"),
                        description=rule_data.get("description"),
                        priority=rule_data.get("priority", 0)
                    )
                    rules.append(rule)
                
                return AuthorityConfig(
                    sprint_id=data["sprint_id"],
                    default_authority=DecisionAuthority(data["default_authority"]),
                    rules=rules,
                    enabled=data.get("enabled", True)
                )
            except (json.JSONDecodeError, KeyError, ValueError):
                # If config is invalid, create a default one
                pass
        
        # Return default configuration
        return AuthorityConfig(
            sprint_id=sprint_id,
            default_authority=DecisionAuthority.AGENT_RECOMMENDS
        )
    
    def save_config(self, config: AuthorityConfig) -> None:
        """
        Save authority configuration for a sprint.
        
        Args:
            config: AuthorityConfig to save
        """
        config_path = self.sprint_dir / f"authority-{config.sprint_id}.json"
        
        # Convert to serializable format
        data = {
            "sprint_id": config.sprint_id,
            "default_authority": config.default_authority.value,
            "rules": [
                {
                    "decision_type": rule.decision_type,
                    "authority_level": rule.authority_level.value,
                    "context_pattern": rule.context_pattern,
                    "description": rule.description,
                    "priority": rule.priority
                }
                for rule in config.rules
            ],
            "enabled": config.enabled
        }
        
        config_path.write_text(json.dumps(data, indent=2))
    
    def create_default_config(self, sprint_id: str) -> AuthorityConfig:
        """
        Create a default authority configuration for a sprint.
        
        Args:
            sprint_id: Sprint identifier
        
        Returns:
            Default AuthorityConfig instance
        """
        config = AuthorityConfig(
            sprint_id=sprint_id,
            default_authority=DecisionAuthority.AGENT_RECOMMENDS
        )
        
        # Add some sensible default rules
        config.add_rule(AuthorityRule(
            decision_type="security_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            description="All security-related changes require human approval",
            priority=10
        ))
        
        config.add_rule(AuthorityRule(
            decision_type="infrastructure_change",
            authority_level=DecisionAuthority.HUMAN_REQUIRED,
            description="Infrastructure changes require human approval",
            priority=10
        ))
        
        config.add_rule(AuthorityRule(
            decision_type="dependency_update",
            authority_level=DecisionAuthority.AGENT_RECOMMENDS,
            context_pattern="critical",
            description="Critical dependency updates require human approval",
            priority=8
        ))
        
        config.add_rule(AuthorityRule(
            decision_type="dependency_update",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS,
            context_pattern="minor",
            description="Minor dependency updates can be handled autonomously",
            priority=8
        ))
        
        config.add_rule(AuthorityRule(
            decision_type="documentation",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS,
            description="Documentation changes can be handled autonomously",
            priority=5
        ))
        
        config.add_rule(AuthorityRule(
            decision_type="testing",
            authority_level=DecisionAuthority.AGENT_AUTONOMOUS,
            description="Test additions and modifications can be handled autonomously",
            priority=5
        ))
        
        return config
    
    def should_require_approval(self, sprint_id: str, decision_type: str, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determine if a decision requires human approval.
        
        Args:
            sprint_id: Sprint identifier
            decision_type: Type of decision being made
            context: Additional context for decision
        
        Returns:
            True if human approval is required
        """
        config = self.load_config(sprint_id)
        
        if not config.enabled:
            return False  # Authority checks disabled
        
        authority_level = config.get_authority_for_decision(decision_type, context)
        return authority_level == DecisionAuthority.HUMAN_REQUIRED
    
    def get_approval_recommendation(self, sprint_id: str, decision_type: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Get a recommendation for how to handle a decision.
        
        Args:
            sprint_id: Sprint identifier
            decision_type: Type of decision being made
            context: Additional context for decision
        
        Returns:
            Recommendation string
        """
        config = self.load_config(sprint_id)
        
        if not config.enabled:
            return "AUTONOMOUS: Authority checks disabled"
        
        authority_level = config.get_authority_for_decision(decision_type, context)
        
        if authority_level == DecisionAuthority.HUMAN_REQUIRED:
            return f"REQUIRES APPROVAL: {decision_type} decisions require explicit human approval"
        elif authority_level == DecisionAuthority.AGENT_RECOMMENDS:
            return f"RECOMMENDATION: {decision_type} decisions should be reviewed by human"
        else:  # AGENT_AUTONOMOUS
            return f"AUTONOMOUS: {decision_type} decisions can be made by agent"
    
    def update_sprint_metadata_with_authority(self, sprint_id: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update sprint metadata with authority information.
        
        Args:
            sprint_id: Sprint identifier
            metadata: Existing metadata to update
        
        Returns:
            Updated metadata with authority information
        """
        config = self.load_config(sprint_id)
        
        authority_metadata = {
            "authority_enabled": config.enabled,
            "authority_default": config.default_authority.value,
            "authority_rules_count": len(config.rules),
            "authority_last_updated": "2026-03-20T20:33:00Z"  # In real implementation, use current time
        }
        
        metadata["authority_rules"] = authority_metadata
        return metadata