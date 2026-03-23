# Carby Sprint CLI Reference

Complete reference for the `carby-sprint` command-line interface.

---

## doctor

Diagnose Carby Studio setup and configuration.

```bash
carby-sprint doctor [--fix]
```

**Checks:**
- Python version (3.11+)
- carby-sprint in PATH
- OpenClaw configuration
- Git availability
- Write permissions to workspace
- Dependencies installed

**Options:**
- `--fix` — Attempt to fix issues automatically (shows fix commands)

**Exit codes:**
- `0` — All checks passed
- `1` — One or more issues found

**Example:**
```bash
$ carby-sprint doctor

🔍 Carby Studio Doctor

✅ Python version: Python 3.11.0
✅ CLI in PATH: carby-sprint found in PATH
✅ OpenClaw config: Config at /Users/.../.openclaw/config.json
✅ Git: Git available
✅ Write permissions: Can write to /Users/.../.openclaw/workspace
✅ Dependencies: All dependencies installed

✅ All checks passed!
```
