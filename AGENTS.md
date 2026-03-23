# Carby Studio Agents

Agent definitions and configurations for the 5-stage SDLC pipeline.

---

## Overview

Carby Studio orchestrates five specialized AI agents that work sequentially through the software development lifecycle:

```
Discover → Design → Build → Verify → Deliver
   ↓         ↓        ↓        ↓        ↓
 options   specs   tasks   review   deploy
```

Each agent validates the previous stage's output (maker-checker pattern) before proceeding.

---

## Agent Summary

| Agent | Purpose | Model | Verifies | Output |
|-------|---------|-------|----------|--------|
| **Discover** | Problem understanding, option generation | Kimi K2.5 | — | requirements.md |
| **Design** | Architecture, API contracts, data models | GLM-5 | Discover | design.md |
| **Build** | Implementation to spec | Qwen Coder Plus | Design | Code, PR |
| **Verify** | Testing, review, security checks | Qwen Coder Plus | Build | Review report |
| **Deliver** | Deployment, documentation, handoff | Kimi K2.5 | Verify | Live service |

---

## Model Assignments

### Default Models

| Agent | Model | Provider | Context Window |
|-------|-------|----------|----------------|
| Discover | `bailian/kimi-k2.5` | Alibaba | 256K |
| Design | `bailian/glm-5` | Zhipu AI | 128K |
| Build | `bailian/qwen3-coder-plus` | Alibaba | 128K |
| Verify | `bailian/qwen3-coder-plus` | Alibaba | 128K |
| Deliver | `bailian/kimi-k2.5` | Alibaba | 256K |

### Model Configuration

Configure via environment variables:

```bash
export CARBY_MODEL_DISCOVER="bailian/kimi-k2.5"
export CARBY_MODEL_DESIGN="bailian/glm-5"
export CARBY_MODEL_BUILD="bailian/qwen3-coder-plus"
export CARBY_MODEL_VERIFY="bailian/qwen3-coder-plus"
export CARBY_MODEL_DELIVER="bailian/kimi-k2.5"
```

Or edit `scripts/carby-studio` to change defaults.

### Thinking Mode

| Agent | Default | Rationale |
|-------|---------|-----------|
| Discover | off | Fast iteration, human in loop |
| Design | on | Complex trade-offs need reasoning |
| Build | off | Code generation is execution-focused |
| Verify | on | Security reviews need deep analysis |
| Deliver | off | Deployment is execution-focused |

---

## Agent Capabilities

### Discover Agent

**Purpose:** Understand the problem space and generate solution options.

**Capabilities:**
- Problem analysis and domain identification
- Generation of 3 distinct solution options (MVP, Balanced, Comprehensive)
- Value/effort/risk scoring for each option
- Requirements document generation
- Human checkpoint for option selection

**Input:** User's natural language description of what they want to build.

**Output:**
- 3 solution options with scoring
- requirements.md (after user selection)
- Verification checklist for Design agent

**Key Behaviors:**
- MUST stop and wait for user selection (A, B, or C)
- Never generates requirements without explicit user choice
- Asks clarifying questions when needed

---

### Design Agent

**Purpose:** Transform requirements into comprehensive technical specifications.

**Capabilities:**
- Requirements validation
- System architecture design
- Technology stack selection
- API contract design (OpenAPI/Swagger)
- Data model design (ER diagrams, schemas)
- Security architecture
- Deployment architecture
- Risk mitigation planning

**Input:**
- requirements.md from Discover stage
- Verification checklist

**Output:**
- design.md with complete specification
- API contracts (if applicable)
- Data models (if applicable)
- ADRs for significant trade-offs

**Key Behaviors:**
- Validates requirements before designing
- Escalates to `/discuss` if requirements are ambiguous
- Requests design approval before proceeding (sequential mode)

---

### Build Agent

**Purpose:** Implement the system according to design specifications.

**Capabilities:**
- Design validation
- Task decomposition
- Test-driven development (TDD) in sequential mode
- Code implementation
- GitHub issue creation
- Feature branch management
- Pull request creation
- Task tracking

**Input:**
- design.md from Design stage
- requirements.md for reference
- Verification checklist

**Output:**
- GitHub Issues (one per task)
- Feature branches
- Working code implementation
- Pull Request for review

**Key Behaviors:**
- Verifies design approval before starting (sequential mode)
- Follows RED-GREEN-REFACTOR TDD cycle when required
- Creates focused, reviewable PRs
- References design.md sections in commits

---

### Verify Agent

**Purpose:** Critically review implementation quality, security, and compliance.

**Capabilities:**
- Spec compliance review (binary PASS/FAIL)
- Code quality review (APPROVE/CONDITIONAL/REQUEST CHANGES)
- Security vulnerability scanning
- Test coverage verification
- Performance review
- Documentation review
- Line-by-line PR feedback

**Two-Stage Verification:**

| Stage | Purpose | Decision |
|-------|---------|----------|
| Stage 1 | Spec compliance | PASS/FAIL (binary gate) |
| Stage 2 | Code quality | APPROVE/CONDITIONAL/REQUEST CHANGES |

**Stage 1 Failure Conditions (Hard Stop):**
- Any critical security vulnerability
- Missing required features from design.md
- API contracts not matching specification
- Data models deviating from design
- Test coverage below 80%
- Tests failing

**Stage 2 Focus Areas:**
- Code quality and maintainability
- Security hardening
- Documentation completeness
- Performance optimization

**Input:**
- Pull Request from Build stage
- design.md specification
- requirements.md original requirements

**Output:**
- Stage 1 report (PASS/FAIL)
- Stage 2 report (APPROVE/CONDITIONAL/REQUEST CHANGES)
- Issue comments with feedback
- Security scan results

---

### Deliver Agent

**Purpose:** Complete deployment, documentation, and handoff.

**Capabilities:**
- Pre-merge verification
- PR merge to main branch
- Deployment execution (Docker, cloud, serverless)
- Post-deployment verification
- Changelog updates
- README updates
- Runbook creation
- Monitoring setup
- Alert configuration
- Stakeholder notification
- Artifact archival

**Input:**
- Approved Pull Request from Verify stage
- Review report
- design.md deployment specifications

**Output:**
- Merged code in main branch
- Deployed service in target environment
- Documentation (runbooks, changelogs)
- Monitoring and alerting configured
- Handoff package for maintenance

**Key Behaviors:**
- Verifies all checks pass before merge
- Follows deployment architecture from design.md
- Creates comprehensive runbooks
- Notifies stakeholders on completion

---

## Handoff Protocols

### Standard Handoff Format

Each agent produces:

1. **Artifacts** — Files for the next agent
2. **Verification Checklist** — Explicit validation criteria
3. **Escalation Path** — When to involve humans

### Discover → Design

```yaml
artifacts:
  - requirements.md
verification_checklist:
  - "All functional requirements have clear acceptance criteria"
  - "Non-functional requirements have measurable targets"
  - "Constraints are explicit and justified"
  - "Out-of-scope items are documented"
escalation_path: "/discuss if requirements conflict or are ambiguous"
```

### Design → Build

```yaml
artifacts:
  - design.md
  - api-contracts.yaml (if applicable)
  - data-models.sql (if applicable)
verification_checklist:
  - "All requirements have corresponding design elements"
  - "API contracts are complete and consistent"
  - "Data models cover all entities in requirements"
  - "Security controls address all NFRs"
  - "Implementation phases are sequenced logically"
escalation_path: "/discuss if design conflicts with requirements"
```

### Build → Verify

```yaml
artifacts:
  - Pull Request
  - Feature branch
  - tests/
verification_checklist:
  - "All