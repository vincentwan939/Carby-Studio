# Security Policy

Security information for Carby Studio.

---

## Reporting Security Vulnerabilities

### How to Report

If you discover a security vulnerability in Carby Studio, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. Email security concerns to: `security@carbystudio.local`
3. Include detailed steps to reproduce
4. Allow reasonable time for response before public disclosure

### Response Timeline

| Severity | Acknowledgment | Fix Target | Disclosure |
|----------|----------------|------------|------------|
| Critical | 24 hours | 7 days | After fix |
| High | 48 hours | 14 days | After fix |
| Medium | 72 hours | 30 days | After fix |
| Low | 7 days | 90 days | After fix |

### What to Include

Your report should include:

- **Description:** Clear description of the vulnerability
- **Steps to Reproduce:** Detailed reproduction steps
- **Impact:** What could an attacker do?
- **Affected Versions:** Which versions are impacted?
- **Mitigation:** Any known workarounds

---

## Security Features Overview

### Path Traversal Protection

Prevents directory traversal attacks through path manipulation.

**Implementation:**
- Regex validation: `^[a-zA-Z0-9_-]+$`
- Safe path joining with `path_utils.py`
- Rejection of `..`, `/`, `\` characters

**Example:**
```python
from carby_sprint.path_utils import validate_sprint_id

validate_sprint_id("sprint-001")   # OK
validate_sprint_id("../etc")       # Raises ValueError
```

### Race Condition Prevention

Distributed file locking prevents concurrent modification conflicts.

**Implementation:**
- `portalocker` for cross-platform file locking
- Timeout and retry mechanisms
- Automatic stale lock detection

**Example:**
```python
from carby_sprint.lock_manager import with_sprint_lock

with with_sprint_lock(".carby-sprints/sprint-001/.lock"):
    # Critical section - only one process
    pass
```

### Command Injection Prevention

List-based subprocess calls eliminate shell injection vulnerabilities.

**Implementation:**
- No `shell=True` usage
- Argument lists instead of string commands
- Input validation before execution

### JSON Validation

Pydantic models enforce data integrity.

**Implementation:**
- `SprintModel` for sprint data
- `WorkItemModel` for work item data
- Automatic type coercion and validation

**Example:**
```python
from carby_sprint.validators import SprintModel

# Invalid data raises ValidationError
sprint = SprintModel(sprint_id="../etc", ...)  # Rejected
```

---

## HMAC Token Security

### Overview

Gate tokens use HMAC-SHA256 signatures to prevent tampering and bypass attempts.

### Token Structure

```
<base64-encoded-payload>.<hmac-signature>
```

**Payload:**
```json
{
  "gate_id": "gate-1",
  "sprint_id": "sprint-001",
  "created_at": "2026-03-23T10:00:00",
  "expires_at": "2026-03-24T10:00:00",
  "nonce": "random-nonce-value"
}
```

### Security Properties

| Property | Implementation | Purpose |
|----------|----------------|---------|
| **Authenticity** | HMAC-SHA256 | Verify token origin |
| **Integrity** | Cryptographic signature | Detect tampering |
| **Expiration** | 24-hour lifetime | Limit attack window |
| **Uniqueness** | Cryptographic nonce | Prevent replay |

### Secret Key Management

```
Location: ~/.openclaw/secrets/carby-studio-gate-key
Permissions: 0o600 (owner read/write only)
Generation: secrets.token_bytes(32)
```

**Key Rotation:**
- Keys are persistent across restarts
- Manual rotation: delete secret file (invalidates all tokens)
- Automatic rotation: not implemented (planned for v4.0)

### Token Validation

```python
from carby_sprint.gate_enforcer import GateToken

# Validate token
try:
    token = GateToken.from_string(token_string)
    is_valid = token.validate()
except InvalidTokenError:
    # Token tampered with
    pass
except ExpiredTokenError:
    # Token expired
    pass
```

### Server-Side Enforcement

Tokens are validated server-side, preventing client bypass:

```python
from carby_sprint.gate_enforcer import GateEnforcer

enforcer = GateEnforcer(sprint_id)
if not enforcer.can_advance(current_gate, next_gate, token):
    raise GateBypassError("Invalid or expired token")
```

---

## Gate Enforcement

### Five Validation Gates

| Gate | Name | Purpose |
|------|------|---------|
| 1 | Planning Gate | Validate sprint planning |
| 2 | Design Gate | Validate design decisions |
| 3 | Implementation Gate | Validate implementation |
| 4 | Validation Gate | Validate completed work |
| 5 | Release Gate | Validate release readiness |

### Gate Bypass Prevention

**Client-Side:**
- Tokens required to advance
- Token validation before state changes

**Server-Side:**
- HMAC verification
- Expiration checking
- Sprint ID binding

**Audit Trail:**
- All gate transitions logged
- Token signatures recorded
- Tampering attempts flagged

### Design Approval Gate

Additional approval required before Build phase:

```python
from carby_sprint.gate_enforcer import DesignGateEnforcer

enforcer = DesignGateEnforcer(sprint_id)
enforcer.request_approval(design_summary="Architecture complete")

# Later, in Build agent:
enforcer.check_approval()  # Raises if not approved
```

---

## Atomic Transactions

### Copy-on-Write Pattern

Ensures data integrity during concurrent access:

```python
from carby_sprint.transaction import atomic_sprint_update

with atomic_sprint_update(sprint_dir) as data:
    # Modifications happen in temp directory
    data["status"] = "running"
    # Atomic rename on success
```

### Properties

- **Isolation:** Changes isolated until commit
- **Consistency:** All-or-nothing updates
- **Durability:** Atomic rename ensures persistence
- **Rollback:** Temp directory cleaned on failure

---

## Health Monitoring

### Stale Lock Detection

Automatically detects and reports stuck locks:

```python
from carby_sprint.health_monitor import HealthMonitor

monitor = HealthMonitor()
status = monitor.check_sprint_health(sprint_id)
# Reports: healthy, stale_lock, hung_agent
```

### Hung Agent Detection

Monitors agent execution time:
- Warning after 80% of timeout
- Critical after 100% of timeout
- Auto-termination option (configurable)

---

## Security Checklist

When deploying Carby Studio:

- [ ] Secret key file has 0o600 permissions
- [ ] `.carby-sprints` directory has 0o700 permissions
- [ ] Audit logging is enabled
- [ ] Gate enforcement is set to `strict`
- [ ] Health monitoring is active
- [ ] Backup retention policy is configured
- [ ] No secrets in code or config files
- [ ] Dependencies are up to date

---

## Security Audit History

| Date | Auditor | Issues Found | Status |
|------|---------|--------------|--------|
| 2026-03-20 | Security Critic | 3 Critical, 2 High | ✅ Fixed |
| 2026-03-20 | Reliability Defender | 3 Critical, 2 High | ✅ Fixed |
| 2026-03-20 | Design Auditor | 3 Critical, 2 High | ✅ Fixed |
| 2026-03-20 | Final Validation | 94% confidence | ✅ Passed |

---

## Known Limitations

1. **Secret Key Rotation:** Manual only (auto-rotation planned for v4.0)
2. **Audit Log Tampering:** Logs are not cryptographically signed (planned for v4.0)
3. **Token Expiration:** Fixed 24-hour lifetime (configurable in v3.2)

---

## Best Practices

### For Users

1. **Keep secrets safe:** Never commit `.openclaw/secrets/`
2. **Regular audits:** Review gate logs for anomalies
3. **Principle of least privilege:** Limit sprint directory access
4. **Monitor health:** Check for stale locks regularly

### For Developers

1. **Validate all inputs:** Use Pydantic models
2. **Use atomic operations:** Prefer transaction context managers
3. **Log security events:** All gate actions should be logged
4. **Test security:** Include security tests in test suite

---

*Carby Studio v3.2.1 — Security Documentation*
