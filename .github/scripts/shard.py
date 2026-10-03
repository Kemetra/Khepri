"""Run one shard of the suite: whole test files, split by measured weight (SCRUM-43).

The `pytest` job ran the whole suite in one process: 956 s of a 17-minute check, on every
pull request, and again on every pull request `strict` branch protection sent back behind
`main`. `FND-001` still requires pytest on every pull request, so nothing is skipped. The
suite is split across parallel jobs instead, each with its own PostgreSQL service, so the
shards share no database, role or temporary directory.

**Whole files, never single tests.** A module-scoped fixture or a PostgreSQL harness that
builds its schema once per module must see all of its tests in one process.

**Weighted by measured time.** `test-weights.json` beside this file holds each file's
seconds from a full run. A file it does not list, being new, weighs its test count times
`UNMEASURED_SECONDS_PER_TEST`. The weights only balance the shards; a stale or missing
weight costs wall time, never coverage, because `merge_shards.py` proves the shards
together ran every collected test.

Loaded only in CI, as `-p shard` with this directory on `PYTHONPATH`, and only when
`KHEPRI_SHARD` is set (`"2/4"`). `KHEPRI_SHARD_REPORT` names the file it writes: what this
shard collected and what it kept, for `merge_shards.py` to check.
"""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

SHARD_ENV = "KHEPRI_SHARD"
REPORT_ENV = "KHEPRI_SHARD_REPORT"
WEIGHTS = Path(__file__).with_name("test-weights.json")
#: What an unmeasured file's test is assumed to cost. Most tests are well under a second;
#: the PostgreSQL and browser ones, which dominate the measured weights, are not.
UNMEASURED_SECONDS_PER_TEST = 0.2


def parse(text: str) -> tuple[int, int]:
    """`"2/4"` -> `(2, 4)`. Anything else, including an index outside `1..total`, is refused."""
    index, _, total = text.partition("/")
    if not (index.isdigit() and total.isdigit()):
        raise ValueError(f"shard must read 'index/total', got {text!r}")
    i, n = int(index), int(total)
    if not 1 <= i <= n:
        raise ValueError(f"shard index must lie in 1..{n}, got {text!r}")
    return i, n


def weights_for(counts: dict[str, int], *, measured: dict[str, float]) -> dict[str, float]:
    """Each file's weight: its measured seconds, or its test count when it was never measured."""
    return {
        name: measured.get(name, count * UNMEASURED_SECONDS_PER_TEST)
        for name, count in counts.items()
    }


def assign(weights: dict[str, float], *, total: int) -> dict[str, int]:
    """Heaviest file first, onto the lightest shard. Ties break by name and by shard index,
    so every shard computes the same plan from the same collection."""
    loads = [0.0] * total
    plan: dict[str, int] = {}
    for name in sorted(weights, key=lambda n: (-weights[n], n)):
        target = min(range(total), key=lambda i: (loads[i], i))
        plan[name] = target + 1
        loads[target] += weights[name]
    return plan


def select(
    nodeids: list[str], *, index: int, total: int, measured: dict[str, float]
) -> list[str]:
    """The node ids, in collection order, whose file the plan gives to `index`."""
    counts = Counter(_file_of(nodeid) for nodeid in nodeids)
    plan = assign(weights_for(counts, measured=measured), total=total)
    return [nodeid for nodeid in nodeids if plan[_file_of(nodeid)] == index]


def _file_of(nodeid: str) -> str:
    return nodeid.split("::", 1)[0]


def _measured() -> dict[str, float]:
    if not WEIGHTS.is_file():
        return {}
    return json.loads(WEIGHTS.read_text(encoding="utf-8"))


class _Shard:
    def __init__(self, index: int, total: int, report: Path | None) -> None:
        self._index, self._total, self._report = index, total, report

    # Before any `trylast` hook, so `marker_report` records only the tests this shard runs.
    @pytest.hookimpl(tryfirst=True)
    def pytest_collection_modifyitems(
        self, config: pytest.Config, items: list[pytest.Item]
    ) -> None:
        collected = [item.nodeid for item in items]
        kept = set(select(collected, index=self._index, total=self._total, measured=_measured()))
        dropped = [item for item in items if item.nodeid not in kept]
        items[:] = [item for item in items if item.nodeid in kept]
        if dropped:
            config.hook.pytest_deselected(items=dropped)
        if self._report is not None:
            document = {
                "shard": f"{self._index}/{self._total}",
                "collected": collected,
                "selected": [item.nodeid for item in items],
            }
            self._report.write_text(json.dumps(document), encoding="utf-8")


def pytest_configure(config: pytest.Config) -> None:
    text = os.environ.get(SHARD_ENV)
    if not text:
        return
    index, total = parse(text)
    report = os.environ.get(REPORT_ENV)
    config.pluginmanager.register(
        _Shard(index, total, Path(report) if report else None), "khepri-shard"
    )
