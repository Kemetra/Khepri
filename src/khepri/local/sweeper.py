"""Re-export of the retention sweep, which now lives in `khepri.runtime`.

The composition moved to `khepri/runtime/retention_sweep.py` in `W1-07b` so it ships in the wheel
(`KHEPRI-DEC-033` §5). This module keeps `khepri.local`'s import path working and holds **no
second definition** -- `test_the_composition_has_exactly_one_definition` asserts identity, so a
copy here fails rather than drifting.
"""

from __future__ import annotations

from khepri.runtime.retention_sweep import (
    REASON_EXPIRED,
    RetentionCounts,
    RetentionPasses,
    RetentionSweeper,
    SweepReport,
    build_retention_sweeper,
)

__all__ = [
    "REASON_EXPIRED",
    "RetentionCounts",
    "RetentionPasses",
    "RetentionSweeper",
    "SweepReport",
    "build_retention_sweeper",
]
