"""
Verify Agent - Production Implementation

Two-stage verification agent for the Carby Studio SDLC pipeline.

Stage 1: Spec Compliance Review (Binary PASS/FAIL)
Stage 2: Code Quality Review (APPROVE/CONDITIONAL/REQUEST_CHANGES)

Usage:
    >>> from carby_sprint.verify_agent import VerifyAgent, VerifyStage1Result, VerifyStage2Result
    >>> agent = VerifyAgent()
    >>> stage1 = agent.run_stage1(pr_data, design_md, requirements_md)
    >>> if stage1.decision == VerifyStage1Result.PASS:
    ...     stage2 = agent.run_stage2(pr_data)
    ...     final = agent.get_final_decision()
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


class VerifyStage1Result(Enum):
    """Stage 1 decision outcomes."""
    PASS = "PASS"
    FAIL = "FAIL"


class VerifyStage2Result(Enum):
    """Stage 2 decision outcomes."""
    APPROVE = "APPROVE"
    CONDITIONAL = "CONDITIONAL"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    SKIPPED = "N/A"


class FinalDecision(Enum):
    """Final combined decision outcomes."""
    PROCEED_TO_DELIVER = "PROCEED_TO_DELIVER"
    PROCEED_WITH_BACKLOG = "PROCEED_WITH_BACKLOG"
    RETURN_TO_BUILD = "RETURN_TO_BUILD"


@dataclass
class VerifyIssue:
    """Represents a verification issue found during review."""
    issue_type: str  # "critical", "high", "medium", "low"
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    suggestion: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert issue to dictionary representation."""
        return {
            "type": self.issue_type,
            "msg": self.message,
            "file": self.file_path,
            "line": self.line_number,
            "suggestion": self.suggestion,
        }


@dataclass
class Stage1Report:
    """Stage 1 verification report."""
    decision: VerifyStage1Result
    issues: List[VerifyIssue] = field(default_factory=list)
    critical_count: int = 0
    coverage_percent: float = 0.0
    tests_passing: bool = True
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary representation."""
        return {
            "decision": self.decision.value,
            "issues": [i.to_dict() for i in self.issues],
            "critical_count": self.critical_count,
            "coverage_percent": self.coverage_percent,
            "tests_passing": self.tests_passing,
            "timestamp": self.timestamp,
        }


@dataclass
class Stage2Report:
    """Stage 2 verification report."""
    decision: VerifyStage2Result
    high_issues: List[str] = field(default_factory=list)
    medium_issues: List[str] = field(default_factory=list)
    low_issues: List[str] = field(default_factory=list)
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    reason: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary representation."""
        return {
            "decision": self.decision.value,
            "high_issues": self.high_issues,
            "medium_issues": self.medium_issues,
            "low_issues": self.low_issues,
            "high_count": self.high_count,
            "medium_count": self.medium_count,
            "low_count": self.low_count,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class FinalReport:
    """Final combined verification report."""
    stage1: VerifyStage1Result
    stage2: VerifyStage2Result
    final: FinalDecision
    reason: Optional[str] = None
    legacy_mapping: str = "NO-GO"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary representation."""
        return {
            "stage1": self.stage1.value,
            "stage2": self.stage2.value,
            "final": self.final.value,
            "reason": self.reason,
            "legacy_mapping": self.legacy_mapping,
            "timestamp": self.timestamp,
        }


class VerifyAgent:
    """
    Production Verify Agent for two-stage code review.

    Stage 1: Spec Compliance Review (Binary Gate)
    - Validates implementation matches design specification
    - Binary PASS/FAIL outcome
    - Fails on: scope mismatch, missing features, security issues, low coverage

    Stage 2: Code Quality Review (Improvement Focus)
    - Only runs if Stage 1 passes
    - Evaluates code quality, maintainability, documentation
    - Outcomes: APPROVE, CONDITIONAL, REQUEST_CHANGES

    Example:
        >>> agent = VerifyAgent()
        >>> pr_data = {
        ...     "scope_matches_design": True,
        ...     "required_features": ["feature1"],
        ...     "implemented_features": ["feature1"],
        ...     "test_coverage": 85,
        ...     "tests_passing": True,
        ... }
        >>> stage1 = agent.run_stage1(pr_data, "", "")
        >>> if stage1.decision == VerifyStage1Result.PASS:
        ...     stage2 = agent.run_stage2(pr_data)
        ...     final = agent.get_final_decision()
    """

    # Configuration thresholds
    MIN_COVERAGE_PERCENT = 80.0
    MAX_HIGH_ISSUES_FOR_APPROVE = 0
    MAX_MEDIUM_ISSUES_FOR_APPROVE = 3
    MAX_HIGH_ISSUES_FOR_CONDITIONAL = 2
    MAX_MEDIUM_ISSUES_FOR_CONDITIONAL = 6

    def __init__(self):
        """Initialize the Verify Agent."""
        self._stage1_report: Optional[Stage1Report] = None
        self._stage2_report: Optional[Stage2Report] = None

    def run_stage1(
        self,
        pr_data: Dict[str, Any],
        design_md: str,
        requirements_md: str,
    ) -> Stage1Report:
        """
        Stage 1: Spec Compliance Review (Binary Gate)

        Validates that the implementation matches the design specification.
        This is a binary gate - code either complies or it doesn't.

        Args:
            pr_data: Dictionary containing PR information:
                - scope_matches_design (bool): Whether scope matches design.md
                - required_features (List[str]): Features required by design
                - implemented_features (List[str]): Features actually implemented
                - api_compliant (bool): Whether API matches specification
                - data_model_compliant (bool): Whether data models match design
                - critical_security_issues (int): Number of critical security issues
                - test_coverage (float): Test coverage percentage
                - tests_passing (bool): Whether all tests pass
            design_md: Contents of design.md file
            requirements_md: Contents of requirements.md file

        Returns:
            Stage1Report with decision and issues list

        Raises:
            ValueError: If pr_data is missing required fields
        """
        issues: List[VerifyIssue] = []

        # Validate required fields
        required_fields = [
            "scope_matches_design",
            "required_features",
            "implemented_features",
            "api_compliant",
            "data_model_compliant",
            "critical_security_issues",
            "test_coverage",
            "tests_passing",
        ]
        for field_name in required_fields:
            if field_name not in pr_data:
                raise ValueError(f"Missing required field in pr_data: {field_name}")

        # Check scope alignment
        if not pr_data.get("scope_matches_design", True):
            issues.append(VerifyIssue(
                issue_type="critical",
                message="Scope does not match design.md specification",
                suggestion="Review design.md and ensure all specified features are implemented",
            ))

        # Check required features
        required_features = set(pr_data.get("required_features", []))
        implemented_features = set(pr_data.get("implemented_features", []))
        missing_features = required_features - implemented_features
        if missing_features:
            issues.append(VerifyIssue(
                issue_type="critical",
                message=f"Missing required features: {missing_features}",
                suggestion=f"Implement the following features: {missing_features}",
            ))

        # Check API compliance
        if not pr_data.get("api_compliant", True):
            issues.append(VerifyIssue(
                issue_type="critical",
                message="API contracts do not match specification",
                suggestion="Update API implementation to match design.md specification",
            ))

        # Check data model compliance
        if not pr_data.get("data_model_compliant", True):
            issues.append(VerifyIssue(
                issue_type="critical",
                message="Data models deviate from design specification",
                suggestion="Update data models to match design.md specification",
            ))

        # Critical security gate
        critical_security_issues = pr_data.get("critical_security_issues", 0)
        if critical_security_issues > 0:
            issues.append(VerifyIssue(
                issue_type="critical",
                message=f"{critical_security_issues} critical security issue(s) found",
                suggestion="Address all critical security issues before proceeding",
            ))

        # Test compliance gate
        coverage_percent = pr_data.get("test_coverage", 0.0)
        if coverage_percent < self.MIN_COVERAGE_PERCENT:
            issues.append(VerifyIssue(
                issue_type="critical",
                message=f"Test coverage {coverage_percent}% below {self.MIN_COVERAGE_PERCENT}% threshold",
                suggestion=f"Increase test coverage to at least {self.MIN_COVERAGE_PERCENT}%",
            ))

        # Check tests passing
        tests_passing = pr_data.get("tests_passing", True)
        if not tests_passing:
            issues.append(VerifyIssue(
                issue_type="critical",
                message="Tests are failing",
                suggestion="Fix all failing tests before proceeding",
            ))

        # Determine Stage 1 decision
        critical_count = sum(1 for i in issues if i.issue_type == "critical")
        decision = (
            VerifyStage1Result.FAIL
            if critical_count > 0
            else VerifyStage1Result.PASS
        )

        self._stage1_report = Stage1Report(
            decision=decision,
            issues=issues,
            critical_count=critical_count,
            coverage_percent=coverage_percent,
            tests_passing=tests_passing,
        )

        return self._stage1_report

    def run_stage2(self, pr_data: Dict[str, Any]) -> Stage2Report:
        """
        Stage 2: Code Quality Review (Improvement Focus)

        Evaluates code quality, maintainability, and documentation.
        Only runs if Stage 1 passed.

        Args:
            pr_data: Dictionary containing PR information:
                - code_readable (bool): Code is readable and well-structured
                - maintainable (bool): Code is maintainable
                - testable (bool): Code is testable
                - insecure_configs (bool): Has insecure configurations
                - input_validation (bool): Has proper input validation
                - readme_updated (bool): README is updated
                - api_docs_match (bool): API docs match implementation
                - performance_regression (bool): Has performance regression
                - tdd_evidence (bool): Has TDD evidence

        Returns:
            Stage2Report with decision and issues lists

        Raises:
            RuntimeError: If Stage 1 has not been run or failed
            ValueError: If pr_data is missing required fields
        """
        if self._stage1_report is None:
            raise RuntimeError("Stage 1 must be run before Stage 2")

        if self._stage1_report.decision != VerifyStage1Result.PASS:
            report = Stage2Report(
                decision=VerifyStage2Result.SKIPPED,
                reason="Stage 1 did not pass",
            )
            self._stage2_report = report
            return report

        high_issues: List[str] = []
        medium_issues: List[str] = []
        low_issues: List[str] = []

        # Code quality checks
        if not pr_data.get("code_readable", True):
            high_issues.append("Code readability issues - consider refactoring for clarity")

        if not pr_data.get("maintainable", True):
            high_issues.append("Maintainability concerns - code may be difficult to maintain")

        if not pr_data.get("testable", True):
            high_issues.append("Testability issues - consider dependency injection and mocking")

        # Security hardening (beyond critical)
        if pr_data.get("insecure_configs", False):
            high_issues.append("Insecure configurations detected - review security settings")

        if not pr_data.get("input_validation", True):
            medium_issues.append("Input validation gaps - add validation for all user inputs")

        # Documentation review
        if not pr_data.get("readme_updated", True):
            medium_issues.append("README not updated - document new features and changes")

        if not pr_data.get("api_docs_match", True):
            medium_issues.append("API docs don't match implementation - update documentation")

        # Performance review
        if pr_data.get("performance_regression", False):
            high_issues.append("Performance regression detected - optimize critical paths")

        # TDD evidence
        if not pr_data.get("tdd_evidence", True):
            medium_issues.append("Insufficient TDD evidence - add tests before implementation")

        # Code style checks (low priority)
        if not pr_data.get("follows_style_guide", True):
            low_issues.append("Code style issues - follow project style guide")

        if not pr_data.get("proper_docstrings", True):
            low_issues.append("Missing docstrings - add documentation to public APIs")

        # Stage 2 Decision Matrix
        high_count = len(high_issues)
        medium_count = len(medium_issues)
        low_count = len(low_issues)

        if high_count > self.MAX_HIGH_ISSUES_FOR_CONDITIONAL or medium_count > self.MAX_MEDIUM_ISSUES_FOR_CONDITIONAL:
            decision = VerifyStage2Result.REQUEST_CHANGES
        elif high_count > self.MAX_HIGH_ISSUES_FOR_APPROVE or medium_count > self.MAX_MEDIUM_ISSUES_FOR_APPROVE:
            decision = VerifyStage2Result.CONDITIONAL
        else:
            decision = VerifyStage2Result.APPROVE

        self._stage2_report = Stage2Report(
            decision=decision,
            high_issues=high_issues,
            medium_issues=medium_issues,
            low_issues=low_issues,
            high_count=high_count,
            medium_count=medium_count,
            low_count=low_count,
        )

        return self._stage2_report

    def get_final_decision(self) -> FinalReport:
        """
        Get combined decision from both stages.

        Returns:
            FinalReport with combined decision and legacy mapping

        Raises:
            RuntimeError: If Stage 1 has not been run
        """
        if self._stage1_report is None:
            raise RuntimeError("Stage 1 must be run before getting final decision")

        stage1 = self._stage1_report.decision

        if stage1 == VerifyStage1Result.FAIL:
            return FinalReport(
                stage1=stage1,
                stage2=VerifyStage2Result.SKIPPED,
                final=FinalDecision.RETURN_TO_BUILD,
                reason="Stage 1 compliance checks failed",
                legacy_mapping="NO-GO",
            )

        stage2 = (
            self._stage2_report.decision
            if self._stage2_report
            else VerifyStage2Result.SKIPPED
        )

        if stage2 == VerifyStage2Result.APPROVE:
            final = FinalDecision.PROCEED_TO_DELIVER
            legacy = "GO"
        elif stage2 == VerifyStage2Result.CONDITIONAL:
            final = FinalDecision.PROCEED_WITH_BACKLOG
            legacy = "CONDITIONAL"
        else:  # REQUEST_CHANGES or SKIPPED
            final = FinalDecision.RETURN_TO_BUILD
            legacy = "NO-GO"

        return FinalReport(
            stage1=stage1,
            stage2=stage2,
            final=final,
            reason=None,
            legacy_mapping=legacy,
        )

    def legacy_mapping(self) -> str:
        """
        Map new two-stage decisions to legacy GO/NO-GO/CONDITIONAL.

        Returns:
            String: "GO", "NO-GO", or "CONDITIONAL"
        """
        final = self.get_final_decision()
        return final.legacy_mapping

    def reset(self) -> None:
        """Reset the agent state for a new verification."""
        self._stage1_report = None
        self._stage2_report = None

    def get_stage1_report(self) -> Optional[Stage1Report]:
        """Get the Stage 1 report if available."""
        return self._stage1_report

    def get_stage2_report(self) -> Optional[Stage2Report]:
        """Get the Stage 2 report if available."""
        return self._stage2_report

    @staticmethod
    def validate_pr_data(pr_data: Dict[str, Any]) -> List[str]:
        """
        Validate PR data structure and return list of missing fields.

        Args:
            pr_data: Dictionary to validate

        Returns:
            List of missing required field names
        """
        stage1_required = [
            "scope_matches_design",
            "required_features",
            "implemented_features",
            "api_compliant",
            "data_model_compliant",
            "critical_security_issues",
            "test_coverage",
            "tests_passing",
        ]

        missing = [f for f in stage1_required if f not in pr_data]
        return missing
