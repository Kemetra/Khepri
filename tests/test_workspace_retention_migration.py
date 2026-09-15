"""Upgrade evidence for existing workspace content affected by issue #429."""

from __future__ import annotations

import importlib.util
from datetime import UTC, timedelta
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import select, update

from khepri.rra.artifact_persistence import ReportArtifactRow
from khepri.rra.delivery_persistence import ReportDeliveryRow
from khepri.rra.persistence import BetaSessionRow, UploadRow
from khepri.runtime.workspace_retention import WORKSPACE_CONTENT_END
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import completed_run

MIGRATION = (
    Path(__file__).resolve().parents[1]
    / "migrations"
    / "versions"
    / "20260915_0030_workspace_content_retention.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("workspace_content_retention", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_upgrade_promotes_existing_workspace_content_off_the_beta_timer() -> None:
    """An upgrade must protect runs completed before the code fix was deployed."""
    j = journey()
    who = member(j.w)
    _run, _job_id, session_id = completed_run(j, who)
    old_deadline = j.clock() + timedelta(days=7)
    with j.w.factory.begin() as database:
        for row in (BetaSessionRow, UploadRow, ReportDeliveryRow, ReportArtifactRow):
            deadline_column = (
                "content_expires_at" if row is BetaSessionRow else "expires_at"
            )
            database.execute(
                update(row)
                .where(row.owner_id == who.owner_id, row.session_id == session_id)
                .values(**{deadline_column: old_deadline})
            )

    engine = j.w.factory.kw["bind"]
    with engine.begin() as connection:
        context = MigrationContext.configure(connection)
        module = _migration()
        token = module.op
        module.op = Operations(context)
        try:
            module.upgrade()
        finally:
            module.op = token

    with j.w.factory() as database:
        deadlines = (
            database.scalar(
                select(BetaSessionRow.content_expires_at).where(
                    BetaSessionRow.session_id == session_id
                )
            ),
            database.scalar(select(UploadRow.expires_at).where(UploadRow.session_id == session_id)),
            database.scalar(
                select(ReportDeliveryRow.expires_at).where(
                    ReportDeliveryRow.session_id == session_id
                )
            ),
            *database.scalars(
                select(ReportArtifactRow.expires_at).where(
                    ReportArtifactRow.session_id == session_id
                )
            ),
        )
    assert deadlines
    assert all(deadline is not None for deadline in deadlines)
    assert all(deadline.replace(tzinfo=UTC) == WORKSPACE_CONTENT_END for deadline in deadlines)
