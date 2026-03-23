# Changelog

All notable changes to Carby Studio are documented in this file.

## [3.2.1] - 2026-03-23

### Two-Stage Verify & Agent Handoff Improvements

This release introduces the Two-Stage Verify pattern for enhanced quality assurance and improves agent handoff reliability for multi-agent workflows.

#### Added
- **Two-Stage Verify Pattern** — Split verification into Implementation Review and Final Validation phases
- **Stage 1: Implementation Review** — Technical correctness, pattern compliance, test coverage validation
- **Stage 2: Final Validation** — Integration testing, regression testing, acceptance criteria verification
- **Agent Handoff Protocol** — Structured context passing between agents with state preservation
- **Handoff State Files** — JSON-based handoff artifacts with complete context for seamless transitions

#### Changed
- **Verification Phase** — Now uses two-stage approach instead of single combined review
- **Agent Dispatcher** — Improved handoff reliability with state persistence and recovery
- **Work Item State Model** — Extended to track stage-specific verification status
- **CLI Output** — Enhanced status display for two-stage verification progress

#### Fixed
- **Agent Handoff Race Condition** — Fixed timing issue where handoff could occur before state persistence
- **Verification State Loss** — Resolved edge case where verification state could be lost on agent restart
- **Context Truncation** — Fixed issue where large handoff contexts could be truncated

#### Security
- **Handoff Token Validation** — Added HMAC-SHA256 validation for inter-agent handoff tokens
- **Context Sanitization** — Automatic sanitization of handoff context to prevent injection attacks

---

## [3.2.0] - 2026-03-20

### TDD Protocol + Design-First HARD-GATE

This release introduces mandatory Test-Driven Development (TDD) protocol and hard-gates the Design phase to prevent implementation without proper design documentation.

#### Added
- **TDD Protocol Enforcement** — Hard-gate requiring tests before implementation
- **Design-First HARD-GATE** — Implementation blocked without approved design document
- **Pre-Implementation Checklist** — Automated verification of design completion before build phase
- **Test Coverage Gates** — Minimum coverage thresholds enforced at validation phase
- **Design Document Schema** — Structured design.md template with mandatory sections
- **Design Approval Workflow** — Explicit design approval required before proceeding to build

#### Changed
- **Build Phase Entry** — Now requires completed and approved design document
- **Validation Gates** — Enhanced to include TDD compliance verification
- **Work Item Lifecycle** — Design phase is now a HARD-GATE with no bypass option
- **Gate Enforcer** — Updated to validate design document presence and approval status
- **CLI Commands** — Added `carby-sprint design-approve` for explicit design sign-off

#### Fixed
- **Design Bypass Issue** — Fixed vulnerability where agents could skip design phase
- **Test-Last Pattern** — Prevented implementation-before-testing workflow
- **Empty Design Documents** — Validation now catches and rejects incomplete designs

#### Security
- **Design Gate Tampering** — Server-side enforcement prevents client-side design gate bypass
- **Approval Token Binding** — Design approval tokens bound to specific sprint and work item

---

## [3.1.0] - 2026-03-21

### Phase Lock Sequential Execution

#### New Features
- **Phase Lock Core** (`phase_lock.py`) — File-based state machine for sequential phase enforcement
- **Sequential Mode** — `carby-sprint start --mode sequential` for controlled phase-by-phase execution
- **Approval Workflow** — `carby-sprint approve <sprint> <phase>` for explicit user approval between phases
- **Phase Status Commands** — `carby-sprint phase-status` and `phase-list` for monitoring
- **Phase Sequence** — discover → design → build → verify → deliver

#### Commands Added
- `carby-sprint approve <sprint-id> <phase-id>` — Approve completed phase to unblock next
- `carby-sprint phase-status <sprint-id>` — Show all phase statuses with visual indicators
- `carby-sprint phase-list <sprint-id>` — List phases in table/JSON/compact format

#### Configuration
- Added `[phase_lock]` section to `carby-studio.conf`
- Settings: `enabled`, `default_mode`, `phase_order`, `approval_required`, `notification`

#### Documentation
- **PHASE_LOCK.md** — Comprehensive feature documentation
- **phase_lock_design.md** — Design rationale and architecture
- **FRAMEWORK_ENHANCEMENT.md** — Framework enhancement proposals
- **PROCESS_AUDIT.md** — Process audit findings (Property Hunter case study)

#### Testing
- **65 new tests** — 20 (phase_lock) + 25 (phase_cli) + 20 (sequential_mode)
- **100% test coverage** for Phase Lock module
- All tests passing: 134/134

#### Migration
- **No breaking changes** — Phase Lock is opt-in via `--mode sequential`
- Default behavior unchanged (parallel execution)
- Existing projects continue to work without modification

---

## [3.0.0] - 2026-03-20

### Security Hardening

#### Critical Fixes
- **Path Traversal Protection** — Implemented regex validation and safe path joining in `path_utils.py`
- **Race Condition Prevention** — Added distributed file locking using `portalocker` in `lock_manager.py`
- **Command Injection Prevention** — Converted to list-based subprocess calls, removed all `shell=True` usages
- **JSON Validation** — Added Pydantic models for sprint and work item validation

#### High Priority Fixes
- **Server-Side Gate Enforcement** — HMAC-SHA256 signed tokens with 24-hour expiration prevent gate bypassing
- **Authority Framework** — Decision authority controls (HUMAN_REQUIRED, AGENT_RECOMMENDS, AGENT_AUTONOMOUS)
- **Token Security** — Cryptographic token validation with tamper detection

### Reliability Improvements

#### Critical Fixes
- **Atomic Transactions** — Thread-safe copy-on-write with unique temp directories (UUID + thread ID)
- **TOCTOU Protection** — Atomic cleanup locks prevent race conditions in lock removal
- **Fail-Fast Error Handling** — Removed silent exception catching, strict validation

#### High Priority Fixes
- **Backup Management** — Automatic cleanup keeps last 10 backups
- **Health Monitoring** — Stale lock detection, hung agent detection, log rotation
- **Thread Safety** — Proper thread-local storage initialization

### Design Improvements

- **Server-Side Gate Enforcement** — Agents cannot bypass gates via client-side manipulation
- **Authority Framework** — Configurable decision authority with priority system
- **Legacy Deprecation** — Clear deprecation warnings for v2.0.0 CLI

### Testing

- **97% Test Coverage** — 69/71 tests passing
- **Security Tests** — Path traversal, race condition, locking tests
- **Reliability Tests** — Transaction rollback, recovery, health monitoring
- **Design Tests** — Gate enforcement, authority framework

### Documentation

- Updated SKILL.md with v3.0.0 features and security documentation
- Updated README.md with production-ready status
- Added comprehensive security and reliability feature tables

## [2.0.0] - 2026-03-18

### Sprint Framework

- Introduced Sprint Framework with parallel work item execution
- Added validation gates (Planning, Design, Implementation, Validation, Release)
- Implemented Gate Enforcer with risk scoring
- Added Doc Trainer for documentation compliance
- Implemented File Locker for parallel execution safety

### Features

- Phase 1: Gate Enforcer, Doc Trainer, File Locker
- Phase 2: CLI Core, State Manager, Agent Dispatcher, GitHub Integration
- 10 security fixes (3 critical vulnerabilities resolved)
- 205+ tests passing
- 92% confidence rating

## [1.0.0] - 2026-03-07

### Initial Release

- 5-stage SDLC pipeline (Discover, Design, Build, Verify, Deliver)
- Agent dispatch via OpenClaw `sessions_spawn`
- Basic file-based storage
- Sequential execution model

---

## Migration Guide

### v2.0.0 → v3.0.0

No breaking changes. v3.0.0 is backward compatible with v2.0.0 sprints.

**New Features Available:**
- Use `carby-sprint` CLI (v2.0.0 `carby-studio` still works but deprecated)
- Gate enforcement now server-side with HMAC tokens
- Atomic transactions prevent data corruption
- Health monitoring auto-detects stuck sprints

**Recommended Actions:**
1. Update to v3.0.0 (`pip install --upgrade carby-sprint`)
2. Run existing sprints — they continue to work
3. New sprints automatically use v3.0.0 features
4. Update scripts to use `carby-sprint` instead of `carby-studio`

### v1.0.0 → v3.0.0

**Breaking Changes:**
- Project structure changed from `projects/<name>/` to `.carby-sprints/<name>/`
- Configuration moved from `.carby-config.json` to sprint metadata

**Migration Steps:**
1. Create new sprint: `carby-sprint init <sprint-id> --project <name> --goal "..."`
2. Copy relevant files from old project to new sprint
3. Update any scripts referencing old paths

---

## Security Audit History

| Date | Auditor | Issues Found | Status |
|------|---------|--------------|--------|
| 2026-03-20 | Security Critic | 3 Critical, 2 High | ✅ Fixed |
| 2026-03-20 | Reliability Defender | 3 Critical, 2 High | ✅ Fixed |
| 2026-03-20 | Design Auditor | 3 Critical, 2 High | ✅ Fixed |
| 2026-03-20 | Final Validation | 94% confidence | ✅ Passed |

---

*Carby Studio follows [Semantic Versioning](https://semver.org/).*
