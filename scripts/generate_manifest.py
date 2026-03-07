#!/usr/bin/env python3
"""Generate manifest.json for a Golden Path template.

Usage:
    python3 generate_manifest.py <template_dir>
    
Example:
    python3 generate_manifest.py templates/python
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def generate_manifest(template_dir: Path) -> dict:
    """Generate manifest for a template directory."""
    
    # Detect language from directory name
    lang = template_dir.name
    
    # Map to framework
    frameworks = {
        "python": "fastapi",
        "nodejs": "express",
        "go": "gin",
        "rust": "axum"
    }
    
    framework = frameworks.get(lang, "unknown")
    
    # Count files
    files = []
    for f in template_dir.rglob("*"):
        if f.is_file() and not f.name.startswith("."):
            rel_path = f.relative_to(template_dir)
            files.append({
                "path": str(rel_path),
                "description": f"Template file: {rel_path.name}"
            })
    
    manifest = {
        "name": f"{lang}-{framework}",
        "language": lang,
        "framework": framework,
        "description": f"Production-ready {lang.title()} {framework.title()} template",
        "version": "1.0.0",
        "validated": False,
        "generated_at": datetime.now().isoformat(),
        "tested_versions": {},
        "metrics": {
            "build_time_seconds": None,
            "test_time_seconds": None,
            "docker_image_size_mb": None
        },
        "customization_points": [
            {
                "file": "src/",
                "action": "create",
                "description": "Add application source code"
            },
            {
                "file": "tests/",
                "action": "create",
                "description": "Add tests"
            }
        ],
        "preserved_patterns": [
            "Health check endpoint",
            "Non-root user in Dockerfile",
            "Graceful shutdown handling"
        ],
        "escape_hatches": [
            "Replace entire src/ directory if needed",
            "Modify Dockerfile for different base images"
        ],
        "files": files[:10]  # Limit to first 10 files
    }
    
    return manifest


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 generate_manifest.py <template_dir>")
        sys.exit(1)
    
    template_dir = Path(sys.argv[1])
    
    if not template_dir.exists():
        print(f"Error: Directory not found: {template_dir}")
        sys.exit(1)
    
    manifest = generate_manifest(template_dir)
    
    # Write to _manifests directory
    manifests_dir = Path(__file__).parent.parent / "templates" / "_manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = manifests_dir / f"{manifest['name']}.json"
    
    with open(output_file, "w") as f:
        json.dump(manifest, f, indent=2)
    
    print(f"Generated manifest: {output_file}")
    print(f"Language: {manifest['language']}")
    print(f"Framework: {manifest['framework']}")
    print(f"Files: {len(manifest['files'])}")


if __name__ == "__main__":
    main()
