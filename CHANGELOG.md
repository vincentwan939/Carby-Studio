# Changelog

All notable changes to Carby Studio will be documented in this file.

## [1.0.0] - 2026-03-07

### Added

#### Phase 1: Production Readiness
- ✅ Comprehensive concurrent access testing (6 scenarios, 1,800+ operations)
- ✅ Prerequisites check script (`carby-studio check-prerequisites`)
- ✅ Smoke test suite (28 tests, all passing)
- ✅ Fixed EDGE-013 and EDGE-014 test scripts
- ✅ Fixed `cmd_reset()` bug in task_manager.py

#### Phase 2: Operational Excellence
- ✅ Metrics collection system (`scripts/metrics.py`)
- ✅ Metrics dashboard (`carby-studio metrics`)
- ✅ JSONL-based event storage
- ✅ Complete prerequisites documentation (`docs/PREREQUISITES.md`)
- ✅ Automated prerequisites checking

#### Phase 3: Scale & Expand
- ✅ Backend abstraction (`team-tasks/scripts/backend.py`)
- ✅ SQLite backend for high-concurrency scenarios
- ✅ Migration tool from file to SQLite
- ✅ Golden Path templates (4 languages)
  - Python (FastAPI) with SQLAlchemy 2.0
  - Node.js (Express) with TypeScript
  - Go (Gin) with standard project layout
  - Rust (Axum) with Tokio and SQLx
- ✅ Language detector (`scripts/language_detector.py`)
- ✅ Template manifests with metadata

### Changed

- Updated main README.md with new features
- Added environment variables documentation
- Improved CLI with `metrics` and `check-prerequisites` commands

### Fixed

- Fixed race condition in concurrent state access (EDGE-015)
- Fixed `cmd_reset()` variable scope issue
- Fixed test scripts (EDGE-013, EDGE-014)
- Fixed Python Dockerfile (added psycopg2-binary)
- Fixed Go module name placeholder
- Fixed Rust package name placeholder
- Added missing .dockerignore and .gitignore files

### Security

- All Dockerfiles use non-root users
- Multi-stage builds for minimal attack surface
- No build tools in production images
- Health checks configured

## [0.9.0] - 2026-03-06

### Added
- Initial release
- 5-stage SDLC pipeline (Discover → Design → Build → Verify → Deliver)
- Linear and DAG workflow modes
- Debate mode for multi-agent discussions
- File-based JSON storage with fcntl locking
- Basic CLI interface
- Agent prompts for all 5 stages

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 1.0.0 | 2026-03-07 | ✅ Production Ready |
| 0.9.0 | 2026-03-06 | Beta |

---

## Future Roadmap

### Potential Enhancements
- [ ] Cloud deployment templates (AWS, GCP, Azure)
- [ ] IDE integrations (VS Code extension)
- [ ] Advanced analytics dashboard
- [ ] Web UI for project management
- [ ] Integration with CI/CD platforms
- [ ] More language templates (Java, C#, etc.)

---

**Note:** This project follows [Semantic Versioning](https://semver.org/).
