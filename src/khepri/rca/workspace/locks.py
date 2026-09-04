"""The named locking statements of the workspace store (`W1-02`, `W1-03`).

Every row lock the store takes is a **module-level named statement** rather than an inline
`.with_for_update()`, following `account_for_update` in `rca/persistence.py` and for the reason
stated there: SQLite emits no `FOR UPDATE` and SQLAlchemy silently omits it for that dialect, so an
inline lock someone later removed would leave the whole suite green. Being named, each is compiled
against the PostgreSQL dialect in `test_w102_workspace_locks.py` and
`test_w103_tombstone_projection.py` to prove the clause, asserted at its call site by source, and
listed in `test_rca001_lock_scope.py`'s `_LOCK_ROUTES` so only the methods that test names may reach
it.

Split from `store.py` on `#371` so the store stays the operations, and the locks -- three
statements whose argument is the same argument -- can be read together.
"""

from __future__ import annotations

from sqlalchemy import select

from khepri.rca.workspace.schema import RETENTION_ACTIVE, AnalysisRunRow, DatasetVersionRow


def run_for_update(run_id: str, owner_id: str | None = None):
    """Lock one run row for the duration of the caller's transaction.

    `complete_analysis_run` needs it because read-then-write is not atomic: two workers can both
    read `started`, both pass the check, and the second overwrite the first's package digest and
    version provenance while both report success. Review on `#370` found that; `FR-111` binds a run
    to the versions it actually derived under, so a lost write there is lost provenance.

    Scoped when `owner_id` is given, so a foreign identifier selects and locks no row -- an
    unscoped lock held another tenant's row before `_visible_in` rejected it, and could block on
    that tenant's transaction.
    """
    statement = select(AnalysisRunRow).where(AnalysisRunRow.run_id == run_id)
    if owner_id is not None:
        statement = statement.where(AnalysisRunRow.owner_id == owner_id)
    return statement.with_for_update()


def version_for_update(version_id: str, owner_id: str | None = None):
    """Lock one dataset version row. See `run_for_update`.

    `seal_dataset_version` needs it for the reason `run_for_update` states: it reports whether
    *this* call sealed the version, and two callers must not both be told they did.
    `set_retention_state` takes it too -- see the comment there for the round on `#370` that
    removed it and put it back.
    """
    statement = select(DatasetVersionRow).where(DatasetVersionRow.version_id == version_id)
    if owner_id is not None:
        statement = statement.where(DatasetVersionRow.owner_id == owner_id)  # see `run_for_update`
    return statement.with_for_update()


def live_runs_for_update(version_id: str, owner_id: str):
    """Lock every live run of one version, in one scope, for the caller's transaction.

    The cascade projects each run's tombstone from the run *as stored* and then tombstones it. A
    plain read there is a race: `complete_analysis_run` holds `run_for_update` on the same row,
    and a plain `SELECT` does not wait for it. The cascade then reads the pre-completion row --
    `started`, no package digest, no versions -- projects an immutable tombstone from that, blocks
    on its own `UPDATE` until the completion commits, and commits over it: a completed run whose
    deletion record says it never completed, and whose provenance `FR-111` bound to it is gone
    from the only record that survives. Two reviewers found it independently on `#371`.

    `FOR UPDATE` here waits for the completion instead, and reads the row it left. The reverse
    order is already safe: a completion that arrives while the cascade holds these rows blocks,
    then finds the run tombstoned and is refused by `_check_terminal_state`.

    Both predicates and the liveness filter are part of the statement, so a run another deletion
    already ended is not locked or re-projected. Compiled in `test_w103_tombstone_projection.py`.
    """
    return (
        select(AnalysisRunRow)
        .where(AnalysisRunRow.version_id == version_id)
        .where(AnalysisRunRow.owner_id == owner_id)
        .where(AnalysisRunRow.retention_state == RETENTION_ACTIVE)
        .with_for_update()
    )
