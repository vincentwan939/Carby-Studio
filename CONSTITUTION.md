# Carby Studio Constitution

**Version:** 1.0.0  
**Status:** Living Document  
**Last Updated:** 2026-03-23

---

## Core Principles

These are non-negotiable defaults for every Carby Studio project.

### 1. Telegram-First UI
- **Rule:** All user-facing features must work through Telegram first
- **Rationale:** Vincent lives in Telegram. If it doesn't work there, it doesn't exist.
- **Exception:** Admin/internal tools can use web UI if they have no user-facing component

### 2. SQLite for Local Data
- **Rule:** Default to SQLite for all local persistence
- **Rationale:** Zero setup, portable, sufficient for 99% of use cases
- **Exception:** Use PostgreSQL only when:
  - Concurrent writes > 100/sec sustained
  - Need full-text search with complex ranking
  - Geographic distribution required

### 3. Test-First for Critical Paths
- **Rule:** Write tests before code for:
  - Authentication/authorization flows
  - Data persistence operations
  - External API integrations
  - Financial calculations
- **Rationale:** These break silently and hurt when they do
- **Exception:** UI-only changes, one-off scripts, prototypes (< 1 week lifespan)

### 4. Python Default Stack
- **Rule:** New projects start with Python unless there's a compelling reason
- **Rationale:** Vincent's strongest language, fastest iteration
- **Exception:** Use other languages when:
  - Performance is critical (Go/Rust)
  - Existing codebase is Node.js
  - Specific library only available elsewhere

### 5. OpenClaw Integration
- **Rule:** All projects must integrate with OpenClaw sub-agent workflow
- **Rationale:** This is the force multiplier. Manual-only projects don't scale.
- **Requirement:** Include `.openclaw/` directory with agent instructions

### 6. Single Source of Truth
- **Rule:** Configuration in one place, environment-specific overrides only
- **Rationale:** Prevents "works on my machine" and config drift
- **Pattern:** `config.yaml` + `config.{env}.yaml` (optional override)

---

## Simplicity Gate

**Purpose:** Reject over-engineering before it happens

### Rejection Criteria

Reject any proposal that includes:

| Red Flag | Why | What To Do Instead |
|----------|-----|-------------------|
| Microservices for < 10K users | Network overhead kills you | Monolith with clean module boundaries |
| Kubernetes for < 5 services | Operational complexity | Docker Compose on single host |
| Custom auth instead of OAuth | Security is hard | Use Auth0, Firebase Auth, or similar |
| Event sourcing for simple CRUD | Cognitive overhead | Standard relational model |
| GraphQL for internal APIs | Overkill | REST with OpenAPI |
| Multiple databases | Sync nightmares | One database, proper indexing |
| Caching layer "just in case" | Premature optimization | Measure first, cache second |
| Message queue for < 10 req/sec | Unnecessary complexity | Direct API calls with retries |

### The "One Month" Rule

If the feature won't matter in one month, don't build it.

- Analytics dashboard? Use Metabase first.
- Admin panel? Use a CLI or direct DB access.
- Custom reporting? Export to CSV.

### Simplicity Checklist

Before adding complexity, answer:

- [ ] Can this be done with a simple script?
- [ ] Can this be a cron job instead of a service?
- [ ] Can this use an existing tool (SQLite, curl, jq)?
- [ ] Will this save time within 2 weeks?
- [ ] Can I explain this to a junior dev in 5 minutes?

**If 3+ are "yes", reject the complex solution.**

---

## Anti-Abstraction Gate

**Purpose:** Know when complexity IS justified

### Complexity Is Allowed When:

| Scenario | Complexity | Justification |
|----------|-----------|---------------|
| Financial transactions | ACID + audit logs | Can't lose money, must be auditable |
| User authentication | OAuth2 + MFA + session mgmt | Security is not optional |
| Rate limiting | Token bucket + distributed store | Abuse prevention is critical |
| Data encryption | Field-level encryption | Compliance (GDPR, etc.) |
| Multi-region deployment | Geo-routing + replication | Latency for global users |
| Circuit breakers | Failure isolation | Cascading failures kill services |

### The Abstraction Tax

Every abstraction has a cost. Pay it only when:

1. **The problem recurs** (3+ similar implementations)
2. **The abstraction is simpler** than the alternative
3. **The team understands it** (can debug at 2 AM)
4. **It has tests** (abstractions without tests become liabilities)

### Abstraction Checklist

Before creating an abstraction:

- [ ] Have I implemented this 3+ times?
- [ ] Will this save lines of code overall?
- [ ] Can I write a test that fails if the abstraction breaks?
- [ ] Is the abstraction simpler than copy-paste?
- [ ] Will someone else understand this in 6 months?

**If < 4 are "yes", don't abstract yet.**

---

## Quality Standards

### Code Quality

| Metric | Minimum | Target |
|--------|---------|--------|
| Test coverage | 70% | 85% |
| Type coverage | 80% | 95% |
| Lint errors | 0 | 0 |
| Cyclomatic complexity | < 15 | < 10 |
| Function length | < 50 lines | < 30 lines |

### Documentation

| Artifact | Required | Location |
|----------|----------|----------|
| README | Always | `README.md` |
| Setup instructions | Always | `README.md` or `docs/setup.md` |
| API docs | If has API | `docs/api.md` or auto-generated |
| Architecture decision | Major changes | `docs/adr/NNN-title.md` |
| Deployment guide | If deployed | `docs/deployment.md` |

### Security Baseline

| Requirement | Implementation |
|-------------|----------------|
| Secrets management | Bitwarden or environment variables |
| No secrets in code | Pre-commit hook |
| Dependency scanning | `pip-audit` or `npm audit` |
| Input validation | Pydantic or similar |
| SQL injection prevention | ORM or parameterized queries |
| XSS prevention | Auto-escaping templates |

### Operational Standards

| Requirement | Implementation |
|-------------|----------------|
| Health check endpoint | `/health` returning 200 |
| Structured logging | JSON format |
| Graceful shutdown | Handle SIGTERM |
| Configuration validation | Fail fast on bad config |
| Database migrations | Version controlled, reversible |

---

## Decision Framework

### When In Doubt

```
Simple > Complex
Working > Perfect
Shipped > Polished
Explicit > Clever
Boring > Novel
```

### The Carby Studio Way

1. **Start with SQLite** — You can always upgrade to PostgreSQL
2. **Start with sync code** — Add async only when profiling shows I/O bound
3. **Start with one file** — Split when it hurts, not before
4. **Start with no framework** — Add FastAPI/Django when the app demands it
5. **Start with no tests** — Add them when the code stabilizes (except critical paths)

### Escalation Path

| Situation | Action |
|-----------|--------|
| Unclear if complexity is justified | Open discussion in Telegram, tag Vincent |
| Security-related decision | Mandatory review, no exceptions |
| Breaking existing pattern | Document in ADR, get approval |
| Technical debt introduced | Create ticket, schedule within 2 sprints |

---

## Amendment Process

This constitution changes when:

1. A pattern proves itself over 3+ projects
2. A rule causes more pain than it prevents
3. Technology landscape shifts significantly

**To propose an amendment:**
- Create a PR with rationale
- Include examples of the problem
- Show the proposed change in practice
- Get Vincent's approval

---

## Quick Reference Card

```
✅ DO:
- SQLite for most projects
- Telegram-first UI
- Python by default
- Tests for auth/payments/data
- Simple over clever

❌ DON'T:
- Microservices prematurely
- Multiple databases
- Custom auth
- Caching "just in case"
- Abstractions without 3+ uses

⚠️ ASK FIRST:
- New language/framework
- External service dependency
- Breaking