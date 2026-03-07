#!/usr/bin/env python3
"""Validator for Carby Studio agent outputs.

Validates that artifacts meet quality standards before stage advancement.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Validation rules per stage
VALIDATION_RULES = {
    "discover": {
        "filename": "docs/requirements.md",
        "required_sections": [
            "## 1. Overview",
            "## 2. Functional Requirements",
            "## 3. Non-Functional Requirements",
            "## 4. Constraints",
            "## 5. Out of Scope"
        ],
        "forbidden_patterns": [
            (r"\[e\.g\.,", "Template placeholder: '[e.g., ...'"),
            (r"\[Why\]", "Template placeholder: '[Why]'"),
            (r"\[Description\]", "Template placeholder: '[Description]'"),
            (r"\[What it does\]", "Template placeholder: '[What it does]'"),
            (r"\[Brief description\]", "Template placeholder: '[Brief description]'"),
            (r"\[e\.g\. Python\]", "Template placeholder: '[e.g. Python]'"),
        ],
        "required_patterns": [
            (r"FR-\d{3}", "At least one functional requirement (FR-XXX)"),
            (r"NFR-\w+-\d{3}", "At least one non-functional requirement (NFR-XXX)"),
        ],
        "min_length": 500,  # Minimum characters
    },
    "design": {
        "filename": "docs/design.md",
        "required_sections": [
            "## 1. Architecture Overview",
            "## 2. Technology Stack",
            "## 3. Data Model",
            "## 4. API Specification"
        ],
        "forbidden_patterns": [
            (r"\[e\.g\.,", "Template placeholder: '[e.g., ...'"),
            (r"\[Why\]", "Template placeholder: '[Why]'"),
            (r"\[What it does\]", "Template placeholder: '[What it does]'"),
            (r"\[Description\]", "Template placeholder: '[Description]'"),
            (r"\[e\.g\. Python\]", "Template placeholder: '[e.g. Python]'"),
            (r"\[API Name\]", "Template placeholder: '[API Name]'"),
            (r"\[Component Name\]", "Template placeholder: '[Component Name]'"),
        ],
        "required_patterns": [
            (r"```\w+", "At least one code block (for API spec or schema)"),
        ],
        "min_length": 800,
    },
    "build": {
        "filename": "tasks/build-tasks.json",
        "file_exists": True,
        "required_sections": [],
        "forbidden_patterns": [],
        "required_patterns": [],
        "min_length": 0,
    },
    "verify": {
        "filename": "docs/verify-report.md",
        "required_sections": [
            "## Executive Summary",
            "## Detailed Findings",
            "## Metrics"
        ],
        "forbidden_patterns": [
            (r"\[e\.g\.,", "Template placeholder: '[e.g., ...'"),
        ],
        "required_patterns": [
            (r"Decision:\s*\[GO|NO-GO|CONDITIONAL\]", "Go/No-go decision"),
        ],
        "min_length": 300,
    },
    "deliver": {
        "filename": "docs/delivery-summary.md",
        "required_sections": [
            "## What Was Delivered",
            "## Where It Lives"
        ],
        "forbidden_patterns": [
            (r"\[e\.g\.,", "Template placeholder: '[e.g., ...'"),
        ],
        "required_patterns": [],
        "min_length": 200,
    }
}


def validate_file(filepath: Path, rules: Dict) -> Dict:
    """Validate a file against rules."""
    errors = []
    warnings = []
    score = 100
    
    # Check file exists
    if not filepath.exists():
        return {
            "valid": False,
            "score": 0,
            "errors": [f"File not found: {filepath}"],
            "warnings": [],
            "details": {}
        }
    
    content = filepath.read_text()
    details = {
        "file_size": len(content),
        "line_count": len(content.splitlines()),
    }
    
    # Check minimum length
    if rules.get("min_length", 0) > 0:
        if len(content) < rules["min_length"]:
            errors.append(f"File too short: {len(content)} chars (min: {rules['min_length']})")
            score -= 15
    
    # Check required sections
    for section in rules.get("required_sections", []):
        if section not in content:
            errors.append(f"Missing section: {section}")
            score -= 10
    
    # Check forbidden patterns (template placeholders)
    for pattern, description in rules.get("forbidden_patterns", []):
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            errors.append(f"{description} found {len(matches)} time(s)")
            score -= 10 * len(matches)
    
    # Check required patterns
    for pattern, description in rules.get("required_patterns", []):
        if not re.search(pattern, content):
            warnings.append(f"Missing: {description}")
            score -= 5
    
    # Ensure score doesn't go below 0
    score = max(0, score)
    
    return {
        "valid": len(errors) == 0 and score >= 80,
        "score": score,
        "errors": errors,
        "warnings": warnings,
        "details": details
    }


def validate_project(project_dir: Path, stage: str) -> Dict:
    """Validate a specific stage of a project."""
    if stage not in VALIDATION_RULES:
        return {
            "valid": False,
            "score": 0,
            "errors": [f"Unknown stage: {stage}"],
            "warnings": [],
            "details": {}
        }
    
    rules = VALIDATION_RULES[stage]
    filepath = project_dir / rules["filename"]
    
    return validate_file(filepath, rules)


def main():
    parser = argparse.ArgumentParser(description="Validate Carby Studio agent outputs")
    parser.add_argument("project_dir", help="Path to project directory")
    parser.add_argument("stage", help="Stage to validate (discover/design/build/verify/deliver)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--threshold", type=int, default=80, help="Minimum score to pass (default: 80)")
    
    args = parser.parse_args()
    
    project_dir = Path(args.project_dir)
    result = validate_project(project_dir, args.stage)
    
    # Apply custom threshold
    result["valid"] = result["score"] >= args.threshold and len(result["errors"]) == 0
    result["threshold"] = args.threshold
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Validation Result for '{args.stage}'")
        print("=" * 50)
        print(f"Score: {result['score']}/100 (threshold: {result['threshold']})")
        print(f"Status: {'✓ PASS' if result['valid'] else '✗ FAIL'}")
        print()
        
        if result["details"]:
            print("Details:")
            for key, value in result["details"].items():
                print(f"  {key}: {value}")
            print()
        
        if result["errors"]:
            print("Errors:")
            for error in result["errors"]:
                print(f"  ✗ {error}")
            print()
        
        if result["warnings"]:
            print("Warnings:")
            for warning in result["warnings"]:
                print(f"  ⚠ {warning}")
            print()
    
    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
