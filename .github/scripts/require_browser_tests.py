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

Run after the full suite, so this re-run costs only the marked subset.
"""

from __future__ import annotations

import subprocess
import sys

MARKER = "browser"


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
        # Pin the codec. `text=True` alone decodes with `locale.getpreferredencoding()`,
        # which is UTF-8 on the CI runner but cp1252 on a Windows developer machine. A
        # skip reason carrying a byte cp1252 cannot map makes `subprocess` hand back
        # `stdout=None`, and the guard then crashes instead of refusing -- a non-zero
        # exit for the wrong reason, on the exact path this script exists to detect.
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = completed.stdout + completed.stderr
    print(output)

    # pytest exits 5 when collection matched nothing.
    if completed.returncode == 5 or " no tests ran" in output:
        print(
            f"FAIL: no test carries the '{MARKER}' marker. Either the browser contracts "
            "were never written, or the marker was renamed and the tests are no longer "
            "selected. Both are refused: a suite that proves nothing about what a real "
            "browser does must not report green.",
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
            "pinned Chromium was unavailable. `uv run playwright install chromium` must "
            "run before the suite in CI. A skipped browser test reports green and reads "
            "as a passing one.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
