# Design Document

## Sprint Metadata
<!-- Auto-populated when using Sprint Framework -->
| Field | Value |
|-------|-------|
| **Sprint ID** | {{SPRINT_ID}} |
| **Gate** | {{CURRENT_GATE}} ({{GATE_NAME}}) |
| **Validation Token** | {{VALIDATION_TOKEN}} |
| **Risk Score** | {{RISK_SCORE}} |
| **Generated** | [timestamp] |

---

## Gate 2 Compliance Checklist
<!-- All items must be checked before passing Gate 2 -->
- [ ] All technical assumptions from Discover phase validated
- [ ] Technology stack choices documented with rationale
- [ ] Architecture addresses all requirements from requirements.md
- [ ] Work items generated for all design components
- [ ] Risk scores assigned to each work item
- [ ] Validation tokens issued for high-risk work items (risk ≥3.0)
- [ ] API contracts defined (if applicable)
- [ ] Data models specified
- [ ] Security architecture documented
- [ ] Deployment architecture specified

---

## 1. Architecture Overview

### 1.1 System Context
[High-level description of where this system fits]

### 1.2 Component Diagram

```mermaid
graph TB
    User[User] --> API[API Gateway]
    API --> Service[Service Layer]
    Service --> DB[(Database)]
    Service --> Cache[(Cache)]
    Service --> Queue[Message Queue]
```

### 1.3 Component List

| Component | Responsibility | Technology |
|-----------|----------------|------------|
| [Name] | [What it does] | [Tech choice] |

---

## 2. Technology Stack

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Language | [e.g., Python] | [3.12] | [Why] |
| Framework | [e.g., FastAPI] | [0.100+] | [Why] |
| Database | [e.g., PostgreSQL] | [15] | [Why] |
| Cache | [e.g., Redis] | [7] | [Why] |
| Message Queue | [e.g., RabbitMQ] | [3.12] | [Why] |
| Container | [e.g., Docker] | [24] | [Why] |
| Orchestration | [e.g., Kubernetes] | [1.28] | [Why] |

---

## 3. Data Model

### 3.1 Entity Relationship Diagram

```mermaid
erDiagram
    USER ||--o{ ORDER : places
    USER {
        uuid id
        string email
        string name
        timestamp created_at
    }
    ORDER {
        uuid id
        uuid user_id
        string status
        decimal total
        timestamp created_at
    }
```

### 3.2 Schema Definitions

```sql
-- Table: users
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Table: orders
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    total DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_orders_user_id ON orders(user_id);
CREATE INDEX idx_orders_status ON orders(status);
```

### 3.3 Migration Strategy
- Migration tool: [e.g., Alembic, Flyway]
- Naming: `YYYYMMDD_HHMMSS_description.sql`
- Rollback: Each migration has corresponding rollback

---

## 4. API Specification

### 4.1 Base URL
- Development: `http://localhost:8000`
- Staging: `https://api-staging.example.com`
- Production: `https://api.example.com`

### 4.2 Authentication
- Type: [JWT / OAuth 2.0 / API Key]
- Header: `Authorization: Bearer <token>`

### 4.3 OpenAPI Specification

```yaml
openapi: 3.0.0
info:
  title: [API Name]
  version: 1.0.0
  description: [Description]

servers:
  - url: https://api.example.com/v1
    description: Production

paths:
  /resource:
    get:
      summary: List resources
      parameters:
        - name: page
          in: query
          schema:
            type: integer
            default: 1
        - name: limit
          in: query
          schema:
            type: integer
            default: 20
      responses:
        '200':
          description: Success
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ResourceList'
    
    post:
      summary: Create resource
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ResourceCreate'
      responses:
        '201':
          description: Created
        '400':
          description: Bad Request

components:
  schemas:
    Resource:
      type: object
      properties:
        id:
          type: string
          format: uuid
        name:
          type: string
        created_at:
          type: string
          format: date-time
    
    ResourceList:
      type: object
      properties:
        items:
          type: array
          items:
            $ref: '#/components/schemas/Resource'
        total:
          type: integer
        page:
          type: integer
```

### 4.4 Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Invalid email format"
      }
    ]
  }
}
```

---

## 5. Component Details

### 5.1 [Component Name]

**Purpose**: [What it does]

**Interface**:
- Inputs: [What it receives]
- Outputs: [What it produces]

**Dependencies**:
- [Dependency 1]
- [Dependency 2]

**Error Handling**:
- [Strategy for errors]

---

## 6. Security Architecture

### 6.1 Authentication Flow

```mermaid
sequenceDiagram
    User->>Client: Login request
    Client->>AuthService: POST /auth/login
    AuthService->>Database: Verify credentials
    Database-->>AuthService: User data
    AuthService-->>Client: JWT token
    Client->>API: Request with Authorization header
    API->>API: Validate JWT
    API-->>Client: Protected resource
```

### 6.2 Authorization Model
- Type: [RBAC / ABAC]
- Roles: [List roles]
- Permissions: [List permissions]

### 6.3 Data Protection
- Encryption at rest: [Method]
- Encryption in transit: [TLS version]
- Secret management: [Tool]

---

## 7. Deployment Architecture

### 7.1 Infrastructure Diagram

```mermaid
graph TB
    LB[Load Balancer] --> API1[API Instance 1]
    LB --> API2[API Instance 2]
    API1 --> DB[(Primary DB)]
    API2 --> DB
    DB --> Replica[(Read Replica)]
```

### 7.2 Environment Configuration

| Environment | URL | Database | Scaling |
|-------------|-----|----------|---------|
| Development | localhost | SQLite | 1 instance |
| Staging | staging.example.com | RDS staging | 2 instances |
| Production | api.example.com | RDS production | Auto 2-10 |

### 7.3 CI/CD Pipeline

```mermaid
graph LR
    Commit --> Test[Unit Tests]
    Test --> Build[Build Image]
    Build --> Scan[Security Scan]
    Scan --> Deploy[Deploy to Staging]
    Deploy --> E2E[E2E Tests]
    E2E --> Prod[Deploy to Production]
```

---

## 8. Monitoring & Observability

### 8.1 Metrics

| Metric | Type | Alert Threshold |
|--------|------|-----------------|
| Request rate | Counter | - |
| Error rate | Gauge | > 1% |
| Latency p95 | Histogram | > 500ms |
| CPU usage | Gauge | > 80% |
| Memory usage | Gauge | > 85% |

### 8.2 Logging
- Level: INFO (production), DEBUG (development)
- Format: JSON
- Fields: timestamp, level, message, trace_id, user_id

### 8.3 Tracing
- Tool: [Jaeger / Zipkin / AWS X-Ray]
- Sampling: 10% production, 100% staging

---

## 9. Technical Assumption Validation Results
<!-- Document validation of assumptions from requirements.md -->
| Assumption | From Discover | Validation Method | Result | Notes |
|------------|---------------|-------------------|--------|-------|
| [Assumption 1] | [Ref] | [Spike/POC/Research] | [Pass/Fail] | [Notes] |

---

## 10. Work Items
<!-- Sprint-level planning artifacts - stored in .sprint/work_items/ -->
| ID | Title | Risk Score | Validation Token | Dependencies | Design Ref |
|----|-------|------------|------------------|--------------|------------|
| WI-001 | [Title] | X.X | [token or N/A] | [WI-XXX] | [Section] |

### Work Item Details

#### WI-001: [Title]
```json
{
  "id": "WI-001",
  "sprint_id": "{{SPRINT_ID}}",
  "title": "[Brief description]",
  "description": "[Detailed description]",
  "status": "planned",
  "risk_score": X.X,
  "validation_token": "[token or null]",
  "gate": 2,
  "dependencies": ["WI-XXX"],
  "github_issues": [],
  "estimated_hours": 4,
  "acceptance_criteria": [
    "Criterion 1",
    "Criterion 2"
  ],
  "design_reference": "design.md#X.Y",
  "created_at": "2026-03-19T10:00:00Z"
}
```

**Note**: Work items are sprint-level planning artifacts. GitHub issues will be created during Gate 3 (Build) for implementation tasks.

---

## 11. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| [Risk description] | High/Med/Low | High/Med/Low | [Strategy] |

---

## 12. Implementation Phases

| Phase | Scope | Dependencies | Effort | Deliverable | Work Items |
|-------|-------|--------------|--------|-------------|------------|
| 1 | [What] | [Prereqs] | [Time] | [Output] | [WI-001, WI-002] |
| 2 | [What] | [Prereqs] | [Time] | [Output] | [WI-003, WI-004] |
| 3 | [What] | [Prereqs] | [Time] | [Output] | [WI-005] |

---

## 13. Open Questions

| # | Question | Owner | Due Date | Blocking |
|---|----------|-------|----------|----------|
| 1 | [Question] | [Name] | [Date] | Yes/No |

---

## 14. Appendix

### 14.1 ADRs
- [ADR-001: Technology choice](adr/001-technology-choice.md)

### 14.2 References
- [Link to external docs]

### 14.3 Sprint Framework Notes
<!-- Internal notes for sprint tracking -->
- **Gate 2 Status**: [In Progress / Complete]
- **Validation Tokens Issued**: [Count]
- **High-Risk Work Items**: [Count] (risk ≥3.0)
- **Next Gate**: Gate 3 (Implementation) - Build agent will create GitHub issues from work items
- **Traceability**: Each work item will spawn 1+ GitHub issues during Build phase
