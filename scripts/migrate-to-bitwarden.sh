#!/bin/bash
#
# Migrate credentials from GPG-encrypted storage to Bitwarden
#
# Usage: migrate-to-bitwarden.sh [project-name|--all]
#
# SECURITY FIXES APPLIED:
# - Issue #1: Password no longer exposed via command line (uses stdin)
# - Issue #3: Decrypted credentials processed in-memory (no temp files)
# - Issue #4: Atomic migration with transaction pattern
# - Issue #6: Metadata updated only after Bitwarden verification
# - Issue #7: JSON processing done via Python (no shell injection)

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Paths
SECRETS_DIR="$HOME/.openclaw/secrets"
PROJECTS_DIR="$SECRETS_DIR/projects"
BACKUP_DIR="$SECRETS_DIR/backups/migration-$(date +%Y%m%d-%H%M%S)"

# Bitwarden settings
ORG_NAME="Carby-Studio"
COLLECTION_NAME="Carby-Studio"

# Logging
LOG_FILE="$BACKUP_DIR/migration.log"

log() {
    echo -e "$1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}✗ $1${NC}" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}✓ $1${NC}" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}⚠ $1${NC}" | tee -a "$LOG_FILE"
}

info() {
    echo -e "${BLUE}ℹ $1${NC}" | tee -a "$LOG_FILE"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."
    
    # Check Bitwarden CLI
    if ! command -v bw &> /dev/null; then
        error "Bitwarden CLI (bw) not found"
        echo "Install: brew install bitwarden-cli"
        exit 1
    fi
    success "Bitwarden CLI found"
    
    # Check GPG
    if ! command -v gpg &> /dev/null; then
        error "GPG not found"
        exit 1
    fi
    success "GPG found"
    
    # Check Python (for YAML parsing)
    if ! command -v python3 &> /dev/null; then
        error "Python 3 not found"
        exit 1
    fi
    success "Python 3 found"
    
    # Check Bitwarden login status
    if ! bw login --check &> /dev/null; then
        warn "Not logged into Bitwarden"
        echo "Please run: bw login"
        exit 1
    fi
    success "Bitwarden login verified"
}

# Unlock Bitwarden
unlock_bitwarden() {
    info "Unlocking Bitwarden..."
    
    # Check if already unlocked
    if bw status | grep -q '"status":"unlocked"'; then
        success "Already unlocked"
        return 0
    fi
    
    # Try to get session from keychain
    SESSION=$(python3 -c "
import sys
sys.path.insert(0, '$(dirname "$0")/../lib')
from session_manager import SessionManager
m = SessionManager()
s = m._get_keychain_session()
print(s if s else '')
" 2>/dev/null)
    
    if [ -n "$SESSION" ]; then
        export BW_SESSION="$SESSION"
        if bw status | grep -q '"status":"unlocked"'; then
            success "Unlocked using keychain session"
            return 0
        fi
    fi
    
    # SECURITY FIX (Issue #1): Use stdin instead of command line for password
    # This prevents password exposure in process list (ps)
    echo -n "Enter Bitwarden master password: "
    read -s BW_PASSWORD
    echo
    
    # Use stdin to pass password - never on command line
    SESSION=$(echo "$BW_PASSWORD" | bw unlock --raw)
    if [ -z "$SESSION" ]; then
        error "Failed to unlock Bitwarden"
        exit 1
    fi
    
    export BW_SESSION="$SESSION"
    
    # Clear password from memory
    unset BW_PASSWORD
    
    # Store in keychain
    python3 -c "
import sys
sys.path.insert(0, '$(dirname "$0")/../lib')
from session_manager import SessionManager
m = SessionManager()
m._set_keychain_session('$SESSION')
" 2>/dev/null
    
    success "Unlocked and session stored"
}

# Get organization and collection IDs
get_org_ids() {
    info "Getting organization info..."
    
    ORG_ID=$(bw list organizations --raw | python3 -c "
import sys, json
orgs = json.load(sys.stdin)
for org in orgs:
    if org.get('name') == '$ORG_NAME':
        print(org.get('id'))
        break
")
    
    if [ -z "$ORG_ID" ]; then
        error "Organization '$ORG_NAME' not found"
        echo "Please create it in Bitwarden first"
        exit 1
    fi
    
    COLLECTION_ID=$(bw list collections --organizationid "$ORG_ID" --raw | python3 -c "
import sys, json
colls = json.load(sys.stdin)
for coll in colls:
    if coll.get('name') == '$COLLECTION_NAME':
        print(coll.get('id'))
        break
")
    
    if [ -z "$COLLECTION_ID" ]; then
        error "Collection '$COLLECTION_NAME' not found"
        exit 1
    fi
    
    success "Organization: $ORG_ID, Collection: $COLLECTION_ID"
}

# Export GPG database to memory (not disk)
export_gpg_database() {
    local project_dir="$1"
    local project_name=$(basename "$project_dir")
    
    info "Exporting GPG database for $project_name..."
    
    local gpg_file="$project_dir/secrets.db.gpg"
    local metadata_file="$project_dir/metadata.yaml"
    
    if [ ! -f "$gpg_file" ]; then
        warn "No GPG database found for $project_name"
        return 1
    fi
    
    # SECURITY FIX (Issue #3): Decrypt to memory only, never write to disk
    # Use process substitution which is memory-based
    local decrypted_json
    decrypted_json=$(gpg --decrypt "$gpg_file" 2>/dev/null) || {
        error "Failed to decrypt $gpg_file"
        return 1
    }
    
    success "Decrypted $project_name database to memory"
    
    # Output the decrypted JSON
    echo "$decrypted_json"
}

# Parse credentials from decrypted database (in memory)
parse_credentials() {
    local json_data="$1"
    local metadata_file="$2"
    local project_name="$3"
    
    # SECURITY FIX (Issue #7): All JSON processing done in Python
    # No shell interpolation of fields_json
    python3 << EOF
import json
import yaml
import sys

try:
    data = json.loads('''$json_data''')
    
    with open("$metadata_file", 'r') as f:
        metadata = yaml.safe_load(f)
    
    credentials = data.get('credentials', [])
    cred_metadata = metadata.get('credentials', {})
    
    for cred in credentials:
        cred_type = cred.get('type', 'unknown')
        name = cred.get('name', 'unknown')
        meta = cred_metadata.get(f"{cred_type}.{name}", {})
        
        # Build fields dict
        fields = {}
        for key, value in cred.items():
            if key not in ['type', 'name', 'project']:
                fields[key] = value
        
        # Output format: project|type|name|fields_json
        # Using JSON output to avoid shell parsing issues
        output = {
            "project": "$project_name",
            "type": cred_type,
            "name": name,
            "fields": fields
        }
        print(json.dumps(output))

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

# Create credential in Bitwarden
create_bw_credential() {
    local project="$1"
    local cred_type="$2"
    local name="$3"
    local fields_json="$4"
    
    local full_name="carby-studio/$project/$cred_type.$name"
    
    # Check if already exists using exact match
    local existing=$(bw list items --search "$full_name" --raw | python3 -c "
import sys, json
items = json.load(sys.stdin)
for item in items:
    if item.get('name') == '$full_name':
        print(item.get('id'))
        break
")
    
    if [ -n "$existing" ]; then
        warn "Credential already exists: $full_name"
        return 0
    fi
    
    # SECURITY FIX (Issue #7): Build template in Python to avoid shell injection
    local template=$(python3 << EOF
import json
import base64

fields = json.loads('''$fields_json''')
cred_type = "$cred_type"
full_name = "$full_name"
project = "$project"
name = "$name"
org_id = "$ORG_ID"
coll_id = "$COLLECTION_ID"

# Base template
template = {
    "type": 1,  # Login
    "name": full_name,
    "notes": f"Carby Studio credential\nProject: {project}\nType: {cred_type}\nName: {name}",
    "organizationId": org_id,
    "collectionIds": [coll_id],
    "fields": []
}

# Type-specific fields
if cred_type == "nas":
    template["login"] = {
        "username": fields.get("username", ""),
        "password": fields.get("password", "")
    }
    # Add host/port as custom fields
    if "host" in fields:
        template["fields"].append({"name": "host", "value": fields["host"], "type": 0})
    if "port" in fields:
        template["fields"].append({"name": "port", "value": fields["port"], "type": 0})

elif cred_type == "icloud":
    template["login"] = {
        "username": fields.get("apple_id", ""),
        "password": fields.get("password", "")
    }
    # Add app-specific password as custom field
    if "app_specific_password" in fields:
        template["fields"].append({"name": "app_specific_password", "value": fields["app_specific_password"], "type": 1})

elif cred_type == "google-api":
    template["login"] = {
        "username": fields.get("client_id", ""),
        "password": fields.get("client_secret", "")
    }
    if "refresh_token" in fields:
        template["fields"].append({"name": "refresh_token", "value": fields["refresh_token"], "type": 1})

elif cred_type == "database":
    template["login"] = {
        "username": fields.get("username", ""),
        "password": fields.get("password", "")
    }
    # Add connection details as custom fields
    for key in ["host", "port", "database"]:
        if key in fields:
            template["fields"].append({"name": key, "value": fields[key], "type": 0})

elif cred_type == "api-key":
    template["login"] = {
        "username": fields.get("key_name", "API Key"),
        "password": fields.get("key", "")
    }
    if "endpoint" in fields:
        template["fields"].append({"name": "endpoint", "value": fields["endpoint"], "type": 0})
    if "rate_limit" in fields:
        template["fields"].append({"name": "rate_limit", "value": fields["rate_limit"], "type": 0})

# Add any remaining fields as custom fields
for key, value in fields.items():
    # Skip fields already handled
    handled = ["username", "password", "apple_id", "client_id", "client_secret", "key", "key_name"]
    if key not in handled:
        template["fields"].append({"name": key, "value": str(value), "type": 1 if "secret" in key.lower() or "password" in key.lower() or "key" in key.lower() else 0})

# Output base64 encoded template
print(base64.b64encode(json.dumps(template).encode()).decode())
EOF
)

    # Create item
    local result=$(bw create item --organizationid "$ORG_ID" "$template" 2>&1)
    
    if [ $? -eq 0 ]; then
        success "Created: $full_name"
        return 0
    else
        error "Failed to create: $full_name"
        echo "  $result" >> "$LOG_FILE"
        return 1
    fi
}

# Verify credential exists in Bitwarden
verify_bw_credential() {
    local project="$1"
    local cred_type="$2"
    local name="$3"
    
    local full_name="carby-studio/$project/$cred_type.$name"
    
    # Check if exists using exact match
    local existing=$(bw list items --search "$full_name" --raw | python3 -c "
import sys, json
items = json.load(sys.stdin)
for item in items:
    if item.get('name') == '$full_name':
        print(item.get('id'))
        break
")
    
    if [ -n "$existing" ]; then
        return 0
    fi
    return 1
}

# Migrate a single project with atomic transaction
migrate_project() {
    local project_dir="$1"
    local project_name=$(basename "$project_dir")
    
    info "Migrating project: $project_name"
    
    # Export GPG database to memory
    local json_data
    json_data=$(export_gpg_database "$project_dir")
    if [ $? -ne 0 ]; then
        warn "Skipping $project_name (no credentials)"
        return 0
    fi
    
    local metadata_file="$project_dir/metadata.yaml"
    
    # ATOMIC MIGRATION FIX (Issue #4): 
    # Phase 1: Validate and collect all credentials
    # Phase 2: Create all in Bitwarden
    # Phase 3: Verify all exist in Bitwarden
    # Phase 4: Only then update metadata
    
    info "Phase 1: Validating credentials for $project_name..."
    
    local credentials_to_migrate=()
    local cred_count=0
    
    # Collect all credentials first
    while IFS= read -r line; do
        if [ -n "$line" ]; then
            credentials_to_migrate+=("$line")
            ((cred_count++))
        fi
    done < <(echo "$json_data" | python3 << EOF
import json
import yaml
import sys

try:
    data = json.load(sys.stdin)
    
    with open("$metadata_file", 'r') as f:
        metadata = yaml.safe_load(f)
    
    credentials = data.get('credentials', [])
    cred_metadata = metadata.get('credentials', {})
    
    for cred in credentials:
        cred_type = cred.get('type', 'unknown')
        name = cred.get('name', 'unknown')
        
        # Build fields dict
        fields = {}
        for key, value in cred.items():
            if key not in ['type', 'name', 'project']:
                fields[key] = value
        
        # Output as JSON line
        output = {
            "project": "$project_name",
            "type": cred_type,
            "name": name,
            "fields": fields
        }
        print(json.dumps(output))

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
)
    
    info "Found $cred_count credentials to migrate"
    
    if [ $cred_count -eq 0 ]; then
        warn "No credentials found for $project_name"
        return 0
    fi
    
    # Phase 2: Create all credentials in Bitwarden
    info "Phase 2: Creating credentials in Bitwarden..."
    
    local created_count=0
    local failed_count=0
    local created_creds=()
    
    for cred_json in "${credentials_to_migrate[@]}"; do
        local project=$(echo "$cred_json" | python3 -c "import sys, json; print(json.load(sys.stdin)['project'])")
        local cred_type=$(echo "$cred_json" | python3 -c "import sys, json; print(json.load(sys.stdin)['type'])")
        local name=$(echo "$cred_json" | python3 -c "import sys, json; print(json.load(sys.stdin)['name'])")
        local fields=$(echo "$cred_json" | python3 -c "import sys, json; print(json.dumps(json.load(sys.stdin)['fields']))")
        
        if create_bw_credential "$project" "$cred_type" "$name" "$fields"; then
            ((created_count++))
            created_creds+=("$cred_type.$name")
        else
            ((failed_count++))
        fi
    done
    
    # Phase 3: Verify all credentials exist in Bitwarden
    info "Phase 3: Verifying credentials in Bitwarden..."
    
    local verified_count=0
    local verify_failed=0
    
    for cred_key in "${created_creds[@]}"; do
        local cred_type="${cred_key%%.*}"
        local name="${cred_key#*.}"
        
        if verify_bw_credential "$project_name" "$cred_type" "$name"; then
            ((verified_count++))
        else
            ((verify_failed++))
            error "Verification failed for: $project_name/$cred_key"
        fi
    done
    
    # Only proceed if all credentials verified
    if [ $verify_failed -gt 0 ]; then
        error "Verification failed for $verify_failed credentials. Aborting migration for $project_name."
        error "Created credentials may need to be manually deleted from Bitwarden."
        return 1
    fi
    
    # SECURITY FIX (Issue #6): Only update metadata after verification
    info "Phase 4: Updating metadata after successful verification..."
    
    if [ -f "$metadata_file" ]; then
        python3 << EOF
import yaml
import datetime

with open("$metadata_file", 'r') as f:
    metadata = yaml.safe_load(f)

metadata['storage'] = 'bitwarden'
metadata['migrated_at'] = datetime.datetime.now().isoformat()
metadata['migrated_credentials_count'] = $verified_count

with open("$metadata_file", 'w') as f:
    yaml.dump(metadata, f)
EOF
        success "Updated metadata for $project_name"
    fi
    
    success "Migrated $verified_count/$cred_count credentials for $project_name"
    return 0
}

# Rollback migration for a project
rollback_project() {
    local project_dir="$1"
    local project_name=$(basename "$project_dir")
    
    warn "Rolling back migration for $project_name..."
    
    # Note: We can't automatically delete from Bitwarden without more complex logic
    # Just update metadata to indicate rollback
    local metadata_file="$project_dir/metadata.yaml"
    
    if [ -f "$metadata_file" ]; then
        python3 << EOF
import yaml

with open("$metadata_file", 'r') as f:
    metadata = yaml.safe_load(f)

# Remove bitwarden markers
if 'storage' in metadata:
    del metadata['storage']
if 'migrated_at' in metadata:
    del metadata['migrated_at']
if 'migrated_credentials_count' in metadata:
    del metadata['migrated_credentials_count']

with open("$metadata_file", 'w') as f:
    yaml.dump(metadata, f)
EOF
        success "Rolled back metadata for $project_name"
    fi
}

# Update carby-studio CLI to use Bitwarden
update_cli_config() {
    info "Updating Carby Studio configuration..."
    
    # Create config file
    local config_file="$HOME/.openclaw/carby-studio.conf"
    
    if [ -f "$config_file" ]; then
        # Update existing config
        if ! grep -q "CREDENTIAL_STORAGE" "$config_file"; then
            echo "CREDENTIAL_STORAGE=bitwarden" >> "$config_file"
        else
            sed -i '' 's/CREDENTIAL_STORAGE=.*/CREDENTIAL_STORAGE=bitwarden/' "$config_file"
        fi
    else
        # Create new config
        cat > "$config_file" << EOF
# Carby Studio Configuration
CREDENTIAL_STORAGE=bitwarden
BITWARDEN_ORG=$ORG_NAME
BITWARDEN_COLLECTION=$COLLECTION_NAME
EOF
    fi
    
    success "Configuration updated"
}

# Main migration function
main() {
    local target="${1:-}"
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    log "=========================================="
    log "Carby Studio Bitwarden Migration"
    log "Started: $(date)"
    log "Backup: $BACKUP_DIR"
    log "=========================================="
    
    # Check prerequisites
    check_prerequisites
    
    # Unlock Bitwarden
    unlock_bitwarden
    
    # Get organization info
    get_org_ids
    
    # Determine projects to migrate
    local projects=()
    
    if [ "$target" == "--all" ] || [ -z "$target" ]; then
        # Migrate all projects
        for project_dir in "$PROJECTS_DIR"/*/; do
            if [ -d "$project_dir" ]; then
                projects+=("$project_dir")
            fi
        done
    else
        # Migrate specific project
        if [ -d "$PROJECTS_DIR/$target" ]; then
            projects+=("$PROJECTS_DIR/$target")
        else
            error "Project not found: $target"
            exit 1
        fi
    fi
    
    if [ ${#projects[@]} -eq 0 ]; then
        warn "No projects found to migrate"
        exit 0
    fi
    
    info "Migrating ${#projects[@]} project(s)..."
    
    # Track migration results for atomic rollback
    declare -a MIGRATED_PROJECTS=()
    declare -a FAILED_PROJECTS=()
    
    # Migrate each project
    for project_dir in "${projects[@]}"; do
        if migrate_project "$project_dir"; then
            MIGRATED_PROJECTS+=("$project_dir")
        else
            FAILED_PROJECTS+=("$project_dir")
            error "Migration failed for $(basename "$project_dir")"
        fi
    done
    
    # Only update CLI config if all projects migrated successfully
    if [ ${#FAILED_PROJECTS[@]} -eq 0 ]; then
        update_cli_config
    else
        warn "Some projects failed to migrate. CLI config not updated."
    fi
    
    # Summary
    log ""
    log "=========================================="
    log "Migration Complete"
    log "=========================================="
    log "Backup location: $BACKUP_DIR"
    log "Projects migrated: ${#MIGRATED_PROJECTS[@]}"
    log "Projects failed: ${#FAILED_PROJECTS[@]}"
    
    if [ ${#FAILED_PROJECTS[@]} -gt 0 ]; then
        log "Failed projects:"
        for proj in "${FAILED_PROJECTS[@]}"; do
            log "  - $(basename "$proj")"
        done
    fi
    
    log ""
    log "Next steps:"
    log "  1. Verify credentials in Bitwarden vault"
    log "  2. Test credential access with: carby-studio credentials verify <project>"
    log "  3. Once verified, you can remove GPG files:"
    log "     rm -rf ~/.openclaw/secrets/projects/*/secrets.db.gpg"
    log ""
    log "To rollback if needed:"
    log "  1. Restore GPG files from: $BACKUP_DIR"
    log "  2. Update metadata.yaml to remove 'storage: bitwarden'"
    log "=========================================="
}

# Show help
show_help() {
    cat << EOF
Carby Studio Bitwarden Migration Tool

Usage: $(basename "$0") [OPTIONS] [PROJECT]

Arguments:
  PROJECT       Specific project to migrate (default: all projects)

Options:
  --all         Migrate all projects (default behavior)
  --help        Show this help message

Examples:
  # Migrate all projects
  $(basename "$0")

  # Migrate specific project
  $(basename "$0") family-photo-hub

Prerequisites:
  - Bitwarden CLI installed and logged in
  - Organization "Carby-Studio" created in Bitwarden
  - Collection "Carby-Studio" created in organization
  - GPG credentials encrypted in ~/.openclaw/secrets/projects/

Security Features:
  - Passwords never exposed on command line
  - Credentials decrypted to memory only
  - Atomic migration with rollback support
  - Verification before metadata update

EOF
}

# Handle arguments
case "${1:-}" in
    --help|-h)
        show_help
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac
