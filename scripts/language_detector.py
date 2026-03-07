#!/usr/bin/env python3
"""Language detection for Carby Studio projects.

Detects the programming language of a project based on file patterns.
"""

import os
from pathlib import Path
from typing import Optional

# Language detection patterns
LANGUAGE_PATTERNS = {
    "python": {
        "files": ["*.py", "requirements.txt", "pyproject.toml", "setup.py", "Pipfile", "poetry.lock"],
        "dirs": ["__pycache__", ".venv", "venv", ".pytest_cache"],
    },
    "nodejs": {
        "files": ["*.js", "*.ts", "*.jsx", "*.tsx", "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "tsconfig.json"],
        "dirs": ["node_modules", ".next", "dist", "build"],
    },
    "go": {
        "files": ["*.go", "go.mod", "go.sum", "go.work"],
        "dirs": ["vendor", "bin"],
    },
    "rust": {
        "files": ["*.rs", "Cargo.toml", "Cargo.lock"],
        "dirs": ["target", ".cargo"],
    },
}

# Language-specific build/test commands
LANGUAGE_COMMANDS = {
    "python": {
        "install": "pip install -r requirements.txt",
        "test": "pytest",
        "test_coverage": "pytest --cov=src --cov-report=term-missing",
        "typecheck": "mypy src/",
        "lint": "ruff check src/",
        "format": "ruff format src/",
        "run": "python -m src.main",
    },
    "nodejs": {
        "install": "npm install",
        "test": "npm test",
        "test_coverage": "npm run test:coverage",
        "typecheck": "npx tsc --noEmit",
        "lint": "npm run lint",
        "format": "npm run format",
        "run": "npm start",
        "dev": "npm run dev",
    },
    "go": {
        "install": "go mod download",
        "test": "go test ./...",
        "test_coverage": "go test -cover ./...",
        "typecheck": "go vet ./...",
        "lint": "golangci-lint run",
        "format": "gofmt -w .",
        "run": "go run .",
        "build": "go build -o bin/app",
    },
    "rust": {
        "install": "cargo build",
        "test": "cargo test",
        "test_coverage": "cargo tarpaulin --out Xml",
        "typecheck": "cargo check",
        "lint": "cargo clippy",
        "format": "cargo fmt",
        "run": "cargo run",
        "build": "cargo build --release",
    },
}

# Language-specific deployment configs
LANGUAGE_DEPLOYMENT = {
    "python": {
        "dockerfile": "templates/python/Dockerfile",
        "dockerignore": "templates/python/.dockerignore",
    },
    "nodejs": {
        "dockerfile": "templates/nodejs/Dockerfile",
        "dockerignore": "templates/nodejs/.dockerignore",
    },
    "go": {
        "dockerfile": "templates/go/Dockerfile",
        "dockerignore": "templates/go/.dockerignore",
    },
    "rust": {
        "dockerfile": "templates/rust/Dockerfile",
        "dockerignore": "templates/rust/.dockerignore",
    },
}


def detect_language(project_dir: Path) -> Optional[str]:
    """Detect the programming language of a project.
    
    Args:
        project_dir: Path to the project directory
        
    Returns:
        Language name (python, nodejs, go, rust) or None if unknown
    """
    if not project_dir.exists():
        return None
    
    scores = {lang: 0 for lang in LANGUAGE_PATTERNS}
    
    for lang, patterns in LANGUAGE_PATTERNS.items():
        # Check for files (recursively)
        for pattern in patterns["files"]:
            if list(project_dir.rglob(pattern)):
                scores[lang] += 1
        
        # Check for directories
        for dirname in patterns["dirs"]:
            if (project_dir / dirname).exists():
                scores[lang] += 2  # Directories are stronger signals
    
    # Return language with highest score
    if scores:
        best_lang = max(scores, key=scores.get)
        if scores[best_lang] > 0:
            return best_lang
    
    return None


def get_language_commands(language: str) -> dict:
    """Get build/test commands for a language.
    
    Args:
        language: Language name
        
    Returns:
        Dictionary of command names to command strings
    """
    return LANGUAGE_COMMANDS.get(language, {})


def get_project_info(project_dir: Path) -> dict:
    """Get comprehensive project information.
    
    Args:
        project_dir: Path to the project directory
        
    Returns:
        Dictionary with language, commands, and other info
    """
    language = detect_language(project_dir)
    
    info = {
        "language": language,
        "commands": get_language_commands(language) if language else {},
        "detected_files": [],
    }
    
    # List detected files
    if language:
        patterns = LANGUAGE_PATTERNS[language]
        for pattern in patterns["files"]:
            files = list(project_dir.rglob(pattern))
            info["detected_files"].extend([f.name for f in files])
    
    return info


def main():
    """CLI for language detection."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Detect project language")
    parser.add_argument("project_dir", nargs="?", default=".",
                       help="Project directory to analyze")
    parser.add_argument("--json", "-j", action="store_true",
                       help="Output as JSON")
    parser.add_argument("--commands", "-c", action="store_true",
                       help="Show available commands")
    
    args = parser.parse_args()
    
    project_dir = Path(args.project_dir)
    language = detect_language(project_dir)
    
    if args.json:
        info = get_project_info(project_dir)
        print(json.dumps(info, indent=2))
    elif args.commands:
        if language:
            commands = get_language_commands(language)
            print(f"Commands for {language}:")
            for name, cmd in commands.items():
                print(f"  {name:15} {cmd}")
        else:
            print("Unknown language")
    else:
        if language:
            print(f"Detected language: {language}")
            print(f"Detected files: {', '.join(get_project_info(project_dir)['detected_files'][:5])}")
        else:
            print("Could not detect language")


if __name__ == "__main__":
    main()
