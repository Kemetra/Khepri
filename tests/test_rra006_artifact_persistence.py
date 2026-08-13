from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import delete, select

from khepri.rra.artifact_persistence import (
    ArtifactConflict,
    ArtifactCorrupted,
    ReportArtifactRow,
    SqlArtifactRepository,
    StoredArtifact,
)
from khepri.rra.delivery_persistence import ReportDeliveryRow
from khepri.rra.pipeline import ReportPublication
from khepri.rra.report_artifacts import (
    HTML_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    REQUIRED_ARTIFACT_KINDS,
    XLSX_MEDIA_TYPE,
    ArtifactPayload,
)
from tests.test_rra006_delivery_persistence import NOW, Harness, harness


def _payload(kind: str) -> ArtifactPayload:
    if kind.startswith("web_"):
        media_type = HTML_MEDIA_TYPE
        file_name = "khepri-evidence.html" if "evidence" in kind else "khepri-report.html"
    elif kind.startswith("pdf_"):
        media_type = PDF_MEDIA_TYPE
        file_name = "khepri-report.pdf"
    else:
        media_type = XLSX_MEDIA_TYPE
        file_name = "khepri-report.xlsx"
    return ArtifactPayload.of(
        kind=kind,
        media_type=media_type,
        file_name=file_name,
        content=f"artifact:{kind}".encode(),
    )


def _publication(test: Harness) -> ReportPublication:
    return ReportPublication(
        delivery=test.delivery(test.leased()),
        artifacts=tuple(_payload(kind) for kind in REQUIRED_ARTIFACT_KINDS),
    )


def _stored(test: Harness, publication: ReportPublication) -> tuple[StoredArtifact, ...]:
    return tuple(
        StoredArtifact(
            job_id=publication.delivery.record.job_id,
            artifact_kind=payload.kind,
            owner_id=test.session.owner_id,
            session_id=test.session.session_id,
            bundle_id=publication.delivery.record.bundle_id,
            object_key=(
                f"owners/{test.session.owner_id}/sessions/{test.session.session_id}/"
                f"reports/{publication.delivery.record.bundle_id}/{payload.kind}"
            ),
            media_type=payload.media_type,
            file_name=payload.file_name,
            size_bytes=len(payload.content),
            sha256_hex=payload.sha256_hex,
            created_at=NOW,
            expires_at=test.session.content_expires_at,
            encryption_algorithm="aws:kms",
            kms_key_id="arn:aws:kms:me-central-1:123456789012:key/example",
        )
        for payload in publication.artifacts
    )


def test_commit_writes_delivery_and_exact_artifact_set_atomically() -> None:
    test = harness()
    publication = _publication(test)
    repository = SqlArtifactRepository(test.factory)

    record = repository.commit(publication, _stored(test, publication))

    assert record == publication.delivery.record
    assert tuple(
        item.artifact_kind
        for item in repository.list_for_job(
            session_id=test.session.session_id,
            job_id=record.job_id,
            now=NOW,
        )
    ) == REQUIRED_ARTIFACT_KINDS
    with test.factory() as database:
        assert len(list(database.scalars(select(ReportDeliveryRow)))) == 1
        assert len(list(database.scalars(select(ReportArtifactRow)))) == 7


def test_identical_retry_returns_the_existing_complete_delivery() -> None:
    test = harness()
    publication = _publication(test)
    stored = _stored(test, publication)
    repository = SqlArtifactRepository(test.factory)

    first = repository.commit(publication, stored)
    second = repository.commit(publication, stored)

    assert second == first
    with test.factory() as database:
        assert len(list(database.scalars(select(ReportArtifactRow)))) == 7


@pytest.mark.parametrize(
    "malformed",
    [
        pytest.param(lambda rows: rows[:-1], id="missing_artifact"),
        pytest.param(
            lambda rows: (*rows[:-1], replace(rows[-1], bundle_id="0" * 64)),
            id="mixed_bundle",
        ),
        pytest.param(
            lambda rows: (*rows[:-1], replace(rows[-1], sha256_hex="0" * 64)),
            id="wrong_digest",
        ),
        pytest.param(
            lambda rows: (*rows[:-1], replace(rows[-1], session_id="ses_foreign")),
            id="wrong_session",
        ),
        pytest.param(
            lambda rows: (*rows[:-1], replace(rows[-1], expires_at=NOW)),
            id="expired_at_creation",
        ),
    ],
)
def test_commit_rejects_any_set_that_cannot_prove_the_publication(malformed) -> None:
    test = harness()
    publication = _publication(test)
    repository = SqlArtifactRepository(test.factory)

    with pytest.raises(ArtifactConflict):
        repository.commit(publication, tuple(malformed(_stored(test, publication))))

    with test.factory() as database:
        assert list(database.scalars(select(ReportDeliveryRow))) == []
        assert list(database.scalars(select(ReportArtifactRow))) == []


def test_session_scoped_read_hides_foreign_expired_and_deleted_content() -> None:
    test = harness()
    publication = _publication(test)
    repository = SqlArtifactRepository(test.factory)
    repository.commit(publication, _stored(test, publication))
    job_id = publication.delivery.record.job_id

    assert repository.find_in_session(
        session_id="ses_foreign", job_id=job_id, artifact_kind="excel", now=NOW
    ) is None
    assert repository.find_in_session(
        session_id=test.session.session_id,
        job_id=job_id,
        artifact_kind="excel",
        now=test.session.content_expires_at,
    ) is None


def test_read_fails_closed_when_the_stored_set_is_incomplete() -> None:
    test = harness()
    publication = _publication(test)
    repository = SqlArtifactRepository(test.factory)
    repository.commit(publication, _stored(test, publication))
    with test.factory.begin() as database:
        database.execute(
            delete(ReportArtifactRow).where(ReportArtifactRow.artifact_kind == "excel")
        )

    with pytest.raises(ArtifactCorrupted):
        repository.list_for_job(
            session_id=test.session.session_id,
            job_id=publication.delivery.record.job_id,
            now=NOW,
        )
