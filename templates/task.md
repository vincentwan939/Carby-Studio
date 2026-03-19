# Task Document

## Sprint Metadata
<!-- Auto-populated when using Sprint Framework -->
| Field | Value |
|-------|-------|
| **Sprint ID** | {{SPRINT_ID}} |
| **Gate** | {{CURRENT_GATE}} ({{GATE_NAME}}) |
| **Work Item** | [WI-XXX] |
| **Validation Token** | {{VALIDATION_TOKEN}} |
| **Risk Score** | {{RISK_SCORE}} |
| **Created** | [timestamp] |

---

## Work Item Format

This document tracks a single work item within the sprint framework. Work items are sprint-level planning artifacts that exist in `.sprint/work_items/` and may spawn multiple GitHub issues during the Build phase.

### Work Item vs GitHub Issue

| Aspect | Work Item | GitHub Issue |
|--------|-----------|--------------|
| **Level** | Sprint planning | Implementation |
| **Location** | `.sprint/work_items/` | GitHub repository |
| **Created** | Gate 2 (Design) | Gate 3 (Build) |
| **Scope** | Feature/component | Specific task |
| **Example** | "Implement authentication" | "Create login endpoint" |

**Relationship**: One work item → Many GitHub issues

---

## Work Item Specification

### Basic Information
- **ID**: WI-XXX
- **Sprint**: {{SPRINT_ID}}
- **Title**: [Brief description]
- **Status**: planned / in_progress / completed / blocked
- **Gate**: {{CURRENT_GATE}}

### Risk Assessment
- **Risk Score**: X.X / 5.0
- **Validation Token**: [token-id or "Not Required"]
- **Risk Factors**:
  - [ ] Technical uncertainty
  - [ ] Integration complexity
  - [ ] Performance requirements
  - [ ] Security implications

### Dependencies
- **Blocks**: [WI-XXX, WI-YYY]
- **Blocked By**: [WI-ZZZ]
- **External Dependencies**: [APIs, services, etc.]

### Estimation
- **Estimated Hours**: [X]
- **Story Points**: [X]
- **Priority**: Critical / High / Medium / Low

---

## Description

### Overview
[Detailed description of what this work item encompasses]

### Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

### Design Reference
- **Document**: design.md
- **Section**: [X.Y Component Name]
- **API Spec**: [Link to OpenAPI/Swagger]

---

## GitHub Issues

<!-- Populated during Gate 3 (Build) -->
| Issue # | Title | Status | Assignee |
|---------|-------|--------|----------|
| #1 | [Issue title] | Open/Closed | [Name] |
| #2 | [Issue title] | Open/Closed | [Name] |

### Issue Creation Template

When creating GitHub issues from this work item:

```markdown
## Description
[Task description]

## Parent Work Item
- **Work Item**: WI-XXX
- **Sprint**: {{SPRINT_ID}}
- **Risk Score**: X.X
- **Validation Token**: [if applicable]

## Design Reference
See design.md section [X.Y]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Estimated Effort
[X] hours
```

---

## Implementation Notes

### Files to Create
- [ ] `src/module/file.py`
- [ ] `tests/test_file.py`

### Files to Modify
- [ ] `src/existing.py`

### Technical Notes
- [Note 1]
- [Note 2]

---

## Validation

### Pre-Implementation Checklist
- [ ] Design approved
- [ ] Risk assessment complete
- [ ] Validation token obtained (if risk ≥3.0)
- [ ] Dependencies resolved

### Post-Implementation Checklist
- [ ] Code implemented
- [ ] Tests written and passing
- [ ] Documentation updated
- [ ] Code review completed
- [ ] GitHub issues closed

---

## Sprint Framework Integration

### Gate Compliance
| Gate | Status | Date | Validator |
|------|--------|------|-----------|
| Gate 2 (Design) | [✓/✗] | [Date] | [Name] |
| Gate 3 (Build) | [✓/✗] | [Date] | [Name] |
| Gate 4 (Validation) | [✓/✗] | [Date] | [Name] |

### Traceability
- **Requirements**: [FR-001, FR-002]
- **Design Section**: [Section X.Y]
- **Test Cases**: [TC-001, TC-002]

---

## History

| Date | Event | User |
|------|-------|------|
| [Date] | Work item created | [Name] |
| [Date] | Status changed to in_progress | [Name] |
| [Date] | GitHub issue #1 created | [Name] |
| [Date] | Status changed to completed | [Name] |

---

## Appendix

### Sprint Framework Notes
- This work item is part of sprint {{SPRINT_ID}}
- Work items are stored in `.sprint/work_items/WI-XXX.json`
- GitHub issues are created during Gate 3 (Build)
- Validation tokens are required for work items with risk score ≥3.0
- All work items must pass Gate 4 (Validation) before sprint completion
