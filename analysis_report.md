# Carby Studio GPG to Bitwarden Migration Analysis Report

## Executive Summary

This report analyzes the current GPG-based credential system in Carby Studio and documents the scope for migration to Bitwarden.

## Current System Analysis

### 1. Directory Structure

```
~/.openclaw/secrets/
├── .master-key-fingerprint      # Master key reference
├── .recovery-key.asc            # Recovery key (encrypted)
├── types.yaml                   # Credential type definitions
├── gate-enforcer.key            # Gate enforcer HMAC secret
├── rescue_key / rescue_key.pub  # Rescue key pair
├── backups/                     # Backup directory
├── family-photo-hub/            # Project-specific secrets
│   ├── metadata.yaml            # Credential metadata (unencrypted)
│   ├── secrets.db.gpg           # ENCRYPTED credential database
│   └── backups/                 # Backup versions
└── projects/                    # Other project directories
    ├── carby-home-security/
    ├── e2e-test-project/
    ├── family-photo-hub/
    ├── homepod-openclaw-bridge/
    └── [test-projects]/
```

### 2. GPG-Encrypted Files Found

| Location | File | Purpose |
|----------|------|---------|
| `~/.openclaw/secrets/projects/*/secrets.db.gpg` | Encrypted DB | Project credential storage |
| `~/.openclaw/secrets/.recovery-key.asc` | ASCII-armored | Recovery key backup |
| `~/.openclaw/secrets/projects/*/backups/*.gpg` | Encrypted DB | Backup versions |

### 3. Credential Type Definitions (`types.yaml`)

```yaml
types:
  nas:        # Synology NAS - fields: [username, password, host, port]
  icloud:     # iCloud Account - fields: [apple_id, app_password]
  google-api: # Google API - fields: [client_id, client_secret, refresh_token]
  database:   # Database - fields: [host, port, username, password, database]
  api-key:    # API Key - fields: [key, secret]
  custom:     # Custom - fields: [] (user-defined)
```

### 4. Current Credential Access Patterns

Based on code analysis, the current system uses:

1. **GPG Encryption**: Files encrypted with user's GPG key
2. **Project-scoped Storage**: Each project has its own `secrets.db.gpg`
3. **Metadata Separation**: `metadata.yaml` stores credential info (unencrypted)
4. **Type System**: Standardized credential types with defined fields

### 5. Files Using Credential System

#### Core Scripts:
- `skills/carby-studio/scripts/carby-studio` - Main CLI (lines 1000+)
  - References: `credentials` subcommand (line 1036)
  - Calls: `carby-credentials` script (line 1038)
  - Deploy check: Validates credentials before deployment (lines 927-941)

#### Bot Components:
- `skills/carby-studio/bot/carby_bot.py` - Bot implementation
  - Line 81: `credentials_used: List[str]` field
  - Line 273: Shows credential count in status
  - Line 302: References `credentials-required.md` in design phase

- `skills/carby-studio/bot/telegram_interface.py`
  - Line 157: Credentials command handler
  - Lines 335-343: Credentials display (delegates to `carby-credentials` skill)

#### Templates:
- `skills/carby-studio/templates/credential_manifest_template.md`
  - Bitwarden integration pattern already documented
  - Shows intent to migrate to Bitwarden

### 6. Dependencies on GPG Vault System

| Component | Dependency | Impact |
|-----------|------------|--------|
| `carby-studio` CLI | `carby-credentials` script | **HIGH** - Core functionality |
| Deploy command | Credential verification | **HIGH** - Blocks deployment if credentials not prod |
| Bot interface | Credentials display | **MEDIUM** - User-facing feature |
| Gate enforcer | `gate-enforcer.key` (not GPG) | **LOW** - Separate HMAC key |

### 7. Secrets Currently Stored

Based on `family-photo-hub/metadata.yaml`:

| Credential | Type | Scope | Status |
|------------|------|-------|--------|
| `google_drive.sony` | google_drive | project | verified |
| `icloud.partner` | icloud | project | verified |
| `icloud.vincent` | icloud | project | unverified |
| `nas.synology` | nas | project | verified |

## Migration Scope

### In Scope:
1. ✅ Project credential databases (`secrets.db.gpg`)
2. ✅ Credential metadata migration
3. ✅ Type definitions mapping to Bitwarden fields
4. ✅ CLI credential commands
5. ✅ Bot credential interface
6. ✅ Deploy-time credential verification

### Out of Scope:
1. ❌ Gate enforcer key (`gate-enforcer.key` - separate HMAC secret)
2. ❌ Recovery key system (may remain GPG)
3. ❌ Project README.txt files (informational only)

### Migration Complexity: **MEDIUM-HIGH**

**Challenges:**
1. GPG files need decryption before Bitwarden import
2. Session management for Bitwarden CLI (`BW_SESSION`)
3. Backward compatibility during transition
4. Testing all credential-dependent workflows

**Estimated Effort:** 10-15 days (consistent with previous analysis)

## Security Considerations

### Current GPG System:
- ✅ Single point of control (user's GPG key)
- ✅ No cloud dependency
- ✅ Offline capable
- ❌ Single-user only
- ❌ No team sharing
- ❌ Manual backup required

### Bitwarden System:
- ✅ Team sharing capability
- ✅ Automatic sync
- ✅ Built-in backup
- ✅ Cross-device access
- ⚠️ Cloud dependency
- ⚠️ Session token management required
- ⚠️ CLI session expiration handling

## Recommended Migration Strategy

1. **Phase 1**: Create Bitwarden DAO layer alongside GPG
2. **Phase 2**: Export GPG credentials to Bitwarden
3. **Phase 3**: Update CLI to use Bitwarden
4. **Phase 4**: Update Bot interface
5. **Phase 5**: Verification and testing
6. **Phase 6**: Deprecate GPG (keep as backup)

## Next Steps

This analysis provides the foundation for:
1. **Stage 2**: Design Bitwarden integration patterns
2. **Stage 3**: Implement migration scripts and updated handlers

---

**Report Generated:** 2026-03-19
**Analyzed By:** Sub-agent Analyzer
**Scope:** Carby Studio credential system
