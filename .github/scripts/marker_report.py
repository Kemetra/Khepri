"""Record every marked test's outcome in the full suite, for the guards that read it.

The two guards beside this file exist because a skipped test reports green and green
reads as proved. They used to re-run their marked subset after the full suite to find
out whether it skipped. That re-ran the 370 browser tests and the 163 concurrency tests
a second time, about seven and a half minutes on every pull request, with the job close
to its timeout. The suite already ran them once, so this plugin writes down what
happened then, and the guards read that.

Loaded only in CI, as `-p marker_report` with this directory on `PYTHONPATH`, and only
when `KHEPRI_MARKER_REPORT` names the file to write. Without that variable it registers
nothing, so a local run is unaffected.

The outcome recorded per test, from its own reports:

* `failed` if any phase failed, which already fails the suite;
* `skipped` if it was skipped at setup or in its body, which an `xfail` is not;
* `xfailed` for an expected failure, which the old guards also accepted;
* `passed` when its call phase passed;
* `not run` when it was collected but never reported, for example after `-x`.

A test counts as marked when the marker applies to it from any level: function, class,
or a module's `pytestmark`.
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

import pytest

REPORT_ENV = "KHEPRI_MARKER_REPORT"
MARKERS = ("browser", "concurrency")
ACCEPTED = frozenset({"passed", "xfailed"})


class _Recorder:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._marked: dict[str, tuple[str, ...]] = {}
        self._outcomes: dict[str, str] = {}

    # After `-m` and `-k` deselection, so a deselected test is not counted as marked.
    @pytest.hookimpl(trylast=True)
    def pytest_collection_modifyitems(self, items: list[pytest.Item]) -> None:
        for item in items:
            names = tuple(sorted({mark.name for mark in item.iter_markers()} & set(MARKERS)))
            if names:
                self._marked[item.nodeid] = names

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.nodeid not in self._marked:
            return
        expected_failure = hasattr(report, "wasxfail")
        if report.failed:
            self._outcomes[report.nodeid] = "failed"
        elif report.skipped and not expected_failure:
            self._outcomes.setdefault(report.nodeid, "skipped")
        elif report.when == "call":
            self._outcomes.setdefault(
                report.nodeid, "xfailed" if expected_failure else "passed"
            )

    def pytest_sessionfinish(self, session: pytest.Session) -> None:
        document = {
            marker: {
                nodeid: self._outcomes.get(nodeid, "not run")
                for nodeid, names in self._marked.items()
                if marker in names
            }
            for marker in MARKERS
        }
        self._path.write_text(json.dumps(document, indent=1, sort_keys=True), encoding="utf-8")


def pytest_configure(config: pytest.Config) -> None:
    path = os.environ.get(REPORT_ENV)
    if path:
        config.pluginmanager.register(_Recorder(Path(path)), "khepri-marker-report")


def require(marker: str, *, unavailable: str) -> int:
    """Refuse unless every test carrying `marker` ran and passed in the recorded suite.

    `unavailable` says what a skip means for this marker, so the failure names the
    missing service rather than only the symptom.
    """
    path = os.environ.get(REPORT_ENV)
    if not path or not Path(path).is_file():
        print(
            f"FAIL: no marker report at {REPORT_ENV}={path!r}. The suite must run with "
            "`-p marker_report` and that variable set, or nothing proves the "
            f"'{marker}' contracts ran.",
            file=sys.stderr,
        )
        return 1
    outcomes: dict[str, str] = json.loads(Path(path).read_text(encoding="utf-8")).get(marker, {})
    if not outcomes:
        print(
            f"FAIL: no test carries the '{marker}' marker. Either those contracts were "
            "never written, or the marker was renamed and they are no longer selected. "
            "Both are refused: a suite that proves nothing must not report green.",
            file=sys.stderr,
        )
        return 1
    counts = Counter(outcomes.values())
    summary = ", ".join(f"{count} {outcome}" for outcome, count in sorted(counts.items()))
    print(f"'{marker}': {len(outcomes)} tests; {summary}")
    refused = sorted(
        (nodeid, outcome) for nodeid, outcome in outcomes.items() if outcome not in ACCEPTED
    )
    if not refused:
        return 0
    for nodeid, outcome in refused[:20]:
        print(f"  {outcome}: {nodeid}", file=sys.stderr)
    if any(outcome == "skipped" for _, outcome in refused):
        print(
            f"FAIL: at least one test marked '{marker}' was skipped, which means "
            f"{unavailable} A skipped test reports green and reads as a passing one.",
            file=sys.stderr,
        )
    else:
        print(f"FAIL: tests marked '{marker}' did not all pass.", file=sys.stderr)
    return 1
