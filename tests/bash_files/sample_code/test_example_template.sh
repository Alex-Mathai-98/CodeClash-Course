#!/bin/bash

# Example test script template
# This script runs the Python test and captures its exit code

echo "Testing example template..."

# Source the prelude to set up environment
. .claude/prelude.sh

# Run the Python test
python tests/bash_files/sample_code/example_test.py

# Exit with the test's exit code
exit $?
