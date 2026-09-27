"""#535: a read checks the object key against the caller's scope, not the row's.

`assert_same_scope` compares a row's scope columns, which the row carries about
itself. Edit only those columns to another scope and the row still names the first
scope's object -- and envelope `v2` binds that object to its own key, so the tag
verifies. These tests make exactly that edit and require the read to refuse it.

`test_i535_envelope_aad` covers the narrower attack, an object moved *with* its row
to another key, which the envelope itself refuses.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from khepri.rra.api import create_app
from khepri.rra.artifact_persistence import ReportArtifactRow
from khepri.rra.delivery_persistence import ReportDeliveryRow
from khepri.rra.persistence import BetaSessionRow, DatasetProfileRow, SqlSessionStore, UploadRow
from khepri.rra.report_services import ReportArtifactAdapter
from khepri.rra.reports import ReportServices
from khepri.rra.sessions import (
    CrossSessionAccessDenied,
    InvitationService,
    SessionScope,
    assert_object_in_scope,
    object_prefix,
)
from tests.rra003_contract_fixtures import profile_payload
from tests.test_rra004_packages import GOLDEN_CSV, Harness, harness, redeem_and_consent
from tests.test_rra006_artifact_publication import MemoryObjects, _publication, _publisher
from tests.test_rra006_delivery_persistence import NOW
from tests.test_rra006_report_api import (
    FakeBundleService,
    FakeReportService,
    invitation_service,
)

SCOPE = SessionScope(owner_id="own_alpha", session_id="ses_alpha")


def test_the_namespace_is_spelled_once() -> None:
    assert object_prefix(SCOPE) == "owners/own_alpha/sessions/ses_alpha/"


@pytest.mark.parametrize(
    "key",
    [
        "owners/own_bravo/sessions/ses_alpha/inputs/upl_1",
        "owners/own_alpha/sessions/ses_bravo/inputs/upl_1",
        "owners/own_alpha/sessions/ses_alpha0/inputs/upl_1",
        "inputs/upl_1",
        "",
    ],
)
def test_a_key_outside_the_callers_namespace_is_refused(key: str) -> None:
    with pytest.raises(CrossSessionAccessDenied):
        assert_object_in_scope(SCOPE, key)


def test_a_key_inside_the_callers_namespace_is_admitted() -> None:
    assert_object_in_scope(SCOPE, "owners/own_alpha/sessions/ses_alpha/inputs/upl_1")


def _second_session(test: Harness, first: SessionScope) -> SessionScope:
    test.client.cookies.clear()
    redeem_and_consent(test)
    with test.factory() as database:
        rows = database.scalars(select(BetaSessionRow)).all()
    other = next(row for row in rows if row.session_id != first.session_id)
    return SessionScope(owner_id=other.owner_id, session_id=other.session_id)


def _only_session(test: Harness) -> SessionScope:
    with test.factory() as database:
        row = database.scalars(select(BetaSessionRow)).one()
    return SessionScope(owner_id=row.owner_id, session_id=row.session_id)


def _move_scope_columns(test: Harness, table: type, source: SessionScope, target: SessionScope):
    """Rewrite only the owner/session columns. The object key is left as it was."""
    with test.factory() as database:
        database.execute(
            update(table)
            .where(table.session_id == source.session_id)
            .values(owner_id=target.owner_id, session_id=target.session_id)
        )
        database.commit()


def _uploaded_by_first_session() -> tuple[Harness, SessionScope]:
    test = harness()
    redeem_and_consent(test)
    assert test.client.post("/api/v1/beta/uploads", content=GOLDEN_CSV).status_code == 201
    return test, _only_session(test)


def test_profiling_refuses_an_upload_row_moved_to_the_callers_scope() -> None:
    test, first = _uploaded_by_first_session()
    second = _second_session(test, first)
    _move_scope_columns(test, UploadRow, first, second)

    response = test.client.post("/api/v1/beta/profile", json=profile_payload())

    assert response.status_code == 401


def test_packaging_refuses_rows_moved_to_the_callers_scope() -> None:
    test, first = _uploaded_by_first_session()
    assert test.client.post("/api/v1/beta/profile", json=profile_payload()).status_code == 201
    second = _second_session(test, first)
    _move_scope_columns(test, DatasetProfileRow, first, second)
    _move_scope_columns(test, UploadRow, first, second)

    response = test.client.post("/api/v1/beta/facts")

    assert response.status_code == 401


def test_an_artifact_row_moved_to_the_callers_scope_reads_as_absent() -> None:
    """Byte-identical to the route's answer for a report this caller does not have."""
    objects = MemoryObjects()
    test, publisher = _publisher(objects)
    publication = _publication(test)
    publisher.publish(publication)
    job_id = publication.delivery.record.job_id
    invitations = InvitationService(SqlSessionStore(test.factory))
    second = invitations.redeem(
        invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)), now=NOW
    )
    first = SessionScope(owner_id=test.session.owner_id, session_id=test.session.session_id)
    target = SessionScope(owner_id=second.owner_id, session_id=second.session_id)
    for table in (ReportDeliveryRow, ReportArtifactRow):
        _move_scope_columns(test, table, first, target)
    client = TestClient(
        create_app(
            service=invitation_service(),
            clock=lambda: NOW,
            report_services=ReportServices(
                jobs=FakeReportService(),
                bundles=FakeBundleService(),
                artifacts=ReportArtifactAdapter(publisher),
            ),
        ),
        base_url="https://testserver",
    )
    client.cookies.set("khepri_beta_session", second.session_id)

    moved = client.get(f"/api/v1/beta/reports/{job_id}/surfaces/excel")
    unknown = client.get("/api/v1/beta/reports/job_unknown/surfaces/excel")

    assert moved.status_code == unknown.status_code == 404
    assert moved.content == unknown.content
    assert objects.values
