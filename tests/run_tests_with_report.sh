#!/bin/bash

# Wrapper script to run all tests and automatically generate a markdown report
# This script combines test execution and report generation in one command
# Designed to work in cron jobs by using absolute paths

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get the project root directory (parent of tests/)
PROJECT_ROOT="$( cd "${SCRIPT_DIR}/.." && pwd )"

# Navigate to project root for relative paths to work
cd "${PROJECT_ROOT}"

# Activate conda environment and set up environment variables
source "${PROJECT_ROOT}/.claude/prelude.sh"

echo "=========================================="
echo "Running Tests with Report Generation"
echo "=========================================="
echo ""

# Run the tests
bash "${SCRIPT_DIR}/bash_files/run_all_tests.sh"
TEST_EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Generating Test Report"
echo "=========================================="
echo ""

# Generate the report
python "${SCRIPT_DIR}/generate_test_report.py"
REPORT_EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Checking for Regressions"
echo "=========================================="
echo ""

# Send regression notification if there are new failures or regressions
python "${SCRIPT_DIR}/regression_email_notifier.py"

echo ""
echo "=========================================="
echo "Complete"
echo "=========================================="
echo ""

# Exit with the test exit code (not the report generation code)
# This ensures CI/CD systems see the actual test results
exit $TEST_EXIT_CODE
