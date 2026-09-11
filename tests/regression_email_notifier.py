#!/usr/bin/env python3
"""Regression email notifier for test reports.

Compares the two most recent test reports and sends email notification
if regressions are detected (new failures or decreased pass count).

Usage:
    python tests/regression_email_notifier.py
    python tests/regression_email_notifier.py --dry-run
    python tests/regression_email_notifier.py --reports-dir /path/to/reports
"""

from __future__ import annotations

import argparse
import os
import re
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional


def find_recent_reports(reports_dir: Path, count: int = 2) -> list[Path]:
    """Return N most recent test_*.md files sorted by filename timestamp."""
    reports = list(reports_dir.glob("test_*.md"))
    return sorted(reports, key=lambda p: p.name, reverse=True)[:count]


def parse_report_summary(report_path: Path) -> dict:
    """Parse markdown report and extract summary data."""
    content = report_path.read_text()

    # Extract run date
    timestamp_match = re.search(r'\*\*Run Date\*\*: (.+)', content)
    timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"

    # Extract summary stats
    total = int(re.search(r'\*\*Total Tests\*\*: (\d+)', content).group(1))
    passed = int(re.search(r'\*\*Passed\*\*: (\d+)', content).group(1))
    failed = int(re.search(r'\*\*Failed\*\*: (\d+)', content).group(1))

    # Extract failed test names
    failed_list = []
    failed_section = re.search(r'## ❌ Failed Tests.*?\n\n(.*?)(?:\n## |\Z)', content, re.DOTALL)
    if failed_section:
        for match in re.finditer(r'- \*\*(.+?)\*\*', failed_section.group(1)):
            failed_list.append(match.group(1))

    return {
        'path': report_path,
        'timestamp': timestamp,
        'total': total,
        'passed': passed,
        'failed': failed,
        'failed_list': set(failed_list),
    }


def detect_regression(current: dict, previous: dict) -> Optional[dict]:
    """Compare reports and return regression info if detected."""
    new_failures = current['failed_list'] - previous['failed_list']
    recovered = previous['failed_list'] - current['failed_list']
    pass_diff = current['passed'] - previous['passed']
    all_failures = current['failed_list']

    # Trigger if: new failures, pass count decreased, OR any failures exist
    if new_failures or pass_diff < 0 or all_failures:
        return {
            'new_failures': sorted(new_failures),
            'recovered': sorted(recovered),
            'pass_diff': pass_diff,
            'all_failures': sorted(all_failures),
        }
    return None


def format_email(regression: dict, current: dict, previous: dict) -> tuple[str, str]:
    """Format email subject and body."""
    n_new = len(regression['new_failures'])
    n_total = len(regression['all_failures'])
    project_name = os.environ.get("PROJECT_NAME", "Project")

    # Subject reflects severity
    if n_new > 0:
        subject = f"[REGRESSION] {project_name} Tests: {n_new} new, {n_total} total failures"
    else:
        subject = f"[TEST FAILURES] {project_name} Tests: {n_total} failing"

    lines = [
        "Test Report",
        "=" * 40,
        "",
        f"Current report:  {current['path'].name}",
        f"Previous report: {previous['path'].name}",
        "",
        f"Pass count: {previous['passed']} -> {current['passed']} ({regression['pass_diff']:+d})",
        "",
    ]

    if regression['new_failures']:
        lines.append(f"NEW FAILURES ({len(regression['new_failures'])}):")
        for test in regression['new_failures']:
            lines.append(f"  - {test}")
        lines.append("")

    if regression['recovered']:
        lines.append(f"RECOVERED ({len(regression['recovered'])}):")
        for test in regression['recovered']:
            lines.append(f"  + {test}")
        lines.append("")

    if regression['all_failures']:
        lines.append(f"ALL CURRENT FAILURES ({len(regression['all_failures'])}):")
        for test in regression['all_failures']:
            lines.append(f"  x {test}")
        lines.append("")

    return subject, "\n".join(lines)


def send_email(subject: str, body: str, recipients: list[str]) -> bool:
    """Send email via SMTP."""
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")

    if not all([host, user, password]):
        print("SMTP not configured (missing SMTP_HOST, SMTP_USER, or SMTP_PASSWORD)")
        return False

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP(host, port) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(user, recipients, msg.as_string())
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect test regressions and send email")
    parser.add_argument("--reports-dir", type=Path, help="Reports directory")
    parser.add_argument("--dry-run", action="store_true", help="Detect without sending email")
    args = parser.parse_args()

    try:
        reports_dir = args.reports_dir or (Path(__file__).parent / "reports")
        reports = find_recent_reports(reports_dir)

        if len(reports) < 2:
            print(f"Need at least 2 reports, found {len(reports)}")
            return 0

        current = parse_report_summary(reports[0])
        previous = parse_report_summary(reports[1])

        print(f"Comparing: {current['path'].name} vs {previous['path'].name}")

        regression = detect_regression(current, previous)

        if not regression:
            print("All tests passing - no notification needed")
            return 0

        subject, body = format_email(regression, current, previous)

        if args.dry_run:
            print(f"\n[DRY RUN] Would send email:\nSubject: {subject}\n\n{body}")
            return 0

        recipients_str = os.environ.get("EMAIL_RECIPIENTS", "")
        if not recipients_str:
            print("EMAIL_RECIPIENTS not set, skipping notification")
            return 0

        recipients = [r.strip() for r in recipients_str.split(",")]
        if send_email(subject, body, recipients):
            print(f"Regression email sent to {len(recipients)} recipient(s)")
        else:
            return 1

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
