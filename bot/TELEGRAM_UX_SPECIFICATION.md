# Carby Studio Telegram Bot — UX Specification v2.0
## Instant-Feedback Menu System

---

## 🎯 Design Principles

### 1. **Instant Feedback First**
- Every button click must provide immediate visual response
- Use `callback_query.answer()` with loading messages
- Update existing messages instead of sending new ones
- Show progress indicators for async operations

### 2. **Zero Typing Required**
- Every action has a corresponding button
- Use inline keyboards for all interactions
- Persistent reply keyboards only for main navigation
- Input via button selection, never free-form text

### 3. **Mobile-Optimized**
- Max 2 buttons per row (thumb-friendly)
- Critical actions on the right (easier to reach)
- Compact text (Telegram mobile truncates at ~200 chars)
- Emoji indicators for instant recognition

### 4. **Context Preservation**
- Never lose user's place in the menu hierarchy
- Breadcrumbs in message headers
- "Back" buttons always available
- State remembered across interactions

---

## 📱 Menu Flow Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  LEVEL 1: GREETING / MAIN MENU                                   │
├─────────────────────────────────────────────────────────────────┤
│  🏠 Entry point after /start or "← Back to Main"                │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  🤖 Carby Studio                                        │    │
│  │  ─────────────────                                      │    │
│  │  Welcome back, Vincent!                                 │    │
│  │                                                         │    │
│  │  📊 Quick Stats:                                        │    │
│  │  • 3 active sprints                                     │    │
│  │  • 1 awaiting approval                                  │    │
│  │  • 0 failed today                                       │    │
│  │                                                         │    │
│  │  ┌────────────┐  ┌────────────┐                         │    │
│  │  │ 📋 Projects│  │ ➕ New     │                         │    │
│  │  └────────────┘  │   Sprint   │                         │    │
│  │                  └────────────┘                         │    │
│  │                                                         │    │
│  │  ┌────────────┐  ┌────────────┐                         │    │
│  │  │ 🔔 Notifs  │  │ ⚙️ More    │                         │    │
│  │  │  (3 new)   │  │            │                         │    │
│  │  └────────────┘  └────────────┘                         │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  🔘 Reply Keyboard: [📋 Projects] [⚙️ More]                      │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  LEVEL 2: PROJECTS LIST                                          │
├─────────────────────────────────────────────────────────────────┤
│  📋 Shows all sprints with status indicators                     │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  📋 Your Sprints (5)                                    │    │
│  │  ─────────────────                                      │    │
│  │                                                         │    │
│  │  ┌────────────────┐ ┌────────────────┐                 │    │
│  │  │ 🔄 family-photo│ │ ⏸️ karina-photo│                 │    │
│  │  │    -hub        │ │    -pipeline   │                 │    │
│  │  └────────────────┘ └────────────────┘                 │    │
│  │                                                         │    │
│  │  ┌────────────────┐ ┌────────────────┐                 │    │
│  │  │ ❌ time-fetcher│ │ ✅ photo-archive│                 │    │
│  │  └────────────────┘ └────────────────┘                 │    │
│  │                                                         │    │
│  │  ┌────────────────┐ ┌────────────────┐                 │    │
│  │  │ ⬜ new-project │ │ ⬜ alpha-hunter │                 │    │
│  │  └────────────────┘ └────────────────┘                 │    │
│  │                                                         │    │
│  │  ┌────────────────────────────────┐                    │    │
│  │  │     ← Back to Main Menu        │                    │    │
│  │  └────────────────────────────────┘                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Status Icons: 🔄 in-progress │ ⏸️ paused │ ✅ done            │
│                ❌ failed      │ ⬜ pending │ 🟡 needs approval  │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│  LEVEL 3: PROJECT DETAIL / ACTIONS                               │
├─────────────────────────────────────────────────────────────────┤
│  📊 Full sprint status with contextual action buttons            │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  📋 family-photo-hub                                    │    │
│  │  ─────────────────                                      │    │
│  │  🎯 Photo management for Sony a7c2 & iPhone             │    │
│  │  📦 Project: family-projects                            │    │
│  │  📅 Created: 2026-03-28                                 │    │
│  │                                                         │    │
│  │  Gates & Phases:                                        │    │
│  │  ✅ Discover                                            │    │
│  │    ✓ research  ✓ requirements                           │    │
│  │  ✅ Design                                              │    │
│  │    ✓ architecture  ✓ ui-design                          │    │
│  │  🔄 Build ← CURRENT                                     │    │
│  │    ◉ coding (in-progress)                               │    │
│  │    ◯ testing (pending)                                  │    │
│  │  ⬜ Verify                                              │    │
│  │  ⬜ Deliver                                             │    │
│  │                                                         │    │
│  │  ┌────────────┐  ┌────────────┐                         │    │
│  │  │ ⏸️ Pause   │  │ 📋 Logs    │                         │    │
│  │  └────────────┘  └────────────┘                         │    │
│  │                                                         │    │
│  │  ┌────────────┐  ┌────────────┐                         │    │
│  │  │ ✏️ Rename  │  │ 🗑️ Delete  │                         │    │
│  │  └────────────┘  └────────────┘                         │    │
│  │                                                         │    │
│  │  ┌────────────────────────────────┐                    │    │
│  │  │     ← Back to Projects         │                    │    │
│  │  └────────────────────────────────┘                    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
┌───────────────────────┐ ┌───────────────┐ ┌───────────────────┐
│ LEVEL 4a: CONFIRM     │ │ LEVEL 4b:     │ │ LEVEL 4c:         │
│ SCREEN (Destructive)  │ │ SELECTION     │ │ INPUT DIALOG      │
├───────────────────────┤ ├───────────────┤ ├───────────────────┤
│                       │ │               │ │                   │
│ ┌─────────────────┐   │ │ ┌─────────┐   │ │ ┌─────────────┐   │
│ │ ⚠️ Delete       │   │ │ │ 🏃 Quick│   │ │ │ ➕ New Sprint│   │
│ │ family-photo-   │   │ │ │         │   │ │ │             │   │
│ │ hub?            │   │ │ ├─────────┤   │ │ ├─────────────┤   │
│ │                 │   │ │ │ 📐 Full │   │ │ │ Choose mode:│   │
│ │ This cannot be  │   │ │ │ Pipeline│   │ │ │             │   │
│ │ undone.         │   │ │ │         │   │ │ │ ┌────────┐  │   │
│ │                 │   │ │ └─────────┘   │ │ │ │🏃 Quick│  │   │
│ │ Type DELETE to  │   │ │               │ │ │ └────────┘  │   │
│ │ confirm:        │   │ │               │ │ │ ┌────────┐  │   │
│ │                 │   │ │               │ │ │ │📐 Full │  │   │
│ │ [__________]    │   │ │               │ │ │ └────────┘  │   │
│ │                 │   │ │               │ │ │             │   │
│ │ ┌────┐ ┌────┐   │   │ │               │ │ │ [Cancel]    │   │
│ │ │✅  │ │❌  │   │   │ │               │ │ └─────────────┘   │
│ │ │Yes │ │No  │   │   │ │               │ │                   │
│ │ └────┘ └────┘   │   │ │               │ │                   │
│ └─────────────────┘   │ │               │ │                   │
│                       │ │               │ │                   │
└───────────────────────┘ └───────────────┘ └───────────────────┘

---

## ⚡ Instant Feedback Patterns

### Pattern 1: Loading State on Button Click
```python
# IMMEDIATE feedback (within 100ms)
async def handle_action(query, ...):
    # 1. Answer callback immediately (stops button "spinning")
    await query.answer("⏳ Processing...")  # Shows toast
    
    # 2. Update message to show loading
    await query.edit_message_text(
        "⏳ Processing your request...\n"
        "🔄 family-photo-hub: Pausing sprint",
        reply_markup=None  # Remove buttons during processing
    )
    
    # 3. Do the work
    result = await async_operation()
    
    # 4. Update with result
    await query.edit_message_text(
        f"✅ Sprint paused successfully!\n\n"
        f"📋 family-photo-hub\n"
        f"Status: ⏸️ Paused",
        reply_markup=resume_keyboard
    )
```

### Pattern 2: State-Based Button Availability
```python
# Buttons change based on current state
STATE_BUTTONS = {
    "pending": [
        ["▶️ Start", "⏭️ Skip"],
        ["✏️ Rename", "🗑️ Delete"],
        ["← Back"]
    ],
    "in-progress": [
        ["⏸️ Pause", "📋 Logs"],
        ["🛑 Stop", "💬 Message"],
        ["← Back"]
    ],
    "completed": [
        ["✅ Approve", "🔄 Retry"],
        ["📖 Review", "📋 Logs"],
        ["← Back"]
    ],
    "failed": [
        ["🔄 Retry", "⏭️ Skip"],
        ["📋 Logs", "🛑 Stop"],
        ["← Back"]
    ],
    "paused": [
        ["▶️ Resume", "⏸️ Keep Paused"],
        ["📋 Logs", "❌ Cancel"],
        ["← Back"]
    ]
}
```

### Pattern 3: Progress Indicators
```python
# Animated progress for long operations
PROGRESS_FRAMES = ["⬜⬜⬜⬜⬜", "🟨⬜⬜⬜⬜", "🟩🟨⬜⬜⬜", 
                   "🟩🟩🟨⬜⬜", "🟩🟩🟩🟨⬜", "🟩🟩🟩🟩🟨", "🟩🟩🟩🟩🟩"]

async def show_progress(query, operation_name, steps):
    for i, frame in enumerate(PROGRESS_FRAMES):
        await query.edit_message_text(
            f"{frame}\n"
            f"{operation_name}... ({i+1}/{len(PROGRESS_FRAMES)})",
            reply_markup=None
        )
        await asyncio.sleep(0.3)
```

---

## 🎨 Button Layout Specifications

### Standard Button Grid
```
Mobile-optimized 2-column layout:
┌────────────────┬────────────────┐
│   Primary      │  Secondary     │
│   Action       │  Action        │
├────────────────┼────────────────┤
│   Contextual   │  Contextual    │
│   Action       │  Action        │
├────────────────┴────────────────┤
│      ← Back to [Parent]          │
└─────────────────────────────────┘
```

### Button Priority Rules
1. **Primary action** (most likely next step) → Top-left
2. **Secondary action** (alternative) → Top-right
3. **Destructive actions** → Bottom row, right side
4. **Navigation** → Always full-width bottom

### Button Text Guidelines
```
✅ Good: "▶️ Start Gate"     (11 chars + emoji)
✅ Good: "⏸️ Pause"          (8 chars + emoji)
✅ Good: "🔄 Retry Build"    (13 chars + emoji)

❌ Bad:  "Click here to start the gate"  (too long)
❌ Bad:  "Start"               (ambiguous)
❌ Bad:  "🔄"                  (emoji only)

Max recommended: 20 characters including emoji
```

---

## 🔄 Transition Animations

### Message Update Strategy
```python
# Use edit_message_text for instant transitions
# Never send new messages for menu navigation

class MenuTransition:
    """Edit existing message instead of sending new ones."""
    
    async def navigate_to(self, query, new_content, new_keyboard):
        # Same message ID, new content = instant feel
        await query.edit_message_text(
            text=new_content,
            reply_markup=new_keyboard,
            parse_mode="Markdown"
        )
        
    async def show_loading(self, query, action):
        # Temporary loading state
        await query.edit_message_text(
            text=f"⏳ {action}...",
            reply_markup=None  # No buttons during loading
        )
        
    async def show_result(self, query, result, keyboard):
        # Final state
        await query.edit_message_text(
            text=result,
            reply_markup=keyboard
        )
```

### Transition Timing
```
User clicks → Bot responds
    │              │
    │              ├──→ 0ms: query.answer() (stops spinner)
    │              ├──→ 50ms: edit_message_text (loading state)
    │              ├──→ 100-500ms: Process operation
    │              └──→ 500ms+: edit_message_text (result)
    │
    └──→ Total perceived delay: <100ms (instant feel)
```

---

## 📋 Complete State Flow Examples

### Example 1: Starting a Sprint
```
User taps [▶️ Start Gate] on pending sprint
         │
         ▼
┌─────────────────────────────┐
│ ⏳ Starting gate...         │  ← Immediate (50ms)
│ 🔄 Initializing agent       │
└─────────────────────────────┘
         │
         ▼ (after 2-3 seconds)
┌─────────────────────────────┐
│ ✅ Gate started!            │  ← Result
│                             │
│ 📋 family-photo-hub         │
│ Status: 🔄 In Progress      │
│ Agent: code-agent           │
│ Started: just now           │
│                             │
│ [⏸️ Pause] [📋 Logs]       │
│ [🛑 Stop] [← Back]         │
└─────────────────────────────┘
```

### Example 2: Approving a Completed Gate
```
User taps [✅ Approve] on completed gate
         │
         ▼
┌─────────────────────────────┐
│ ⏳ Approving...             │  ← Immediate
└─────────────────────────────┘
         │
         ▼ (after 1 second)
┌─────────────────────────────┐
│ ✅ Gate approved!           │  ← Result
│                             │
│ Next: Build phase ready     │
│                             │
│ [▶️ Start Build]            │
│ [⏭️ Skip] [← Back]         │
└─────────────────────────────┘
```

### Example 3: Handling Failure
```
User taps [🔄 Retry] on failed gate
         │
         ▼
┌─────────────────────────────┐
│ ⏳ Retrying...              │  ← Immediate
└─────────────────────────────┘
         │
         ▼ (after processing)
┌─────────────────────────────┐
│ ✅ Retry successful!        │  ← Success
│                             │
│ OR                          │
│                             │
│ ❌ Retry failed             │  ← Failure
│ Error: Tests still failing  │
│                             │
│ [🔄 Retry Again] [📋 Logs] │
│ [← Back]                   │
└─────────────────────────────┘
```

---

## 🎛️ Implementation Code Patterns

### Pattern A: Instant Button Handler
```python
async def handle_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any button click with instant feedback."""
    query = update.callback_query
    
    # 1. IMMEDIATE: Stop the loading spinner
    await query.answer()
    
    # Parse callback data
    data = query.data
    action, entity_type, entity_id = data.split(":")
    
    # 2. IMMEDIATE: Show loading state
    loading_text = get_loading_message(action)
    await query.edit_message_text(
        text=f"⏳ {loading_text}...",
        reply_markup=None  # Remove buttons during processing
    )
    
    try:
        # 3. PROCESS: Do the actual work
        result = await execute_action(action, entity_id)
        
        # 4. RESULT: Show success with new buttons
        success_text, success_keyboard = build_result_view(result)
        await query.edit_message_text(
            text=success_text,
            reply_markup=success_keyboard,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        # 4. ERROR: Show error with retry options
        error_text, error_keyboard = build_error_view(e)
        await query.edit_message_text(
            text=error_text,
            reply_markup=error_keyboard,
            parse_mode="Markdown"
        )
```

### Pattern B: State Machine for Menu Flow
```python
class MenuStateMachine:
    """Track user menu state for instant navigation."""
    
    STATES = {
        "main": {
            "message": "main_menu",
            "keyboard": MAIN_KEYBOARD,
            "parent": None
        },
        "projects": {
            "message": "projects_list",
            "keyboard": PROJECTS_KEYBOARD,
            "parent": "main"
        },
        "project_detail": {
            "message": "project_detail",
            "keyboard": DYNAMIC_KEYBOARD,  # Based on state
            "parent": "projects"
        },
        "confirm": {
            "message": "confirm_dialog",
            "keyboard": CONFIRM_KEYBOARD,
            "parent": "project_detail"
        }
    }
    
    def __init__(self):
        self.user_states = {}  # user_id -> state
    
    def transition(self, user_id, new_state, **context):
        """Transition to new state, return render params."""
        self.user_states[user_id] = {
            "state": new_state,
            "context": context,
            "timestamp": time.time()
        }
        return self.STATES[new_state]
    
    def go_back(self, user_id):
        """Go to parent state."""
        current = self.user_states.get(user_id, {}).get("state")
        parent = self.STATES.get(current, {}).get("parent")
        if parent:
            return self.transition(user_id, parent)
        return None
```

### Pattern C: Optimized Keyboard Builder
```python
def build_action_keyboard(entity_id: str, status: str) -> InlineKeyboardMarkup:
    """Build context-aware action buttons."""
    buttons = []
    
    # Row 1: Primary actions based on status
    if status == "pending":
        buttons.append([
            InlineKeyboardButton("▶️ Start", callback_data=f"start:{entity_id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{entity_id}")
        ])
    elif status == "in-progress":
        buttons.append([
            InlineKeyboardButton("⏸️ Pause", callback_data=f"pause:{entity_id}"),
            InlineKeyboardButton("📋 Logs", callback_data=f"logs:{entity_id}")
        ])
    elif status == "completed":
        buttons.append([
            InlineKeyboardButton("✅ Approve", callback_data=f"approve:{entity_id}"),
            InlineKeyboardButton("🔄 Retry", callback_data=f"retry:{entity_id}")
        ])
    elif status == "failed":
        buttons.append([
            InlineKeyboardButton("🔄 Retry", callback_data=f"retry:{entity_id}"),
            InlineKeyboardButton("⏭️ Skip", callback_data=f"skip:{entity_id}")
        ])
        buttons.append([
            InlineKeyboardButton("📋 Logs", callback_data=f"logs:{entity_id}")
        ])
    elif status == "paused":
        buttons.append([
            InlineKeyboardButton("▶️ Resume", callback_data=f"resume:{entity_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"cancel:{entity_id}")
        ])
    
    # Row 2-3: Management actions
    buttons.append([
        InlineKeyboardButton("✏️ Rename", callback_data=f"rename:{entity_id}"),
        InlineKeyboardButton("🗑️ Delete", callback_data=f"delete:{entity_id}")
    ])
    
    # Row 4: Navigation
    buttons.append([
        InlineKeyboardButton("← Back to Projects", callback_data="back:projects")
    ])
    
    return InlineKeyboardMarkup(buttons)
```

---

## 📱 Mobile-Specific Optimizations

### Touch Target Sizing
```
Telegram button constraints:
- Minimum height: 48px (automatic)
- Recommended text: 15-20 chars
- Max buttons per row: 2 (mobile), 3 (tablet/desktop)
- Padding: Built into Telegram's rendering
```

### Thumb Zone Optimization
```
┌─────────────────────────────┐
│         HARD TO REACH       │  ← Top 25% of screen
│    (requires hand movement) │
├─────────────────────────────┤
│                             │
│      EASY TO REACH          │  ← Middle 50%
│      (natural thumb zone)   │
│                             │
├─────────────────────────────┤
│      EASY TO REACH          │  ← Bottom 25%
│      (resting position)     │
└─────────────────────────────┘

Button placement strategy:
- Primary actions: Middle or bottom
- Secondary actions: Middle
- Destructive actions: Top (harder to hit accidentally)
- Navigation: Bottom (always accessible)
```

### Message Length Guidelines
```
Maximum visible text (mobile, without scrolling):
- iPhone SE: ~800 chars
- iPhone 12/13/14: ~1200 chars
- iPhone Pro Max: ~1500 chars

Recommended: Keep under 800 chars for instant comprehension
```

---

## 🧪 Testing Checklist

### Instant Feedback Tests
- [ ] Button click shows response within 100ms
- [ ] Loading state appears immediately
- [ ] No "spinning" button state lasts >500ms
- [ ] Result replaces loading state smoothly

### Navigation Tests
- [ ] Back button works from every screen
- [ ] Menu depth never exceeds 4 levels
- [ ] State is preserved on back navigation
- [ ] No duplicate messages created

### Mobile Tests
- [ ] All buttons reachable with one hand
- [ ] No horizontal scrolling required
- [ ] Text readable without zooming
- [ ] Works on iPhone SE (smallest screen)

### Zero-Typing Tests
- [ ] Every action has a button
- [ ] No commands required after /start
- [ ] Confirmation uses buttons, not text input
- [ ] Selection uses inline keyboards

---

## 📊 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Button Response Time | <100ms | Time from click to visual feedback |
| Menu Navigation Time | <2s | Time to reach any screen |
| Typing Required | 0% | Actions completed without typing |
| Error Recovery | <3s | Time to retry after failure |
| User Satisfaction | >4.5/5 | Subjective rating |

---

## 🔄 Comparison: Old vs New UX

### Old Flow (Current)
```
User: /start
Bot: [New message] Welcome!
User: 📋 Projects (button)
Bot: [New message] Here are your projects...
User: Clicks project
Bot: [New message] Project details...
User: Clicks action
Bot: [New message] Processing...
Bot: [Another message] Result!

Problems:
- 6+ messages for simple flow
- Chat gets cluttered
- No instant feedback
- Requires scrolling
```

### New Flow (Optimized)
```
User: /start
Bot: [Single message] Main menu
User: 📋 Projects (button)
Bot: [Edits same message] Projects list
User: Clicks project
Bot: [Edits same message] Project details
User: Clicks action
Bot: [Edits same message] ⏳ Loading...
Bot: [Edits same message] ✅ Result!

Benefits:
- 1 message throughout
- Clean chat history
- Instant feedback
- Always in context
```

---

## 🚀 Migration Path

### Phase 1: Core Navigation (Week 1)
1. Implement `edit_message_text` for all menu transitions
2. Add loading states to all async operations
3. Update button layouts to 2-column mobile format

### Phase 2: State Management (Week 2)
1. Implement `MenuStateMachine` for tracking
2. Add back button functionality
3. Optimize message content length

### Phase 3: Polish (Week 3)
1. Add progress animations
2. Implement error recovery flows
3. Mobile testing and refinement

---

*Specification Version: 2.0*
*Last Updated: 2026-03-28*
*Author: UX Design Sub-Agent*
