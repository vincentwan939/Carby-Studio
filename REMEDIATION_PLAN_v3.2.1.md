# Carby Studio v3.2.1 Remediation Plan

**Generated:** 2026-03-23  
**Based on:** Security, Architecture, Testing, and UX Audits

---

## Executive Summary

| Category | Score | Priority |
|----------|-------|----------|
| Security | ⚠️ 1 Critical, 3 High | **P0 - Immediate** |
| Architecture | 6.6/10 | **P1 - Next Sprint** |
| Testing | 60-70% | **P1 - Next Sprint** |
| UX | 5.7/10 | **P2 - Following Sprint** |

**Estimated Effort:** 3-4 weeks full-time  
**Risk if Not Addressed:** Security vulnerabilities exploitable, state corruption possible, user adoption blocked

---

## P0 - Critical (Fix This Week)

### SECURITY-001: Timing Attack on HMAC Verification
**File:** `carby_sprint/gate_enforcer.py` (lines 201-218)  
**Severity:** 🔴 Critical  
**Effort:** 30 minutes

**Issue:** Expiration check happens BEFORE signature verification, leaking token validity timing.

**Fix:**
```python
# BEFORE (vulnerable):
if datetime.utcnow() > expires_at:
    raise ExpiredTokenError("Token has expired")
expected_signature = token_obj._sign_token()
if not hmac.compare_digest(expected_signature, signature):
    raise InvalidTokenError("Invalid token signature")

# AFTER (secure):
expected_signature = token_obj._sign_token()
if not hmac.compare_digest(expected_signature, signature):
    raise InvalidTokenError("Invalid token signature")
if datetime.utcnow() > expires_at:
    raise ExpiredTokenError("Token has expired")
```

---

### SECURITY-002: Race Condition in Gate Status Updates
**File:** `carby_sprint/gate_enforcer.py` (lines 129-150)  
**Severity:** 🟠 High  
**Effort:** 2 hours

**Issue:** No file locking for gate status updates — concurrent writes can corrupt state.

**Fix:**
```python
from .lock_manager import DistributedLock

def _save_gate_status(self, status: Dict[str, Any]) -> None:
    lock_path = self.sprint_dir / ".gate-status.lock"
    with DistributedLock(lock_path):
        self.status_file.write_text(json.dumps(status, indent=2))
```

---

### SECURITY-003: Token File Permissions
**File:** `carby_sprint/gate_enforcer.py` (line 443)  
**Severity:** 🟠 High  
**Effort:** 30 minutes

**Issue:** Design approval tokens written without restrictive permissions.

**Fix:**
```python
import os

self.token_path.parent.mkdir(parents=True, exist_ok=True)
with open(self.token_path, 'w') as f:
    json.dump(token.to_dict(), f, indent=2)
os.chmod(self.token_path, 0o600)  # Owner read/write only
```

---

### SECURITY-004: Input Validation on project_dir
**File:** `carby_sprint/gate_enforcer.py` (lines 226-230)  
**Severity:** 🟠 High  
**Effort:** 1 hour

**Issue:** No validation on `project_dir` parameter — potential directory traversal.

**Fix:**
```python
def __init__(self, project_dir: str):
    if '..' in str(project_dir) or '~' in str(project_dir):
        raise ValueError("Invalid project_dir: path traversal detected")
    self.project_dir = Path(project_dir).resolve()
    # Optional: validate within allowed base directory
```

---

### UX-001: Fix CLI Version Mismatch
**File:** `carby_sprint/cli.py` (line 25)  
**Severity:** 🔴 Critical (confusion)  
**Effort:** 5 minutes

**Issue:** CLI reports version `2.0.0`, docs claim `3.2.1`.

**Fix:**
```python
# Line 25 in cli.py
@click.version_option(version="3.2.1", prog_name="carby-sprint")
```

---

## P1 - High Priority (Next 2 Weeks)

### ARCH-001: Unify Phase State Management
**Files:** `phase_lock.py`, `sprint_repository.py`, `commands/phase.py`  
**Severity:** 🟠 High  
**Effort:** 3-4 days

**Issue:** Three state systems (`phase_lock.json`, `metadata.json`, `design-approval-token.json`) can drift.

**Approach:**
1. Create `PhaseLockService` class
2. Single method: `update_phase_state()` updates all three atomically
3. Deprecate direct file access

```python
class PhaseLockService:
    def __init__(self, repository: SprintRepository, gate_enforcer: GateEnforcer):
        self.repo = repository
        self.gate = gate_enforcer
    
    def update_phase_state(self, sprint_id: str, phase_id: str, 
                          state: PhaseState, summary: str = None):
        """Atomic update to all state systems."""
        with atomic_sprint_update(sprint_id, self.repo.sprints_dir):
            # Update phase_lock.json
            # Update metadata.json
            # Update gate tokens if needed
```

---

### TEST-001: Add Tests for Untested Modules
**Files:** `commands/init.py`, `commands/plan.py`, `authority.py`, `health_monitor.py`  
**Severity:** 🟠 High  
**Effort:** 3-4 days

**Target:** 13 modules with zero tests → minimum 70% coverage

**Priority order:**
1. `commands/init.py` - Sprint creation (critical path)
2. `commands/plan.py` - Work item planning
3. `authority.py` - Decision authority framework
4. `health_monitor.py` - System health checks

---

### TEST-002: Security Test Suite
**New File:** `tests/test_security.py`  
**Severity:** 🟠 High  
**Effort:** 2 days

**Required tests:**
- HMAC token tampering detection
- Path traversal attempts
- Token expiration handling
- Race condition simulation
- Permission validation

---

### ARCH-002: Extract Phase Lock from start.py
**File:** `commands/start.py` (lines 200-400)  
**Severity:** 🟠 High  
**Effort:** 2 days

**Issue:** 200+ lines of Phase Lock logic mixed with agent spawning.

**Approach:**
```python
# New file: services/phase_orchestrator.py
class PhaseOrchestrator:
    def __init__(self, phase_lock_service: PhaseLockService):
        self.service = phase_lock_service
    
    def prepare_phase(self, sprint_id: str, phase_id: str) -> PhaseResult:
        """Check gates, acquire locks, return ready status."""
```

---

### ARCH-003: Standardize Error Handling
**Files:** `phase_lock.py`, `commands/start.py`, `commands/phase.py`  
**Severity:** 🟡 Medium  
**Effort:** 2 days

**Issue:** Mix of `RuntimeError`, `ClickException`, domain exceptions.

**New exceptions:**
```python
class PhaseBlockedError(Exception):
    def __init__(self, phase_id: str, reason: str, resolution: str):
        self.phase_id = phase_id
        self.reason = reason
        self.resolution = resolution
        super().__init__(f"Phase {phase_id} blocked: {reason}. {resolution}")
```

---

## P2 - Medium Priority (Following Sprint)

### UX-002: Add `carby-sprint doctor` Command
**New File:** `commands/doctor.py`  
**Severity:** 🟡 Medium  
**Effort:** 1 day

**Checks:**
- Python version
- carby-sprint in PATH
- OpenClaw configured
- Git available
- Write permissions
- Dependencies installed

---

### UX-003: Add Progress Indicators
**Files:** `commands/start.py`, `commands/gate.py`  
**Severity:** 🟡 Medium  
**Effort:** 1 day

**Implementation:**
```python
import click

with click.progressbar(length=100, label='Spawning agent...') as bar:
    # Agent spawning logic
    bar.update(50)
    # Continue
```

---

### TEST-003: E2E Workflow Tests
**New File:** `tests/test_e2e_sprint_lifecycle.py`  
**Severity:** 🟡 Medium  
**Effort:** 2 days

**Test flow:**
1. `carby-sprint init`
2. `carby-sprint plan`
3. `carby-sprint start` (all 5 phases)
4. `carby-sprint gate` (all 5 gates)
5. Verify final state

---

### ARCH-004: Split GateEnforcer God Class
**File:** `carby_sprint/gate_enforcer.py` (600+ lines)  
**Severity:** 🟡 Medium  
**Effort:** 2 days

**Split into:**
- `gate_token.py` - Token generation/validation
- `gate_state.py` - Gate status management
- `design_gate.py` - Design approval specifics

---

## P3 - Low Priority (Future Releases)

### UX-004: Quick-Start Wizard
**New File:** `commands/wizard.py`  
**Effort:** 2 days

Interactive prompts for first-time users.

---

### UX-005: Bulk Work Item Operations
**New File:** `commands/work_item_bulk.py`  
**Effort:** 1 day

```bash
carby-sprint work-item update-all <sprint> --status completed
```

---

### ARCH-005: Consider Database Backend
**Effort:** 1 week

SQLite for state persistence at 100+ sprints scale.

---

## Implementation Schedule

### Week 1: Security & Critical Fixes
| Day | Task | Owner |
|-----|------|-------|
| 1 | SECURITY-001 (timing attack) | Security lead |
| 1 | SECURITY-004 (input validation) | Security lead |
| 2 | SECURITY-002 (race condition) | Backend dev |
| 2 | SECURITY-003 (token permissions) | Backend dev |
| 3 | UX-001 (version fix) | Frontend dev |
| 4-5 | TEST-002 (security tests) | QA |

### Week 2: Architecture & Testing
| Day | Task | Owner |
|-----|------|-------|
| 1-3 | ARCH-001 (unify state) | Architect |
| 4-5 | TEST-001 (untested modules) | QA |

### Week 3: Refactoring & Polish
| Day | Task | Owner |
|-----|------|-------|
| 1-2 | ARCH-002 (extract phase lock) | Backend dev |
| 3-4 | ARCH-003 (error handling) | Backend dev |
| 5 | UX-002 (doctor command) | Frontend dev |

### Week 4: E2E & Final Testing
| Day | Task | Owner |
|-----|------|-------|
| 1-2 | TEST-003 (E2E tests) | QA |
| 3 | UX-003 (progress indicators) | Frontend dev |
| 4-5 | Integration testing & release | All |

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Security issues (Critical/High) | 4 | 0 |
| Test coverage | 60-70% | 85%+ |
| Architecture score | 6.6/10 | 8.0+ |
| UX score | 5.7/10 | 7.5+ |
| State system count | 3 | 1 |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| State unification breaks existing sprints | Medium | High | Backup before migration |
| Security fixes introduce regressions | Low | Medium | Comprehensive testing |
| Timeline slips | Medium | Low | Prioritize P0, defer P2/P3 |

---

*Remediation Plan v3.2.1 - Generated by Team Task Audit*