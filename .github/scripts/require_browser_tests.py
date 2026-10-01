"""Fail CI when the browser contracts did not actually run.

A browser test that skips reports green, and green reads as proved. That is the specific
failure this script exists to prevent: the pinned Chromium missing from the runner, a
`playwright install` step removed, or the marker being renamed all produce a suite that
passes while proving nothing about what a real browser does.

`FND-005` is the authority. It records that 236 tests carried the `browser` marker at
`64190f7` and that every one of them skipped in CI, so the `FR-200` accessibility floors,
`FR-204`'s visual evidence, the shell typeface's wire proof, and the journey and PDF
surfaces were verified only on developer machines that happened to have Chromium.

Two conditions are treated as failures, and the second is the less obvious one:

* any test marked `browser` was skipped -- the browser is unavailable;
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
            "browser",
            unavailable="the pinned Chromium was unavailable. `uv run playwright install "
            "chromium` must run before the suite in CI.",
        )
    )
