"""Where one delivered report and its content-free evidence are kept.

**One row per job, and the primary key says so.** The pipeline asks "was this
job already delivered" before any stage runs, so at most one delivery may exist
for a job. That is the table's identity rather than a unique constraint beside a
generated identifier: a second, different report for one job is the mixture of
versions RRA-006 forbids, and the schema is where that is cheapest to enforce.

**Why the surfaces are their own table.** A delivery names every required
surface, and `DeliveryRecord` refuses to exist otherwise. Storing the three
names in a column would make that claim unverifiable after the fact; storing
them as rows under a composite foreign key on `(job_id, bundle_id)` makes a
surface from another bundle unrepresentable beside this delivery. Both tables are
written inside one transaction, so a delivery is either whole or absent.

**What is stored, and what is deliberately not.** A surface carries figures,
labels, caveats and prose, all of it customer content. What is kept is a digest
over what the surface presented -- enough to tell two runs apart, not enough to
read a word of either. `rra_deletion_evidence.content_digest` already keeps
evidence of customer content this way. There are no report bytes here: bytes
belong in object storage beside the input, and no renderer in this slice
produces any.

**The clock lives here.** RRA-006 binds a generation timestamp to a bundle while
also requiring deterministic regeneration, so the timestamp cannot be part of
the bundle's identity -- it is a fact about the run, and this is the record of
the run. The pipeline therefore has no clock and this store stamps the time.

**The retention boundary.** A published output inherits the input's expiry, so
`expires_at` is copied from the session the same way `rra_uploads.expires_at` is,
and a delivery into a boundary that has already passed is refused. The rows
themselves are content-free and outlive a deletion request, as the report job
and operational event rows do: RRA-007 requires content-free evidence of what
happened to be retained.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from khepri.rra.bundle import REQUIRED_SURFACES, SurfaceContent
from khepri.rra.job_persistence import ReportJobRow
from khepri.rra.persistence import Base, BetaSessionRow, _utc
from khepri.rra.pipeline import DeliveryRecord, ReportDelivery
from khepri.rra.profiling import canonical_json
from khepri.rra.sessions import CrossSessionAccessDenied, SessionExpired


class DeliveryCorrupted(ValueError):
    """A stored delivery does not describe a whole report."""


class DeliveryConflict(RuntimeError):
    """This job already delivered a different report."""


class ReportDeliveryRow(Base):
    __tablename__ = "rra_report_deliveries"
    __table_args__ = (
        CheckConstraint("length(bundle_id) = 64", name="ck_delivery_bundle_id"),
        CheckConstraint(
            "narrative_state IN ('included', 'refused', 'omitted')",
            name="ck_delivery_narrative_state",
        ),
        CheckConstraint(
            "expires_at > generated_at",
            name="ck_delivery_expiry_after_generation",
        ),
        # Supports the surface table's composite reference, which is what makes
        # a surface built for another bundle unrepresentable here.
        UniqueConstraint("job_id", "bundle_id", name="uq_delivery_job_bundle"),
        ForeignKeyConstraint(
            ["job_id", "session_id"],
            ["rra_report_jobs.job_id", "rra_report_jobs.session_id"],
            name="fk_delivery_job_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["owner_id", "session_id"],
            ["rra_beta_sessions.owner_id", "rra_beta_sessions.session_id"],
            name="fk_delivery_session_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_delivery_expiry", "expires_at"),
    )

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    bundle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    package_version: Mapped[str] = mapped_column(String, nullable=False)
    narrative_state: Mapped[str] = mapped_column(String, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ReportDeliverySurfaceRow(Base):
    __tablename__ = "rra_report_delivery_surfaces"
    __table_args__ = (
        CheckConstraint(
            "surface IN ('web', 'pdf', 'excel')",
            name="ck_delivery_surface_name",
        ),
        CheckConstraint(
            "length(content_digest) = 64",
            name="ck_delivery_surface_digest",
        ),
        ForeignKeyConstraint(
            ["job_id", "bundle_id"],
            [
                "rra_report_deliveries.job_id",
                "rra_report_deliveries.bundle_id",
            ],
            name="fk_delivery_surface_bundle",
            ondelete="RESTRICT",
        ),
    )

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    surface: Mapped[str] = mapped_column(String, primary_key=True)
    bundle_id: Mapped[str] = mapped_column(String(64), nullable=False)
    content_digest: Mapped[str] = mapped_column(String(64), nullable=False)


@dataclass(frozen=True, slots=True)
class DeliveredSurface:
    """Content-free evidence of one surface of one delivered report."""

    surface: str
    bundle_id: str
    content_digest: str


class SqlDeliveryStore:
    def __init__(
        self,
        factory: sessionmaker[Session],
        *,
        now: Callable[[], datetime],
    ) -> None:
        self._factory = factory
        self._now = now

    def find_delivery(self, job_id: str) -> DeliveryRecord | None:
        """The record of this job's delivery, if it already has one."""
        with self._factory() as database:
            row = database.get(ReportDeliveryRow, job_id)
            if row is None:
                return None
            return _record_from_row(row, self._surfaces(database, job_id))

    def find_surfaces(self, job_id: str) -> tuple[DeliveredSurface, ...]:
        """Every surface this job delivered, by digest rather than by content."""
        with self._factory() as database:
            return self._surfaces(database, job_id)

    def deliver(self, delivery: ReportDelivery) -> DeliveryRecord:
        """Write the whole report, or none of it.

        One transaction covers the record and every surface. A store that
        committed the record and then failed on the third surface would leave a
        delivery claiming a report that was never wholly written, and RRA-006
        calls a partial export an incomplete bundle rather than a delivery.
        """
        try:
            return self._insert_or_get(delivery)
        except IntegrityError:
            with self._factory() as database:
                row = database.get(ReportDeliveryRow, delivery.record.job_id)
                if row is None:
                    raise
                return _existing(row, self._surfaces(database, row.job_id), delivery)

    def _insert_or_get(self, delivery: ReportDelivery) -> DeliveryRecord:
        record = delivery.record
        with self._factory.begin() as database:
            job = _leased_job(database, record)
            generated_at = self._now()
            expires_at = _boundary(database, job, generated_at=generated_at)
            existing = database.get(ReportDeliveryRow, record.job_id)
            if existing is not None:
                return _existing(existing, self._surfaces(database, record.job_id), delivery)
            database.add(
                ReportDeliveryRow(
                    job_id=record.job_id,
                    owner_id=job.owner_id,
                    session_id=record.session_id,
                    bundle_id=record.bundle_id,
                    package_version=record.package_version,
                    narrative_state=record.narrative_state,
                    generated_at=generated_at,
                    expires_at=expires_at,
                )
            )
            for content in delivery.surfaces:
                database.add(
                    ReportDeliverySurfaceRow(
                        job_id=record.job_id,
                        surface=content.surface,
                        bundle_id=content.bundle_id,
                        content_digest=surface_digest(content),
                    )
                )
            database.flush()
            return record

    @staticmethod
    def _surfaces(database: Session, job_id: str) -> tuple[DeliveredSurface, ...]:
        rows = database.scalars(
            select(ReportDeliverySurfaceRow).where(
                ReportDeliverySurfaceRow.job_id == job_id
            )
        )
        found = {
            row.surface: DeliveredSurface(
                surface=row.surface,
                bundle_id=row.bundle_id,
                content_digest=row.content_digest,
            )
            for row in rows
        }
        # Ordered by the required sequence rather than by the stored name, which
        # sorts to `excel, pdf, web` and is not the order a delivery names.
        return tuple(found[surface] for surface in REQUIRED_SURFACES if surface in found)


def surface_digest(content: SurfaceContent) -> str:
    """A content address for what one surface presented.

    Over the surface name, the bundle it echoes, and every language, figure,
    caveat and disclosure it stated. Two runs that presented the same report
    reach the same digest; a surface that dropped a row, softened a disclosure,
    or came from another run does not.
    """
    return hashlib.sha256(canonical_json(_surface_document(content)).encode()).hexdigest()


def _surface_document(content: SurfaceContent) -> dict[str, object]:
    return {
        "surface": content.surface,
        "bundle_id": content.bundle_id,
        "languages": [
            {
                "language": entry.language,
                "direction": entry.direction,
                "disclosure": entry.disclosure,
                # Placement is part of what a surface presented, so it belongs in
                # the address of what it presented. Two surfaces stating the same
                # figures and caveats under different headings are two different
                # surfaces, and a digest blind to that would call them one.
                "sections": list(entry.sections),
                "caveats": [
                    {"code": caveat.code, "section": caveat.section}
                    for caveat in entry.caveats
                ],
                "stated": [
                    {
                        "figure_id": stated.figure_id,
                        "text": stated.text,
                        "section": stated.section,
                    }
                    for stated in entry.stated
                ],
            }
            for entry in sorted(content.languages, key=lambda entry: entry.language)
        ],
    }


def _leased_job(database: Session, record: DeliveryRecord) -> ReportJobRow:
    """The job this delivery claims to be for, inside its own session.

    A report reaches only the session that queued it. The record names a job and
    a session, and a job that does not sit in that session is not this job.
    """
    row = database.scalar(
        select(ReportJobRow)
        .where(
            ReportJobRow.job_id == record.job_id,
            ReportJobRow.session_id == record.session_id,
        )
        .with_for_update()
    )
    if row is None:
        raise CrossSessionAccessDenied("Resource is unavailable.")
    return row


def _boundary(
    database: Session,
    job: ReportJobRow,
    *,
    generated_at: datetime,
) -> datetime:
    """The expiry a published output inherits from the input's session."""
    row = database.scalar(
        select(BetaSessionRow).where(
            BetaSessionRow.owner_id == job.owner_id,
            BetaSessionRow.session_id == job.session_id,
        )
    )
    if row is None:
        raise CrossSessionAccessDenied("Resource is unavailable.")
    expires_at = _utc(row.content_expires_at)
    if expires_at is None:
        raise SessionExpired("Session content has expired.")
    if expires_at <= generated_at:
        raise SessionExpired("Session content has expired.")
    return expires_at


def _existing(
    row: ReportDeliveryRow,
    surfaces: tuple[DeliveredSurface, ...],
    delivery: ReportDelivery,
) -> DeliveryRecord:
    """The record already written, provided it is the same report.

    A retry of one job delivers the same bundle, because a bundle is named by a
    digest over its content. A different name means a different report, and
    serving either of two reports for one job is the mixture RRA-006 forbids.
    """
    if row.bundle_id != delivery.record.bundle_id:
        raise DeliveryConflict("This job already delivered another report.")
    return _record_from_row(row, surfaces)


def _record_from_row(
    row: ReportDeliveryRow,
    surfaces: tuple[DeliveredSurface, ...],
) -> DeliveryRecord:
    """Hydrate a stored delivery, refusing one that is not a whole report."""
    named = tuple(entry.surface for entry in surfaces)
    if named != REQUIRED_SURFACES:
        raise DeliveryCorrupted("Stored delivery does not name every required surface.")
    if {entry.bundle_id for entry in surfaces} != {row.bundle_id}:
        raise DeliveryCorrupted("Stored delivery mixes surfaces from another bundle.")
    return DeliveryRecord(
        job_id=row.job_id,
        session_id=row.session_id,
        bundle_id=row.bundle_id,
        package_version=row.package_version,
        narrative_state=row.narrative_state,
        surfaces=named,
    )


__all__ = [
    "DeliveredSurface",
    "DeliveryConflict",
    "DeliveryCorrupted",
    "ReportDeliveryRow",
    "ReportDeliverySurfaceRow",
    "SqlDeliveryStore",
    "surface_digest",
]
