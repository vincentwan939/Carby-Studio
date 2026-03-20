# Carby Studio Skill

## Overview

**Carby Studio v3.0.0** — Production-ready AI-native software development framework with integrated security, reliability, and validation gates.

Carby Studio orchestrates five core agents — **Discover**, **Design**, **Build**, **Verify**, and **Deliver** — using OpenClaw's `sessions_spawn` runtime. The Sprint Framework provides atomic transactions, distributed locking, server-side gate enforcement, and comprehensive audit logging.

**GitHub Repository:** https://github.com/vincentwan939/Carby-Studio

## Quick Start

```bash
# Initialize a new sprint
carby-sprint init my-project --goal "Build a REST API for user management"

# Check sprint status
carby-sprint status my-project

# Start the sprint (runs discover phase)
carby-sprint start my-project
```

For detailed documentation, see [getting-started.md](docs/getting-started.md).

## ✅ Production Ready

Carby Studio v3.0.0 has undergone comprehensive security audits and reliability hardening:

- **97% test coverage** (69/71 tests passing)
- **3 debate-mode security audits** completed
- **Atomic transactions** with rollback capability
- **Distributed locking** for concurrent operations
- **Server-side gate enforcement** with HMAC tokens
- **Automatic backup cleanup** and health monitoring

## 🔒 Security Features

| Feature | Implementation |
|---------|---------------|
| Path Traversal Protection | Regex validation + safe path joining |
| Race Condition Prevention | `portalocker` distributed file locking |
| Command Injection Prevention | List-based subprocess calls |
| JSON Validation | Pydantic schema validation |
| Gate Bypass Prevention | HMAC-SHA256 tokens with 24h expiry |
| Atomic Transactions | Copy-on-write with unique temp directories |

## 🔧 Reliability Features

| Feature | Implementation |
|---------|---------------|
| Atomic Updates | Thread-safe transactions with UUID-based temp files |
| Backup Management | Auto-cleanup (keeps last 10 backups) |
| Health Monitoring | Stale lock detection, hung agent detection, log rotation |
| TOCTOU Protection | Atomic cleanup locks for race condition prevention |
| Thread Safety | Thread-local storage with proper initialization |

## 📁 Core Modules

| Module | Purpose |
|--------|---------|
| `carby_sprint/lock_manager.py` | Distributed file locking with `portalocker` |
| `carby_sprint/validators.py` | Pydantic models for sprint/work item validation |
| `carby_sprint/transaction.py` | Atomic transactions with rollback |
| `carby_sprint/gate_enforcer.py` | HMAC-signed gate tokens |
| `carby_sprint/authority.py` | Decision authority framework |
| `carby_sprint/health_monitor.py` | System health monitoring |
| `carby_sprint/path_utils.py` | Path validation and safe joining |

## 🧪 Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific category
python -m pytest tests/security/ -v
python -m pytest tests/reliability/ -v
python -m pytest tests/design/ -v
```

## ⚠️ Legacy Mode Deprecated

The original `carby-studio` CLI is deprecated. Use `carby-sprint` for all new projects.

```bash
# Old way (deprecated)
carby-studio init my-project

# New way
carby-sprint init my-project --goal "..."
```

## 📊 Version History

| Version | Status | Key Changes |
|---------|--------|-------------|
| v3.0.0 | **Current** | Security hardening, atomic transactions, gate enforcement |
| v2.0.0 | Deprecated | Legacy linear pipeline |
| v1.0.0 | Deprecated | Initial release |

## 🔗 Links

- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api.md)
- [Troubleshooting](TROUBLESHOOTING.md)

---
*Carby Studio v3.0.0 — Production-ready AI-native software development*
