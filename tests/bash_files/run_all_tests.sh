#!/bin/bash

# Master script to run all tests and track pass/fail status
# Source the prelude to set up environment
. .claude/prelude.sh

# Create logs directory if it doesn't exist
# Script is in tests/bash_files/, so go up one level to tests/
TESTS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
LOGS_DIR="${TESTS_DIR}/logs"
mkdir -p "$LOGS_DIR"

# Generate timestamped log filename
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="${LOGS_DIR}/test_run_${TIMESTAMP}.log"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track results
PASSED=0
FAILED=0
declare -a FAILED_TESTS

# Redirect all output to log file while also displaying to console
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=========================================="
echo "Running All Tests"
echo "=========================================="
echo "Test run started: $(date '+%Y-%m-%d %H:%M:%S')"
echo "Log file: $LOG_FILE"
echo ""

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Find all test bash files
TEST_FILES=$(find "$SCRIPT_DIR" -name "test_*.sh" -type f | sort)

# Count total tests
TOTAL=$(echo "$TEST_FILES" | wc -l)

echo "Found $TOTAL test files"
echo ""

# Run each test
for test_file in $TEST_FILES; do
    # Get relative path for cleaner output
    rel_path=$(realpath --relative-to="$SCRIPT_DIR" "$test_file")

    echo "----------------------------------------"
    echo "Running: $rel_path"
    echo "----------------------------------------"

    # Set timeout for tests (5 minutes)
    TIMEOUT=300

    # Run the test with appropriate timeout
    timeout $TIMEOUT bash "$test_file"
    exit_code=$?

    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED${NC}: $rel_path"
        ((PASSED++))
    elif [ $exit_code -eq 124 ]; then
        if [ $TIMEOUT -eq 600 ]; then
            echo -e "${RED}✗ TIMEOUT${NC}: $rel_path (exceeded 10 minutes)"
        else
            echo -e "${RED}✗ TIMEOUT${NC}: $rel_path (exceeded 5 minutes)"
        fi
        ((FAILED++))
        FAILED_TESTS+=("$rel_path (TIMEOUT)")
    else
        echo -e "${RED}✗ FAILED${NC}: $rel_path (exit code: $exit_code)"
        ((FAILED++))
        FAILED_TESTS+=("$rel_path (exit code: $exit_code)")
    fi
    echo ""
done

# Print summary
echo "=========================================="
echo "Test Results Summary"
echo "=========================================="
echo -e "Total Tests: $TOTAL"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [ $FAILED -gt 0 ]; then
    echo "Failed Tests:"
    for failed_test in "${FAILED_TESTS[@]}"; do
        echo -e "  ${RED}✗${NC} $failed_test"
    done
    echo ""
    echo "Full test log saved to: $LOG_FILE"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    echo ""
    echo "Full test log saved to: $LOG_FILE"
    exit 0
fi
