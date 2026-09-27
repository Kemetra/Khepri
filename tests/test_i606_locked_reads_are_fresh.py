"""A locked read returns the row as the lock found it, not as the session last loaded it (`#606`).

`#606` and `#610`: a `SELECT ... FOR UPDATE` whose row is already in the session's identity map
hands back that cached object with its attributes unrefreshed (SQLAlchemy's `populate_existing`
default is off). A re-check under the lock then reads the state from before the wait, and a
completion that waited for another to commit passed its `started` guard and wrote over it.

These tests need no PostgreSQL. The defect is the ORM's, not the database's: a file-backed SQLite
engine hands each session its own connection, so session A loads a row, session B changes it and
commits, and A's locked read either sees B's value or does not. SQLite emits no `FOR UPDATE`, but
`populate_existing` is what refreshes the object, and it applies to the statement either way.
`tests/test_w110_concurrent_runs_postgres.py` drives the same defect through the real doors.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session

from khepri.rca.workspace.contracts import RUN_FAILED
from khepri.rca.workspace.locks import live_runs_for_update, run_for_update, version_for_update
from khepri.rca.workspace.schema import AnalysisRunRow, DatasetVersionRow
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import started_run

_RUN_FAILED_BEHIND = "UPDATE rca_workspace_analysis_runs SET state = :value WHERE run_id = :key"
_VERSION_ENDED_BEHIND = (
    "UPDATE rca_workspace_dataset_versions SET retention_state = :value WHERE version_id = :key"
)


@dataclass(frozen=True)
class LockCase:
    """One named lock: the row it locks, how another transaction changes it, and what must show."""

    row: type
    key: Callable[[Any], str]
    lock: Callable[[Any, str], Any]
    change: str
    attribute: str
    value: str


CASES = {
    "run_for_update": LockCase(
        AnalysisRunRow,
        lambda run: run.run_id,
        lambda run, owner: run_for_update(run.run_id, owner),
        _RUN_FAILED_BEHIND,
        "state",
        RUN_FAILED,
    ),
    "version_for_update": LockCase(
        DatasetVersionRow,
        lambda run: run.version_id,
        lambda run, owner: version_for_update(run.version_id, owner),
        _VERSION_ENDED_BEHIND,
        "retention_state",
        "tombstoned",
    ),
    "live_runs_for_update": LockCase(
        AnalysisRunRow,
        lambda run: run.run_id,
        lambda run, owner: live_runs_for_update(run.version_id, owner),
        _RUN_FAILED_BEHIND,
        "state",
        RUN_FAILED,
    ),
}


def _file_engine(path: Path) -> Engine:
    """Its own connection per session, foreign keys enforced as `sqlite_engine` enforces them."""
    engine = create_engine(f"sqlite+pysqlite:///{path}")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(connection, _record) -> None:
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


@pytest.fixture
def run_world(tmp_path: Path):
    """A journey over a file engine, with one started run: `(engine, run, owner_id)`."""
    engine = _file_engine(tmp_path / "w606.sqlite")
    j = journey(engine)
    who = member(j.w)
    run, _job_id, _session_id = started_run(j, who)
    yield engine, run, who.owner_id
    engine.dispose()


def _locked_after_stale_load(engine: Engine, case: LockCase, run: Any, owner_id: str) -> list:
    """Session A loads the row, B changes it and commits, then A takes the lock: what A sees.

    `loaded` is held until the lock has run. The identity map keeps objects by weak reference, so
    a load nobody holds is collected and the locked read would load afresh -- a test that passes
    with the defect present. In production the holder is the caller's own earlier read.
    """
    with Session(engine) as database:
        loaded = database.get(case.row, case.key(run))
        assert loaded is not None, "the row to hold was not loaded"
        with engine.begin() as other:
            other.execute(text(case.change), {"value": case.value, "key": case.key(run)})
        seen = list(database.scalars(case.lock(run, owner_id)))
        del loaded
        return seen


@pytest.mark.parametrize("name", sorted(CASES))
def test_a_locked_read_sees_the_row_as_the_lock_found_it(run_world, name: str) -> None:
    engine, run, owner_id = run_world
    case = CASES[name]

    (row,) = _locked_after_stale_load(engine, case, run, owner_id)

    assert getattr(row, case.attribute) == case.value, f"{name} returned the row as first loaded"
