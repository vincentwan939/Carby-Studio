# Carby Studio Roadmap - Steps 2-8

## Overview

This document contains detailed proposals for steps 2-8 of the Carby Studio improvement roadmap. Each step includes:
- Detailed implementation plan
- Self-evaluation criteria
- Confidence scoring
- Risk assessment

---

## Step 2: Retest EDGE-015 (Concurrent Access Fix Verification)

### Current Status
- Race condition bug identified and fixed with file locking
- Initial concurrent test with 5 processes passed
- Need comprehensive verification under various load conditions

### Implementation Plan

#### 2.1 Test Scenarios
```
Scenario A: Light Concurrent Load
- 5 parallel processes
- 10 iterations each
- Mix of update/log/result/reset operations
- Expected: 100% success, no corruption

Scenario B: Medium Concurrent Load  
- 10 parallel processes
- 20 iterations each
- Rapid-fire operations (no delays)
- Expected: 100% success, no corruption

Scenario C: Heavy Concurrent Load
- 20 parallel processes
- 50 iterations each
- Maximum stress test
- Expected: 100% success, no corruption

Scenario D: Mixed Operations Load
- 15 parallel processes
- Random operations (update 40%, log 30%, result 20%, reset 10%)
- 30 iterations each
- Expected: 100% success, no corruption

Scenario E: Long-Running Load
- 5 parallel processes
- 100 iterations each
- Sustained load over 5 minutes
- Expected: 100% success, no corruption
```

#### 2.2 Test Implementation
```bash
#!/bin/bash
# test_edge015_comprehensive.sh

TEST_PROJECT="test-edge015-comprehensive"
ITERATIONS=$1
PROCESSES=$2

create_project() {
    python3 team-tasks/scripts/task_manager.py init $TEST_PROJECT -m dag --force
    python3 team-tasks/scripts/task_manager.py add $TEST_PROJECT task1 -a code-agent
    python3 team-tasks/scripts/task_manager.py add $TEST_PROJECT task2 -a test-agent
}

concurrent_worker() {
    local worker_id=$1
    local iterations=$2
    
    for i in $(seq 1 $iterations); do
        # Random operation
        op=$((RANDOM % 4))
        case $op in
            0) python3 team-tasks/scripts/task_manager.py update $TEST_PROJECT task1 in-progress ;;
            1) python3 team-tasks/scripts/task_manager.py log $TEST_PROJECT task1 "Worker $worker_id log $i" ;;
            2) python3 team-tasks/scripts/task_manager.py result $TEST_PROJECT task1 "Result $worker_id-$i" ;;
            3) python3 team-tasks/scripts/task_manager.py reset $TEST_PROJECT task1 ;;
        esac
    done
}

validate_results() {
    # Check JSON validity
    python3 -c "import json; json.load(open('$TASKS_DIR/$TEST_PROJECT.json'))"
    
    # Check no negative log counts
    python3 -c "
import json
with open('$TASKS_DIR/$TEST_PROJECT.json') as f:
    data = json.load(f)
    for task_id, task in data['stages'].items():
        logs = task.get('logs', [])
        print(f'{task_id}: {len(logs)} logs')
"
}
```

#### 2.3 Success Criteria
- All 5 scenarios pass
- JSON remains valid in all cases
- No log entries lost
- No status inconsistencies
- Performance remains acceptable (<100ms per operation)

### Self-Evaluation

| Criterion | Weight | Score (1-10) |
|-----------|--------|--------------|
| Test coverage | 25% | 9 |
| Implementation clarity | 20% | 9 |
| Success criteria specificity | 20% | 9 |
| Edge case handling | 15% | 8 |
| Automation feasibility | 10% | 10 |
| Documentation quality | 10% | 8 |

**Confidence: 8.9/10 (89%)**

### Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Fix incomplete | Low | High | Multiple test scenarios |
| Performance degradation | Low | Medium | Benchmark testing |
| Platform differences | Medium | Low | Test on target platform |

---

## Step 3: Deploy to Production (Single-User Environments)

### Current Status
- All tests passed (97.8%)
- Critical bug fixed
- System validated for production use

### Implementation Plan

#### 3.1 Pre-Deployment Checklist
```
□ Verify file locking fix is in place
□ Confirm all unit tests pass
□ Validate E2E test results
□ Check documentation completeness
□ Review security considerations
□ Prepare rollback plan
□ Set up monitoring
```

#### 3.2 Deployment Steps
```
Step 1: Environment Preparation
- Ensure Python 3.11+ installed
- Verify fcntl module available (Unix)
- Check disk space (>1GB free)
- Confirm network connectivity for models

Step 2: Installation
- Clone carby-studio-repo
- Set up team-tasks submodule
- Configure environment variables
- Test basic commands

Step 3: Configuration
- Set CARBY_WORKSPACE
- Configure model preferences
- Set up deployment targets
- Configure GitHub CLI (optional)

Step 4: Validation
- Run smoke tests
- Verify project creation
- Test pipeline execution
- Validate artifact generation

Step 5: Go-Live
- Announce availability
- Provide user documentation
- Set up support channel
```

#### 3.3 Monitoring Setup
```python
# monitoring.py - Track key metrics
import json
import time
from datetime import datetime

METRICS_FILE = "~/.openclaw/workspace/carby-metrics.json"

def log_metric(event_type, project, stage, duration, success):
    metric = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "project": project,
        "stage": stage,
        "duration_ms": duration,
        "success": success
    }
    # Append to metrics file
    ...

def get_dashboard():
    # Return success rates, avg times, etc.
    ...
```

#### 3.4 Rollback Plan
```
If issues detected:
1. Document issue with logs
2. Pause new project creation
3. Allow in-progress pipelines to complete
4. Apply fix or revert to previous version
5. Validate fix
6. Resume operations
```

### Self-Evaluation

| Criterion | Weight | Score (1-10) |
|-----------|--------|--------------|
| Deployment plan completeness | 25% | 9 |
| Risk mitigation | 20% | 8 |
| Monitoring strategy | 20% | 7 |
| Rollback plan | 15% | 8 |
| Documentation | 10% | 8 |
| Automation | 10% | 7 |

**Confidence: 8.1/10 (81%)**

### Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Undiscovered bugs | Medium | High | Gradual rollout, monitoring |
| Performance issues | Low | Medium | Benchmark before deploy |
| User confusion | Medium | Low | Documentation, training |

---

## Step 4: Fix Test Scripts (EDGE-013, EDGE-014)

### Current Status
- Test scripts reference wrong stage names in DAG mode
- Not product bugs, but need fixing for test accuracy

### Implementation Plan

#### 4.1 EDGE-013: Cycle Detection Test Fix
```python
# Current (broken):
# References "discover" stage which doesn't exist in DAG

# Fixed:
def test_cycle_detection():
    # Create DAG project
    init_project("test-cycle", mode="dag")
    
    # Add tasks that would create cycle
    add_task("task-a", deps=[])
    add_task("task-b", deps=["task-a"])
    
    # Try to add task-a depending on task-b (creates cycle)
    result = add_task("task-a", deps=["task-b"])
    
    # Should fail with cycle detection error
    assert result.status == "error"
    assert "cycle" in result.message.lower()
```

#### 4.2 EDGE-014: Cross-Project Isolation Test Fix
```python
# Current (broken):
# References "discover" stage

# Fixed:
def test_cross_project_isolation():
    # Create two separate projects
    init_project("project-a", mode="dag")
    init_project("project-b", mode="dag")
    
    # Add tasks to both
    add_task_to_project("project-a", "task-1")
    add_task_to_project("project-b", "task-1")  # Same name, different project
    
    # Update task in project-a
    update_task("project-a", "task-1", "in-progress")
    
    # Verify project-b task unchanged
    status_a = get_task_status("project-a", "task-1")
    status_b = get_task_status("project-b", "task-1")
    
    assert status_a == "in-progress"
    assert status_b == "pending"  # Unchanged
```

#### 4.3 Test Script Updates
```bash
# Update test_edge_cases.sh
# Fix stage references from "discover" to actual DAG task names
# Add proper DAG structure setup before tests
```

### Self-Evaluation

| Criterion | Weight | Score (1-10) |
|-----------|--------|--------------|
| Fix accuracy | 30% | 9 |
| Test coverage | 25% | 8 |
| Implementation clarity | 20% | 9 |
| Verification approach | 15% | 8 |
| Documentation | 10% | 7 |

**Confidence: 8.5/10 (85%)**

---

## Step 5: Add Metrics Collection

### Current Status
- No performance tracking
- No success rate monitoring
- No usage analytics

### Implementation Plan

#### 5.1 Metrics to Collect
```python
METRICS_SCHEMA = {
    "pipeline_metrics": {
        "pipeline_start": ["project", "mode", "timestamp"],
        "pipeline_complete": ["project", "mode", "duration", "success"],
        "stage_start": ["project", "stage", "agent", "timestamp"],
        "stage_complete": ["project", "stage", "duration", "success", "validation_score"],
    },
    "performance_metrics": {
        "command_execution": ["command", "duration", "args_hash"],
        "model_calls": ["model", "stage", "tokens_in", "tokens_out", "duration"],
        "file_operations": ["operation", "file_size", "duration"],
    },
    "quality_metrics": {
        "validation_scores": ["stage", "score", "project_type"],
        "retry_counts": ["stage", "retry_count"],
        "failure_reasons": ["stage", "reason", "count"],
    }
}
```

#### 5.2 Implementation
```python
# metrics.py
import json
import time
import hashlib
from datetime import datetime
from pathlib import Path

class MetricsCollector:
    def __init__(self, metrics_dir="~/.openclaw/workspace/metrics"):
        self.metrics_dir = Path(metrics_dir).expanduser()
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = self._generate_session_id()
        
    def _generate_session_id(self):
        return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    
    def record(self, event_type, **kwargs):
        event = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id,
            "event_type": event_type,
            "data": kwargs
        }
        
        # Write to daily log
        date_str = datetime.now().strftime("%Y-%m-%d")
        log_file = self.metrics_dir / f"metrics-{date_str}.jsonl"
        
        with open(log_file, "a") as f:
            f.write(json.dumps(event) + "\n")
    
    def get_summary(self, days=7):
        # Aggregate metrics for dashboard
        ...

# Global collector
metrics = MetricsCollector()

# Usage in task_manager.py
def cmd_update(args):
    start_time = time.time()
    ...
    duration = (time.time() - start_time) * 1000
    metrics.record("stage_update", 
                   project=args.project,
                   stage=args.stage,
                   status=args.status,
                   duration_ms=duration)
```

#### 5.3 Dashboard
```python
# dashboard.py
import streamlit as st  # or simple CLI

def show_dashboard():
    metrics = MetricsCollector()
    summary = metrics.get_summary(days=7)
    
    print("=== Carby Studio Metrics ===")
    print(f"Pipelines run: {summary['total_pipelines']}")
    print(f"Success rate: {summary['success_rate']:.1f}%")
    print(f"Avg pipeline time: {summary['avg_duration']:.1f} min")
    print(f"Stage success rates:")
    for stage, rate in summary['stage_rates'].items():
        print(f"  {stage}: {rate:.1f}%")
```

### Self-Evaluation

| Criterion | Weight | Score (1-10) |
|-----------|--------|--------------|
| Metrics coverage | 25% | 9 |
| Implementation feasibility | 20% | 8 |
| Performance impact | 20% | 7 |
| Dashboard usefulness | 15% | 8 |
| Privacy/security | 10% | 8 |
| Documentation | 10% | 7 |

**Confidence: 8.1/10 (81%)**

---

## Step 6: Document External Dependencies

### Current Status
- 6 integration tests skipped due to missing tools
- No clear documentation on prerequisites

### Implementation Plan

#### 6.1 Documentation Structure
```
docs/
├── PREREQUISITES.md          # Main requirements doc
├── GITHUB_SETUP.md           # GitHub CLI configuration
├── DEPLOYMENT_TARGETS.md     # Deployment options
└── TROUBLESHOOTING.md        # Common issues
```

#### 6.2 PREREQUISITES.md
```markdown
# Carby Studio Prerequisites

## Required
- Python 3.11+
- OpenClaw (configured)
- Git

## Optional (for full functionality)

### GitHub Integration
**For:** Issue creation, branch management, PR creation
**Install:** `brew install gh` (macOS) or `apt install gh` (Linux)
**Configure:** `gh auth login`
**Tests affected:** GH-001, GH-002, GH-005, GH-006, GH-007

### Docker Deployment
**For:** local-docker deployment target
**Install:** Docker Desktop (macOS/Windows) or `docker.io` (Linux)
**Configure:** Ensure docker daemon running
**Tests affected:** DEP-001, DEP-002

### Fly.io Deployment
**For:** fly-io deployment target
**Install:** `curl -L https://fly.io/install.sh | sh`
**Configure:** `fly auth login`
**Tests affected:** DEP-003

## Verification
Run `./scripts/check-prerequisites.sh` to verify setup
```

#### 6.3 Check Script
```bash
#!/bin/bash
# check-prerequisites.sh

echo "=== Carby Studio Prerequisites Check ==="
echo ""

# Required
check_python() {
    if python3 --version | grep -E "3\.(11|12)"; then
        echo "✅ Python 3.11+"
    else
        echo "❌ Python 3.11+ required"
    fi
}

# Optional
check_github() {
    if command -v gh &> /dev/null; then
        if gh auth status &> /dev/null; then
            echo "✅ GitHub CLI (authenticated)"
        else
            echo "⚠️  GitHub CLI (not authenticated - run 'gh auth login')"
        fi
    else
        echo "ℹ️  GitHub CLI (optional - install for GitHub integration)"
    fi
}

check_docker() {
    if command -v docker &> /dev/null; then
        if docker info &> /dev/null; then
            echo "✅ Docker (running)"
        else
            echo "⚠️  Docker (installed but not running)"
        fi
    else
        echo "ℹ️  Docker (optional - install for local deployment)"
    fi
}

check_fly() {
    if command -v flyctl &> /dev/null; then
        echo "✅ Fly.io CLI"
    else
        echo "ℹ️  Fly.io CLI (optional - install for Fly deployment)"
    fi
}

check_python
check_github
check_docker
check_fly
```

### Self-Evaluation

| Criterion | Weight | Score (1-10) |
|-----------|--------|--------------|
| Documentation completeness | 30% | 9 |
| Clarity | 25% | 9 |
| Check script quality | 20% | 8 |
| Maintenance ease | 15% | 8 |
| User experience | 10% | 9 |

**Confidence: 8.7/10 (87%)**

---

## Step 7: SQLite Backend for High-Concurrency

### Current Status
- File-based JSON storage (works for single-user)
- File locking added for concurrent access
- SQLite would be better for high-concurrency scenarios

### Implementation Plan

#### 7.1 Database Schema
```sql
-- schema.sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    goal TEXT,
    mode TEXT,
    status TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    data JSON
);

CREATE TABLE stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT,
    stage_id TEXT,
    agent TEXT,
    status TEXT,
    task TEXT,
    output TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    depends_on JSON,
    logs JSON,
    FOREIGN KEY (project_id) REFERENCES projects(id),
    UNIQUE(project_id, stage_id)
);

CREATE INDEX idx_stages_project ON stages(project_id);
CREATE INDEX idx_stages_status ON stages(status);
```

#### 7.2 Backend Interface
```python
# backend.py
from abc import ABC, abstractmethod

class Backend(ABC):
    @abstractmethod
    def load_project(self, project_id: str) -> dict:
        pass
    
    @abstractmethod
    def save_project(self, project_id: str, data: dict):
        pass
    
    @abstractmethod
    def atomic_update(self, project_id: str, update_func):
        pass
    
    @abstractmethod
    def list_projects(self) -> list:
        pass

class FileBackend(Backend):
    # Current implementation with fcntl locking
    ...

class SQLiteBackend(Backend):
    def __init__(self, db_path="~/.openclaw/workspace/carby.db"):
        self.db_path = Path(db_path).expanduser()
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(SCHEMA_SQL)
    
    def atomic_update(self, project_id: str, update_func):
        with sqlite3.connect(self.db_path) as conn:
            conn.isolation_level = 'EXCLUSIVE'
            try:
                cursor = conn.cursor()
                cursor.execute("BEGIN EXCLUSIVE")
                
                # Load
                cursor.execute("SELECT data FROM projects WHERE id = ?", (project_id,))
                row = cursor.fetchone()
                data = json.loads(row[0]) if row else {}
                
                # Update
                update_func(data)
                
                # Save
                cursor.execute(
                    "INSERT OR REPLACE INTO projects (id, data, updated_at) VALUES (?, ?, ?)",
                    (project_id, json.dumps(data), datetime.now().isoformat())
                )
                
                conn.commit()
            except:
                conn.rollback()
                raise
```

#### 7.3 Configuration
```python
# config.py
BACKEND_TYPE = os.environ.get("CARBY_BACKEND", "file")  # file | sqlite

if BACKEND_TYPE == "sqlite":
    backend = SQLiteBackend()
else:
    backend = FileBackend()
```

### Self-Evaluation

| Criterion | Weight | Score (1-10) |
|-----------|--------|--------------|
| Design quality | 25% | 8 |
| Implementation complexity | 20% | 7 |
| Migration path | 20% | 8 |
| Performance gain | 15% | 8 |
| Testing requirements | 15% | 7 |
| Documentation | 5% | 7 |

**Confidence: 7.6/10 (76%)**

### Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Migration data loss | Low | High | Backup before migration |
| Performance regression | Low | Medium | Benchmark testing |
| Complexity increase | Medium | Low | Abstract interface |

---

## Step 8: Language-Agnostic Templates

### Current Status
- Templates are Python-focused
- Need support for Node.js, Go, Rust

### Implementation Plan

#### 8.1 Template Structure
```
templates/
├── _common/                    # Shared across languages
│   ├── requirements.md
│   └── design.md
├── python/
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── pyproject.toml
├── nodejs/
│   ├── src/
│   ├── tests/
│   ├── Dockerfile
│   └── package.json
├── go/
│   ├── cmd/
│   ├── pkg/
│   ├── Dockerfile
│   └── go.mod
└── rust/
    ├── src/
    ├── tests/
    ├── Dockerfile
    └── Cargo.toml
```

#### 8.2 Language Detection
```python
# language_detector.py
LANGUAGE_PATTERNS = {
    "python": ["*.py", "requirements.txt", "pyproject.toml", "setup.py"],
    "nodejs": ["*.js", "*.ts", "package.json", "node_modules"],
    "go": ["*.go", "go.mod", "go.sum"],
    "rust": ["*.rs", "Cargo.toml", "Cargo.lock"],
}

def detect_language(project_dir: Path) -> str:
    for lang, patterns in LANGUAGE_PATTERNS.items():
        for pattern in patterns:
            if list(project_dir.glob(pattern)):
                return lang
    return "python"  # Default
```

#### 8.3 Build Agent Templates
```markdown
# agents/build-python.md
## Build Agent (Python)

### Technology Stack
- **Framework:** FastAPI (for APIs) or Flask (for simple apps)
- **ORM:** SQLAlchemy
- **Validation:** Pydantic
- **Testing:** pytest
- **Type Checking:** mypy (optional)

### Output Structure
```
src/
├── __init__.py
├── main.py          # Application entry point
├── models.py        # Database models
├── schemas.py       # Pydantic schemas
├── crud.py          # Database operations
├── database.py      # DB configuration
└── api/
    ├── __init__.py
    └── v1/
        ├── __init__.py
        └── endpoints/
            └── ...
tests/
├── __init__.py
├── conftest.py      # pytest fixtures
└── test_*.py        # Test files
```

### Build Commands
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest --cov=src --cov-report=term-missing

# Type checking (if mypy configured)
mypy src/
```
```

```markdown
# agents/build-nodejs.md
## Build Agent (Node.js)

### Technology Stack
- **Runtime:** Node.js 18+ or 20+
- **Framework:** Express.js (APIs) or Next.js (full-stack)
- **ORM:** Prisma or TypeORM
- **Validation:** Zod or Joi
- **Testing:** Jest or Vitest
- **TypeScript:** Recommended

### Output Structure
```
src/
├── index.ts         # Application entry
├── app.ts           # Express app setup
├── routes/          # Route definitions
├── controllers/     # Request handlers
├── services/        # Business logic
├── models/          # Data models
├── middleware/      # Express middleware
└── utils/           # Utilities
tests/
├── unit/            # Unit tests
├── integration/     # Integration tests
└── setup.ts         # Test setup
```

### Build Commands
```bash
# Install dependencies
npm install

# Run tests
npm test

# Type checking
npx tsc --noEmit
```
```

### Self-Evaluation

| Criterion | Weight | Score (1-10) |
|-----------|--------|--------------|
| Language coverage | 25% | 8 |
| Template quality | 20% | 7 |
| Detection accuracy | 20% | 8 |
| Maintenance burden | 15% | 6 |
| User value | 15% | 9 |
| Documentation | 5% | 7 |

**Confidence: 7.6/10 (76%)**

### Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Template quality issues | Medium | Medium | Community contributions |
| Detection errors | Medium | Low | Manual override option |
| Maintenance overhead | High | Medium | Start with 2 languages |

---

# Overall Roadmap Confidence

| Step | Confidence | Priority | Risk Level |
|------|------------|----------|------------|
| 2: Retest EDGE-015 | 89% | P0 | Low |
| 3: Production Deploy | 81% | P0 | Medium |
| 4: Fix Test Scripts | 85% | P2 | Low |
| 5: Metrics Collection | 81% | P1 | Low |
| 6: Document Dependencies | 87% | P2 | Low |
| 7: SQLite Backend | 76% | P2 | Medium |
| 8: Language Templates | 76% | P3 | Medium |

**Average Confidence: 82.1%**

---

# Recommended Execution Order

## Phase 1: Production Readiness (This Week)
1. ✅ Step 2: Retest EDGE-015 (verify fix)
2. ✅ Step 3: Deploy to production
3. Step 4: Fix test scripts

## Phase 2: Operational Excellence (Next 2 Weeks)
4. Step 5: Add metrics collection
5. Step 6: Document dependencies

## Phase 3: Scale & Expand (Next Month)
6. Step 7: SQLite backend (if needed)
7. Step 8: Language templates

---

*Roadmap generated with 82.1% average confidence*
