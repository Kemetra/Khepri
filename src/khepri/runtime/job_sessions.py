"""The session behind each of a scope's report jobs, read in one pass for the artifact handoff
(`W1-06`).

Analysis detail offers an artifact only while the run's analysis session can still be resumed, and
the Analyses spine words a report by the same rule. Both need, for each settling job, the session's
two liveness facts -- whether its deletion was requested, and when its content expires -- and the
job's scope. Read per run through `JobReader.find` and `SqlSessionStore.get_session` that was two
round trips per completed run on a spine the roadmap leaves unbounded (review on `#376`, round 3);
here it is one join over the scope's jobs, however many runs the spine lists.

Composed in `khepri.runtime` because it joins an `RRA` table to an `RRA` table on behalf of an `RCA`
surface: `R7-01` §3 forbids either package importing the other, and the join is a *read* the shell
makes, not a rule either package owns. It publishes nothing about a job but what the handoff needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import Select

from khepri.rra.job_persistence import ReportJobRow
from khepri.rra.persistence import BetaSessionRow

#: One selected row: the job's identity and scope, then the session's two liveness facts.
_ScopeRow = tuple[str, str, str, "datetime | None", "datetime"]


@dataclass(frozen=True, slots=True)
class JobSession:
    """One job's scope and the liveness of the session it ran in."""

    job_id: str
    owner_id: str
    session_id: str
    deletion_requested_at: datetime | None
    content_expires_at: datetime


class JobSessionsPort(Protocol):
    def for_scope(self, owner_id: str) -> dict[str, JobSession]: ...

    def job(self, job_id: str, owner_id: str) -> JobSession | None: ...


class SqlJobSessions:
    """Every job of one scope with its session's liveness, by job identifier, in one read."""

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def scope_statement(self, owner_id: str) -> Select[_ScopeRow]:
        """The scope's jobs, asked of the relation whose index leads with `owner_id`.

        `rra_report_jobs` has no `owner_id`-leading index -- only `(state, available_at)`,
        `(lease_expires_at)` and `(session_id, state)` -- so asking the scope there scans every
        organization's jobs, on a spine the roadmap leaves unbounded (review on `#378`).
        `rra_beta_sessions` carries `uq_session_owner_scope` on `(owner_id, session_id)`, whose
        leading column is `owner_id`; the jobs are then reached by `session_id`, which
        `ix_report_job_session_state` leads with. Both sides stay index-backed.

        The same rows either way, and provably: `session_id` is `rra_beta_sessions`' primary key,
        so the join answers exactly one session per job, and `fk_report_job_session_scope` ties
        that job's `owner_id` to that session's. No job of this scope hangs off another scope's
        session, and none of another scope's off this one's. `owner_id` is still selected from the
        job, so what the reader publishes about scope is unchanged.
        """
        return (
            select(
                ReportJobRow.job_id,
                ReportJobRow.owner_id,
                ReportJobRow.session_id,
                BetaSessionRow.deletion_requested_at,
                BetaSessionRow.content_expires_at,
            )
            .join(BetaSessionRow, BetaSessionRow.session_id == ReportJobRow.session_id)
            .where(BetaSessionRow.owner_id == owner_id)
        )

    def for_scope(self, owner_id: str) -> dict[str, JobSession]:
        statement = self.scope_statement(owner_id)
        with self._factory() as database:
            rows = database.execute(statement).all()
        return {
            row.job_id: JobSession(
                job_id=row.job_id,
                owner_id=row.owner_id,
                session_id=row.session_id,
                deletion_requested_at=_utc(row.deletion_requested_at),
                content_expires_at=_utc(row.content_expires_at),
            )
            for row in rows
        }

    def job(self, job_id: str, owner_id: str) -> JobSession | None:
        """One job of this scope, for a surface asking about a single run (`#380`).

        The spine reads the whole scope because it words every row; Analysis detail and an artifact
        download ask about one run, and answering those from `for_scope` made each click read a
        history the roadmap leaves unbounded. Same statement, same indexed path -- `owner_id` on
        `uq_session_owner_scope`, then the job by `session_id` -- narrowed by the job's own
        identifier, which is `rra_report_jobs`' primary key.
        """
        statement = self.scope_statement(owner_id).where(ReportJobRow.job_id == job_id)
        with self._factory() as database:
            row = database.execute(statement).first()
        if row is None:
            return None
        return JobSession(
            job_id=row.job_id,
            owner_id=row.owner_id,
            session_id=row.session_id,
            deletion_requested_at=_utc(row.deletion_requested_at),
            content_expires_at=_utc(row.content_expires_at),
        )


def _utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive instants; every instant this module states is UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


__all__ = ["JobSession", "JobSessionsPort", "SqlJobSessions"]
