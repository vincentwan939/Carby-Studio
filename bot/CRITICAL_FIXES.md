# Critical Fixes Required Before Deployment
## Carby Studio Telegram Bot

---

## 🔴 CRITICAL (Must Fix Before Any Deployment)

### FIX-1: Command Injection Vulnerability
**File:** `cli_executor.py`  
**Severity:** HIGH  
**Risk:** Malicious project names could execute arbitrary commands

**Current Code:**
```python
def dispatch(self, project: str, stage: str) -> CLIResult:
    command = ["carby-studio", "dispatch", project, stage]
    return self._run(command)
```

**Problem:** If `project` contains shell metacharacters (e.g., "; rm -rf /"), it could inject commands.

**Fix:**
```python
def dispatch(self, project: str, stage: str) -> CLIResult:
    # Validate inputs before passing to shell
    valid, error = self.validate_project_name(project)
    if not valid:
        return CLIResult(False, "", error, 1, "dispatch")
    
    # Additional safety: only allow alphanumeric, hyphens
    if not re.match(r'^[a-z0-9-]+$', project):
        return CLIResult(False, "", "Invalid project name format", 1, "dispatch")
    
    command = ["carby-studio", "dispatch", project, stage]
    return self._run(command)
```

**Apply to:** All methods that accept project/stage names (`dispatch`, `skip`, `retry`, `rename`, `delete`, `status`, `approve`, `stop`, `logs`)

---

### FIX-2: Permanent Delete Without Backup
**File:** `cli_executor.py` ( `_manual_delete` method)  
**Severity:** HIGH  
**Risk:** Accidental deletion is irreversible

**Current Code:**
```python
def _manual_delete(self, project: str) -> CLIResult:
    json_file.unlink()  # Permanent delete
    shutil.rmtree(project_dir)  # Permanent delete
```

**Fix Options:**

**Option A: Move to Trash (macOS)**
```python
def _manual_delete(self, project: str) -> CLIResult:
    import subprocess
    from datetime import datetime
    
    json_file = Config.PROJECTS_DIR / f"{project}.json"
    project_dir = Config.PROJECTS_DIR / project
    
    # Move to trash using osascript
    try:
        if json_file.exists():
            subprocess.run([
                "osascript", "-e",
                f'tell application "Finder" to delete POSIX file "{json_file}"'
            ], check=True, capture_output=True)
        
        if project_dir.exists():
            subprocess.run([
                "osascript", "-e",
                f'tell application "Finder" to delete POSIX file "{project_dir}"'
            ], check=True, capture_output=True)
        
        return CLIResult(True, f"Moved {project} to trash", "", 0, f"delete {project}")
    except Exception as e:
        return CLIResult(False, "", str(e), 1, f"delete {project}")
```

**Option B: Backup Before Delete**
```python
def _manual_delete(self, project: str) -> CLIResult:
    import shutil
    from datetime import datetime
    
    backup_dir = Config.CACHE_DIR / "deleted_projects" / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    json_file = Config.PROJECTS_DIR / f"{project}.json"
    project_dir = Config.PROJECTS_DIR / project
    
    try:
        # Backup before delete
        if json_file.exists():
            shutil.copy2(json_file, backup_dir / f"{project}.json")
            json_file.unlink()
        
        if project_dir.exists():
            shutil.copytree(project_dir, backup_dir / project)
            shutil.rmtree(project_dir)
        
        return CLIResult(
            True, 
            f"Deleted {project} (backup at {backup_dir})", 
            "", 
            0, 
            f"delete {project}"
        )
    except Exception as e:
        return CLIResult(False, "", str(e), 1, f"delete {project}")
```

**Recommendation:** Option B (backup) - gives user recovery option

---

### FIX-3: Missing Global Error Handler
**File:** `telegram_interface.py` ( `run()` method)  
**Severity:** HIGH  
**Risk:** Unhandled exceptions crash the bot

**Current Code:**
```python
def run(self):
    application = Application.builder().token(self.token).build()
    # ... handlers ...
    application.run_polling()
```

**Fix:**
```python
def run(self):
    application = Application.builder().token(self.token).build()
    
    # Add global error handler
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Exception while handling update: {context.error}")
        
        # Log full traceback
        import traceback
        tb = traceback.format_exc()
        logger.error(tb)
        
        # Notify user if possible
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ An error occurred. The team has been notified.\n"
                "Please try again or contact support if the issue persists."
            )
        
        # Could also send alert to admin here
    
    application.add_error_handler(error_handler)
    
    # ... existing handlers ...
    application.run_polling()
```

---

## 🟡 HIGH (Fix Before Beta)

### FIX-4: Thread Leak on Double-Start
**File:** `bot.py` ( `start()` method)  
**Severity:** MEDIUM  
**Risk:** Multiple polling threads could run simultaneously

**Current Code:**
```python
def start(self):
    self._running = True
    self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
    self._poll_thread.start()
```

**Fix:**
```python
def start(self):
    if self._running:
        logger.warning("Bot already running, ignoring start() call")
        return
    
    if self._poll_thread and self._poll_thread.is_alive():
        logger.warning("Polling thread already exists, ignoring start() call")
        return
    
    logger.info("Starting Carby Bot...")
    self._running = True
    self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
    self._poll_thread.start()
    logger.info("Bot started")
```

---

### FIX-5: Cache Race Condition
**File:** `state_manager.py` ( `detect_changes()` method)  
**Severity:** MEDIUM  
**Risk:** State loss if crash between change detection and cache save

**Fix:** Use atomic write for cache
```python
def _save_cache(self):
    """Save cache to disk atomically."""
    try:
        Config.ensure_directories()
        temp_file = self.cache_file.with_suffix('.tmp')
        
        # Write to temp file first
        with open(temp_file, 'w') as f:
            json.dump(self._cache, f, indent=2)
        
        # Atomic rename
        temp_file.rename(self.cache_file)
        
    except Exception as e:
        logger.error(f"Failed to save cache: {e}")
```

---

## 🟢 MEDIUM (Fix Before Production)

### FIX-6: Hard-coded Timeouts
**File:** `cli_executor.py`  
**Severity:** MEDIUM  
**Risk:** Long operations may timeout unnecessarily

**Fix:** Make configurable per command
```python
# In config.py
CLI_TIMEOUTS = {
    "dispatch": 300,   # 5 minutes for dispatch
    "skip": 60,
    "retry": 300,
    "status": 30,
    "rename": 60,
    "delete": 60,
}

# In cli_executor.py
def _run(self, command: list, timeout: int = None) -> CLIResult:
    cmd_name = command[1] if len(command) > 1 else "unknown"
    timeout = timeout or CLI_TIMEOUTS.get(cmd_name, 60)
    # ... rest of method
```

---

### FIX-7: No Retry Logic
**File:** `cli_executor.py`  
**Severity:** MEDIUM  
**Risk:** Transient failures require manual retry

**Fix:** Add retry decorator
```python
import functools
import time

def retry_on_failure(max_retries=3, delay=1):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                result = func(*args, **kwargs)
                if result.success:
                    return result
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # Exponential backoff
            return result
        return wrapper
    return decorator

# Usage
@retry_on_failure(max_retries=3, delay=2)
def dispatch(self, project: str, stage: str) -> CLIResult:
    # ... existing code
```

---

## Implementation Priority

```
Week 1 (Critical):
├── FIX-1: Command injection protection
├── FIX-2: Backup before delete
└── FIX-3: Global error handler

Week 2 (Beta Prep):
├── FIX-4: Thread leak protection
├── FIX-5: Atomic cache writes
└── Security audit

Week 3 (Production Prep):
├── FIX-6: Configurable timeouts
├── FIX-7: Retry logic
└── Performance testing
```

---

## Verification Checklist

After implementing fixes, verify:

- [ ] FIX-1: Attempt injection with `project="; echo hacked"` - should be rejected
- [ ] FIX-2: Delete project - verify backup exists in cache/deleted_projects/
- [ ] FIX-3: Raise exception in handler - verify error message sent to user
- [ ] FIX-4: Call start() twice - verify only one thread created
- [ ] FIX-5: Kill bot mid-operation - verify cache integrity on restart
- [ ] FIX-6: Set timeout to 1s - verify timeout occurs
- [ ] FIX-7: Simulate failure - verify retry occurs

---

**Document Version:** 1.0  
**Priority:** CRITICAL  
**Estimated Effort:** 2-3 days for all critical fixes
