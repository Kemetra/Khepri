"""The report each analysis run is settled by (`W1-04b`; `RCA-005` `FR-111`).

A run is started in the web process when the report job is queued and completed in the worker
process when that job delivers -- two processes, one run, and the second holds only a job. This
table is the link between them: one row per run naming the job that will settle it, unique per
job, so the worker asks "which run is this job's" and gets one answer or none.

**Why a job identifier may be written to a workspace row when a session identifier may not.**
`runtime/workspace.py` keeps `session_id` out of every record because a session identifier is
bearer-adjacent (`KHEPRI-DEC-015` §7). A job identifier is not: it is derived from the scope, the
session and the package digest, confers nothing on its holder (`FR-023`), and is already served to
the session's owner in the report API's own addresses. It is an opaque object identifier of the
kind `FR-125` puts on every audit event, and it stays out of every surface, tombstone and log.

**One job, one run; one run, one job.** The unique constraint on `job_id` is the arbiter between
two requests that both found no link: the loser's insert fails, `link` raises
`ReportAlreadyLinked`, and the caller rolls back the run it had started -- see
`PipelineRecorder.requested`. The primary key on `run_id` holds the other direction.

**`RESTRICT`, like its siblings.** `_scope_foreign_key` in `schema.py` records why every workspace
foreign key restricts rather than cascades: deletion is `W1-07`'s evidenced operation, not a
constraint's silent side effect. A run's link goes when `W1-07` deletes the run, and a `RESTRICT`
key makes forgetting it loud.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime, ForeignKeyConstraint, String, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker

from khepri.rca.persistence import Base
from khepri.rca.workspace.contracts import RUN_STARTED
from khepri.rca.workspace.unit_of_work import Arbitrated, is_uniqueness_clash, reading, writing

# Content-free, per `rca/errors.py`: it names the constraint and never the identifiers.
REPORT_LINKED_FAILURE = "This report already settles an analysis run, or this run another report."


class ReportAlreadyLinked(Arbitrated):
    """The link exists for this job or this run. The caller rolls back and reads the winner."""


@dataclass(frozen=True, slots=True)
class RunReport:
    """Which job settles which run, in which scope. Paired at the type, as every workspace
    identifier pair is, so a link cannot name one scope's run under another scope's identifier."""

    run_id: str
    owner_id: str
    job_id: str


class RunReportRow(Base):
    """One run's settling job. Frozen once written; deletable only with its run (`W1-07`)."""

    __tablename__ = "rca_workspace_run_reports"
    __table_args__ = (
        ForeignKeyConstraint(
            ["owner_id"],
            ["rca_isolation_scopes.owner_id"],
            name="fk_rca_workspace_run_report_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["owner_id", "run_id"],
            ["rca_workspace_analysis_runs.owner_id", "rca_workspace_analysis_runs.run_id"],
            name="fk_rca_workspace_run_report_run",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("job_id", name="uq_rca_workspace_run_report_job"),
    )

    run_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    job_id: Mapped[str] = mapped_column(String, nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SqlRunReportStore:
    """The link, written once per run and read by scope."""

    def __init__(self, factory: sessionmaker) -> None:
        self._factory = factory

    def link(self, report: RunReport, *, now: datetime) -> RunReport:
        """Bind a run to the job that will settle it.

        Flushed here rather than at commit, so a job already linked -- or a run already linked --
        surfaces inside this call as `ReportAlreadyLinked` and the caller's unit of work can roll
        back what it started. Left to commit, the same violation would surface after the audit
        event was written, as a driver error carrying both identifiers.

        **Two flushes, in this order.** The run this link names is usually still pending in the
        same unit of work, and the ORM orders inserts of unrelated mappers by no foreign key it can
        see, so the first flush writes whatever is pending -- the run -- before the link is added;
        the second writes the link and is where a clash surfaces. Found when the link's `INSERT`
        ran ahead of the run's and the foreign key refused it.
        """
        with writing(self._factory) as database:
            database.flush()
            database.add(
                RunReportRow(
                    run_id=report.run_id,
                    owner_id=report.owner_id,
                    job_id=report.job_id,
                    linked_at=now,
                )
            )
            try:
                database.flush()
            except IntegrityError as clash:
                if not is_uniqueness_clash(clash):
                    raise
                raise ReportAlreadyLinked(REPORT_LINKED_FAILURE) from clash
        return report

    def run_id_for_job(self, owner_id: str, job_id: str) -> str | None:
        """The run a job settles, within one scope. Another scope's job is `None` here."""
        with reading(self._factory) as database:
            return database.scalar(
                select(RunReportRow.run_id).where(
                    RunReportRow.owner_id == owner_id, RunReportRow.job_id == job_id
                )
            )

    def job_id_for_run(self, run_id: str, owner_id: str) -> str | None:
        """The job that settles a run, within one scope."""
        with reading(self._factory) as database:
            return database.scalar(
                select(RunReportRow.job_id).where(
                    RunReportRow.owner_id == owner_id, RunReportRow.run_id == run_id
                )
            )

    def links_of_started_runs(self) -> tuple[RunReport, ...]:
        """Every link whose run is still `started`, across scopes -- what the worker reconciles.

        Across scopes deliberately: the worker acts for no organization, and a run left `started`
        by a crash between a job's terminal transition and its recording is found here whichever
        scope it is in. Each link names its scope, and what follows is read under that scope.
        """
        from khepri.rca.workspace.schema import AnalysisRunRow  # noqa: PLC0415 -- schema imports us

        with reading(self._factory) as database:
            rows = database.scalars(
                select(RunReportRow)
                .join(AnalysisRunRow, AnalysisRunRow.run_id == RunReportRow.run_id)
                .where(AnalysisRunRow.state == RUN_STARTED)
                .order_by(RunReportRow.linked_at, RunReportRow.run_id)
            )
            return tuple(
                RunReport(run_id=row.run_id, owner_id=row.owner_id, job_id=row.job_id)
                for row in rows
            )


__all__ = [
    "REPORT_LINKED_FAILURE",
    "ReportAlreadyLinked",
    "RunReport",
    "RunReportRow",
    "SqlRunReportStore",
]
