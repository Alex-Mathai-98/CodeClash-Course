# Test Suite Documentation

This directory contains the automated test suite, along with logging and reporting infrastructure.

## Directory Structure

```
tests/
├── bash_files/           # Test scripts organized by category
│   ├── run_all_tests.sh  # Main test runner (with logging)
│   └── ...               # Individual test scripts
├── logs/                 # Auto-generated test logs (timestamped)
├── reports/              # Auto-generated markdown reports (timestamped)
├── generate_test_report.py  # Report generator script
└── run_tests_with_report.sh # Convenience wrapper
```

## Running Tests

### Option 1: Run Tests Only
```bash
bash tests/bash_files/run_all_tests.sh
```

This will:
- Run all 24 test files
- Display results to console (with colors)
- Save full output to `tests/logs/test_run_YYYY-MM-DD_HH-MM-SS.log`
- Exit with code 0 (success) or 1 (failure)

### Option 2: Run Tests + Generate Report
```bash
bash tests/run_tests_with_report.sh
```

This will:
- Run all tests (as above)
- Automatically generate a markdown report
- Save report to `tests/reports/test_YYYY-MM-DD_HH-MM-SS.md`

### Option 3: Generate Report from Existing Log
```bash
# Use most recent log file
python tests/generate_test_report.py

# Use specific log file
python tests/generate_test_report.py --log tests/logs/test_run_2025-10-30_17-30-00.log

# Specify output location
python tests/generate_test_report.py --log <log_file> --output <report_file>
```

## Report Format

The generated markdown reports include:

1. **Test Run Timestamp**: When tests were executed
2. **Summary Statistics**: Total/Passed/Failed counts and success rate
3. **Passed Tests**: Bulleted list of all passing tests ✅
4. **Failed Tests**: Bulleted list with failure details (exit codes, timeouts) ❌
5. **Log Reference**: Link to full test output

### Example Report

```markdown
# Test Report
**Run Date**: 2025-10-30 17:30:00

## Summary
- **Total Tests**: 24
- **Passed**: 23 ✅
- **Failed**: 1 ❌
- **Success Rate**: 95.83%

## ✅ Passed Tests (23)
- root_tests/test_hydra_integration.sh
- root_tests/test_config_equivalence.sh
[... more tests ...]

## ❌ Failed Tests (1)
- **tools/execution_log_parser/test_equivalence_with_existing_tests.sh**
  - Exit Code: 1

## Logs
Full output: `logs/test_run_2025-10-30_17-30-00.log`
```

## Log Files

Log files are automatically created with timestamps:
- Location: `tests/logs/test_run_YYYY-MM-DD_HH-MM-SS.log`
- Content: Full test output including all command output
- Format: Plain text (ANSI color codes included but also work without)
- Retention: Manual (not auto-deleted)

## Test Categories

The test suite includes:
- **Root Tests**: Configuration and integration tests
- **Tool Tests**: Testing of individual tools (instrumentation, minimization, etc.)
- **Log Instrumentation**: Execution trace and representation tests
- **Integration Tests**: End-to-end workflow tests

## Timeouts

Tests have different timeout limits based on complexity:
- **Regular tests**: 5 minutes (300s)
- **Parallel tests**: 10 minutes (600s)
  - `test_batch_processor_utility`
  - `test_tool_instrumentation`
  - `test_monolith_backward_compatibility`
  - `test_solution_minimization`

## CI/CD Integration

The test runner exits with appropriate codes:
- **Exit Code 0**: All tests passed
- **Exit Code 1**: One or more tests failed
- **Exit Code 124**: Test timeout

This makes it easy to integrate with CI/CD pipelines:
```bash
if bash tests/bash_files/run_all_tests.sh; then
    echo "Tests passed!"
else
    echo "Tests failed - check logs"
    exit 1
fi
```

## Nightly Test Runs (CRON)

To run tests automatically every night, use a cron job with `run_tests_with_report.sh`.

### Setup

1. Make the script executable:
```bash
chmod +x tests/run_tests_with_report.sh
```

2. Edit your crontab:
```bash
crontab -e
```

3. Add an entry to run tests nightly (e.g., at 10 PM):
```bash
0 22 * * * /path/to/your-project/tests/run_tests_with_report.sh >> /path/to/your-project/tests/logs/cron_$(date +\%Y-\%m-\%d_\%H-\%M-\%S).log 2>&1
```

### How it works

The cron job:
- Runs the full test suite with report generation
- Redirects all output to a timestamped log file in `tests/logs/`
- Note: In crontab, `%` must be escaped as `\%`

### Viewing Results

Check the generated log and report files:
```bash
# View cron output
ls tests/logs/cron_*.log

# View generated test reports
ls tests/reports/test_*.md
```

## Troubleshooting

### Log file not found
Ensure you're running from the project root directory and have sourced the environment:
```bash
. .claude/prelude.sh
bash tests/bash_files/run_all_tests.sh
```

### Permission denied
Make sure scripts are executable:
```bash
chmod +x tests/bash_files/run_all_tests.sh
chmod +x tests/run_tests_with_report.sh
chmod +x tests/generate_test_report.py
```

### Report shows 0 tests
This happens if the test run was interrupted before completion. Check the log file to see where it stopped.
