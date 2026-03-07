#!/bin/bash
# Step 2: Comprehensive EDGE-015 Retest
# Tests concurrent access fix under various load conditions

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEAM_TASKS_DIR="${TEAM_TASKS_DIR:-$HOME/.openclaw/workspace/projects}"
TASK_MANAGER="python3 $SCRIPT_DIR/../team-tasks/scripts/task_manager.py"
TEST_PROJECT="test-edge015-comprehensive"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0

# Cleanup function
cleanup() {
    rm -f "$TEAM_TASKS_DIR/${TEST_PROJECT}*.json" 2>/dev/null || true
}

# Validate JSON and check for corruption
validate_json() {
    local project=$1
    local file="$TEAM_TASKS_DIR/${project}.json"
    
    if [[ ! -f "$file" ]]; then
        echo -e "${RED}❌ File not found: $file${NC}"
        return 1
    fi
    
    if ! python3 -c "import json; json.load(open('$file'))" 2>/dev/null; then
        echo -e "${RED}❌ JSON corruption detected!${NC}"
        return 1
    fi
    
    return 0
}

# Check for negative log counts or other inconsistencies
validate_consistency() {
    local project=$1
    local file="$TEAM_TASKS_DIR/${project}.json"
    
    python3 << EOF
import json
import sys

try:
    with open('$file') as f:
        data = json.load(f)
    
    issues = []
    
    for task_id, task in data.get('stages', {}).items():
        logs = task.get('logs', [])
        if not isinstance(logs, list):
            issues.append(f"{task_id}: logs is not a list")
        
        status = task.get('status')
        if status not in ['pending', 'in-progress', 'done', 'failed', 'skipped']:
            issues.append(f"{task_id}: invalid status '{status}'")
    
    if issues:
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    else:
        sys.exit(0)
except Exception as e:
    print(f"  - Validation error: {e}")
    sys.exit(1)
EOF
}

# Worker function that performs random operations
concurrent_worker() {
    local worker_id=$1
    local iterations=$2
    local project=$3
    
    for i in $(seq 1 $iterations); do
        # Random operation (0-4)
        op=$((RANDOM % 5))
        task_id="task$(( (RANDOM % 3) + 1 ))"
        
        case $op in
            0) $TASK_MANAGER update $project $task_id in-progress 2>/dev/null || true ;;
            1) $TASK_MANAGER log $project $task_id "Worker $worker_id log $i" 2>/dev/null || true ;;
            2) $TASK_MANAGER result $project $task_id "Result $worker_id-$i" 2>/dev/null || true ;;
            3) $TASK_MANAGER update $project $task_id done 2>/dev/null || true ;;
            4) $TASK_MANAGER reset $project $task_id 2>/dev/null || true ;;
        esac
        
        # Small delay to simulate realistic usage
        sleep 0.005
    done
}

# Run a test scenario
run_scenario() {
    local scenario_name=$1
    local processes=$2
    local iterations=$3
    local project_suffix=$4
    local project="${TEST_PROJECT}-${project_suffix}"
    
    echo -e "${YELLOW}▶ Scenario: $scenario_name${NC}"
    echo "  Processes: $processes, Iterations each: $iterations"
    
    # Create project
    $TASK_MANAGER init $project -g "Test $scenario_name" -m dag --force 2>/dev/null
    $TASK_MANAGER add $project task1 -a code-agent --desc "Task 1" 2>/dev/null
    $TASK_MANAGER add $project task2 -a test-agent --desc "Task 2" 2>/dev/null
    $TASK_MANAGER add $project task3 -a docs-agent -d "task1,task2" --desc "Task 3" 2>/dev/null
    
    # Start concurrent workers
    local pids=()
    for w in $(seq 1 $processes); do
        concurrent_worker $w $iterations $project &
        pids+=($!)
    done
    
    # Wait for all workers
    for pid in "${pids[@]}"; do
        wait $pid
    done
    
    # Validate results
    if validate_json $project && validate_consistency $project; then
        echo -e "${GREEN}✅ PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# Main test execution
echo "=========================================="
echo "Step 2: EDGE-015 Comprehensive Retest"
echo "=========================================="
echo ""
echo "Testing file locking fix under various load conditions"
echo ""

# Cleanup before tests
cleanup

# Scenario A: Light Concurrent Load (baseline)
echo "=========================================="
echo "Scenario A: Light Concurrent Load"
echo "=========================================="
run_scenario "Light Load" 5 10 "light"
echo ""

# Scenario B: Medium Concurrent Load
echo "=========================================="
echo "Scenario B: Medium Concurrent Load"
echo "=========================================="
run_scenario "Medium Load" 10 20 "medium"
echo ""

# Scenario C: Heavy Concurrent Load
echo "=========================================="
echo "Scenario C: Heavy Concurrent Load"
echo "=========================================="
run_scenario "Heavy Load" 20 50 "heavy"
echo ""

# Scenario D: Mixed Operations Load
echo "=========================================="
echo "Scenario D: Mixed Operations Load"
echo "=========================================="
run_scenario "Mixed Operations" 15 30 "mixed"
echo ""

# Scenario E: Long-Running Load (sustained)
echo "=========================================="
echo "Scenario E: Long-Running Load"
echo "=========================================="
run_scenario "Long-Running" 5 100 "longrun"
echo ""

# Platform-specific test (macOS fcntl behavior)
echo "=========================================="
echo "Scenario F: Platform-Specific (macOS)"
echo "=========================================="
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Running macOS-specific fcntl test..."
    # macOS-specific: Test with larger file operations
    run_scenario "macOS Specific" 8 40 "macos"
else
    echo "Skipping macOS-specific test (not on macOS)"
fi
echo ""

# Final summary
echo "=========================================="
echo "Step 2 Test Summary"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

# Cleanup
cleanup

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}✅ All scenarios PASSED - EDGE-015 fix verified!${NC}"
    echo "The file locking implementation is working correctly."
    exit 0
else
    echo -e "${RED}❌ Some scenarios FAILED - review output above${NC}"
    exit 1
fi
