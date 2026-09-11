#!/usr/bin/env python3
"""
Example test file demonstrating the FAIL-FAST test runner pattern.

This serves as a template for creating Python test files that properly
propagate failures to the bash runner.

=============================================================================
CRITICAL DESIGN PATTERN: FAIL-FAST ON ASSERTION ERRORS
=============================================================================

This test runner is designed to FAIL IMMEDIATELY when any test raises an
AssertionError. This ensures that:

1. The bash wrapper (test_example_template.sh) receives a non-zero exit code
2. run_all_tests.sh correctly counts this as a FAILED test
3. Errors are NOT swallowed silently

=============================================================================
ANTI-PATTERN - DO NOT DO THIS:
=============================================================================

    # BAD: This swallows errors and returns success even when tests fail!
    failures = 0
    for test in tests:
        try:
            test()
        except Exception:
            failures += 1
            print(f"Test {test.__name__} failed")
    print(f"Total failures: {failures}")
    return 0  # WRONG: returns success (exit code 0) even with failures!

The anti-pattern above causes run_all_tests.sh to count the test as PASSED
because the exit code is 0, even though failures occurred.

=============================================================================
CORRECT PATTERN (used below):
=============================================================================

Let AssertionError propagate naturally. Python will exit with code 1,
and the bash runner will correctly report this as a failure.

"""

from __future__ import annotations

import sys
from typing import Callable


def test_example_1() -> None:
    """First example test - uses assert to validate conditions."""
    result = 1 + 1
    assert result == 2, f"Expected 2, got {result}"


def test_example_2() -> None:
    """Second example test - demonstrates string validation."""
    value = "hello"
    assert isinstance(value, str), "Expected a string"
    assert len(value) > 0, "Expected non-empty string"


def run_all_tests() -> int:
    """
    Run all test functions sequentially.

    IMPORTANT: This function does NOT catch exceptions. If any test raises
    an AssertionError, it propagates up and causes a non-zero exit code.
    This is intentional - see module docstring for explanation.

    Returns:
        0 if all tests pass (AssertionError will prevent reaching return)
    """
    tests: list[Callable[[], None]] = [
        test_example_1,
        test_example_2,
    ]

    print("Running example tests...")

    for test in tests:
        print(f"  Running {test.__name__}...")
        test()  # AssertionError propagates up - no try/except!
        print(f"  {test.__name__} passed")

    print("All tests passed!")
    return 0


if __name__ == "__main__":
    sys.exit(run_all_tests())
