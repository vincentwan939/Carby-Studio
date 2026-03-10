# Carby Studio Bot — Implementation & Testing Plan

## Overview

Complete implementation with end-to-end testing. All phases executed sequentially.

**Timeline**: Single session (estimated 4-6 hours)
**Approach**: Build → Test → Iterate

---

## Phase 1: Core Infrastructure (Polling & State Management)

### 1.1 Project State Reader
```python
class ProjectStateReader:
    - read_project(project_id) -> dict
    - list_projects() -> List[str]
    - watch_projects(callback) -> None
```

### 1.2 State Change Detector
```python
class StateChangeDetector:
    - detect_changes(old_state, new_state) -> List[ChangeEvent]
    - ChangeEvent: type, project, stage, old_status, new_status
```

### 1.3 Notification Generator
```python
class NotificationGenerator:
    - generate_notification(change_event) -> Notification
    - format_message(notification) -> str
```

### 1.4 Tests
- [ ] Read valid project JSON
- [ ] Handle missing project
- [ ] Detect status change pending→in-progress
- [ ] Detect status change in-progress→done
- [ ] Detect status change in-progress→failed
- [ ] Generate correct notification text
- [ ] Handle concurrent project changes

---

## Phase 2: Telegram Interface

### 2.1 Bot Setup
```python
class CarbyTelegramBot:
    - __init__(token)
    - start_polling()
    - stop()
```

### 2.2 Command Handlers
```python
- cmd_start() -> Welcome message
- cmd_projects() -> Projects list
- cmd_status() -> System status
- cmd_help() -> Help text
```

### 2.3 Button Callbacks
```python
- on_view_project(project_id) -> Detail view
- on_dispatch(project_id, stage) -> Execute CLI
- on_skip(project_id, stage) -> Execute CLI
- on_retry(project_id, stage) -> Execute CLI
- on_rename(project_id) -> Start rename flow
- on_delete(project_id) -> Start delete flow
```

### 2.4 Tests
- [ ] Bot starts without error
- [ ] /start returns welcome
- [ ] /projects returns list
- [ ] Button callback triggers action
- [ ] Error handling for invalid callback

---

## Phase 3: CLI Integration

### 3.1 CLI Executor
```python
class CLIExecutor:
    - dispatch(project, stage) -> Result
    - skip(project, stage) -> Result
    - retry(project, stage) -> Result
    - rename(old, new) -> Result
    - delete(project) -> Result
```

### 3.2 Result Handler
```python
class ResultHandler:
    - format_success(result) -> str
    - format_error(result) -> str
    - show_in_telegram(message)
```

### 3.3 Tests
- [ ] dispatch executes correct command
- [ ] skip executes correct command
- [ ] retry executes correct command
- [ ] rename validates before executing
- [ ] delete requires confirmation
- [ ] Handle CLI not found error
- [ ] Handle CLI command failure

---

## Phase 4: Safety Features

### 4.1 Rename Safety
```python
- validate_name(new_name) -> bool
- check_exists(new_name) -> bool
- confirm_rename(old, new) -> bool
```

### 4.2 Delete Safety
```python
- check_in_progress(project) -> bool
- require_typed_confirmation(project) -> bool
- show_what_will_be_deleted(project) -> str
```

### 4.3 Tests
- [ ] Reject invalid name (spaces, special chars)
- [ ] Reject existing name
- [ ] Block delete if in-progress
- [ ] Require exact "DELETE" confirmation
- [ ] Show preview of files to delete

---

## Phase 5: Integration & Polling Loop

### 5.1 Main Loop
```python
class BotMain:
    - __init__()
    - start()
    - poll_once()
    - handle_notifications()
    - run_forever()
```

### 5.2 Tests
- [ ] Poll detects new project
- [ ] Poll detects stage completion
- [ ] Poll detects stage failure
- [ ] Send notification to Telegram
- [ ] Handle poll error gracefully
- [ ] Recover from crash

---

## Phase 6: End-to-End Testing

### 6.1 Test Scenarios

#### Scenario A: Happy Path
```
1. Create project via CLI
2. Bot detects new project
3. User sees project in list
4. User dispatches Discover
5. Bot detects in-progress
6. Agent completes Discover
7. Bot notifies: "Discover complete"
8. User taps [Dispatch Design]
9. Continue through pipeline...
```

#### Scenario B: Stage Failure
```
1. Build stage fails
2. Bot notifies: "Build failed"
3. User taps [View Logs]
4. User sees error
5. User taps [Retry Build]
6. Bot executes retry
7. Build succeeds
8. Bot notifies: "Build complete"
```

#### Scenario C: Project Management
```
1. Project completed
2. User enters detail view
3. User taps [Rename]
4. User enters new name
5. Bot validates and renames
6. User sees new name in list
7. User taps [Delete]
8. Bot asks for confirmation
9. User types "DELETE"
10. Bot deletes project
11. Project gone from list
```

#### Scenario D: Error Handling
```
1. CLI command fails
2. Bot shows error in Telegram
3. User can retry
4. File read error
5. Bot logs warning, continues
6. Invalid project name
7. Bot shows validation error
```

### 6.2 Test Matrix

| Test | Type | Expected | Status |
|------|------|----------|--------|
| Poll new project | Unit | Notification sent | ⬜ |
| Poll stage done | Unit | Notification sent | ⬜ |
| Poll stage failed | Unit | Notification sent | ⬜ |
| Dispatch button | Integration | CLI executed | ⬜ |
| Skip button | Integration | CLI executed | ⬜ |
| Retry button | Integration | CLI executed | ⬜ |
| Rename valid | Integration | Project renamed | ⬜ |
| Rename invalid | Integration | Error shown | ⬜ |
| Delete confirmed | Integration | Project deleted | ⬜ |
| Delete cancelled | Integration | Project kept | ⬜ |
| Full pipeline | E2E | All stages complete | ⬜ |
| Concurrent projects | E2E | Both tracked | ⬜ |
| Crash recovery | E2E | State restored | ⬜ |

---

## Phase 7: Deployment & Documentation

### 7.1 Files to Create
```
bot/
├── carby_bot.py           # Core logic (refactored)
├── telegram_handler.py    # Telegram interface (refactored)
├── cli_executor.py        # CLI wrapper
├── state_manager.py       # State reading/caching
├── notification_service.py # Notification generation
├── safety.py              # Rename/delete safety
├── config.py              # Configuration
├── test_bot.py            # Unit tests
├── test_integration.py    # Integration tests
├── test_e2e.py            # End-to-end tests
├── requirements.txt       # Dependencies
├── README.md              # Usage guide
└── IMPLEMENTATION.md      # This file
```

### 7.2 Documentation
- [ ] README with setup instructions
- [ ] Command reference
- [ ] Troubleshooting guide

---

## Execution Checklist

### Pre-Implementation
- [x] Design approved
- [x] Testing plan defined
- [ ] Environment ready

### Implementation
- [ ] Phase 1: Core (1 hour)
- [ ] Phase 2: Telegram (1 hour)
- [ ] Phase 3: CLI (1 hour)
- [ ] Phase 4: Safety (30 min)
- [ ] Phase 5: Integration (30 min)

### Testing
- [ ] Phase 6: Unit tests (30 min)
- [ ] Phase 6: Integration tests (30 min)
- [ ] Phase 6: E2E tests (30 min)

### Documentation
- [ ] Phase 7: Documentation (30 min)

---

## Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| All unit tests pass | 100% | pytest output |
| All integration tests pass | 100% | pytest output |
| E2E scenarios pass | 4/4 | Manual test |
| No critical bugs | 0 | Bug count |
| Code coverage | > 80% | pytest-cov |
| Documentation complete | 100% | Checklist |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Time overrun | Prioritize core features, cut nice-to-have |
| CLI incompatibility | Implement fallback in bot |
| Test failures | Iterate, don't proceed with broken tests |
| Telegram API issues | Use polling, not webhooks |

---

## Start Implementation

**Beginning Phase 1 now...**
