from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.datasets import ProfilingService
from khepri.rra.deletion import DeletionService
from khepri.rra.intake import IntakeService, StoredObject
from khepri.rra.mapping import MAPPING_VERSION
from khepri.rra.persistence import (
    Base,
    SqlDeletionRepository,
    SqlProfileRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.profiling import PROFILE_VERSION
from khepri.rra.sessions import InvitationService

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
GOLDEN_CSV = (
    b"date,revenue,units,branch,buyer_email\n"
    b"2026-01-05,125.50,3,Cairo Downtown,buyer.one@example.com\n"
    b"2026-01-06,90.00,2,Giza Mall,buyer.two@example.com\n"
)
NO_MEASURE_CSV = b"date,branch\n2026-01-05,Cairo\n2026-01-06,Giza\n"


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.corrupt = False

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
    ) -> StoredObject:
        self.objects[key] = content
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256_hex=sha256_hex,
            media_type=media_type,
            encryption_algorithm="AES-256-GCM",
            envelope_version=1,
            ciphertext_sha256_hex="c" * 64,
        )

    def get(self, key: str, **_: object) -> bytes:
        if self.corrupt:
            return b"date,revenue\n2026-01-05,0\n"
        return self.objects[key]

    def abort_multipart_uploads(self, prefix: str) -> None:
        return None

    def delete_prefix(self, prefix: str) -> None:
        for key in tuple(self.objects):
            if key.startswith(prefix):
                self.objects.pop(key)

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@dataclass
class Harness:
    client: TestClient
    invitations: InvitationService
    objects: MemoryObjectStore
    profiles: SqlProfileRepository


def harness() -> Harness:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    sessions = SqlSessionStore(factory)
    uploads = SqlUploadRepository(factory)
    profiles = SqlProfileRepository(factory)
    objects = MemoryObjectStore()
    invitations = InvitationService(sessions)
    upload_ids = iter(f"upl_{index}" for index in range(1, 32))
    profile_ids = iter(f"prf_{index}" for index in range(1, 32))
    app = create_app(
        service=invitations,
        clock=lambda: NOW,
        intake_service=IntakeService(
            sessions=sessions,
            uploads=uploads,
            objects=objects,
            new_upload_id=lambda: next(upload_ids),
        ),
        deletion_service=DeletionService(
            sessions=sessions,
            deletions=SqlDeletionRepository(factory),
            objects=objects,
            new_deletion_id=lambda: "del_example",
            new_evidence_id=lambda: "dev_example",
        ),
        profiling_service=ProfilingService(
            sessions=sessions,
            uploads=uploads,
            objects=objects,
            profiles=profiles,
            new_profile_id=lambda: next(profile_ids),
        ),
    )
    return Harness(
        client=TestClient(app, base_url="https://testserver"),
        invitations=invitations,
        objects=objects,
        profiles=profiles,
    )


def redeem_and_consent(test: Harness) -> str:
    token = test.invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    redeemed = test.client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    session_id = redeemed.cookies["khepri_beta_session"]
    consented = test.client.post(
        "/api/v1/beta/consent",
        json={"consent_version": "beta-privacy-v1"},
    )
    assert consented.status_code == 204
    return session_id


def upload(test: Harness, content: bytes = GOLDEN_CSV) -> None:
    response = test.client.post("/api/v1/beta/uploads", content=content)
    assert response.status_code == 201


def test_profile_requires_a_beta_session() -> None:
    test = harness()

    response = test.client.post("/api/v1/beta/profile", json={})

    assert response.status_code == 401
    assert response.json() == {"detail": "Session is unavailable."}


def test_profile_requires_consent() -> None:
    test = harness()
    token = test.invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    test.client.post("/api/v1/beta/sessions/redeem", json={"token": token})

    response = test.client.post("/api/v1/beta/profile", json={})

    assert response.status_code == 403


def test_profile_requires_a_governed_upload() -> None:
    test = harness()
    redeem_and_consent(test)

    response = test.client.post("/api/v1/beta/profile", json={})

    assert response.status_code == 404


def test_profile_admits_a_golden_retail_dataset() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)

    response = test.client.post("/api/v1/beta/profile", json={})

    assert response.status_code == 201
    body = response.json()
    assert body["profile_id"] == "prf_1"
    assert body["profile_version"] == PROFILE_VERSION
    assert body["mapping_version"] == MAPPING_VERSION
    assert len(body["profile_digest"]) == 64
    assert body["row_count"] == 2
    assert body["column_count"] == 5
    assert body["admissible"] is True
    assert body["reasons"] == []
    states = {entry["semantic"]: entry["state"] for entry in body["mappings"]}
    assert states["transaction_date"] == "mapped"
    assert states["revenue"] == "mapped"
    assert states["units"] == "mapped"
    assert states["store"] == "mapped"
    assert states["channel"] == "unavailable"


def test_profile_response_excludes_personal_data_from_reporting_inputs() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)

    body = test.client.post("/api/v1/beta/profile", json={}).json()

    assert body["excluded_columns"] == ["buyer_email"]
    email = next(
        column for column in body["columns"] if column["safe_label"] == "buyer_email"
    )
    assert email["personal_data_risk"] is True
    assert email["minimum"] is None
    assert email["maximum"] is None
    mapped_labels = {
        candidate["safe_label"]
        for entry in body["mappings"]
        for candidate in entry["candidates"]
    }
    assert "buyer_email" not in mapped_labels


def test_profile_reports_ranges_only_for_numeric_and_date_columns() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)

    columns = {
        column["safe_label"]: column
        for column in test.client.post("/api/v1/beta/profile", json={}).json()["columns"]
    }

    assert columns["date"]["minimum"] == "2026-01-05"
    assert columns["date"]["maximum"] == "2026-01-06"
    assert columns["revenue"]["minimum"] == "90.00"
    assert columns["revenue"]["maximum"] == "125.50"
    assert columns["branch"]["minimum"] is None
    assert columns["branch"]["maximum"] is None


def test_rerunning_the_profile_returns_the_preserved_provenance() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)
    first = test.client.post("/api/v1/beta/profile", json={})

    second = test.client.post("/api/v1/beta/profile", json={})

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["profile_id"] == first.json()["profile_id"]
    assert second.json()["profile_digest"] == first.json()["profile_digest"]


def test_inadmissible_dataset_is_reported_with_fail_closed_reasons() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test, NO_MEASURE_CSV)

    body = test.client.post("/api/v1/beta/profile", json={}).json()

    assert body["admissible"] is False
    assert body["reasons"] == ["no_answerable_core_measure"]


def test_requested_semantics_tighten_admissibility() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)

    body = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": ["category"]},
    ).json()

    assert body["admissible"] is False
    assert body["reasons"] == ["missing_requested_semantic"]


def test_ungoverned_requested_semantics_are_refused() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)

    response = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": ["forecast"]},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Requested retail semantics are not governed."
    }


def test_unknown_request_fields_are_refused() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)

    response = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "formula": "revenue * 2"},
    )

    assert response.status_code == 422


def test_stored_content_that_lost_its_digest_is_never_profiled() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)
    test.objects.corrupt = True

    response = test.client.post("/api/v1/beta/profile", json={})

    assert response.status_code == 503
    assert response.json() == {"detail": "Upload storage is unavailable."}


def test_profile_can_be_read_back_for_the_session() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)
    created = test.client.post("/api/v1/beta/profile", json={})

    response = test.client.get("/api/v1/beta/profile")

    assert response.status_code == 200
    assert response.json() == created.json()


def test_reading_a_profile_before_profiling_is_a_not_found() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)

    response = test.client.get("/api/v1/beta/profile")

    assert response.status_code == 404


def test_a_second_session_cannot_read_another_profile() -> None:
    test = harness()
    redeem_and_consent(test)
    upload(test)
    test.client.post("/api/v1/beta/profile", json={})
    first_session = test.client.cookies["khepri_beta_session"]

    test.client.cookies.clear()
    redeem_and_consent(test)
    second_session = test.client.cookies["khepri_beta_session"]
    response = test.client.get("/api/v1/beta/profile")

    assert first_session != second_session
    assert response.status_code == 404


def test_content_deletion_removes_the_session_profile() -> None:
    test = harness()
    session_id = redeem_and_consent(test)
    upload(test)
    assert test.client.post("/api/v1/beta/profile", json={}).status_code == 201

    deleted = test.client.delete("/api/v1/beta/content")

    assert deleted.status_code == 204
    assert test.profiles.get_profile_for_session(session_id) is None
