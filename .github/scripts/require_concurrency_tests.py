"""Fail CI when the concurrency contracts did not actually run.

A concurrency test that skips reports green, and green reads as proved. That is the
specific failure this script exists to prevent: `KHEPRI_TEST_DATABASE_URL` pointing at
nothing, the service failing to start, or the marker being renamed all produce a suite
that passes while proving nothing about concurrency.

Two conditions are treated as failures, and the second is the less obvious one:

* any test marked `concurrency` was skipped -- the service is unreachable;
* no test carries the marker at all -- "these tests do not exist yet" and "these tests
  were silently disabled" are indistinguishable from outside, and only the second is a
  regression. Refusing both is the fail-closed reading.

Run after the full suite, so this re-run costs only the marked subset.
"""

from __future__ import annotations

import subprocess
import sys

MARKER = "concurrency"


def main() -> int:
    completed = subprocess.run(  # noqa: S603 -- fixed argv, no shell, no user input
        [
            sys.executable,
            "-m",
            "pytest",
            "-m",
            MARKER,
            "--strict-markers",
            "-q",
            "--no-header",
            "-rs",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    print(output)

    # pytest exits 5 when collection matched nothing.
    if completed.returncode == 5 or " no tests ran" in output:
        print(
            f"FAIL: no test carries the '{MARKER}' marker. Either the concurrency "
            "contracts were never written, or the marker was renamed and the tests "
            "are no longer selected. Both are refused: a suite that proves nothing "
            "about concurrency must not report green.",
            file=sys.stderr,
        )
        return 1

    if completed.returncode != 0:
        print(
            f"FAIL: tests marked '{MARKER}' did not pass.",
            file=sys.stderr,
        )
        return completed.returncode

    if " skipped" in output:
        print(
            f"FAIL: at least one test marked '{MARKER}' was skipped, which means the "
            "PostgreSQL service was unreachable. KHEPRI_TEST_DATABASE_URL must point "
            "at a live database in CI. A skipped concurrency test reports green and "
            "reads as a passing one.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
