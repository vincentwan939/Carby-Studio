#!/bin/bash
# TintinBot Monitoring Script
# Usage: ./monitor.sh [--alert] [--json]

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="${BOT_DIR}/bot.log"
ALERT_MODE=false
JSON_OUTPUT=false
TELEGRAM_API_URL="https://api.telegram.org/bot${CARBY_BOT_TOKEN:-}/getMe"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --alert)
            ALERT_MODE=true
            shift
            ;;
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--alert] [--json]"
            exit 1
            ;;
    esac
done

# Logging function
log() {
    if [[ "$JSON_OUTPUT" == false ]]; then
        echo -e "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    fi
}

# JSON output
json_output() {
    if [[ "$JSON_OUTPUT" == true ]]; then
        echo "$1"
    else
        echo -e "$1"
    fi
}

# Check if bot is running
check_process() {
    local pid
    pid=$(pgrep -f "python.*bot.py" || true)
    
    if [[ -n "$pid" ]]; then
        echo "$pid"
        return 0
    else
        return 1
    fi
}

# Check Telegram API connectivity
check_telegram_api() {
    if [[ -z "${CARBY_BOT_TOKEN:-}" ]]; then
        if [[ -f "${BOT_DIR}/.env" ]]; then
            source "${BOT_DIR}/.env"
        fi
    fi
    
    if [[ -z "${CARBY_BOT_TOKEN:-}" ]]; then
        return 1
    fi
    
    # Test API endpoint
    local response
    response=$(curl -s --max-time 10 "$TELEGRAM_API_URL" || true)
    
    if echo "$response" | grep -q '"ok":true'; then
        return 0
    else
        return 1
    fi
}

# Count sprints vs projects
count_sprints_projects() {
    local sprints=0
    local projects=0
    
    if [[ -d "${BOT_DIR}/.carby-sprints" ]]; then
        sprints=$(find "${BOT_DIR}/.carby-sprints" -mindepth 1 -maxdepth 1 -type d | wc -l)
    fi
    
    if [[ -d "${BOT_DIR}/../projects" ]]; then
        projects=$(find "${BOT_DIR}/../projects" -mindepth 1 -maxdepth 1 -type d | wc -l)
    fi
    
    echo "$((sprints + 0))" "$((projects + 0))"
}

# Check for errors in log
check_errors_in_log() {
    if [[ -f "$LOG_FILE" ]]; then
        # Look for recent errors in the last 100 lines
        local recent_lines
        recent_lines=$(tail -100 "$LOG_FILE" 2>/dev/null || true)
        
        if echo "$recent_lines" | grep -qi "error\|exception\|traceback\|failed"; then
            echo "$recent_lines" | grep -i "error\|exception\|traceback\|failed" || true
            return 0
        fi
    fi
    return 1
}

# Generate alert if issues detected
generate_alert() {
    local alerts=()
    local has_issues=false
    
    # Check if bot is running
    if ! check_process >/dev/null; then
        alerts+=("❌ Bot is not running")
        has_issues=true
    fi
    
    # Check Telegram API
    if ! check_telegram_api; then
        alerts+=("❌ Telegram API connectivity failed")
        has_issues=true
    fi
    
    # Check for errors in log
    if check_errors_in_log >/dev/null; then
        alerts+=("⚠️ Errors found in recent logs")
        has_issues=true
    fi
    
    # Print alerts if any
    if [[ "$has_issues" == true ]]; then
        for alert in "${alerts[@]}"; do
            if [[ "$JSON_OUTPUT" == false ]]; then
                echo -e "${RED}$alert${NC}"
            else
                echo "$alert"
            fi
        done
        return 0
    else
        if [[ "$JSON_OUTPUT" == false ]]; then
            echo -e "${GREEN}✅ All systems operational${NC}"
        else
            echo '{"status":"operational","alerts":[]}'
        fi
        return 1
    fi
}

# Main monitoring function
main() {
    if [[ "$JSON_OUTPUT" == true ]]; then
        # JSON output mode
        local pid
        pid=$(check_process || echo "null")
        
        local telegram_ok
        if check_telegram_api; then
            telegram_ok="true"
        else
            telegram_ok="false"
        fi
        
        local counts
        counts=$(count_sprints_projects)
        local sprint_count=$(echo "$counts" | awk '{print $1}')
        local project_count=$(echo "$counts" | awk '{print $2}')
        
        local errors_found
        if check_errors_in_log >/dev/null; then
            errors_found="true"
        else
            errors_found="false"
        fi
        
        cat <<EOF
{
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "bot_running": $([[ -n "${pid:-}" ]] && echo "true" || echo "false"),
  "bot_pid": $pid,
  "telegram_connected": $telegram_ok,
  "sprint_count": $sprint_count,
  "legacy_project_count": $project_count,
  "errors_in_log": $errors_found,
  "bot_directory": "$BOT_DIR"
}
EOF
    else
        # Human-readable output
        log "${BLUE}=== TintinBot Status Monitor ===${NC}"
        
        # Process status
        if check_process >/dev/null; then
            local pid
            pid=$(check_process)
            log "${GREEN}✅ Bot is running (PID: $pid)${NC}"
        else
            log "${RED}❌ Bot is not running${NC}"
        fi
        
        # Telegram connectivity
        if check_telegram_api; then
            log "${GREEN}✅ Telegram API connectivity OK${NC}"
        else
            log "${RED}❌ Telegram API connectivity FAILED${NC}"
        fi
        
        # Sprint/project counts
        local counts
        counts=$(count_sprints_projects)
        local sprints=$(echo "$counts" | awk '{print $1}')
        local projects=$(echo "$counts" | awk '{print $2}')
        log "${BLUE}📊 Sprint Count: $sprints | Legacy Project Count: $projects${NC}"
        
        # Log errors
        if check_errors_in_log >/dev/null; then
            log "${YELLOW}⚠️ Recent errors found in log:${NC}"
            check_errors_in_log | head -10 | while read -r line; do
                log "   $line"
            done
        else
            log "${GREEN}✅ No recent errors in log${NC}"
        fi
        
        # Generate alerts if requested
        if [[ "$ALERT_MODE" == true ]]; then
            log ""
            log "${BLUE}=== Alert Check ===${NC}"
            generate_alert
        fi
        
        log "${BLUE}=========================${NC}"
    fi
}

main "$@"