#!/bin/bash
# TintinBot Deployment Script
# Usage: ./deploy.sh [--force]

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BOT_NAME="TintinBot"
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="${BOT_DIR}/.venv"
REQUIRED_FILES=(
    "bot.py"
    "carby_bot.py"
    "cli_executor.py"
    "state_manager.py"
    "telegram_interface.py"
    "telegram_handler.py"
    "config.py"
    "requirements.txt"
)
LOG_FILE="${BOT_DIR}/deploy.log"
FORCE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--force]"
            exit 1
            ;;
    esac
done

# Logging function
log() {
    echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

error() {
    log "${RED}ERROR: $1${NC}"
}

success() {
    log "${GREEN}✓ $1${NC}"
}

warning() {
    log "${YELLOW}⚠ $1${NC}"
}

# Check if running from correct directory
check_directory() {
    if [[ ! -f "${BOT_DIR}/bot.py" ]]; then
        error "Must run from bot directory containing bot.py"
        exit 1
    fi
    success "Running from correct directory: ${BOT_DIR}"
}

# Check Python version
check_python() {
    if ! command -v python3 &> /dev/null; then
        error "Python 3 is not installed"
        exit 1
    fi
    
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    log "Python version: ${PYTHON_VERSION}"
    success "Python 3 is available"
}

# Check virtual environment
check_venv() {
    if [[ ! -d "$VENV_PATH" ]]; then
        warning "Virtual environment not found at ${VENV_PATH}"
        log "Creating virtual environment..."
        python3 -m venv "$VENV_PATH"
        success "Virtual environment created"
    else
        success "Virtual environment exists"
    fi
    
    # Activate venv
    source "${VENV_PATH}/bin/activate"
    success "Virtual environment activated"
}

# Install/update dependencies
install_deps() {
    log "Installing dependencies..."
    pip install --quiet --upgrade pip
    pip install --quiet -r "${BOT_DIR}/requirements.txt"
    success "Dependencies installed"
}

# Check required files exist
check_files() {
    log "Verifying required files..."
    local missing=0
    
    for file in "${REQUIRED_FILES[@]}"; do
        if [[ ! -f "${BOT_DIR}/${file}" ]]; then
            error "Missing required file: ${file}"
            missing=$((missing + 1))
        fi
    done
    
    if [[ $missing -gt 0 ]]; then
        error "${missing} required file(s) missing"
        exit 1
    fi
    
    success "All required files present"
}

# Check Python syntax
check_syntax() {
    log "Checking Python syntax..."
    local errors=0
    
    while IFS= read -r -d '' file; do
        if ! python3 -m py_compile "$file" 2>/dev/null; then
            error "Syntax error in: ${file}"
            errors=$((errors + 1))
        fi
    done < <(find "${BOT_DIR}" -name "*.py" -type f -print0)
    
    if [[ $errors -gt 0 ]]; then
        error "${errors} file(s) with syntax errors"
        exit 1
    fi
    
    success "All Python files have valid syntax"
}

# Check if bot is currently running
check_running() {
    local pid
    pid=$(pgrep -f "python.*bot.py" || true)
    
    if [[ -n "$pid" ]]; then
        log "Bot is currently running (PID: ${pid})"
        return 0
    else
        log "Bot is not running"
        return 1
    fi
}

# Stop the bot gracefully
stop_bot() {
    local pid
    pid=$(pgrep -f "python.*bot.py" || true)
    
    if [[ -n "$pid" ]]; then
        log "Stopping bot (PID: ${pid})..."
        
        # Try graceful shutdown first
        kill -TERM "$pid" 2>/dev/null || true
        
        # Wait up to 10 seconds
        local count=0
        while [[ $count -lt 10 ]] && kill -0 "$pid" 2>/dev/null; do
            sleep 1
            count=$((count + 1))
        done
        
        # Force kill if still running
        if kill -0 "$pid" 2>/dev/null; then
            warning "Bot did not stop gracefully, force killing..."
            kill -KILL "$pid" 2>/dev/null || true
            sleep 1
        fi
        
        if kill -0 "$pid" 2>/dev/null; then
            error "Failed to stop bot"
            exit 1
        fi
        
        success "Bot stopped successfully"
    fi
}

# Backup current state
backup_state() {
    local backup_dir="${BOT_DIR}/backups/$(date +%Y%m%d_%H%M%S)"
    log "Creating backup at ${backup_dir}..."
    
    mkdir -p "$backup_dir"
    
    # Backup state files
    if [[ -d "${BOT_DIR}/.carby-sprints" ]]; then
        cp -r "${BOT_DIR}/.carby-sprints" "${backup_dir}/"
    fi
    
    # Backup log
    if [[ -f "${BOT_DIR}/bot.log" ]]; then
        cp "${BOT_DIR}/bot.log" "${backup_dir}/"
    fi
    
    success "Backup created at ${backup_dir}"
}

# Start the bot
start_bot() {
    log "Starting ${BOT_NAME}..."
    
    # Check if token is set
    if [[ -z "${CARBY_BOT_TOKEN:-}" ]]; then
        if [[ -f "${BOT_DIR}/.env" ]]; then
            source "${BOT_DIR}/.env"
        fi
    fi
    
    if [[ -z "${CARBY_BOT_TOKEN:-}" ]]; then
        error "CARBY_BOT_TOKEN environment variable not set"
        exit 1
    fi
    
    # Start bot in background with logging
    cd "$BOT_DIR"
    nohup python3 bot.py >> "${BOT_DIR}/bot.log" 2>&1 &
    local pid=$!
    
    # Wait a moment and check if it's still running
    sleep 2
    
    if ! kill -0 "$pid" 2>/dev/null; then
        error "Bot failed to start (process died immediately)"
        exit 1
    fi
    
    success "Bot started (PID: ${pid})"
    log "Log file: ${BOT_DIR}/bot.log"
}

# Verify bot is responding
verify_bot() {
    log "Verifying bot startup..."
    sleep 3
    
    local pid
    pid=$(pgrep -f "python.*bot.py" || true)
    
    if [[ -z "$pid" ]]; then
        error "Bot process not found after startup"
        exit 1
    fi
    
    # Check log for startup message
    if [[ -f "${BOT_DIR}/bot.log" ]]; then
        if tail -20 "${BOT_DIR}/bot.log" | grep -q "Bot started"; then
            success "Bot startup verified in logs"
        else
            warning "Bot may have started but no confirmation in recent logs"
        fi
    fi
    
    success "Bot is running (PID: ${pid})"
}

# Main deployment flow
main() {
    log "=========================================="
    log "Starting ${BOT_NAME} Deployment"
    log "=========================================="
    
    check_directory
    check_python
    check_files
    check_syntax
    check_venv
    install_deps
    
    # Check if already running
    if check_running; then
        if [[ "$FORCE" == false ]]; then
            log "Bot is already running. Use --force to redeploy."
            exit 0
        fi
        backup_state
        stop_bot
    fi
    
    start_bot
    verify_bot
    
    log "=========================================="
    log "${GREEN}Deployment Complete!${NC}"
    log "=========================================="
    log "To check status: ./monitor.sh"
    log "To view logs: tail -f ${BOT_DIR}/bot.log"
}

# Run main function
main "$@"
