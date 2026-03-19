# Credential Manifest: {project_name}

## Overview
Description of the project and its credential requirements

## Credentials List
| Name | Type | Environment | Purpose | Owner | Next Rotation |
|------|------|-------------|---------|-------|---------------|
| {name} | {type} | {env} | {purpose} | {owner} | {rotation_date} |

## Access Requirements
- Required collections: {collections}
- Minimum permissions: {permissions}

## Integration Pattern
```bash
# Example integration pattern for retrieving credentials
get_credential() {
    local item_name="$1"
    local field_name="${2:-password}"
    
    # Ensure session is valid
    if ! bw login --check; then
        echo "Error: Bitwarden session invalid"
        return 1
    fi
    
    # Retrieve credential
    bw get "$field_name" "$item_name" --session "$BW_SESSION"
}

# Usage example
DB_PASSWORD=$(get_credential "MY-PROJECT-DB-PASSWORD" "password")
API_KEY=$(get_credential "MY-PROJECT-API-KEY" "password")
```

## Rotation Schedule
- API keys: Every 90 days
- Database passwords: Every 180 days
- Service account credentials: Every 30 days
- SSH keys: Every 365 days

## Emergency Procedures
- Lost credential access: Contact {admin_contact}
- Compromised credential: Immediately rotate and notify {incident_team}
- Bitwarden outage: Temporary access via {backup_procedure}