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

It reads the outcomes the full suite recorded (`marker_report.py`) rather than running
the marked subset a second time, and a missing report is refused too.
"""

from __future__ import annotations

from marker_report import require

if __name__ == "__main__":
    raise SystemExit(
        require(
            "concurrency",
            unavailable="the PostgreSQL service was unreachable. KHEPRI_TEST_DATABASE_URL "
            "must point at a live database in CI.",
        )
    )
