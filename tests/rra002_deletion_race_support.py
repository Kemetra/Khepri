"""Two requests inside `DeletionService.delete_session_content` at once (`#560` item 6; `RRA-002`).

`#557` proved overlapping *version* deletions end the version once. The session-content path it
calls had no such proof: two requests that both read the session live, or that both hold the same
pending job, depend on how `SqlDeletionRepository.begin` and `complete` settle the race.

`RRA-002` requires "immediate idempotent deletion" and "content-free deletion evidence". Two
concurrent requests for one session are that idempotence under contention, so both must answer the
one completed job, and the evidence must record one attempt -- not one per request.

The two windows a second request can be caught in, each hooked at a seam the service still calls:

- `WINDOW_AFTER_READ` -- after `get_session`, the service's one unlocked read, and before `begin`.
  `begin` settles it: the session row is taken `FOR UPDATE`, and the job already written is
  returned rather than a second inserted against `uq_deletion_session`.
- `WINDOW_AFTER_TARGETS` -- after `begin` returned the shared pending job and `get_targets` read
  its targets, before any object is touched. `complete` settles it: under the job's row lock a job
  already `complete` is returned, so the second request's evidence is not written against targets
  the first already removed.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from khepri.rra.artifact_persistence import ReportArtifactRow  # noqa: F401 -- registers the table
from khepri.rra.deletion import DeletionJob, DeletionService, DeletionTarget
from khepri.rra.persistence import (
    BetaSessionRow,
    DeletionJobRow,
    SqlDeletionRepository,
    SqlSessionStore,
)
from khepri.rra.sessions import BetaSession, SessionScope

WINDOW_AFTER_READ = "after_read"
WINDOW_AFTER_TARGETS = "after_targets"
WINDOWS = (WINDOW_AFTER_READ, WINDOW_AFTER_TARGETS)

Hook = Callable[[], None]


class ObjectStore:
    """An object store with S3's semantics for this path: deleting a missing key succeeds."""

    def __init__(self) -> None:
        self.deleted_keys: list[str] = []

    def abort_multipart_uploads(self, prefix: str) -> None:
        del prefix

    def delete_prefix(self, prefix: str) -> None:
        del prefix

    def delete(self, key: str) -> None:
        self.deleted_keys.append(key)


class _HookedSessions:
    """The session reader, with the hook run after the service's unlocked read."""

    def __init__(self, store: SqlSessionStore, hook: Hook) -> None:
        self._store = store
        self._hook = hook

    def get_session(self, session_id: str) -> BetaSession | None:
        session = self._store.get_session(session_id)
        self._hook()
        return session


class _HookedDeletions(SqlDeletionRepository):
    """The real repository, with the hook run after `get_targets` read the job's targets."""

    def __init__(self, factory: sessionmaker[Session], hook: Hook) -> None:
        super().__init__(factory)
        self._hook = hook

    def get_targets(self, job: DeletionJob) -> tuple[DeletionTarget, ...]:
        targets = super().get_targets(job)
        self._hook()
        return targets


def _no_hook() -> None:
    return None


def hooked_service(
    factory: sessionmaker[Session],
    *,
    window: str,
    hook: Hook,
    objects: ObjectStore,
) -> DeletionService:
    """One request's deletion service over the real SQL stores, caught in `window`."""
    read_hook = hook if window == WINDOW_AFTER_READ else _no_hook
    targets_hook = hook if window == WINDOW_AFTER_TARGETS else _no_hook
    return DeletionService(
        sessions=_HookedSessions(SqlSessionStore(factory), read_hook),
        deletions=_HookedDeletions(factory, targets_hook),
        objects=objects,
    )


def delete(service: DeletionService, scope: SessionScope, now: datetime) -> DeletionJob:
    return service.delete_session_content(session_id=scope.session_id, reason="immediate", now=now)


@dataclass(frozen=True, slots=True)
class Settled:
    """What the store holds for one session once both requests returned."""

    jobs: int
    attempt_count: int
    evidence: tuple[tuple[int, str, str], ...]
    content_deleted: bool


def settled(factory: sessionmaker[Session], scope: SessionScope) -> Settled:
    with factory() as database:
        jobs = database.scalar(
            select(func.count())
            .select_from(DeletionJobRow)
            .where(DeletionJobRow.session_id == scope.session_id)
        )
        job = database.scalar(
            select(DeletionJobRow).where(DeletionJobRow.session_id == scope.session_id)
        )
        session = database.get(BetaSessionRow, scope.session_id)
    evidence = SqlDeletionRepository(factory).list_evidence(job.deletion_id)
    return Settled(
        jobs=jobs,
        attempt_count=job.attempt_count,
        evidence=tuple((item.attempt_number, item.target_id, item.outcome) for item in evidence),
        content_deleted=session.content_deleted_at is not None,
    )


def assert_one_deletion(results: list[DeletionJob], state: Settled, upload_id: str) -> None:
    """Both requests answer the one completed job, which recorded one attempt."""
    assert [result.state for result in results] == ["complete", "complete"]
    assert len({result.deletion_id for result in results}) == 1
    assert state == Settled(
        jobs=1,
        attempt_count=1,
        evidence=((1, upload_id, "deleted"),),
        content_deleted=True,
    )
