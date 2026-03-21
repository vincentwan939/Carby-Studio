# TintinBot Migration Proposal: carby-studio → carby-sprint

**Document Version:** 1.0  
**Date:** 2026-03-21  
**Author:** Carby (AI Assistant)  
**Status:** Pending Review

---

## 1. Executive Summary

### Why Migrate?

Carby Studio v3.1.0 has deprecated the `carby-studio` CLI in favor of the new `carby-sprint` CLI. The new sprint-based model introduces:

- **Gates & Phases**: More granular control with 5 gates (1-5) and multiple phases per gate
- **Better State Management**: Centralized sprint storage in `.carby-sprints/`
- **Enhanced Workflow**: Sequential/parallel execution modes with phase-level approvals
- **Improved CLI**: More consistent command structure and better error handling

### Key Benefits

| Benefit | Description |
|---------|-------------|
| **Future-Proof** | Aligns with Carby Studio v3.1.0+ roadmap |
| **Better UX** | Phase-level approvals give finer control over workflow |
| **Parallel Execution** | Support for parallel phase execution in build gate |
| **Cleaner State** | Unified sprint storage vs scattered project files |
| **Richer Status** | More detailed progress tracking with phase-level visibility |

### Estimated Effort

| Phase | Effort | Files Modified |
|-------|--------|----------------|
| Phase 1: CLI Wrapper | 2-3 hours | `cli_executor.py` |
| Phase 2: State Manager | 3-4 hours | `state_manager.py` |
| Phase 3: Telegram UI | 4-5 hours | `telegram_interface.py`, `bot.py` |
| Phase 4: Testing | 2-3 hours | Test scripts, validation |
| **Total** | **11-15 hours** | **4 core files** |

---

## 2. Concept Mapping

### 2.1 Projects → Sprints

| Aspect | Old (carby-studio) | New (carby-sprint) |
|--------|-------------------|-------------------|
| **Entity Name** | Project | Sprint |
| **ID Format** | `my-project` | `my-project` (same naming) |
| **Creation** | `carby-studio init <project> --goal "..."` | `carby-sprint init <sprint> --project <project> --goal "..."` |
| **Storage** | `~/.openclaw/workspace/projects/<project>.json` | `~/.openclaw/workspace/.carby-sprints/<sprint>/state.json` |
| **Metadata** | Embedded in project JSON | Separate sprint metadata + project reference |

**Key Insight:** A sprint is a temporal execution container that references a project. This allows multiple sprints per project (e.g., "website-v2" project could have "website-v2-sprint1", "website-v2-sprint2").

### 2.2 Stages → Gates & Phases

| Old Stage | Old Purpose | New Gate | New Phases |
|-----------|-------------|----------|------------|
| `discover` | Research & requirements | Gate 1 | `research`, `requirements` |
| `design` | Architecture & planning | Gate 2 | `architecture`, `design-review` |
| `build` | Implementation | Gate 3 | `implement`, `unit-test`, `integrate` |
| `verify` | Testing & QA | Gate 4 | `qa`, `security-scan`, `performance` |
| `deliver` | Deployment | Gate 5 | `deploy`, `monitor`, `handoff` |

**Status Mapping:**

| Old Status | New Phase Status |
|------------|------------------|
| `pending` | `pending` |
| `in-progress` | `in-progress` |
| `done` | `completed` |
| `approved` | `approved` |
| `failed` | `failed` |
| `skipped` | `skipped` |

### 2.3 State File Locations

```
OLD STRUCTURE:
~/.openclaw/workspace/
└── projects/
    ├── my-project.json          # Project state
    └── my-project/              # Project artifacts
        ├── discover/
        ├── design/
        ├── build/
        ├── verify/
        └── deliver/

NEW STRUCTURE:
~/.openclaw/workspace/
├── .carby-sprints/              # Sprint storage (NEW)
│   └── my-project/              # Sprint directory
│       ├── state.json           # Sprint state
│       ├── logs/                # Execution logs
│       ├── phases/              # Phase outputs
│       └── artifacts/           # Generated artifacts
└── projects/                    # Project definitions (remain)
    └── my-project.json          # Project metadata
```

**Important:** The bot needs to read from `.carby-sprints/` for sprint state while `projects/` becomes read-only reference data.

---

## 3. Command Migration Matrix

### 3.1 Core Bot Actions

| Bot Action | Old CLI (carby-studio) | New CLI (carby-sprint) | Notes |
|------------|------------------------|------------------------|-------|
| **Initialize** | `carby-studio init <project> -g <goal> --mode <mode>` | `carby-sprint init <sprint> --project <project> --goal <goal> [--duration <days>]` | New `--project` flag required |
| **Start Sprint** | `carby-studio dispatch <project> <stage>` | `carby-sprint start <sprint>` | No stage arg needed |
| **Advance Gate** | `carby-studio dispatch <project> <stage>` | `carby-sprint gate <sprint> <gate_number>` | Explicit gate advancement |
| **Approve** | `carby-studio approve <project>` | `carby-sprint approve <sprint> [phase_id] [--auto-advance]` | Can approve specific phase |
| **Skip** | `carby-studio skip <project> <stage>` | `carby-sprint gate <sprint> <gate> --force` | Force flag skips gate |
| **Retry** | `carby-studio retry <project> <stage>` | `carby-sprint gate <sprint> <gate> --retry` | Retry current gate |
| **Stop** | `carby-studio stop <project>` | `carby-sprint pause <sprint>` | Pause instead of stop |
| **Cancel** | (manual file edit) | `carby-sprint cancel <sprint>` | New: proper cancel command |
| **Resume** | (manual state edit) | `carby-sprint resume <sprint>` | New: proper resume command |
| **Status** | `carby-studio status <project>` | `carby-sprint status <sprint> [--watch]` | Similar output |
| **Logs** | `carby-studio logs <project>` | `carby-sprint verify-logs` OR read `.carby-sprints/<sprint>/logs/` | Multiple log sources |
| **List** | `carby-studio list` | `carby-sprint list` | Similar output |
| **Archive** | (manual file move) | `carby-sprint archive <sprint>` | New: proper archive command |

### 3.2 New Commands to Support

| Command | Purpose | Bot Integration |
|---------|---------|-----------------|
| `carby-sprint plan <sprint> --work-items <items>` | Define work items | New bot command: `/plan <sprint>` |
| `carby-sprint phase-status <sprint>` | Get phase-level status | New UI: Phase detail view |
| `carby-sprint phase-list <sprint>` | List all phases | New UI: Phase list button |

### 3.3 Deprecated Commands (No Longer Needed)

| Old Command | Reason |
|-------------|--------|
| `carby-studio ready <project>` | DAG mode handled differently in sprint model |
| `carby-studio dispatch-ready` | Replaced by `start` and `gate` commands |

---

## 4. Architecture Changes

### 4.1 Files Requiring Modification

```
bot/
├── cli_executor.py          # MAJOR: Replace all carby-studio commands
├── state_manager.py         # MAJOR: New data structures, new file paths
├── telegram_interface.py    # MODERATE: New buttons, flows, callbacks
├── bot.py                   # MODERATE: New action handlers
└── config.py                # MINOR: Update paths, constants
```

### 4.2 New Classes/Methods Required

#### 4.2.1 `cli_executor.py` Changes

```python
# NEW: Sprint validation (replaces project validation)
VALID_GATE_NUMBERS = {1, 2, 3, 4, 5}

def _validate_sprint_name(self, name: str) -> None:
    """Validate sprint ID format."""
    # Same validation as project names
    
def _validate_gate_number(self, gate: int) -> None:
    """Validate gate number (1-5)."""
    if gate not in self.VALID_GATE_NUMBERS:
        raise SecurityError(f"Gate must be 1-5, got {gate}")

# MODIFIED: All methods change signature

def init(self, sprint: str, project: str, goal: str, duration: Optional[int] = None) -> CLIResult:
    """Initialize new sprint."""
    command = ["carby-sprint", "init", sprint, "--project", project, "--goal", goal]
    if duration:
        command.extend(["--duration", str(duration)])
    return self._run(command)

def start(self, sprint: str, mode: str = "sequential") -> CLIResult:
    """Start sprint execution."""
    command = ["carby-sprint", "start", sprint, "--mode", mode]
    return self._run(command)

def gate(self, sprint: str, gate_number: int, force: bool = False, retry: bool = False) -> CLIResult:
    """Advance to or retry a gate."""
    self._validate_gate_number(gate_number)
    command = ["carby-sprint", "gate", sprint, str(gate_number)]
    if force:
        command.append("--force")
    if retry:
        command.append("--retry")
    return self._run(command)

def approve(self, sprint: str, phase_id: Optional[str] = None, auto_advance: bool = False) -> CLIResult:
    """Approve current or specific phase."""
    command = ["carby-sprint", "approve", sprint]
    if phase_id:
        command.extend(["--phase", phase_id])
    if auto_advance:
        command.append("--auto-advance")
    return self._run(command)

def pause(self, sprint: str) -> CLIResult:
    """Pause sprint execution."""
    return self._run(["carby-sprint", "pause", sprint])

def resume(self, sprint: str) -> CLIResult:
    """Resume paused sprint."""
    return self._run(["carby-sprint", "resume", sprint])

def cancel(self, sprint: str) -> CLIResult:
    """Cancel sprint."""
    return self._run(["carby-sprint", "cancel", sprint])

def archive(self, sprint: str) -> CLIResult:
    """Archive completed sprint."""
    return self._run(["carby-sprint", "archive", sprint])

def phase_status(self, sprint: str) -> CLIResult:
    """Get detailed phase status."""
    return self._run(["carby-sprint", "phase-status", sprint, "--json"])

def list_sprints(self) -> CLIResult:
    """List all sprints."""
    return self._run(["carby-sprint", "list", "--json"])
```

#### 4.2.2 `state_manager.py` Changes

```python
# NEW: Sprint state structures
@dataclass
class PhaseState:
    """Individual phase within a gate."""
    phase_id: str
    name: str
    status: str  # pending, in-progress, completed, approved, failed, skipped
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    agent: Optional[str] = None
    logs: List[str] = field(default_factory=list)

@dataclass
class GateState:
    """Gate containing multiple phases."""
    gate_number: int
    name: str
    status: str
    phases: List[PhaseState] = field(default_factory=list)
    current_phase: Optional[str] = None

@dataclass
class SprintState:
    """Complete sprint state."""
    sprint_id: str
    project: str
    goal: str
    status: str
    mode: str  # sequential or parallel
    current_gate: int
    gates: List[GateState] = field(default_factory=list)
    created_at: str
    updated_at: str

# MODIFIED: StateManager class
class StateManager:
    """Manages sprint state from .carby-sprints/ directory."""
    
    SPRINTS_DIR = Path("~/.openclaw/workspace/.carby-sprints").expanduser()
    
    def read_sprint_state(self, sprint_id: str) -> Optional[SprintState]:
        """Read sprint state from .carby-sprints/<sprint>/state.json"""
        state_file = self.SPRINTS_DIR / sprint_id / "state.json"
        # ... implementation
    
    def get_all_sprints(self) -> List[SprintState]:
        """Read all sprint states."""
        # ... implementation
    
    def detect_changes(self) -> List[StateChange]:
        """Detect changes across all sprints."""
        # ... implementation
```

#### 4.2.3 `telegram_interface.py` Changes

```python
# NEW: Gate and phase visualization

async def show_sprint_detail(self, update: Update, sprint_id: str):
    """Show sprint detail with gate/phase visualization."""
    sprint = self.state_manager.read_sprint_state(sprint_id)
    
    message = f"📋 *{sprint.sprint_id}*\n"
    message += f"🎯 {sprint.goal}\n"
    message += f"📦 Project: {sprint.project}\n"
    message += f"⚙️ Mode: {sprint.mode}\n\n"
    
    # Gate visualization
    for gate in sprint.gates:
        icon = self._gate_icon(gate.status)
        message += f"{icon} Gate {gate.gate_number}: {gate.name}\n"
        
        # Show phases for current gate
        if gate.gate_number == sprint.current_gate:
            for phase in gate.phases:
                phase_icon = self._phase_icon(phase.status)
                message += f"   {phase_icon} {phase.name}\n"
    
    # Action buttons based on state
    keyboard = self._build_sprint_actions(sprint)
    
    await update.message.reply_text(
        message, 
        parse_mode="Markdown",
        reply_markup=keyboard
    )

def _gate_icon(self, status: str) -> str:
    """Get icon for gate status."""
    icons = {
        "pending": "⬜",
        "in-progress": "🔄",
        "completed": "✅",
        "approved": "✅",
        "failed": "❌",
        "skipped": "⏭️"
    }
    return icons.get(status, "⬜")

def _phase_icon(self, status: str) -> str:
    """Get icon for phase status."""
    icons = {
        "pending": "◯",
        "in-progress": "◉",
        "completed": "✓",
        "approved": "✓",
        "failed": "✗",
        "skipped": "›"
    }
    return icons.get(status, "◯")

def _build_sprint_actions(self, sprint: SprintState) -> InlineKeyboardMarkup:
    """Build action buttons based on sprint state."""
    buttons = []
    
    current_gate = sprint.gates[sprint.current_gate - 1]
    
    if current_gate.status == "pending":
        # Gate not started - show start button
        buttons.append([
            InlineKeyboardButton("▶️ Start Gate", callback_data=f"gate:{sprint.sprint_id}:{sprint.current_gate}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{sprint.sprint_id}:{sprint.current_gate}")
        ])
    elif current_gate.status == "in-progress":
        # Gate running - show pause and logs
        buttons.append([
            InlineKeyboardButton("⏸️ Pause", callback_data=f"pause:{sprint.sprint_id}"),
            InlineKeyboardButton("📋 Logs", callback_data=f"logs:{sprint.sprint_id}")
        ])
    elif current_gate.status == "completed":
        # Gate done - show approve
        buttons.append([
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{sprint.sprint_id}"),
            InlineKeyboardButton("🔄 Retry", callback_data=f"retry:{sprint.sprint_id}:{sprint.current_gate}")
        ])
    elif current_gate.status == "failed":
        # Gate failed - show retry/skip
        buttons.append([
            InlineKeyboardButton("🔄 Retry", callback_data=f"retry:{sprint.sprint_id}:{sprint.current_gate}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{sprint.sprint_id}:{sprint.current_gate}"),
            InlineKeyboardButton("📋 Logs", callback_data=f"logs:{sprint.sprint_id}")
        ])
    
    # Management buttons
    buttons.append([
        InlineKeyboardButton("🗄️ Archive", callback_data=f"archive:{sprint.sprint_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{sprint.sprint_id}")
    ])
    
    return InlineKeyboardMarkup(buttons)
```

---

## 5. UI/UX Updates

### 5.1 New Menu Structure

**Main Menu (unchanged):**
```
📋 Sprints  |  ➕ New  |  ⚙️ More
```

**Sprint List View (updated):**
```
📋 Your Sprints (4)

🔄 family-photo-hub
   Gate 3: Build • implement phase
   [View Details]

✅ karina-pipeline
   Gate 5: Deliver • completed
   [View Details]

❌ time-fetcher
   Gate 4: Verify • qa failed
   [View Details]

⏸️ photo-archive
   Gate 2: Design • awaiting approval
   [View Details]
```

**Sprint Detail View (updated):**
```
family-photo-hub
🎯 Photo management for Sony a7c2 & iPhone
📦 Project: family-photo-hub
⚙️ Mode: sequential

Gates:
✅ Gate 1: Discover (completed)
✅ Gate 2: Design (approved)
🔄 Gate 3: Build (in-progress)
   ◉ implement phase • code-agent • 12m
   ◯ unit-test phase • pending
   ◯ integrate phase • pending
⬜ Gate 4: Verify (pending)
⬜ Gate 5: Deliver (pending)

Actions:
[⏸️ Pause] [📋 Logs] [🗄️ Archive]
[❌ Cancel]

 [← Back to Sprints]
```

### 5.2 New Interaction Flows

#### Phase-Level Approval Flow
```
User: Views sprint detail
Bot: Shows "Gate 2: Design (completed)"
User: Taps [✅ Approve]
Bot: "Approve Gate 2: Design?"
     "This will allow Gate 3: Build to start."
     [✅ Approve] [❌ Cancel]
User: Taps [✅ Approve]
Bot: Runs: carby-sprint approve family-photo-hub --auto-advance
Bot: "✅ Gate 2 approved. Starting Gate 3: Build..."
```

#### Gate Retry Flow
```
User: Views failed sprint
Bot: Shows "❌ Gate 4: Verify (failed)"
User: Taps [🔄 Retry]
Bot: "Retry Gate 4: Verify?"
     "This will restart the QA phase."
     [🔄 Retry] [❌ Cancel]
User: Taps [🔄 Retry]
Bot: Runs: carby-sprint gate family-photo-hub 4 --retry
Bot: "🔄 Retrying Gate 4: Verify..."
```

---

## 6. Implementation Plan

### Phase 1: CLI Wrapper Update (2-3 hours)
**Goal**: Replace carby-studio commands with carby-sprint equivalents

**Tasks:**
- [ ] Update `cli_executor.py` with new command signatures
- [ ] Add sprint/gate/phase validation
- [ ] Implement new methods (pause, resume, cancel, archive)
- [ ] Update error handling for new CLI output format
- [ ] Test each command manually

**Files Modified:**
- `cli_executor.py`

**Success Criteria:**
- All carby-sprint commands execute successfully
- Error messages are user-friendly
- Validation prevents invalid inputs

---

### Phase 2: State Manager Adaptation (3-4 hours)
**Goal**: Read sprint state from .carby-sprints/ directory

**Tasks:**
- [ ] Create new data classes (SprintState, GateState, PhaseState)
- [ ] Update StateManager to read from .carby-sprints/
- [ ] Implement state change detection for new structure
- [ ] Add backward compatibility for legacy projects
- [ ] Update caching mechanism

**Files Modified:**
- `state_manager.py`
- `config.py` (update paths)

**Success Criteria:**
- Successfully reads all sprint states
- Detects state changes correctly
- Maintains cache integrity

---

### Phase 3: Telegram UI Updates (4-5 hours)
**Goal**: Update UI to show gates/phases and new actions

**Tasks:**
- [ ] Update project list to show sprint status
- [ ] Create gate/phase visualization
- [ ] Add new action buttons (pause, resume, cancel, archive)
- [ ] Update callback handlers for new actions
- [ ] Implement phase-level approval flow
- [ ] Update notification messages

**Files Modified:**
- `telegram_interface.py`
- `bot.py`

**Success Criteria:**
- UI clearly shows gate/phase progress
- All action buttons work correctly
- Approval flow is intuitive

---

### Phase 4: Testing & Validation (2-3 hours)
**Goal**: Verify migration works end-to-end

**Tasks:**
- [ ] Run existing E2E tests (update for new structure)
- [ ] Test each command manually
- [ ] Verify state change detection
- [ ] Test error handling
- [ ] Validate security (input validation)

**Files Modified:**
- `test_e2e.py`
- `test_cli_executor.py`

**Success Criteria:**
- All tests pass
- Manual testing confirms functionality
- No security regressions

---

## 7. Risk Assessment

### Risk 1: Data Migration Complexity
**Risk**: Existing project JSON files may not map cleanly to sprint structure
**Likelihood**: Medium
**Impact**: High
**Mitigation:**
- Maintain backward compatibility
- Create migration script for existing projects
- Keep projects/ directory as read-only reference

### Risk 2: User Confusion
**Risk**: Users familiar with old stage model may be confused by gates/phases
**Likelihood**: Medium
**Impact**: Medium
**Mitigation:**
- Provide clear visual mapping (Gate 1 = Discover)
- Update help text
- Add tooltip explanations

### Risk 3: CLI Output Changes
**Risk**: carby-sprint output format may differ from carby-studio
**Likelihood**: High
**Impact**: Medium
**Mitigation:**
- Use --json flag where available
- Implement robust parsing with fallbacks
- Add output format validation

### Risk 4: Parallel Mode Complexity
**Risk**: Parallel execution mode adds complexity to state tracking
**Likelihood**: Low
**Impact**: Medium
**Mitigation:**
- Start with sequential mode only
- Add parallel mode support in Phase 2
- Clear visual distinction in UI

### Risk 5: Breaking Changes in Future carby-sprint Versions
**Risk**: carby-sprint is actively developed; CLI may change
**Likelihood**: Medium
**Impact**: Medium
**Mitigation:**
- Pin to specific carby-sprint version
- Add version checking on startup
- Design for easy updates

---

## 8. Rollback Plan

If migration fails:

1. **Immediate Rollback** (< 5 minutes):
   - Restore cli_executor.py from git
   - Restart bot
   - Bot reverts to carby-studio commands

2. **Data Rollback** (if needed):
   - projects/ directory unchanged
   - .carby-sprints/ is additive only
   - No data loss risk

3. **User Communication**:
   - Send notification: "Bot temporarily reverted to legacy mode"
   - Explain known limitations
   - Provide ETA for fix

---

## 9. Success Criteria

### Functional Requirements
- [ ] All carby-sprint commands execute successfully
- [ ] State changes detected within 30 seconds
- [ ] Notifications sent for gate/phase changes
- [ ] Phase-level approvals work correctly
- [ ] Pause/resume/cancel/archive functional

### UX Requirements
- [ ] Gate/phase visualization is clear
- [ ] Action buttons appropriate for state
- [ ] Error messages user-friendly
- [ ] No increase in user confusion

### Performance Requirements
- [ ] Poll completes < 1 second for 50 sprints
- [ ] Button response < 3 seconds
- [ ] Memory usage stable over 24 hours

### Security Requirements
- [ ] Input validation prevents injection
- [ ] No token exposure in logs
- [ ] Proper authorization checks

---

## 10. Appendix

### A. Test Scenarios

**Scenario 1: Create Sprint → Start → Complete**
1. Create new sprint via bot
2. Start sprint (Gate 1)
3. Approve Gate 1
4. Verify Gate 2 starts automatically
5. Continue through all gates
6. Archive completed sprint

**Scenario 2: Gate Failure → Retry**
1. Start sprint
2. Let gate fail (simulate)
3. Receive failure notification
4. Tap retry button
5. Verify gate restarts
6. Complete successfully

**Scenario 3: Pause → Resume**
1. Start sprint
2. Pause during execution
3. Verify paused state
4. Resume sprint
5. Verify continues from pause point

### B. Migration Checklist

- [ ] Phase 1: CLI Wrapper complete
- [ ] Phase 2: State Manager complete
- [ ] Phase 3: Telegram UI complete
- [ ] Phase 4: Testing complete
- [ ] Documentation updated
- [ ] User communication sent
- [ ] Rollback plan tested
- [ ] Monitoring in place

---

**Document Status:** Ready for Review  
**Next Step:** Vincent to review and approve implementation  
**Estimated Total Effort:** 11-15 hours str = "sequential") -> CLIResult:
    """Start sprint execution."""
    command = ["carby-sprint", "start", sprint, "--mode", mode]
    return self._run(command)

def gate(self, sprint: str, gate_number: int, force: bool = False, retry: bool = False) -> CLIResult:
    """Advance to specific gate."""
    command = ["carby-sprint", "gate", sprint, str(gate_number)]
    if force:
        command.append("--force")
    if retry:
        command.append("--retry")
    return self._run(command)

def approve(self, sprint: str, phase_id: Optional[str] = None, auto_advance: bool = False) -> CLIResult:
    """Approve current phase or specific phase."""
    command = ["carby-sprint", "approve", sprint]
    if phase_id:
        command.append(phase_id)
    if auto_advance:
        command.append("--auto-advance")
    return self._run(command)

def pause(self, sprint: str) -> CLIResult:
    """Pause sprint execution."""
    command = ["carby-sprint", "pause", sprint]
    return self._run(command)

def resume(self, sprint: str) -> CLIResult:
    """Resume paused sprint."""
    command = ["carby-sprint", "resume", sprint]
    return self._run(command)

def cancel(self, sprint: str) -> CLIResult:
    """Cancel sprint execution."""
    command = ["carby-sprint", "cancel", sprint]
    return self._run(command)

def status(self, sprint: str, watch: bool = False) -> CLIResult:
    """Get sprint status."""
    command = ["carby-sprint", "status", sprint]
    if watch:
        command.append("--watch")
    return self._run(command)

def logs(self, sprint: str) -> CLIResult:
    """Get sprint logs."""
    command = ["carby-sprint", "verify-logs"]  # or read from .carby-sprints/<sprint>/logs/
    return self._run(command)

def list_sprints(self) -> CLIResult:
    """List all sprints."""
    command = ["carby-sprint", "list"]
    return self._run(command)

def phase_status(self, sprint: str) -> CLIResult:
    """Get phase-level status."""
    command = ["carby-sprint", "phase-status", sprint]
    return self._run(command)

def plan(self, sprint: str, work_items: str) -> CLIResult:
    """Plan work items for sprint."""
    command = ["carby-sprint", "plan", sprint, "--work-items", work_items]
    return self._run(command)
```

#### 4.2.2 `state_manager.py` Changes

```python
# NEW: Sprint-specific paths and state structures
CARBY_SPRINTS_DIR = Path.home() / ".openclaw" / "workspace" / ".carby-sprints"

class SprintState:
    """New state structure for sprints."""
    def __init__(self):
        self.id: str
        self.project: str
        self.goal: str
        self.status: str
        self.current_gate: int
        self.current_phase: str
        self.phases: Dict[str, PhaseState]
        self.gates: Dict[int, GateState]
        self.created_at: str
        self.updated_at: str

class PhaseState:
    """State of a single phase."""
    def __init__(self):
        self.id: str
        self.gate: int
        self.status: str
        self.agent: Optional[str]
        self.started_at: Optional[str]
        self.completed_at: Optional[str]
        self.output: Optional[str]
        self.error: Optional[str]

class GateState:
    """State of a single gate."""
    def __init__(self):
        self.number: int
        self.status: str
        self.phases: List[str]
        self.completed_phases: int
        self.total_phases: int

class StateManager:
    # NEW: Methods to handle sprint-based state
    
    def _get_sprint_path(self, sprint_id: str) -> Path:
        """Get path to sprint state file."""
        return CARBY_SPRINTS_DIR / sprint_id / "state.json"
    
    def read_sprint(self, sprint_id: str) -> Optional[dict]:
        """Read sprint state from new location."""
        path = self._get_sprint_path(sprint_id)
        try:
            with locked_json_read(path, sprint_id, CARBY_SPRINTS_DIR) as data:
                return data
        except TimeoutError:
            return safe_read_json(path)
    
    def list_sprints(self) -> List[str]:
        """List all sprints from new location."""
        sprints = []
        try:
            for sprint_dir in CARBY_SPRINTS_DIR.iterdir():
                if sprint_dir.is_dir():
                    state_file = sprint_dir / "state.json"
                    if state_file.exists():
                        sprints.append(sprint_dir.name)
        except (OSError, IOError, PermissionError):
            pass
        return sorted(sprints)
    
    # DEPRECATED: Old project-based methods still available for backward compatibility
    # until full migration is complete
```

#### 4.2.3 `bot.py` Changes

```python
class CarbyBot:
    # NEW: Sprint-aware methods replacing project-based ones
    
    def dispatch_gate(self, sprint: str, gate_number: int) -> CLIResult:
        """Dispatch a specific gate."""
        return self.cli_executor.gate(sprint, gate_number)
    
    def start_sprint(self, sprint: str, mode: str = "sequential") -> CLIResult:
        """Start a sprint."""
        return self.cli_executor.start(sprint, mode)
    
    def pause_sprint(self, sprint: str) -> CLIResult:
        """Pause a sprint."""
        return self.cli_executor.pause(sprint)
    
    def resume_sprint(self, sprint: str) -> CLIResult:
        """Resume a sprint."""
        return self.cli_executor.resume(sprint)
    
    def cancel_sprint(self, sprint: str) -> CLIResult:
        """Cancel a sprint."""
        return self.cli_executor.cancel(sprint)
    
    def approve_phase(self, sprint: str, phase_id: Optional[str] = None) -> CLIResult:
        """Approve specific phase."""
        return self.cli_executor.approve(sprint, phase_id)
    
    # MODIFIED: Existing methods adapted to work with sprints instead of projects
    def get_sprint_detail(self, sprint: str) -> Optional[str]:
        """Get formatted sprint detail."""
        summary = self.state_manager.get_sprint_summary(sprint)
        if not summary:
            return None
        return self.notification_service.format_sprint_detail(summary)
```

---

## 5. UI/UX Updates

### 5.1 Telegram Interface Changes

#### 5.1.1 Main Menu Updates

| Button | Old Behavior | New Behavior |
|--------|--------------|--------------|
| 📋 Projects | Listed projects | Lists sprints (still shows as "projects" to user for consistency) |
| ⚙️ More | Same options | Same options |

#### 5.1.2 Project Detail → Sprint Detail

| Section | Old Content | New Content |
|---------|-------------|-------------|
| Header | Project ID, Goal | Sprint ID, Project, Goal |
| Status | Current Stage | Current Gate, Current Phase |
| Progress | Stage-by-stage | Gate-by-gate with phase details |

#### 5.1.3 New Buttons/Actions

| Button | Purpose | New Callback |
|--------|---------|--------------|
| 🚀 Start Sprint | Begin sprint execution | `start:<sprint>` |
| 🎯 Advance Gate | Move to next gate | `gate:<sprint>:<next_gate>` |
| ⏭️ Skip Gate | Skip current gate | `skip-gate:<sprint>:<gate>` |
| 🔄 Retry Gate | Retry current gate | `retry-gate:<sprint>:<gate>` |
| ⏸️ Pause | Pause sprint | `pause:<sprint>` |
| ▶️ Resume | Resume sprint | `resume:<sprint>` |
| ❌ Cancel | Cancel sprint | `cancel:<sprint>` |
| 📋 Phase Status | View phase details | `phase-status:<sprint>` |

#### 5.1.2 Updated Action Flows

**Old Flow:** Project → Stage → Approve Stage → Next Stage  
**New Flow:** Sprint → Gate → Phase → Approve Phase → Next Phase → Next Gate

**Phase Approval Workflow:**
1. Sprint reaches gate with multiple phases
2. Phases execute (possibly in parallel)
3. User sees phase status in detail view
4. User can approve individual phases with `approve-phase:<sprint>:<phase>`
5. Once all phases in gate are approved, advance to next gate

### 5.2 Loading Indicators Update

Loading indicators need to be updated to reflect new terminology:

- `dispatch` → `start` or `gate`
- `approve` → `approve-phase`
- `stop` → `pause`

### 5.3 Error Messages Update

All error messages need to be updated to use sprint terminology instead of project terminology.

---

## 6. Implementation Plan

### Phase 1: Core CLI Wrapper Update (Days 1-2)

**Objective:** Replace all `carby-studio` CLI calls with `carby-sprint` equivalents

**Tasks:**
1. Update `cli_executor.py` with new command mappings
2. Add validation for sprint names and gate numbers
3. Implement new methods for sprint-specific commands
4. Maintain backward compatibility temporarily
5. Add unit tests for new CLI methods

**Deliverables:**
- Updated `cli_executor.py`
- Unit test suite
- CLI integration tests

### Phase 2: State Manager Adaptation (Days 2-3)

**Objective:** Migrate state reading/writing to new sprint-based structure

**Tasks:**
1. Update `state_manager.py` to read from `.carby-sprints/`
2. Create new data structures for sprint/phase state
3. Maintain backward compatibility with old project structure
4. Update caching mechanism for new state structure
5. Add migration utilities for existing projects

**Deliverables:**
- Updated `state_manager.py`
- Migration script for existing projects
- Updated cache system

### Phase 3: Telegram UI Updates (Days 3-5)

**Objective:** Update Telegram interface to use sprint terminology and features

**Tasks:**
1. Update `telegram_interface.py` with new buttons/callbacks
2. Modify project detail view to show sprint/phase information
3. Add new action handlers for sprint-specific commands
4. Update loading indicators and status messages
5. Create phase approval workflow
6. Update error handling and messages

**Deliverables:**
- Updated `telegram_interface.py`
- Updated `bot.py` action handlers
- New sprint detail views

### Phase 4: Testing & Validation (Days 5-6)

**Objective:** Ensure all functionality works correctly with new sprint model

**Tasks:**
1. End-to-end testing of all bot commands
2. Migration testing with existing projects
3. Phase approval workflow testing
4. Error condition testing
5. Performance testing
6. User acceptance testing

**Deliverables:**
- Test execution report
- Migration validation report
- Performance benchmarks

### Phase 5: Production Deployment (Day 6)

**Objective:** Deploy updated bot to production

**Tasks:**
1. Deploy updated code
2. Run migration script for existing projects
3. Monitor for issues
4. Update documentation
5. Train users on new features

---

## 7. Risk Assessment

### 7.1 Potential Issues

| Risk | Impact | Probability | Mitigation Strategy |
|------|--------|-------------|-------------------|
| **Breaking Changes** | High | Medium | Maintain backward compatibility during transition |
| **State Migration** | High | Low | Comprehensive migration script with rollback |
| **User Confusion** | Medium | Medium | Clear communication about terminology changes |
| **API Incompatibility** | High | Low | Thorough testing before deployment |
| **Performance Degradation** | Medium | Low | Performance testing during Phase 4 |

### 7.2 Mitigation Strategies

**Backward Compatibility:**
- Maintain old project-based methods during transition
- Allow gradual migration of existing projects
- Provide clear upgrade path

**Data Safety:**
- Backup all project state before migration
- Implement transaction-like operations for critical changes
- Test migration on staging environment first

**User Experience:**
- Maintain familiar terminology in UI despite internal changes
- Provide clear explanations for new features
- Offer training resources for advanced features

### 7.3 Rollback Plan

If migration fails critically:

1. **Immediate Response:** Switch bot back to old carby-studio CLI
2. **Data Recovery:** Restore from pre-migration backups
3. **Communication:** Notify users of temporary service disruption
4. **Analysis:** Identify root cause and develop fix
5. **Retry:** Schedule new migration window

---

## 8. Success Criteria

### 8.1 Functional Requirements

| Requirement | Test Scenario | Success Criteria |
|-------------|---------------|------------------|
| **Sprint Creation** | Create new sprint via CLI and verify in bot | Sprint appears in bot projects list |
| **Gate Advancement** | Start sprint, advance through gates | Gates complete successfully |
| **Phase Approval** | Execute phase, approve, advance | Individual phases can be approved |
| **Sprint Management** | Pause, resume, cancel sprints | All lifecycle operations work |
| **Status Reporting** | Check sprint status via bot | Accurate status information displayed |
| **Error Handling** | Trigger various error conditions | Appropriate error messages shown |

### 8.2 Non-Functional Requirements

| Requirement | Metric | Target |
|-------------|--------|--------|
| **Performance** | Command response time | < 2 seconds average |
| **Reliability** | Successful command execution | > 99% success rate |
| **Availability** | Bot uptime | > 99.5% uptime |
| **Migration** | Existing project migration | 100% of projects migrated successfully |

### 8.3 User Acceptance Criteria

- Users can create and manage sprints through bot
- Phase-level approval workflow is intuitive
- All existing functionality remains available
- New features enhance rather than complicate workflow
- Migration from old projects is seamless

---

## 9. Conclusion

This migration represents a significant enhancement to the TintinBot functionality, aligning it with the latest Carby Studio architecture. The transition from project-based to sprint-based execution provides:

- More granular control over development workflows
- Better visibility into execution progress
- Enhanced approval mechanisms
- Improved state management

The proposed implementation plan balances feature enhancement with risk mitigation, ensuring a smooth transition for existing users while unlocking new capabilities. With proper testing and phased rollout, this migration will position TintinBot as a powerful interface for the modern Carby Studio experience.

**Next Steps:**
1. Review and approve this proposal
2. Schedule migration timeline
3. Begin Phase 1 implementation
4. Conduct user training on new features