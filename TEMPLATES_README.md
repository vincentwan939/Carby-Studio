# Carby Studio Golden Path Templates

**Version:** 1.0.0  
**Status:** ✅ Production Ready  
**Last Updated:** 2026-03-07

---

## Overview

Golden Path templates provide production-ready starting points for the **Build** phase of the Carby Studio SDLC. Each template includes:

- **Complete project structure** with best practices
- **Working code** that compiles and runs
- **Dockerfile** for containerized deployment
- **Tests** with examples
- **Documentation** (STRUCTURE.md) explaining conventions
- **Manifest** (JSON) with metadata and customization points

---

## Available Templates

| Language | Framework | Status | Files | Docker Size |
|----------|-----------|--------|-------|-------------|
| Python | FastAPI | ✅ Validated | 12 | ~125 MB |
| Node.js | Express | ✅ Validated | 10 | ~180 MB |
| Go | Gin | ✅ Validated | 9 | ~25 MB |
| Rust | Axum | ✅ Validated | 10 | ~35 MB |

---

## Quick Start

### For Build Agents

```python
# 1. Detect project language
from scripts.language_detector import detect_language
lang = detect_language("/path/to/project")  # "python", "nodejs", "go", "rust"

# 2. Copy appropriate template
cp -r templates/{lang}/* /path/to/project/

# 3. Read STRUCTURE.md for conventions
cat /path/to/project/STRUCTURE.md

# 4. Follow customization points in manifest
cat templates/_manifests/{lang}-{framework}.json
```

### For Developers

```bash
# Initialize project with template
carby-studio init my-api -g "Build REST API"

# During Build phase, template is auto-copied
carby-studio status my-api
# Shows: Build phase - template ready

# Customize following STRUCTURE.md guidelines
# See: src/STRUCTURE.md
```

---

## Template Structure

Each template includes:

```
templates/{language}/
├── STRUCTURE.md              # Conventions & patterns (READ THIS FIRST)
├── README.md                 # Quick start guide
├── .gitignore                # Git ignore patterns
├── .dockerignore             # Docker ignore patterns
├── {build-config}            # pyproject.toml, package.json, etc.
├── Dockerfile                # Production container image
├── src/                      # Application source code
│   ├── main.{ext}            # Entry point with health check
│   ├── config.{ext}          # Configuration management
│   └── ...                   # Additional modules
└── tests/                    # Test files
    └── test_main.{ext}       # Example tests
```

---

## Template Manifests

Manifests provide metadata for the Build agent:

```json
{
  "name": "python-fastapi",
  "language": "python",
  "framework": "fastapi",
  "validated": true,
  "customization_points": [
    {
      "file": "src/models/",
      "action": "create",
      "description": "Add SQLAlchemy models"
    }
  ],
  "preserved_patterns": [
    "Health check endpoint at /health",
    "Non-root user in Dockerfile"
  ]
}
```

**Location:** `templates/_manifests/`

---

## Validation Status

All templates have been:

- ✅ **Syntax validated** - Code compiles/parses correctly
- ✅ **Structure reviewed** - Follows language best practices
- ✅ **Docker tested** - Multi-stage builds work
- ✅ **Security checked** - Non-root users, minimal images
- ✅ **Documentation complete** - STRUCTURE.md explains all conventions

---

## Customization Guide

### What to Modify

Each template's STRUCTURE.md includes:

1. **Customization Points** - Where to add your code
2. **Preserved Patterns** - What must not be removed
3. **Escape Hatches** - How to deviate if needed

### Example: Adding a Route (Python/FastAPI)

```python
# 1. Create router file (src/routers/users.py)
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/")
def list_users():
    return {"users": []}

# 2. Register in src/main.py
from routers import users
app.include_router(users.router)
```

---

## Health Check Endpoint

All templates include a `/health` endpoint:

```bash
curl http://localhost:8000/health
# {"status": "healthy", "version": "0.1.0"}
```

**Required for:** Load balancers, Kubernetes probes, Docker HEALTHCHECK

---

## Docker Images

### Build

```bash
cd templates/python  # or nodejs, go, rust
docker build -t myapp .
```

### Run

```bash
docker run -p 8000:8000 myapp
```

### Security Features

- ✅ Multi-stage builds (smaller images)
- ✅ Non-root user execution
- ✅ Minimal base images
- ✅ No build tools in final image

---

## Language-Specific Notes

### Python (FastAPI)
- **Dependencies:** FastAPI, SQLAlchemy 2.0, Pydantic 2.x
- **Testing:** pytest with async support
- **Config:** Pydantic Settings (environment-based)

### Node.js (Express)
- **Dependencies:** Express 4.x, TypeScript 5.x
- **Testing:** Jest with supertest
- **Config:** dotenv with TypeScript types

### Go (Gin)
- **Dependencies:** Gin, logrus
- **Testing:** testify
- **Config:** Environment variables with defaults
- **Layout:** Standard Go project structure

### Rust (Axum)
- **Dependencies:** Axum 0.7, Tokio 1.34, SQLx 0.7
- **Testing:** Built-in test framework
- **Config:** Environment variables
- **Features:** Structured logging with tracing

---

## Maintenance

### Updating Dependencies

Edit the build config file:
- Python: `pyproject.toml`
- Node.js: `package.json`
- Go: `go.mod`
- Rust: `Cargo.toml`

### Testing Changes

```bash
# Python
cd templates/python
pip install -e "."
pytest

# Node.js
cd templates/nodejs
npm install
npm test

# Go
cd templates/go
go test ./...

# Rust
cd templates/rust
cargo test
```

---

## Troubleshooting

### Template Not Found

```bash
# Check available templates
ls templates/
# Should show: python, nodejs, go, rust
```

### Docker Build Fails

```bash
# Check Docker is running
docker info

# Try with no cache
docker build --no-cache -t myapp .
```

### Import Errors

Make sure you're following the STRUCTURE.md conventions for your language.

---

## Contributing

To add a new template:

1. Create directory: `templates/{language}/`
2. Add STRUCTURE.md explaining conventions
3. Add working source code
4. Add Dockerfile (multi-stage, non-root)
5. Add tests
6. Generate manifest: `python3 scripts/generate_manifest.py templates/{language}`
7. Validate: `python3 scripts/validate_templates.py`

---

## References

- [Golden Path Pattern](https://engineering.atspotify.com/2020/08/how-we-use-golden-paths-to-solve-fragmentation-in-our-software-ecosystem/)
- [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices)
- [Go Project Layout](https://github.com/golang-standards/project-layout)
- [Rust API Guidelines](https://rust-lang.github.io/api-guidelines/)

---

**Questions?** See [STRUCTURE.md](templates/python/STRUCTURE.md) in any template for detailed conventions.
