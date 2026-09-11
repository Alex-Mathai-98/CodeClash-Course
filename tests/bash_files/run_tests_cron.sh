#!/bin/bash

# Wrapper script for running tests via cron
# This script handles environment setup and output redirection

# Get the project root directory (script is in tests/bash_files/, go up 2 levels)
KAGENT_PATH="$( cd "$( dirname "${BASH_SOURCE[0]}" )/../.." && pwd )"
cd "$KAGENT_PATH" || exit 1

# Load environment variables
if [ -f "$KAGENT_PATH/dev.env" ]; then
    source "$KAGENT_PATH/dev.env"
fi

# Generate timestamped report filename
REPORT_DIR="$KAGENT_PATH/tests"
TIMESTAMP=$(date +%Y-%m-%d)
REPORT_FILE="$REPORT_DIR/test_${TIMESTAMP}.log"

# Create report directory if it doesn't exist
mkdir -p "$REPORT_DIR"

# Write header to report
{
    echo "=========================================="
    echo "Automated Test Run"
    echo "Date: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "=========================================="
    echo ""
} > "$REPORT_FILE"

# Run the test script and append to report
bash "$KAGENT_PATH/tests/bash_files/run_all_tests.sh" >> "$REPORT_FILE" 2>&1

# Capture exit code
EXIT_CODE=$?

# Write footer to report
{
    echo ""
    echo "=========================================="
    echo "Test run completed at: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "Exit code: $EXIT_CODE"
    echo "=========================================="
} >> "$REPORT_FILE"

exit $EXIT_CODE
