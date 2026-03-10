# Carby Studio Bot — End-to-End Testing Plan
## Critical Self-Evaluation Framework

---

## Executive Summary

This document establishes a rigorous end-to-end testing framework for the Carby Studio Telegram Bot. Each test scenario includes:
- **Preconditions**: Required setup state
- **Test Steps**: Exact user actions
- **Expected Results**: Success criteria
- **Failure Modes**: What could go wrong
- **Self-Evaluation**: Confidence assessment with evidence

**Target Confidence Level: 95%+ before production deployment**

---

## Test Environment Requirements

### Required Setup
```bash
# Environment variables
export CARBY_BOT_TOKEN="<test_bot_token>"
export CARBY_WORKSPACE="/tmp/carby-test-workspace"
export CARBY_CACHE_DIR="/tmp/carby-test-cache"
export CARBY_POLL_INTERVAL="5"  # Fast polling for tests
export CARBY_DEBUG="true"

# Create test workspace
mkdir -p $CARBY_WORKSPACE
mkdir -p $CARBY_CACHE_DIR
```

### Test Data
- Test project: `e2e-test-project`
- Test credentials: `test-nas`, `test-api`
- Mock carby-studio CLI (for isolated testing)

---

## Scenario A: Complete Project Lifecycle (Happy Path)

### Objective
Verify a project can be created, progressed through all stages, and completed without errors.

### Preconditions
- [ ] Bot is running and connected to Telegram
- [ ] Test workspace is empty
- [ ] Mock CLI responds to all commands

### Test Steps

#### A1: Project Creation
| Step | Action | Expected Result |
|------|--------|-----------------|
| A1.1 | User sends `/start` | Welcome message with main keyboard |
| A1.2 | User taps "➕ New Project" | Prompt for project description |
| A1.3 | User enters "Build a photo hub" | Project created, ID generated |
| A1.4 | User selects "📐 Full Pipeline" | Project initialized with all stages |
| A1.5 | Bot shows project list | New project appears with "pending" status |

**Self-Evaluation Checklist:**
- [ ] Project JSON file created in workspace
- [ ] Project ID follows naming convention (lowercase, hyphens)
- [ ] All 5 stages initialized with "pending" status
- [ ] Cache updated with new project
- [ ] **Confidence: ___%** (Evidence: ____________)

#### A2: Discover Stage
| Step | Action | Expected Result |
|------|--------|-----------------|
| A2.1 | User taps "▶️ Start" on project | Bot executes `dispatch <project> discover` |
| A2.2 | Mock CLI updates status to "in-progress" | Bot detects change within 5s |
| A2.3 | Bot shows updated status | Project shows "🟢 discover: in-progress" |
| A2.4 | Mock CLI completes discover | Status changes to "done" |
| A2.5 | Bot sends notification | "✅ discover complete" with [Approve] button |
| A2.6 | User taps "✅ Approve" | Bot executes approval, advances to design |

**Self-Evaluation Checklist:**
- [ ] Dispatch command executed with correct arguments
- [ ] State change detected by polling loop
- [ ] Notification generated and sent
- [ ] Approval advances stage correctly
- [ ] **Confidence: ___%** (Evidence: ____________)

#### A3: Design Stage with Credentials
| Step | Action | Expected Result |
|------|--------|-----------------|
| A3.1 | Design stage starts automatically | Bot dispatches design agent |
| A3.2 | Agent completes design | Status = "done", credentials required |
| A3.3 | Bot shows credential check | Lists required credentials |
| A3.4 | User taps "🔐 Setup Credentials" | Credential setup flow starts |
| A3.5 | User enters credentials | Saved to shared credential store |
| A3.6 | User taps "✅ Approve" | Design approved, build starts |

**Self-Evaluation Checklist:**
- [ ] Credentials persisted correctly
- [ ] Credential validation works
- [ ] All required credentials checked before approval
- [ ] **Confidence: ___%** (Evidence: ____________)

#### A4: Build Stage
| Step | Action | Expected Result |
|------|--------|-----------------|
| A4.1 | Build stage starts | Bot dispatches code-agent |
| A4.2 | User taps "📋 Logs" | Recent logs displayed |
| A4.3 | User taps "💬 Message Agent" | Message sent to agent (if supported) |
| A4.4 | Build completes | Status = "done" |
| A4.5 | User approves | Advances to verify |

**Self-Evaluation Checklist:**
- [ ] Logs retrieved and formatted correctly
- [ ] Agent messaging works (if implemented)
- [ ] **Confidence: ___%** (Evidence: ____________)

#### A5: Verify & Deliver Stages
| Step | Action | Expected Result |
|------|--------|-----------------|
| A5.1 | Verify stage runs | Tests execute |
| A5.2 | Verify passes | Status = "done" |
| A5.3 | User approves | Advances to deliver |
| A5.4 | Deliver stage runs | Deployment artifacts created |
| A5.5 | Deliver completes | Project marked "completed" |
| A5.6 | Bot offers archive | [Archive Project] button shown |

**Self-Evaluation Checklist:**
- [ ] All 5 stages complete successfully
- [ ] Project transitions to completed state
- [ ] Archive option presented
- [ ] **Confidence: ___%** (Evidence: ____________)

### Scenario A: Overall Confidence
**Target: 95% | Actual: ___%**

**Critical Risks:**
1. State change detection latency
2. Notification delivery failures
3. Stage advancement race conditions

**Mitigation Evidence:**
- [ ] Polling interval tested at 5s
- [ ] Notification deduplication verified
- [ ] State locking prevents race conditions

---

## Scenario B: Stage Failure & Recovery

### Objective
Verify the bot handles stage failures gracefully and supports retry/skip workflows.

### Preconditions
- [ ] Active project in "build" stage
- [ ] Mock CLI configured to fail build

### Test Steps

#### B1: Build Failure Detection
| Step | Action | Expected Result |
|------|--------|-----------------|
| B1.1 | Build stage starts | Status = "in-progress" |
| B1.2 | Mock CLI simulates failure | Error: "Connection timeout" |
| B1.3 | Bot detects failure | Status = "failed" |
| B1.4 | Bot sends notification | "❌ build failed" with error summary |
| B1.5 | Project list shows failure | "🔴 build: failed" |

**Self-Evaluation Checklist:**
- [ ] Failure detected within polling interval
- [ ] Error message captured and displayed
- [ ] Retry count incremented
- [ ] **Confidence: ___%** (Evidence: ____________)

#### B2: Retry Flow
| Step | Action | Expected Result |
|------|--------|-----------------|
| B2.1 | User taps "🔄 Retry" | Bot executes `retry <project> build` |
| B2.2 | Mock CLI succeeds this time | Status = "in-progress" then "done" |
| B2.3 | Bot notifies success | "✅ build complete" |
| B2.4 | User approves | Continues to verify |

**Self-Evaluation Checklist:**
- [ ] Retry command executes correctly
- [ ] Retry count tracked
- [ ] Success after retry properly handled
- [ ] **Confidence: ___%** (Evidence: ____________)

#### B3: Skip Flow
| Step | Action | Expected Result |
|------|--------|-----------------|
| B3.1 | New build failure | Status = "failed" |
| B3.2 | User taps "⏭️ Skip" | Confirmation dialog shown |
| B3.3 | User confirms skip | Bot executes `skip <project> build` |
| B3.4 | Stage marked skipped | Status = "skipped" |
| B3.5 | Next stage starts | Verify stage begins |

**Self-Evaluation Checklist:**
- [ ] Skip confirmation prevents accidental skips
- [ ] Skip command executes correctly
- [ ] Skipped stage tracked in history
- [ ] **Confidence: ___%** (Evidence: ____________)

#### B4: Multiple Failures & Escalation
| Step | Action | Expected Result |
|------|--------|-----------------|
| B4.1 | Stage fails 5 times | Retry count = 5 |
| B4.2 | Bot shows escalation option | [Escalate] button appears |
| B4.3 | User taps escalate | Notification sent to admin |

**Self-Evaluation Checklist:**
- [ ] Retry limit enforced
- [ ] Escalation triggered after max retries
- [ ] **Confidence: ___%** (Evidence: ____________)

### Scenario B: Overall Confidence
**Target: 90% | Actual: ___%**

---

## Scenario C: Project Management (Rename/Delete)

### Objective
Verify project rename and delete operations with safety controls.

### Preconditions
- [ ] Completed project exists: `test-project`
- [ ] Project has associated files in workspace

### Test Steps

#### C1: Rename Project (Success)
| Step | Action | Expected Result |
|------|--------|-----------------|
| C1.1 | User views project detail | Rename button visible |
| C1.2 | User taps "✏️ Rename" | Prompt for new name |
| C1.3 | User enters "renamed-project" | Name validated |
| C1.4 | Bot executes rename | Files renamed, JSON updated |
| C1.5 | Project list updates | Shows new name |
| C1.6 | Old name no longer exists | Returns "not found" |

**Self-Evaluation Checklist:**
- [ ] Rename blocked if project in-progress
- [ ] Name validation rejects invalid formats
- [ ] All files renamed atomically
- [ ] Cache updated after rename
- [ ] **Confidence: ___%** (Evidence: ____________)

#### C2: Rename Project (Failure Cases)
| Step | Action | Expected Result |
|------|--------|-----------------|
| C2.1 | Try rename in-progress project | Error: "Cannot rename while running" |
| C2.2 | Enter invalid name "Test Project!" | Error: "lowercase letters, numbers, hyphens only" |
| C2.3 | Enter existing name | Error: "Project already exists" |
| C2.4 | Enter name >50 chars | Error: "Name too long" |

**Self-Evaluation Checklist:**
- [ ] All validation errors caught
- [ ] Clear error messages shown
- [ ] No partial renames occur
- [ ] **Confidence: ___%** (Evidence: ____________)

#### C3: Delete Project (Success)
| Step | Action | Expected Result |
|------|--------|-----------------|
| C3.1 | User views project detail | Delete button visible |
| C3.2 | User taps "🗑️ Delete" | Preview of files to delete |
| C3.3 | Bot shows confirmation | "Type DELETE to confirm" |
| C3.4 | User types "DELETE" | Project deleted |
| C3.5 | Files removed | JSON and directory gone |
| C3.6 | Cache updated | Project no longer listed |

**Self-Evaluation Checklist:**
- [ ] Delete blocked if project in-progress
- [ ] Preview shows all files to be deleted
- [ ] Confirmation required (not just button tap)
- [ ] Atomic deletion (all or nothing)
- [ ] **Confidence: ___%** (Evidence: ____________)

#### C4: Delete Project (Failure Cases)
| Step | Action | Expected Result |
|------|--------|-----------------|
| C4.1 | Try delete in-progress project | Error: "Cannot delete while running" |
| C4.2 | Type wrong confirmation | Error: "Confirmation incorrect" |
| C4.3 | Type "delete" (lowercase) | Error: "Type DELETE (uppercase)" |
| C4.4 | Cancel delete | Returns to project detail |

**Self-Evaluation Checklist:**
- [ ] All safety checks enforced
- [ ] Wrong confirmation rejected
- [ ] Cancel works correctly
- [ ] **Confidence: ___%** (Evidence: ____________)

### Scenario C: Overall Confidence
**Target: 95% | Actual: ___%**

---

## Scenario D: Error Handling & Edge Cases

### Objective
Verify graceful handling of errors and edge cases.

### Test Steps

#### D1: CLI Errors
| Step | Action | Expected Result |
|------|--------|-----------------|
| D1.1 | CLI command not found | Error: "Command not found: carby-studio" |
| D1.2 | CLI returns non-zero | Error message displayed to user |
| D1.3 | CLI times out | Error: "Command timed out after 60s" |
| D1.4 | Invalid project ID | Error: "Project 'xyz' not found" |

**Self-Evaluation Checklist:**
- [ ] All CLI errors caught
- [ ] User sees helpful error messages
- [ ] Bot continues running after errors
- [ ] **Confidence: ___%** (Evidence: ____________)

#### D2: File System Errors
| Step | Action | Expected Result |
|------|--------|-----------------|
| D2.1 | Project JSON corrupted | Log warning, skip project |
| D2.2 | Workspace directory missing | Create on startup |
| D2.3 | Permission denied | Error shown, operation cancelled |
| D2.4 | Disk full | Error during write operations |

**Self-Evaluation Checklist:**
- [ ] Corrupted files don't crash bot
- [ ] Missing directories auto-created
- [ ] Permission errors handled gracefully
- [ ] **Confidence: ___%** (Evidence: ____________)

#### D3: Telegram API Errors
| Step | Action | Expected Result |
|------|--------|-----------------|
| D3.1 | Network timeout | Retry with exponential backoff |
| D3.2 | Rate limited | Back off and retry |
| D3.3 | Invalid token | Clear error on startup |
| D3.4 | Message too long | Split into multiple messages |

**Self-Evaluation Checklist:**
- [ ] Network errors retried
- [ ] Rate limiting respected
- [ ] Long messages handled
- [ ] **Confidence: ___%** (Evidence: ____________)

#### D4: Concurrent Operations
| Step | Action | Expected Result |
|------|--------|-----------------|
| D4.1 | Two users approve same project | First succeeds, second gets "already approved" |
| D4.2 | Rename while dispatch running | Blocked: "Operation in progress" |
| D4.3 | Multiple projects update simultaneously | All changes detected and notified |

**Self-Evaluation Checklist:**
- [ ] Race conditions prevented
- [ ] Concurrent updates handled
- [ ] State consistency maintained
- [ ] **Confidence: ___%** (Evidence: ____________)

### Scenario D: Overall Confidence
**Target: 85% | Actual: ___%**

---

## Scenario E: Performance & Reliability

### Objective
Verify bot performs well under load and recovers from failures.

### Test Steps

#### E1: Polling Performance
| Step | Action | Expected Result |
|------|--------|-----------------|
| E1.1 | 50 projects in workspace | Poll completes <1s |
| E1.2 | Rapid state changes | All changes detected |
| E1.3 | Long-running bot | No memory leaks over 24h |

**Self-Evaluation Checklist:**
- [ ] Polling scales to 50+ projects
- [ ] No missed state changes
- [ ] Memory usage stable
- [ ] **Confidence: ___%** (Evidence: ____________)

#### E2: Crash Recovery
| Step | Action | Expected Result |
|------|--------|-----------------|
| E2.1 | Kill bot mid-operation | State persisted to cache |
| E2.2 | Restart bot | Recovers from cache |
| E2.3 | Corrupted cache | Rebuilds from project files |

**Self-Evaluation Checklist:**
- [ ] Cache persists on disk
- [ ] Recovery works after crash
- [ ] Corrupted cache handled
- [ ] **Confidence: ___%** (Evidence: ____________)

#### E3: Notification Flood
| Step | Action | Expected Result |
|------|--------|-----------------|
| E3.1 | 10 projects complete simultaneously | All notifications sent |
| E3.2 | Same notification generated twice | Deduplication prevents spam |
| E3.3 | Telegram rate limit hit | Queue and retry |

**Self-Evaluation Checklist:**
- [ ] High volume handled
- [ ] Deduplication works
- [ ] Rate limits respected
- [ ] **Confidence: ___%** (Evidence: ____________)

### Scenario E: Overall Confidence
**Target: 80% | Actual: ___%**

---

## Test Execution Checklist

### Pre-Test Setup
- [ ] Test environment configured
- [ ] Mock CLI installed
- [ ] Test bot token valid
- [ ] Test workspace clean
- [ ] Logs directory created

### Test Execution
- [ ] Scenario A: Happy Path (___% confidence)
- [ ] Scenario B: Failure Recovery (___% confidence)
- [ ] Scenario C: Project Management (___% confidence)
- [ ] Scenario D: Error Handling (___% confidence)
- [ ] Scenario E: Performance (___% confidence)

### Post-Test Verification
- [ ] All test artifacts cleaned up
- [ ] Logs reviewed for errors
- [ ] Coverage report generated
- [ ] Confidence scores documented

---

## Confidence Scoring Rubric

### 95-100%: Production Ready
- All tests pass consistently
- Edge cases handled
- No known bugs
- Documentation complete

### 85-94%: Beta Ready
- Core functionality works
- Minor edge cases may fail
- Known issues documented
- Workarounds available

### 70-84%: Alpha Ready
- Basic functionality works
- Some features incomplete
- Known bugs exist
- Not suitable for production

### <70%: Development Only
- Major features missing
- Frequent failures
- Not ready for testing

---

## Final Self-Evaluation

### Overall System Confidence

| Component | Target | Actual | Evidence |
|-----------|--------|--------|----------|
| State Management | 95% | ___% | ____________ |
| CLI Integration | 90% | ___% | ____________ |
| Telegram Interface | 95% | ___% | ____________ |
| Safety Features | 95% | ___% | ____________ |
| Error Handling | 85% | ___% | ____________ |
| Performance | 80% | ___% | ____________ |
| **OVERALL** | **90%** | **___%** | **__________** |

### Go/No-Go Decision

**Production Deployment:** ⬜ GO / ⬜ NO-GO

**Conditions for GO:**
- [ ] Overall confidence ≥ 90%
- [ ] No critical bugs open
- [ ] All safety features verified
- [ ] Rollback plan documented

**If NO-GO, blockers:**
1. ________________________________
2. ________________________________
3. ________________________________

---

## Appendix: Test Automation

### Automated Test Script
```bash
#!/bin/bash
# run_e2e_tests.sh

set -e

echo "=== Carby Studio Bot E2E Tests ==="

# Setup
export CARBY_WORKSPACE="/tmp/carby-e2e-$$"
export CARBY_CACHE_DIR="/tmp/carby-e2e-cache-$$"
mkdir -p $CARBY_WORKSPACE $CARBY_CACHE_DIR

# Run tests
echo "Running Scenario A..."
python3 -m pytest test_e2e.py::TestEndToEndFlow::test_scenario_a_happy_path -v

echo "Running Scenario B..."
python3 -m pytest test_e2e.py::TestEndToEndFlow::test_scenario_b_stage_failure -v

echo "Running Scenario C..."
python3 -m pytest test_e2e.py::TestEndToEndFlow::test_scenario_c_project_management -v

echo "Running Scenario D..."
python3 -m pytest test_e2e.py::TestEndToEndFlow::test_scenario_d_error_handling -v

echo "Running Scenario E..."
python3 -m pytest test_e2e.py::TestEndToEndFlow::test_polling_and_notifications -v

# Cleanup
rm -rf $CARBY_WORKSPACE $CARBY_CACHE_DIR

echo "=== All E2E Tests Passed ==="
```

### Manual Test Script
```bash
# manual_test.sh
# Requires: Telegram bot token, Telegram client

echo "Manual Test Checklist:"
echo "1. Send /start - verify welcome message"
echo "2. Create project - verify appears in list"
echo "3. Dispatch stage - verify status updates"
echo "4. Approve stage - verify advancement"
echo "5. Rename project - verify validation"
echo "6. Delete project - verify confirmation"
echo "7. Check logs - verify no errors"
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-09  
**Author:** AI Assistant  
**Status:** Ready for Testing
