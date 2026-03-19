# Bitwarden Integration for Carby Studio

## Overview

Carby Studio now supports Bitwarden Organization for secure credential management, replacing the previous GPG-encrypted local storage.

## Architecture

### Components

1. **Session Manager** (`lib/session_manager.py`)
   - Manages BW_SESSION token in macOS Keychain
   - Auto-refresh before 30-minute expiration
   - Handles unlock/lock operations

2. **Bitwarden DAO** (`lib/bitwarden_dao.py`)
   - CRUD operations for credentials
   - Supports all credential types: nas, icloud, google-api, database, api-key
   - Secure field handling (secrets never logged)

3. **Credentials Handler** (`lib/credentials_handler.py`)
   - Unified interface for credential management
   - Backward compatibility with GPG during transition
   - Project-level credential operations

4. **Migration Script** (`scripts/migrate-to-bitwarden.sh`)
   - One-shot migration from GPG to Bitwarden
   - Backup creation before migration
   - Metadata updates

## Setup

### Prerequisites

1. Install Bitwarden CLI:
   ```bash
   brew install bitwarden-cli
   ```

2. Login to Bitwarden:
   ```bash
   bw login
   ```

3. Create Organization in Bitwarden:
   - Name: `Carby-Studio`
   - Create Collection: `Carby-Studio`

### Configuration

Credentials are automatically stored with the naming convention:
```
carby-studio/{project}/{credential-type}.{identifier}

Examples:
- carby-studio/family-photo-hub/nas.synology
- carby-studio/family-photo-hub/icloud.vincent
- carby-studio/shared/api-key.openai
```

## Usage

### CLI Commands

```bash
# List credentials for a project
carby-studio credentials list <project>

# Get credential value (fields only, no secrets shown)
carby-studio credentials get <project> <type> <name>

# Add new credential
carby-studio credentials add <project> <type> <name> --field key=value

# Verify credential
carby-studio credentials verify <project>

# Show credential status
carby-studio credentials status <project>

# Audit all projects
carby-studio credentials audit

# Migrate project to Bitwarden
carby-studio credentials migrate <project>

# Unlock Bitwarden session
carby-studio credentials unlock

# Lock Bitwarden session
carby-studio credentials lock
```

### Telegram Bot

The Telegram bot now shows credential status in:
- `/credentials` command - Overview of all projects
- Project detail view - Credential count and storage type

## Migration

### Migrate a Single Project

```bash
carby-studio credentials migrate family-photo-hub
```

### Migrate All Projects

```bash
./scripts/migrate-to-bitwarden.sh --all
```

### Migration Process

1. **Export** - Decrypt GPG database
2. **Parse** - Read metadata.yaml
3. **Import** - Create Bitwarden items
4. **Verify** - Check imported credentials
5. **Update** - Mark metadata as migrated
6. **Backup** - Keep GPG files until verified

### Post-Migration

After verifying credentials work:

```bash
# Remove GPG files (optional, after verification)
rm ~/.openclaw/secrets/projects/*/secrets.db.gpg
```

## Security

### Keychain Storage

- BW_SESSION stored in macOS Keychain
- Service: `com.carby-studio.bitwarden`
- Account: `bw-session`

### Session Management

- Sessions expire after 30 minutes
- Auto-refresh at 25 minutes
- Fallback to user prompt if refresh fails

### Secret Handling

- Credentials never logged
- Safe repr/str methods on Credential class
- Secure field types in Bitwarden (hidden fields)

## Credential Types

### NAS (Network Attached Storage)
```yaml
type: nas
name: synology
fields:
  host: 192.168.1.100
  port: 5000
  username: admin
  password: <secret>
```

### iCloud
```yaml
type: icloud
name: vincent
fields:
  apple_id: user@icloud.com
  password: <secret>
  app_specific_password: <secret>
```

### Google API
```yaml
type: google-api
name: photos
fields:
  client_id: <id>
  client_secret: <secret>
  refresh_token: <token>
```

### Database
```yaml
type: database
name: postgres
fields:
  host: localhost
  port: 5432
  database: mydb
  username: user
  password: <secret>
```

### API Key
```yaml
type: api-key
name: openai
fields:
  key: <api-key>
  endpoint: https://api.openai.com
  rate_limit: 60
```

## Testing

Run unit tests:
```bash
cd skills/carby-studio
python3 tests/test_bitwarden_integration.py
```

Run integration tests (requires Bitwarden login):
```bash
RUN_BW_TESTS=1 python3 tests/test_bitwarden_integration.py
```

## Troubleshooting

### Session Expired

```bash
# Re-unlock Bitwarden
carby-studio credentials unlock
```

### Credential Not Found

```bash
# Check if using correct storage
carby-studio credentials status <project>

# If still on GPG, migrate
carby-studio credentials migrate <project>
```

### Migration Failed

1. Check Bitwarden login: `bw status`
2. Verify organization exists
3. Check backup in `~/.openclaw/secrets/backups/`
4. Retry migration

## Backward Compatibility

During transition:
- GPG files remain until explicitly removed
- Metadata tracks storage type
- Fallback to GPG if Bitwarden unavailable
- Gradual project-by-project migration supported
