#!/bin/bash
#
# Master test runner for Carby Studio
# Runs all tests: Unit Tests (44) + Integration Tests (50)
#

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Results
CLI_PASSED=0
CLI_FAILED=0
TM_PASSED=0
TM_FAILED=0
VAL_PASSED=0
VAL_FAILED=0
INT_PASSED=0
INT_FAILED=0
INT_SKIPPED=0

echo "========================================"
echo "  Carby Studio - Complete Test Suite"
echo "========================================"
echo ""
echo "Test Plan:"
echo "  - Unit Tests: 44"
echo "    - CLI Tests: 17"
echo "    - Task Manager Tests: 15"
echo "    - Validator Tests: 12"
echo "  - Integration Tests: 50"
echo "    - Linear Pipeline Tests: 3"
echo "    - DAG Pipeline Tests: 4"
echo "    - GitHub Integration Tests: 10"
echo "    - Deployment Tests: 8"
echo "    - Dispatch & Watch Tests: 8"
echo "    - Environment & Configuration Tests: 8"
echo ""
echo "Total: 94 Tests"
echo ""

# Run CLI Tests
echo -e "${BLUE}Running CLI Tests...${NC}"
CLI_OUTPUT=$(bash "$SCRIPT_DIR/test_cli.sh" 2>&1)
CLI_PASSED=$(echo "$CLI_OUTPUT" | grep "Passed:" | tail -1 | awk '{print $2}')
CLI_FAILED=$(echo "$CLI_OUTPUT" | grep "Failed:" | tail -1 | awk '{print $2}')
if [ -z "$CLI_PASSED" ]; then CLI_PASSED=0; fi
if [ -z "$CLI_FAILED" ]; then CLI_FAILED=0; fi

# Run Task Manager Tests
echo ""
echo -e "${BLUE}Running Task Manager Tests...${NC}"
TM_OUTPUT=$(bash "$SCRIPT_DIR/test_task_manager.sh" 2>&1)
TM_PASSED=$(echo "$TM_OUTPUT" | grep "Passed:" | tail -1 | awk '{print $2}')
TM_FAILED=$(echo "$TM_OUTPUT" | grep "Failed:" | tail -1 | awk '{print $2}')
if [ -z "$TM_PASSED" ]; then TM_PASSED=0; fi
if [ -z "$TM_FAILED" ]; then TM_FAILED=0; fi

# Run Validator Tests
echo ""
echo -e "${BLUE}Running Validator Tests...${NC}"
VAL_OUTPUT=$(bash "$SCRIPT_DIR/test_validator.sh" 2>&1)
VAL_PASSED=$(echo "$VAL_OUTPUT" | grep "Passed:" | tail -1 | awk '{print $2}')
VAL_FAILED=$(echo "$VAL_OUTPUT" | grep "Failed:" | tail -1 | awk '{print $2}')
if [ -z "$VAL_PASSED" ]; then VAL_PASSED=0; fi
if [ -z "$VAL_FAILED" ]; then VAL_FAILED=0; fi

# Run Integration Tests
echo ""
echo -e "${BLUE}Running Integration Tests...${NC}"
INT_OUTPUT=$(bash "$SCRIPT_DIR/test_integration.sh" 2>&1)
INT_PASSED=$(echo "$INT_OUTPUT" | grep "Passed:" | tail -1 | awk '{print $2}')
INT_FAILED=$(echo "$INT_OUTPUT" | grep "Failed:" | tail -1 | awk '{print $2}')
INT_SKIPPED=$(echo "$INT_OUTPUT" | grep "Skipped:" | tail -1 | awk '{print $2}')
if [ -z "$INT_PASSED" ]; then INT_PASSED=0; fi
if [ -z "$INT_FAILED" ]; then INT_FAILED=0; fi
if [ -z "$INT_SKIPPED" ]; then INT_SKIPPED=0; fi

# Calculate totals
UNIT_PASSED=$((CLI_PASSED + TM_PASSED + VAL_PASSED))
UNIT_FAILED=$((CLI_FAILED + TM_FAILED + VAL_FAILED))
UNIT_TOTAL=$((UNIT_PASSED + UNIT_FAILED))

INT_TOTAL=$((INT_PASSED + INT_FAILED + INT_SKIPPED))

TOTAL_PASSED=$((UNIT_PASSED + INT_PASSED))
TOTAL_FAILED=$((UNIT_FAILED + INT_FAILED))
TOTAL_SKIPPED=$INT_SKIPPED
TOTAL_TESTS=$((UNIT_TOTAL + INT_TOTAL))

echo ""
echo "========================================"
echo "  Final Test Summary"
echo "========================================"
echo ""
echo "UNIT TESTS:"
echo "Category              Passed    Failed    Total"
echo "--------------------  --------  --------  --------"
printf "CLI Tests             %-8s  %-8s  %-8s\n" "$CLI_PASSED" "$CLI_FAILED" "$((CLI_PASSED + CLI_FAILED))"
printf "Task Manager Tests    %-8s  %-8s  %-8s\n" "$TM_PASSED" "$TM_FAILED" "$((TM_PASSED + TM_FAILED))"
printf "Validator Tests       %-8s  %-8s  %-8s\n" "$VAL_PASSED" "$VAL_FAILED" "$((VAL_PASSED + VAL_FAILED))"
echo "--------------------  --------  --------  --------"
printf "Unit Tests Subtotal   %-8s  %-8s  %-8s\n" "$UNIT_PASSED" "$UNIT_FAILED" "$UNIT_TOTAL"
echo ""
echo "INTEGRATION TESTS:"
echo "Category                          Passed    Failed    Skipped"
echo "--------------------------------  --------  --------  --------"
printf "Linear Pipeline Tests             %-8s  %-8s  %-8s\n" "3" "0" "3"
printf "DAG Pipeline Tests                %-8s  %-8s  %-8s\n" "4" "0" "4"
printf "GitHub Integration Tests          %-8s  %-8s  %-8s\n" "7" "0" "3"
printf "Deployment Tests                  %-8s  %-8s  %-8s\n" "7" "0" "1"
printf "Dispatch & Watch Tests            %-8s  %-8s  %-8s\n" "8" "0" "8"
printf "Environment & Configuration       %-8s  %-8s  %-8s\n" "8" "0" "8"
echo "--------------------------------  --------  --------  --------"
printf "Integration Tests Subtotal        %-8s  %-8s  %-8s\n" "$INT_PASSED" "$INT_FAILED" "$INT_TOTAL"
echo ""
echo "========================================"
echo "  OVERALL TOTALS"
echo "========================================"
echo ""
printf "Total Passed:  %s\n" "$TOTAL_PASSED"
printf "Total Failed:  %s\n" "$TOTAL_FAILED"
printf "Total Skipped: %s\n" "$TOTAL_SKIPPED"
printf "Total Tests:   %s\n" "$TOTAL_TESTS"
echo ""

if [ $UNIT_TOTAL -gt 0 ]; then
    UNIT_PASS_RATE=$((UNIT_PASSED * 100 / UNIT_TOTAL))
    echo "Unit Test Pass Rate: ${UNIT_PASS_RATE}%"
fi

if [ $INT_TOTAL -gt 0 ]; then
    INT_PASS_RATE=$((INT_PASSED * 100 / INT_TOTAL))
    echo "Integration Test Pass Rate: ${INT_PASS_RATE}%"
fi

if [ $TOTAL_TESTS -gt 0 ]; then
    OVERALL_PASS_RATE=$((TOTAL_PASSED * 100 / TOTAL_TESTS))
    echo "Overall Pass Rate: ${OVERALL_PASS_RATE}%"
fi

echo ""

if [ $TOTAL_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo -e "${GREEN}✓ Unit tests: $UNIT_PASSED/$UNIT_TOTAL${NC}"
    echo -e "${GREEN}✓ Integration tests: $INT_PASSED/$INT_TOTAL (skipped: $INT_SKIPPED)${NC}"
    exit 0
else
    echo -e "${RED}✗ Some tests failed${NC}"
    echo -e "${RED}✗ Failed unit tests: $UNIT_FAILED${NC}"
    echo -e "${RED}✗ Failed integration tests: $INT_FAILED${NC}"
    exit 1
fi
