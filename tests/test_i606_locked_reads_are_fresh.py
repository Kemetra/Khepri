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
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session

from khepri.rca.workspace.contracts import RUN_FAILED
from khepri.rca.workspace.locks import live_runs_for_update, run_for_update, version_for_update
from khepri.rca.workspace.schema import AnalysisRunRow, DatasetVersionRow
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import started_run


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
    """A journey over a file engine, with one started run: `(engine, journey, run, owner_id)`."""
    engine = _file_engine(tmp_path / "w606.sqlite")
    j = journey(engine)
    who = member(j.w)
    run, _job_id, _session_id = started_run(j, who)
    yield engine, j, run, who.owner_id
    engine.dispose()


def _changed_behind(engine: Engine, statement: str, **values: str) -> None:
    """Session B: change the row beneath the ORM and commit, as another transaction would."""
    with engine.begin() as connection:
        connection.execute(text(statement), values)


def _locked_after_stale_load(
    engine: Engine, load: Callable[[Session], object], change: Callable[[], None], lock
) -> list:
    """Session A loads the row, B changes it, then A takes the lock and returns what it sees.

    `loaded` is held until the lock has run. The identity map keeps objects by weak reference, so
    a load nobody holds is collected and the locked read would load afresh -- a test that passes
    with the defect present. In production the holder is the caller's own earlier read.
    """
    with Session(engine) as database:
        loaded = load(database)
        assert loaded is not None, "the row to hold was not loaded"
        change()
        seen = list(database.scalars(lock))
        del loaded
        return seen


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#606: RED until the lock refreshes")
def test_run_for_update_reads_the_run_as_the_lock_found_it(run_world) -> None:
    engine, _j, run, owner_id = run_world
    (row,) = _locked_after_stale_load(
        engine,
        lambda database: database.get(AnalysisRunRow, run.run_id),
        lambda: _changed_behind(
            engine,
            "UPDATE rca_workspace_analysis_runs SET state = :state WHERE run_id = :run",
            state=RUN_FAILED,
            run=run.run_id,
        ),
        run_for_update(run.run_id, owner_id),
    )
    assert row.state == RUN_FAILED, "the locked read returned the run as first loaded (#606)"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#606: RED until the lock refreshes")
def test_version_for_update_reads_the_version_as_the_lock_found_it(run_world) -> None:
    engine, _j, run, owner_id = run_world
    (row,) = _locked_after_stale_load(
        engine,
        lambda database: database.get(DatasetVersionRow, run.version_id),
        lambda: _changed_behind(
            engine,
            "UPDATE rca_workspace_dataset_versions SET retention_state = 'tombstoned' "
            "WHERE version_id = :version",
            version=run.version_id,
        ),
        version_for_update(run.version_id, owner_id),
    )
    assert row.retention_state == "tombstoned", "the locked read returned the version as loaded"


@pytest.mark.xfail(strict=True, raises=AssertionError, reason="#606: RED until the lock refreshes")
def test_live_runs_for_update_reads_each_run_as_the_lock_found_it(run_world) -> None:
    engine, _j, run, owner_id = run_world
    (row,) = _locked_after_stale_load(
        engine,
        lambda database: database.get(AnalysisRunRow, run.run_id),
        lambda: _changed_behind(
            engine,
            "UPDATE rca_workspace_analysis_runs SET state = :state WHERE run_id = :run",
            state=RUN_FAILED,
            run=run.run_id,
        ),
        live_runs_for_update(run.version_id, owner_id),
    )
    assert row.state == RUN_FAILED, "the locked read returned a live run as first loaded"
