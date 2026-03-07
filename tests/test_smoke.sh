#!/bin/bash
# Step 3: Production Deployment - Smoke Tests
# Validates core functionality before declaring production-ready

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CARBY_STUDIO="$SCRIPT_DIR/../scripts/carby-studio"
TASK_MANAGER="$SCRIPT_DIR/../team-tasks/scripts/task_manager.py"
TEST_PROJECT="smoke-test-$(date +%s)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

TESTS_PASSED=0
TESTS_FAILED=0

cleanup() {
    echo ""
    echo "Cleaning up test project..."
    rm -rf "$HOME/.openclaw/workspace/projects/$TEST_PROJECT" 2>/dev/null || true
    rm -f "$HOME/.openclaw/workspace/projects/${TEST_PROJECT}.json" 2>/dev/null || true
}

trap cleanup EXIT

run_test() {
    local test_name="$1"
    local test_cmd="$2"
    
    echo -e "${BLUE}▶ $test_name${NC}"
    if eval "$test_cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}  ✅ PASSED${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}  ❌ FAILED${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

echo "=========================================="
echo "Step 3: Production Smoke Tests"
echo "=========================================="
echo ""
echo "Testing Carby Studio core functionality"
echo "Test project: $TEST_PROJECT"
echo ""

# Test 1: CLI help works
echo "--- CLI Tests ---"
run_test "CLI help displays" "$CARBY_STUDIO help"
run_test "CLI init command exists" "$CARBY_STUDIO help 2>&1 | grep -q 'init'"
run_test "CLI status command exists" "$CARBY_STUDIO help 2>&1 | grep -q 'status'"

# Test 2: Project initialization
echo ""
echo "--- Project Initialization ---"
run_test "Init linear project" "echo '1' | $CARBY_STUDIO init $TEST_PROJECT -g 'Test project' --mode linear"
run_test "Project JSON created" "test -f $HOME/.openclaw/workspace/projects/${TEST_PROJECT}.json"
run_test "Project directory created" "test -d $HOME/.openclaw/workspace/projects/$TEST_PROJECT"
run_test "Project has docs folder" "test -d $HOME/.openclaw/workspace/projects/$TEST_PROJECT/docs"
run_test "Project has src folder" "test -d $HOME/.openclaw/workspace/projects/$TEST_PROJECT/src"
run_test "Project has tests folder" "test -d $HOME/.openclaw/workspace/projects/$TEST_PROJECT/tests"

# Test 3: Status and query commands
echo ""
echo "--- Status & Query ---"
run_test "Status command works" "$CARBY_STUDIO status $TEST_PROJECT"
run_test "Next command works" "$CARBY_STUDIO next $TEST_PROJECT"
run_test "List command works" "$CARBY_STUDIO list | grep -q $TEST_PROJECT"

# Test 4: Stage management
echo ""
echo "--- Stage Management ---"
run_test "Assign task to discover" "$CARBY_STUDIO assign $TEST_PROJECT discover 'Test task'"
run_test "Update status to in-progress" "$CARBY_STUDIO update $TEST_PROJECT discover in-progress"
run_test "Log entry added" "$TASK_MANAGER log $TEST_PROJECT discover 'Test log entry'"
run_test "Result saved" "$TASK_MANAGER result $TEST_PROJECT discover 'Test result output'"

# Test 5: DAG mode
echo ""
echo "--- DAG Mode ---"
TEST_PROJECT_DAG="${TEST_PROJECT}-dag"
run_test "Init DAG project" "echo '1' | $CARBY_STUDIO init $TEST_PROJECT_DAG -g 'DAG test' --mode dag"
run_test "Add task to DAG" "$TASK_MANAGER add $TEST_PROJECT_DAG task1 -a code-agent"
run_test "Add dependent task" "$TASK_MANAGER add $TEST_PROJECT_DAG task2 -a test-agent -d task1"
run_test "Ready command works" "$CARBY_STUDIO ready $TEST_PROJECT_DAG"
run_test "Graph command works" "$CARBY_STUDIO graph $TEST_PROJECT_DAG"

# Test 6: Recovery commands
echo ""
echo "--- Recovery Commands ---"
run_test "Reset stage" "$CARBY_STUDIO reset $TEST_PROJECT discover"
run_test "Skip stage" "$CARBY_STUDIO update $TEST_PROJECT discover skipped"
run_test "Retry resets to pending" "$CARBY_STUDIO retry $TEST_PROJECT discover 2>&1 | grep -q 'reset'"

# Test 7: Validation
echo ""
echo "--- Validation ---"
run_test "Validator script exists" "test -f $SCRIPT_DIR/../scripts/validator.py"
run_test "Validator runs" "python3 $SCRIPT_DIR/../scripts/validator.py $HOME/.openclaw/workspace/projects/$TEST_PROJECT discover 2>&1 | grep -q -i 'fail\|error\|pass\|valid'"

# Test 8: Configuration persistence
echo ""
echo "--- Configuration ---"
run_test "Config file created" "test -f $HOME/.openclaw/workspace/projects/$TEST_PROJECT/.carby-config.json"
run_test "Deploy target in config" "cat $HOME/.openclaw/workspace/projects/$TEST_PROJECT/.carby-config.json | grep -q 'deploy_target'"

# Cleanup DAG project
rm -rf "$HOME/.openclaw/workspace/projects/$TEST_PROJECT_DAG" 2>/dev/null || true
rm -f "$HOME/.openclaw/workspace/projects/${TEST_PROJECT_DAG}.json" 2>/dev/null || true

# Summary
echo ""
echo "=========================================="
echo "Smoke Test Summary"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}✅ All smoke tests passed!${NC}"
    echo "Carby Studio is ready for production deployment."
    exit 0
else
    echo -e "${RED}❌ Some smoke tests failed${NC}"
    echo "Review failures above before deploying to production."
    exit 1
fi
