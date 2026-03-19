# Bitwarden Migration Design Document

## Overview

This document describes the migration from GPG-encrypted local credential storage to Bitwarden Organization-based credential management for Carby Studio.

## Architecture

### 1. Bitwarden Organization Structure

```
Organization: Carby-Studio
├── Collection: "Carby-Studio"
│   ├── Items with naming convention:
│   │   carby-studio/{project}/{credential-type}.{identifier}
│   │   
│   │   Examples:
│   │   - carby-studio/family-photo-hub/nas.synology
│   │   - carby-studio/family-photo-hub/icloud.vincent
│   │   - carby-studio/family-photo-hub/google-api.photos
│   │   - carby-studio/shared/database.postgres
│   │   - carby-studio/shared/api-key.openai
```

### 2. Session Management

```
┌─────────────────────────────────────────────────────────────┐
│                    Session Manager                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   Keychain   │    │   BW_SESSION │    │   Bitwarden  │  │
│  │   Service    │◄──►│   Cache      │◄──►│     CLI      │  │
│  └──────────────┘    └──────────────┘    └──────────────┘  │
│         │                   │                   │           │
│         └───────────────────┴───────────────────┘           │
│                             │                               │
│                    ┌────────┴────────┐                      │
│                    │  Auto-Refresh   │                      │
│                    │  (25-min timer) │                      │
│                    └─────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

**Keychain Integration:**
- Service: `com.carby-studio.bitwarden`
- Account: `bw-session`
- Value: BW_SESSION token

**Auto-Refresh:**
- Trigger: 25 minutes after unlock (before 30-min expiration)
- Action: `bw sync` + `bw unlock` to refresh session
- Fallback: Prompt user to unlock Bitwarden

### 3. Credential Types

| Type | Fields | Example |
|------|--------|---------|
| nas | host, port, username, password | synology NAS |
| icloud | apple_id, password, app_specific_password | iCloud account |
| google-api | client_id, client_secret, refresh_token | Google OAuth |
| database | host, port, database, username, password | PostgreSQL |
| api-key | key, endpoint, rate_limit | OpenAI API |

### 4. Migration Flow

```
┌────────────────────────────────────────────────────────────────┐
│                    Migration Process                           │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   Export     │────►│   Parse      │────►│   Import     │   │
│  │   GPG DB     │     │   Metadata   │     │   Bitwarden  │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│         │                    │                    │            │
│         ▼                    ▼                    ▼            │
│  secrets.db.gpg         metadata.yaml        BW Items          │
│                                                                │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   Verify     │────►│   Update     │────►│   Cleanup    │   │
│  │   Import     │     │   Metadata   │     │   GPG Files  │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

## File Structure

```
skills/carby-studio/
├── lib/
│   ├── bitwarden_dao.py          # NEW: Bitwarden data access
│   └── session_manager.py        # NEW: Session + Keychain management
├── scripts/
│   ├── carby-studio              # MODIFIED: Update credential commands
│   └── migrate-to-bitwarden.sh   # NEW: Migration script
└── bot/
    ├── telegram_interface.py     # MODIFIED: Credential display
    └── carby_bot.py              # MODIFIED: Credential tracking
```

## Implementation Details

### bitwarden_dao.py
- CRUD operations for Bitwarden items
- Search by project/type/name
- Template-based item creation
- Secure field handling (never log secrets)

### session_manager.py
- Keychain read/write for BW_SESSION
- Session validity checking
- Auto-refresh mechanism
- Fallback to user unlock prompt

### migrate-to-bitwarden.sh
- Export GPG database
- Parse metadata.yaml
- Create Bitwarden items
- Verify and cleanup

## Security Considerations

1. **Never log secrets** - All credential values are redacted in logs
2. **Keychain storage** - BW_SESSION stored in macOS Keychain
3. **Session expiration** - Auto-refresh before 30-minute timeout
4. **Migration safety** - GPG backup before deletion
5. **Access control** - Bitwarden Organization membership controls access

## Backward Compatibility

During transition:
- GPG files remain until migration verified
- Metadata.yaml updated with `storage: bitwarden`
- Fallback to GPG if Bitwarden unavailable
- Gradual project-by-project migration
