"""#535: deletion and retention never remove an object outside the row's own scope.

Both delete by a row's `object_key`. After a row-only scope edit, that key still
names the first scope's object, so deleting by it removes another scope's bytes.
Each writer holds the key to the namespace the row claims and refuses a mismatch,
leaving the object where it is.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select, update

from khepri.rra.persistence import BetaSessionRow, DeletionEvidenceRow, UploadRow
from khepri.runtime.workspace_retention import RawUploadRetentionSweeper
from tests.test_i535_read_scope import (
    _move_scope_columns,
    _second_session,
    _uploaded_by_first_session,
)
from tests.w104_support import member
from tests.w107_support import journey, sealed_version, uploads_for


def test_deleting_the_callers_content_refuses_a_row_naming_another_scopes_object() -> None:
    test, first = _uploaded_by_first_session()
    (first_key,) = test.objects.objects
    second = _second_session(test, first)
    _move_scope_columns(test, UploadRow, first, second)

    response = test.client.delete("/api/v1/beta/content")

    assert response.status_code == 503
    assert response.json() == {"detail": "Content deletion is pending retry."}
    assert first_key in test.objects.objects
    with test.factory() as database:
        codes = set(database.scalars(select(DeletionEvidenceRow.error_code)))
    assert codes == {"object_outside_scope"}


def test_retention_leaves_a_row_naming_another_sessions_object() -> None:
    j = journey()
    who = member(j.w)
    version, _ = sealed_version(j, who, with_run=True)
    (upload,) = uploads_for(j, who.owner_id)
    with j.w.factory() as database:
        # A real second session in the same scope, so the edited row stays admissible
        # to every key the schema enforces and only its object key disagrees with it.
        database.add(
            BetaSessionRow(
                session_id="ses_edited",
                owner_id=who.owner_id,
                created_at=version.sealed_at,
                content_expires_at=version.sealed_at + timedelta(days=30),
            )
        )
        database.flush()
        database.execute(
            update(UploadRow)
            .where(UploadRow.upload_id == upload.upload_id)
            .values(session_id="ses_edited")
        )
        database.commit()
    sweeper = RawUploadRetentionSweeper(factory=j.w.factory, objects=j.w.objects, audit=j.w.audit)

    report = sweeper.sweep(now=version.sealed_at + timedelta(days=7))

    assert report.purged_uploads == 0
    assert upload.object_key in j.w.objects.objects
    assert len(uploads_for(j, who.owner_id)) == 1
