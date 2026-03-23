"""Doctor command for diagnosing Carby Studio setup."""
import click
import sys
import shutil
import subprocess
import os
from pathlib import Path
from typing import List, Dict, Any


@click.command(name="doctor")
@click.option("--fix", is_flag=True, help="Attempt to fix issues automatically")
def doctor_command(fix: bool):
    """Diagnose Carby Studio setup and configuration.
    
    Checks:
    - Python version (3.11+)
    - carby-sprint in PATH
    - OpenClaw configuration
    - Git availability
    - Write permissions to workspace
    - Dependencies installed
    """
    checks = [
        check_python_version,
        check_cli_in_path,
        check_openclaw_config,
        check_git_available,
        check_write_permissions,
        check_dependencies,
    ]
    
    results = []
    issues = []
    
    for check in checks:
        result = check(fix=fix)
        results.append(result)
        if not result["passed"]:
            issues.append(result)
    
    # Print results
    print_diagnosis(results)
    
    if issues:
        click.echo(f"\n⚠️  Found {len(issues)} issue(s)")
        sys.exit(1)
    else:
        click.echo("\n✅ All checks passed!")
        sys.exit(0)


def check_python_version(fix: bool = False) -> Dict[str, Any]:
    """Check Python version is 3.11+."""
    import platform
    version = platform.python_version()
    major, minor = map(int, version.split('.')[:2])
    passed = major > 3 or (major == 3 and minor >= 11)
    return {
        "name": "Python version",
        "passed": passed,
        "message": f"Python {version}" if passed else f"Python {version} (requires 3.11+)",
        "fixable": False
    }


def check_cli_in_path(fix: bool = False) -> Dict[str, Any]:
    """Check carby-sprint is in PATH."""
    passed = shutil.which("carby-sprint") is not None
    return {
        "name": "CLI in PATH",
        "passed": passed,
        "message": "carby-sprint found in PATH" if passed else "carby-sprint not in PATH",
        "fixable": True,
        "fix_command": "export PATH=\"$HOME/.openclaw/workspace/skills/carby-studio:$PATH\""
    }


def check_openclaw_config(fix: bool = False) -> Dict[str, Any]:
    """Check OpenClaw is configured."""
    config_path = Path.home() / ".openclaw" / "config.json"
    passed = config_path.exists()
    return {
        "name": "OpenClaw config",
        "passed": passed,
        "message": f"Config at {config_path}" if passed else "OpenClaw not configured",
        "fixable": False
    }


def check_git_available(fix: bool = False) -> Dict[str, Any]:
    """Check Git is available."""
    passed = shutil.which("git") is not None
    return {
        "name": "Git",
        "passed": passed,
        "message": "Git available" if passed else "Git not found",
        "fixable": False
    }


def check_write_permissions(fix: bool = False) -> Dict[str, Any]:
    """Check write permissions to workspace."""
    workspace = Path.home() / ".openclaw" / "workspace"
    passed = workspace.exists() and os.access(workspace, os.W_OK)
    return {
        "name": "Write permissions",
        "passed": passed,
        "message": f"Can write to {workspace}" if passed else f"Cannot write to {workspace}",
        "fixable": False
    }


def check_dependencies(fix: bool = False) -> Dict[str, Any]:
    """Check required dependencies are installed."""
    required = ["click", "pydantic", "portalocker"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    passed = len(missing) == 0
    return {
        "name": "Dependencies",
        "passed": passed,
        "message": "All dependencies installed" if passed else f"Missing: {', '.join(missing)}",
        "fixable": True,
        "fix_command": "pip install " + " ".join(missing) if missing else None
    }


def print_diagnosis(results: List[Dict[str, Any]]):
    """Print diagnosis results in a table format."""
    click.echo("\n🔍 Carby Studio Doctor\n")
    for result in results:
        icon = "✅" if result["passed"] else "❌"
        click.echo(f"{icon} {result['name']}: {result['message']}")
        if not result["passed"] and result.get("fixable") and result.get("fix_command"):
            click.echo(f"   💡 Fix: {result['fix_command']}")


if __name__ == "__main__":
    doctor_command()
