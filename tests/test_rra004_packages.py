from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.datasets import ProfilingService
from khepri.rra.deletion import DeletionService
from khepri.rra.facts import FORMULA_VERSION, PACKAGE_VERSION
from khepri.rra.intake import IntakeService, StoredObject
from khepri.rra.packages import (
    FactPackageRecord,
    FactPackageService,
    PackageRefused,
    ProfileNotFound,
)
from khepri.rra.persistence import (
    Base,
    DatasetProfileRow,
    FactPackageRow,
    SqlDeletionRepository,
    SqlFactPackageRepository,
    SqlProfileRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.sessions import InvitationService

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)
GOLDEN_CSV = (
    b"date,revenue,units,invoice_no,category,branch\n"
    b"2026-01-05,125.50,3,INV-1,Beverages,Cairo\n"
    b"2026-01-06,90.00,2,INV-2,Snacks,Giza\n"
    b"2026-01-07,210.25,5,INV-3,Beverages,Cairo\n"
    b"2026-01-07,74.25,1,INV-3,Snacks,Giza\n"
)
NO_MEASURE_CSV = b"date,branch\n2026-01-05,Cairo\n2026-01-06,Giza\n"


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
        encryption_context: dict[str, str],
    ) -> StoredObject:
        self.objects[key] = content
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256_hex=sha256_hex,
            media_type=media_type,
            encryption_algorithm="aws:kms",
            kms_key_id="kms-beta-content",
        )

    def get(self, key: str) -> bytes:
        return self.objects[key]

    def abort_multipart_uploads(self, prefix: str) -> None:
        return None

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@dataclass
class Harness:
    client: TestClient
    invitations: InvitationService
    objects: MemoryObjectStore
    packages: SqlFactPackageRepository
    factory: sessionmaker
    service: FactPackageService


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
    packages = SqlFactPackageRepository(factory)
    objects = MemoryObjectStore()
    invitations = InvitationService(sessions)
    upload_ids = iter(f"upl_{index}" for index in range(1, 32))
    profile_ids = iter(f"prf_{index}" for index in range(1, 32))
    package_ids = iter(f"fct_{index}" for index in range(1, 32))
    service = FactPackageService(
        sessions=sessions,
        uploads=uploads,
        objects=objects,
        profiles=profiles,
        packages=packages,
        new_package_id=lambda: next(package_ids),
    )
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
        package_service=service,
    )
    return Harness(
        client=TestClient(app, base_url="https://testserver"),
        invitations=invitations,
        objects=objects,
        packages=packages,
        factory=factory,
        service=service,
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


def prepared(content: bytes = GOLDEN_CSV) -> Harness:
    test = harness()
    redeem_and_consent(test)
    assert test.client.post("/api/v1/beta/uploads", content=content).status_code == 201
    assert test.client.post("/api/v1/beta/profile", json={}).status_code == 201
    return test


def test_facts_require_a_beta_session() -> None:
    test = harness()

    assert test.client.post("/api/v1/beta/facts").status_code == 401


def test_facts_require_consent() -> None:
    test = harness()
    token = test.invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    test.client.post("/api/v1/beta/sessions/redeem", json={"token": token})

    assert test.client.post("/api/v1/beta/facts").status_code == 403


def test_facts_require_a_profile_first() -> None:
    test = harness()
    redeem_and_consent(test)
    test.client.post("/api/v1/beta/uploads", content=GOLDEN_CSV)

    response = test.client.post("/api/v1/beta/facts")

    assert response.status_code == 404
    assert "profile" in response.json()["detail"]


def test_a_golden_dataset_publishes_its_governed_figures() -> None:
    test = prepared()

    response = test.client.post("/api/v1/beta/facts")

    assert response.status_code == 201
    body = response.json()
    assert body["package_id"] == "fct_1"
    assert body["package_version"] == PACKAGE_VERSION
    assert body["formula_version"] == FORMULA_VERSION
    assert body["row_count"] == 4
    assert len(body["package_digest"]) == 64
    assert body["source_sha256_hex"] == hashlib.sha256(GOLDEN_CSV).hexdigest()

    figures = {fact["metric"]: fact["value"] for fact in body["facts"]}
    assert figures["revenue"] == "500.00"
    assert figures["units"] == "11"
    assert figures["transactions"] == "3"
    assert figures["average_order_value"] == "166.67"


def test_aggregates_carry_their_scope_unit_and_citation() -> None:
    body = prepared().client.post("/api/v1/beta/facts").json()

    revenue_trend = next(
        entry for entry in body["series"] if entry["measure"] == "revenue"
    )
    assert revenue_trend["scope"] == "day"
    assert revenue_trend["unit_kind"] == "monetary"
    assert revenue_trend["citation_id"].startswith("cit_")
    assert sum(float(point["value"]) for point in revenue_trend["buckets"]) == 500.00

    category = next(
        entry
        for entry in body["comparisons"]
        if entry["scope"] == "category" and entry["measure"] == "revenue"
    )
    assert [bucket["label"] for bucket in category["buckets"]] == [
        "Beverages",
        "Snacks",
    ]

    citations = [entry["citation_id"] for entry in body["series"] + body["comparisons"]]
    citations += [fact["citation_id"] for fact in body["facts"]]
    assert len(set(citations)) == len(citations)


def test_refusals_are_published_rather_than_omitted() -> None:
    body = prepared().client.post("/api/v1/beta/facts").json()

    refusals = {entry["metric"]: entry["reason"] for entry in body["refusals"]}
    assert refusals["cost"] == "required_input_unavailable"
    assert refusals["gross_margin"] == "required_input_unavailable"
    assert "cost" not in {fact["metric"] for fact in body["facts"]}


def test_a_package_is_published_once_and_then_returned_unchanged() -> None:
    test = prepared()

    first = test.client.post("/api/v1/beta/facts")
    second = test.client.post("/api/v1/beta/facts")

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()

    fetched = test.client.get("/api/v1/beta/facts")
    assert fetched.status_code == 200
    assert fetched.json()["package_digest"] == first.json()["package_digest"]


def test_reading_before_publication_is_a_refusal_not_an_empty_package() -> None:
    test = prepared()

    response = test.client.get("/api/v1/beta/facts")

    assert response.status_code == 404
    assert response.json()["detail"] == "No fact package is available for this session."


def test_an_inadmissible_dataset_is_refused_with_a_reason() -> None:
    test = prepared(NO_MEASURE_CSV)

    response = test.client.post("/api/v1/beta/facts")

    assert response.status_code == 409
    assert "admissible" in response.json()["detail"]
    with test.factory() as database:
        assert database.scalar(select(FactPackageRow)) is None


def test_a_package_is_bound_to_the_profile_it_was_published_against() -> None:
    test = prepared()
    test.client.post("/api/v1/beta/facts")

    with test.factory() as database:
        row = database.scalar(select(FactPackageRow))
        profile = database.scalar(select(DatasetProfileRow))
        assert row.profile_id == profile.profile_id
        assert row.profile_digest == profile.profile_digest
        assert row.source_sha256_hex == profile.source_sha256_hex


def test_a_stale_profile_refuses_the_package_rather_than_publishing_against_it() -> None:
    test = prepared()

    with test.factory.begin() as database:
        stored = database.scalar(select(DatasetProfileRow))
        stored.profile_digest = "0" * 64

    with pytest.raises(PackageRefused):
        test.service.build_session_package(session_id=_session(test), now=NOW)


def test_a_missing_profile_refuses_the_package() -> None:
    test = harness()
    redeem_and_consent(test)
    test.client.post("/api/v1/beta/uploads", content=GOLDEN_CSV)

    with pytest.raises(ProfileNotFound):
        test.service.build_session_package(session_id=_session(test), now=NOW)


def test_deleting_session_content_removes_the_package_with_the_profile() -> None:
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201

    assert test.client.delete("/api/v1/beta/content").status_code == 204

    with test.factory() as database:
        assert database.scalar(select(FactPackageRow)) is None
        assert database.scalar(select(DatasetProfileRow)) is None


def test_every_published_figure_carries_its_stable_fact_id() -> None:
    # RRA-004 requires stable fact identifiers; a consumer can only address a
    # figure by one if the served package actually carries it.
    body = prepared().client.post("/api/v1/beta/facts").json()

    published = body["facts"] + body["series"] + body["comparisons"]
    identifiers = [entry["fact_id"] for entry in published]

    assert all(identifier.startswith("fct_") for identifier in identifiers)
    assert len(set(identifiers)) == len(identifiers)


def test_the_package_inherits_the_semantics_the_profile_was_decided_under() -> None:
    # Requesting a semantic the profile cannot answer must refuse the dataset,
    # and it does so at the profile, which is where admissibility is decided.
    test = harness()
    redeem_and_consent(test)
    test.client.post("/api/v1/beta/uploads", content=NO_MEASURE_CSV)
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": ["store"]},
    )
    assert profiled.status_code == 201
    assert profiled.json()["admissible"] is False

    response = test.client.post("/api/v1/beta/facts")

    assert response.status_code == 409


def test_a_second_publication_cannot_be_asked_for_under_other_semantics() -> None:
    # The facts endpoint takes no request of its own, so the semantics a
    # package was published under cannot drift from the profile's.
    test = prepared()
    first = test.client.post("/api/v1/beta/facts")

    second = test.client.post("/api/v1/beta/facts", json={"requested_semantics": ["store"]})

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()


def test_a_new_governed_version_may_be_published_beside_the_old_one() -> None:
    # RRA-004 makes a new formula a new version, not a replacement, so the
    # store must admit both rather than resolving back to the first.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201

    with test.factory() as database:
        original = database.scalar(select(FactPackageRow))
        successor = FactPackageRecord(
            package_id="fct_next",
            owner_id=original.owner_id,
            session_id=original.session_id,
            profile_id=original.profile_id,
            package_version=original.package_version,
            formula_version="rra004.formula.v2",
            mapping_version=original.mapping_version,
            profile_digest=original.profile_digest,
            source_sha256_hex=original.source_sha256_hex,
            package_digest="b" * 64,
            row_count=original.row_count,
            created_at=NOW + timedelta(minutes=1),
            document=dict(original.document),
        )

    stored = test.packages.add_package(successor)

    assert stored.package_id == "fct_next"
    with test.factory() as database:
        assert len(list(database.scalars(select(FactPackageRow)))) == 2
    # The session reads the most recent publication.
    assert test.client.get("/api/v1/beta/facts").json()["package_id"] == "fct_next"


def test_reruns_over_the_same_input_are_byte_equivalent() -> None:
    first = prepared().client.post("/api/v1/beta/facts").json()
    second = prepared().client.post("/api/v1/beta/facts").json()

    assert first["package_digest"] == second["package_digest"]


def _session(test: Harness) -> str:
    return test.client.cookies["khepri_beta_session"]
