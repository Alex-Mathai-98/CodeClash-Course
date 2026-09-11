#!/usr/bin/env python3
"""
Generate a human-readable markdown test report from test log files.

This script parses the test log output from run_all_tests.sh and generates
a formatted markdown report with pass/fail statistics and detailed results.
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def find_latest_log(logs_dir: Path) -> Optional[Path]:
    """Find the most recent test log file."""
    log_files = list(logs_dir.glob("test_run_*.log"))
    if not log_files:
        return None
    return max(log_files, key=lambda p: p.stat().st_mtime)


def parse_log_file(log_path: Path) -> Dict:
    """Parse the test log file and extract test results."""
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    # Remove ANSI color codes for cleaner parsing
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_content = ansi_escape.sub('', content)

    # Extract timestamp from log file
    timestamp_match = re.search(r'Test run started: (.+)', clean_content)
    timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"

    # Extract summary statistics from the final "Test Results Summary" section
    # This ensures we get the overall totals, not intermediate test suite results
    summary_section_match = re.search(
        r'Test Results Summary.*?Total Tests: (\d+).*?Passed: (\d+).*?Failed: (\d+)',
        clean_content,
        re.DOTALL
    )

    if summary_section_match:
        total_tests = int(summary_section_match.group(1))
        passed_tests = int(summary_section_match.group(2))
        failed_tests = int(summary_section_match.group(3))
    else:
        # Fallback: use the last occurrence if summary section not found
        total_matches = re.findall(r'Total Tests: (\d+)', clean_content)
        passed_matches = re.findall(r'Passed: (\d+)', clean_content)
        failed_matches = re.findall(r'Failed: (\d+)', clean_content)

        total_tests = int(total_matches[-1]) if total_matches else 0
        passed_tests = int(passed_matches[-1]) if passed_matches else 0
        failed_tests = int(failed_matches[-1]) if failed_matches else 0

    # Extract individual test results
    passed_list = re.findall(r'✓ PASSED: (.+)', clean_content)

    # Extract failed tests with details
    failed_list = []
    for match in re.finditer(r'✗ FAILED: (.+?) \(exit code: (\d+)\)', clean_content):
        failed_list.append({
            'test': match.group(1),
            'exit_code': int(match.group(2)),
            'type': 'failed'
        })

    # Extract timeout tests with details
    for match in re.finditer(r'✗ TIMEOUT: (.+?) \(exceeded (.+?)\)', clean_content):
        failed_list.append({
            'test': match.group(1),
            'timeout': match.group(2),
            'type': 'timeout'
        })

    return {
        'timestamp': timestamp,
        'log_path': log_path,
        'total': total_tests,
        'passed': passed_tests,
        'failed': failed_tests,
        'passed_list': passed_list,
        'failed_list': failed_list
    }


def generate_markdown_report(data: Dict, output_path: Path) -> None:
    """Generate a markdown report from parsed test data."""

    # Calculate success rate
    success_rate = (data['passed'] / data['total'] * 100) if data['total'] > 0 else 0

    # Build the markdown content
    lines = [
        "# Test Report",
        f"**Run Date**: {data['timestamp']}",
        "",
        "## Summary",
        f"- **Total Tests**: {data['total']}",
        f"- **Passed**: {data['passed']} ✅",
        f"- **Failed**: {data['failed']} ❌",
        f"- **Success Rate**: {success_rate:.2f}%",
        "",
    ]

    # Add passed tests section
    if data['passed_list']:
        lines.append(f"## ✅ Passed Tests ({len(data['passed_list'])})")
        lines.append("")
        for test in sorted(data['passed_list']):
            lines.append(f"- {test}")
        lines.append("")

    # Add failed tests section
    if data['failed_list']:
        lines.append(f"## ❌ Failed Tests ({len(data['failed_list'])})")
        lines.append("")
        for failure in sorted(data['failed_list'], key=lambda x: x['test']):
            lines.append(f"- **{failure['test']}**")
            if failure['type'] == 'failed':
                lines.append(f"  - Exit Code: {failure['exit_code']}")
            elif failure['type'] == 'timeout':
                lines.append(f"  - Timeout: {failure['timeout']}")
        lines.append("")

    # Add logs section
    lines.extend([
        "## Logs",
        f"Full output: `{data['log_path'].relative_to(data['log_path'].parent.parent)}`",
        ""
    ])

    # Write the report
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate markdown test report from test logs'
    )
    parser.add_argument(
        '--log',
        type=Path,
        help='Path to specific log file (default: most recent log)'
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='Output path for markdown report (default: auto-generated in reports/)'
    )

    args = parser.parse_args()

    # Determine the tests directory
    script_dir = Path(__file__).parent
    logs_dir = script_dir / 'logs'
    reports_dir = script_dir / 'reports'

    # Find or use specified log file
    if args.log:
        log_path = args.log
        if not log_path.exists():
            print(f"Error: Log file not found: {log_path}", file=sys.stderr)
            return 1
    else:
        log_path = find_latest_log(logs_dir)
        if not log_path:
            print(f"Error: No log files found in {logs_dir}", file=sys.stderr)
            return 1

    print(f"Parsing log file: {log_path}")

    # Parse the log file
    data = parse_log_file(log_path)

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        # Extract timestamp from log filename
        timestamp_match = re.search(r'test_run_(.+)\.log', log_path.name)
        if timestamp_match:
            timestamp_str = timestamp_match.group(1)
        else:
            timestamp_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        output_path = reports_dir / f"test_{timestamp_str}.md"

    # Generate the report
    generate_markdown_report(data, output_path)

    print(f"Report generated: {output_path}")
    print()
    print("Summary:")
    print(f"  Total Tests: {data['total']}")
    print(f"  Passed: {data['passed']} ✅")
    print(f"  Failed: {data['failed']} ❌")
    print(f"  Success Rate: {data['passed'] / data['total'] * 100:.2f}%" if data['total'] > 0 else "  Success Rate: N/A")

    return 0


if __name__ == '__main__':
    sys.exit(main())
