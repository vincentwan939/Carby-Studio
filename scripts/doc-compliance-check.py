#!/usr/bin/env python3
"""
Documentation Compliance Checker for Sprint Framework

Validates that all required documentation exists and is up-to-date.
Ensures agents follow the documentation-first approach.

Usage:
    python doc-compliance-check.py /path/to/project [options]

Options:
    --sprint N          Check specific sprint number
    --work-item WI-XXX  Check specific work item
    --strict            Fail on warnings (default: warnings only)
    --json              Output results as JSON
    --fix               Attempt to auto-fix minor issues
"""

from __future__ import annotations

import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class ComplianceIssue:
    """Represents a documentation compliance issue."""
    severity: str  # critical, high, medium, low
    category: str  # file_missing, content_incomplete, outdated, format_error
    file_path: str
    message: str
    suggestion: str
    line_number: Optional[int] = None


@dataclass
class ComplianceReport:
    """Complete compliance check report."""
    project_path: str
    timestamp: str
    sprint_number: Optional[int]
    overall_status: str  # pass, fail, warn
    score: float  # 0-100
    issues: List[ComplianceIssue] = field(default_factory=list)
    checks_performed: List[str] = field(default_factory=list)
    summary: Dict[str, int] = field(default_factory=dict)


class DocumentationComplianceChecker:
    """Checks project documentation for Sprint Framework compliance."""

    REQUIRED_FILES = [
        "sprint-context.md",
        "design-evolution-log.md",
        "sprint-handoff-checklist.md",
    ]

    REQUIRED_SECTIONS = {
        "sprint-context.md": [
            "Current Sprint",
            "Project Overview",
            "Current State Summary",
            "Technical Architecture",
            "Completed Work",
            "In Progress",
            "Backlog",
        ],
        "design-evolution-log.md": [
            "Design Principles",
            "Architecture Decisions",
            "Pattern Library",
            "Evolution Timeline",
        ],
    }

    def __init__(self, project_path: str, strict: bool = False):
        self.project_path = Path(project_path)
        self.strict = strict
        self.issues: List[ComplianceIssue] = []
        self.checks_performed: List[str] = []

    def check_all(self, sprint_number: Optional[int] = None,
                  work_item_id: Optional[str] = None) -> ComplianceReport:
        """Run all compliance checks."""
        self.checks_performed.append("all")

        # Core file checks
        self._check_required_files()
        self._check_required_sections()
        self._check_sprint_context_completeness()

        # Sprint-specific checks
        if sprint_number:
            self._check_sprint_handoff(sprint_number)

        # Work item checks
        if work_item_id:
            self._check_work_item(work_item_id)
        else:
            self._check_all_work_items()

        # Design evolution checks
        self._check_design_evolution()

        # Git status checks
        self._check_git_status()

        # Calculate score and status
        score = self._calculate_score()
        status = self._determine_status(score)

        return ComplianceReport(
            project_path=str(self.project_path),
            timestamp=datetime.now().isoformat(),
            sprint_number=sprint_number,
            overall_status=status,
            score=score,
            issues=self.issues,
            checks_performed=self.checks_performed,
            summary=self._generate_summary()
        )

    def _check_required_files(self) -> None:
        """Check that all required files exist."""
        self.checks_performed.append("required_files")

        for filename in self.REQUIRED_FILES:
            file_path = self.project_path / filename
            if not file_path.exists():
                self.issues.append(ComplianceIssue(
                    severity="critical",
                    category="file_missing",
                    file_path=str(file_path),
                    message=f"Required file missing: {filename}",
                    suggestion=f"Create {filename} using the template from AGENT_PROMPT.md"
                ))
            elif file_path.stat().st_size == 0:
                self.issues.append(ComplianceIssue(
                    severity="critical",
                    category="content_incomplete",
                    file_path=str(file_path),
                    message=f"Required file is empty: {filename}",
                    suggestion=f"Populate {filename} with required content"
                ))

    def _check_required_sections(self) -> None:
        """Check that required sections exist in each file."""
        self.checks_performed.append("required_sections")

        for filename, sections in self.REQUIRED_SECTIONS.items():
            file_path = self.project_path / filename
            if not file_path.exists():
                continue

            content = file_path.read_text()
            for section in sections:
                # Check for section header (various markdown formats)
                patterns = [
                    rf"^##\s+{re.escape(section)}",
                    rf"^###\s+{re.escape(section)}",
                    rf"^##\s*\[?{re.escape(section)}\]?",
                ]
                if not any(re.search(p, content, re.MULTILINE) for p in patterns):
                    self.issues.append(ComplianceIssue(
                        severity="high",
                        category="content_incomplete",
                        file_path=str(file_path),
                        message=f"Missing required section: '{section}'",
                        suggestion=f"Add '## {section}' section to {filename}"
                    ))

    def _check_sprint_context_completeness(self) -> None:
        """Check sprint-context.md for completeness."""
        self.checks_performed.append("sprint_context")

        file_path = self.project_path / "sprint-context.md"
        if not file_path.exists():
            return

        content = file_path.read_text()

        # Check for sprint number
        if not re.search(r"Sprint Number:\s*\d+", content):
            self.issues.append(ComplianceIssue(
                severity="critical",
                category="content_incomplete",
                file_path=str(file_path),
                message="Sprint number not specified",
                suggestion="Add 'Sprint Number: N' to Current Sprint section"
            ))

        # Check for status
        if not re.search(r"Status:\s*(in-progress|completed|blocked)", content, re.IGNORECASE):
            self.issues.append(ComplianceIssue(
                severity="high",
                category="content_incomplete",
                file_path=str(file_path),
                message="Sprint status not specified",
                suggestion="Add 'Status: in-progress | completed | blocked'"
            ))

        # Check for progress percentage
        if not re.search(r"\d+%\s*complete", content, re.IGNORECASE):
            self.issues.append(ComplianceIssue(
                severity="medium",
                category="content_incomplete",
                file_path=str(file_path),
                message="Overall progress percentage not specified",
                suggestion="Add progress percentage to Current State Summary"
            ))

        # Check for credentials section
        if "Credentials" not in content:
            self.issues.append(ComplianceIssue(
                severity="medium",
                category="content_incomplete",
                file_path=str(file_path),
                message="Credentials section missing",
                suggestion="Add Credentials table for tracking access"
            ))

    def _check_sprint_handoff(self, sprint_number: int) -> None:
        """Check sprint handoff checklist completeness."""
        self.checks_performed.append("sprint_handoff")

        handoff_path = self.project_path / "sprint-logs" / f"sprint-{sprint_number}-handoff.md"

        if not handoff_path.exists():
            self.issues.append(ComplianceIssue(
                severity="critical",
                category="file_missing",
                file_path=str(handoff_path),
                message=f"Sprint {sprint_number} handoff checklist missing",
                suggestion=f"Create sprint-logs/sprint-{sprint_number}-handoff.md"
            ))
            return

        content = handoff_path.read_text()

        # Check for required checklist sections
        required_checks = [
            "Work Items Status",
            "Code State",
            "Documentation Updates",
            "Handoff Notes",
        ]

        for check in required_checks:
            if check not in content:
                self.issues.append(ComplianceIssue(
                    severity="high",
                    category="content_incomplete",
                    file_path=str(handoff_path),
                    message=f"Handoff checklist section missing: {check}",
                    suggestion=f"Add '{check}' section to handoff checklist"
                ))

        # Check for sign-off
        if "Handoff Completed By" not in content:
            self.issues.append(ComplianceIssue(
                severity="high",
                category="content_incomplete",
                file_path=str(handoff_path),
                message="Handoff sign-off missing",
                suggestion="Add 'Handoff Completed By' with agent identifier and date"
            ))

    def _check_all_work_items(self) -> None:
        """Check all work items in the work-items directory."""
        self.checks_performed.append("all_work_items")

        work_items_dir = self.project_path / "work-items"
        if not work_items_dir.exists():
            self.issues.append(ComplianceIssue(
                severity="high",
                category="file_missing",
                file_path=str(work_items_dir),
                message="work-items directory missing",
                suggestion="Create work-items/ directory and add work item files"
            ))
            return

        work_items = list(work_items_dir.glob("WI-*.md"))
        if not work_items:
            self.issues.append(ComplianceIssue(
                severity="high",
                category="file_missing",
                file_path=str(work_items_dir),
                message="No work item files found",
                suggestion="Create work item files using WI-XXX-*.md naming"
            ))
            return

        for work_item in work_items:
            self._check_work_item_file(work_item)

    def _check_work_item(self, work_item_id: str) -> None:
        """Check a specific work item."""
        self.checks_performed.append(f"work_item_{work_item_id}")

        work_item_path = self.project_path / "work-items" / f"{work_item_id}-*.md"
        matches = list(self.project_path.glob(f"work-items/{work_item_id}-*.md"))

        if not matches:
            self.issues.append(ComplianceIssue(
                severity="critical",
                category="file_missing",
                file_path=str(self.project_path / "work-items" / f"{work_item_id}.md"),
                message=f"Work item {work_item_id} not found",
                suggestion=f"Create work-items/{work_item_id}-*.md"
            ))
            return

        self._check_work_item_file(matches[0])

    def _check_work_item_file(self, file_path: Path) -> None:
        """Check a single work item file for completeness."""
        content = file_path.read_text()
        filename = file_path.name

        # Required sections
        required_sections = [
            "Metadata",
            "Context",
            "Technical Specification",
            "Definition of Done",
        ]

        for section in required_sections:
            if section not in content:
                self.issues.append(ComplianceIssue(
                    severity="high",
                    category="content_incomplete",
                    file_path=str(file_path),
                    message=f"Work item missing section: {section}",
                    suggestion=f"Add '## {section}' to {filename}"
                ))

        # Check for specific required fields
        required_fields = [
            (r"ID:\s*WI-\d+", "Work item ID"),
            (r"Sprint:\s*\d+", "Sprint number"),
            (r"Status:\s*(Not started|In progress|Code review|Done)", "Status"),
        ]

        for pattern, field_name in required_fields:
            if not re.search(pattern, content):
                self.issues.append(ComplianceIssue(
                    severity="high",
                    category="content_incomplete",
                    file_path=str(file_path),
                    message=f"Work item missing field: {field_name}",
                    suggestion=f"Add '{field_name}' to Metadata section"
                ))

        # Check for credentials table if credentials mentioned
        if "credential" in content.lower() and "| Service |" not in content:
            self.issues.append(ComplianceIssue(
                severity="medium",
                category="content_incomplete",
                file_path=str(file_path),
                message="Credentials mentioned but not in table format",
                suggestion="Add credentials table with Service, Purpose, Location columns"
            ))

        # Check for handoff notes if status is Done
        if "Status: Done" in content and "Handoff Notes" not in content:
            self.issues.append(ComplianceIssue(
                severity="medium",
                category="content_incomplete",
                file_path=str(file_path),
                message="Completed work item missing handoff notes",
                suggestion="Add '## Handoff Notes' section for next agent"
            ))

    def _check_design_evolution(self) -> None:
        """Check design evolution log for completeness."""
        self.checks_performed.append("design_evolution")

        file_path = self.project_path / "design-evolution-log.md"
        if not file_path.exists():
            return

        content = file_path.read_text()

        # Check for ADR format
        adr_pattern = r"###\s+ADR-\d+"
        adrs = re.findall(adr_pattern, content)

        if not adrs:
            self.issues.append(ComplianceIssue(
                severity="low",
                category="content_incomplete",
                file_path=str(file_path),
                message="No Architecture Decision Records (ADRs) found",
                suggestion="Add ADRs for significant design decisions using ADR-XXX format"
            ))

        # Check ADRs have required fields
        for adr_match in re.finditer(r"(###\s+ADR-\d+.*?)(?=###|\Z)", content, re.DOTALL):
            adr_content = adr_match.group(1)
            adr_title = adr_content.split('\n')[0]

            if "Status:" not in adr_content:
                self.issues.append(ComplianceIssue(
                    severity="medium",
                    category="content_incomplete",
                    file_path=str(file_path),
                    message=f"ADR missing status: {adr_title}",
                    suggestion="Add 'Status: Proposed | Accepted | Superseded'"
                ))

            if "Context:" not in adr_content:
                self.issues.append(ComplianceIssue(
                    severity="medium",
                    category="content_incomplete",
                    file_path=str(file_path),
                    message=f"ADR missing context: {adr_title}",
                    suggestion="Add 'Context:' section explaining the problem"
                ))

            if "Decision:" not in adr_content:
                self.issues.append(ComplianceIssue(
                    severity="medium",
                    category="content_incomplete",
                    file_path=str(file_path),
                    message=f"ADR missing decision: {adr_title}",
                    suggestion="Add 'Decision:' section with explicit choice"
                ))

    def _check_git_status(self) -> None:
        """Check for uncommitted documentation changes."""
        self.checks_performed.append("git_status")

        import subprocess

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.project_path,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return  # Not a git repo or git not available

            uncommitted = result.stdout.strip()
            if uncommitted:
                # Check if any are documentation files
                doc_files = [line for line in uncommitted.split('\n')
                           if any(ext in line for ext in ['.md', 'sprint-', 'work-item'])]

                if doc_files:
                    self.issues.append(ComplianceIssue(
                        severity="high",
                        category="outdated",
                        file_path=str(self.project_path),
                        message=f"Uncommitted documentation changes: {len(doc_files)} files",
                        suggestion="Commit documentation changes before handoff",
                        line_number=None
                    ))

        except Exception:
            pass  # Git not available, skip this check

    def _calculate_score(self) -> float:
        """Calculate compliance score (0-100)."""
        if not self.issues:
            return 100.0

        # Weight by severity
        weights = {
            "critical": 20,
            "high": 10,
            "medium": 5,
            "low": 1
        }

        total_penalty = sum(weights.get(issue.severity, 5) for issue in self.issues)
        score = max(0, 100 - total_penalty)
        return round(score, 1)

    def _determine_status(self, score: float) -> str:
        """Determine overall status based on score and issues."""
        critical_count = sum(1 for i in self.issues if i.severity == "critical")
        high_count = sum(1 for i in self.issues if i.severity == "high")

        if critical_count > 0:
            return "fail"
        if self.strict and high_count > 0:
            return "fail"
        if score >= 90:
            return "pass"
        if score >= 70:
            return "warn"
        return "fail"

    def _generate_summary(self) -> Dict[str, int]:
        """Generate summary statistics."""
        return {
            "total_issues": len(self.issues),
            "critical": sum(1 for i in self.issues if i.severity == "critical"),
            "high": sum(1 for i in self.issues if i.severity == "high"),
            "medium": sum(1 for i in self.issues if i.severity == "medium"),
            "low": sum(1 for i in self.issues if i.severity == "low"),
        }


def format_report(report: ComplianceReport, use_json: bool = False) -> str:
    """Format the compliance report for output."""
    if use_json:
        return json.dumps(asdict(report), indent=2)

    lines = []
    lines.append("=" * 70)
    lines.append("DOCUMENTATION COMPLIANCE REPORT")
    lines.append("=" * 70)
    lines.append(f"Project: {report.project_path}")
    lines.append(f"Timestamp: {report.timestamp}")
    if report.sprint_number:
        lines.append(f"Sprint: {report.sprint_number}")
    lines.append("")

    # Status with color codes
    status_colors = {
        "pass": "\033[92m",  # Green
        "warn": "\033[93m",  # Yellow
        "fail": "\033[91m",  # Red
    }
    reset = "\033[0m"
    color = status_colors.get(report.overall_status, "")
    lines.append(f"Overall Status: {color}{report.overall_status.upper()}{reset}")
    lines.append(f"Compliance Score: {report.score}/100")
    lines.append("")

    # Summary
    lines.append("-" * 70)
    lines.append("SUMMARY")
    lines.append("-" * 70)
    for key, value in report.summary.items():
        lines.append(f"  {key.replace('_', ' ').title()}: {value}")
    lines.append("")

    # Issues
    if report.issues:
        lines.append("-" * 70)
        lines.append("ISSUES FOUND")
        lines.append("-" * 70)

        severity_order = ["critical", "high", "medium", "low"]
        for severity in severity_order:
            severity_issues = [i for i in report.issues if i.severity == severity]
            if severity_issues:
                lines.append("")
                lines.append(f"[{severity.upper()}] ({len(severity_issues)} issues)")
                for issue in severity_issues:
                    lines.append(f"  📄 {issue.file_path}")
                    lines.append(f"     {issue.message}")
                    lines.append(f"     💡 {issue.suggestion}")
                    lines.append("")
    else:
        lines.append("-" * 70)
        lines.append("✅ No issues found!")
        lines.append("-" * 70)

    lines.append("")
    lines.append("=" * 70)
    lines.append(f"Checks performed: {', '.join(report.checks_performed)}")
    lines.append("=" * 70)

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check documentation compliance for Sprint Framework projects"
    )
    parser.add_argument(
        "project_path",
        help="Path to the project directory"
    )
    parser.add_argument(
        "--sprint",
        type=int,
        help="Check specific sprint number"
    )
    parser.add_argument(
        "--work-item",
        help="Check specific work item ID (e.g., WI-001)"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on warnings (default: warnings only)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Attempt to auto-fix minor issues (not implemented)"
    )

    args = parser.parse_args()

    # Validate project path
    if not os.path.isdir(args.project_path):
        print(f"Error: Project path does not exist: {args.project_path}", file=sys.stderr)
        sys.exit(1)

    # Run compliance check
    checker = DocumentationComplianceChecker(args.project_path, strict=args.strict)
    report = checker.check_all(
        sprint_number=args.sprint,
        work_item_id=args.work_item
    )

    # Output report
    print(format_report(report, use_json=args.json))

    # Exit with appropriate code
    if report.overall_status == "fail":
        sys.exit(1)
    elif report.overall_status == "warn":
        sys.exit(2)  # Warning exit code
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()