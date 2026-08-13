from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra import packages
from khepri.rra.admissibility import ReportRequest
from khepri.rra.api import create_app
from khepri.rra.datasets import (
    DatasetProfileRecord,
    ProfileRequestConflict,
    ProfilingService,
    document_digest,
)
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
from khepri.rra.profiling import canonical_json
from khepri.rra.sessions import InvitationService, SessionScope

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
    document = body["document"]
    assert body["package_id"] == "fct_1"
    assert document["package_version"] == PACKAGE_VERSION
    assert document["formula_version"] == FORMULA_VERSION
    assert document["row_count"] == 4
    assert body["package_digest"] == _digest_of(document)
    assert document["source_sha256_hex"] == hashlib.sha256(GOLDEN_CSV).hexdigest()

    figures = {fact["metric"]: fact["value"] for fact in document["facts"]}
    assert figures["revenue"] == "500.00"
    assert figures["units"] == "11"
    assert figures["transactions"] == "3"
    assert figures["average_order_value"] == "166.67"


def test_aggregates_are_served_in_their_canonical_shape() -> None:
    document = prepared().client.post("/api/v1/beta/facts").json()["document"]

    revenue_trend = next(
        entry for entry in document["series"] if entry["measure"] == "revenue"
    )
    assert revenue_trend["granularity"] == "day"
    assert revenue_trend["unit_kind"] == "monetary"
    assert revenue_trend["citation_id"].startswith("cit_")
    assert sum(float(point["value"]) for point in revenue_trend["points"]) == 500.00

    category = next(
        entry
        for entry in document["comparisons"]
        if entry["dimension"] == "category" and entry["measure"] == "revenue"
    )
    assert [bucket["label"] for bucket in category["buckets"]] == [
        "Beverages",
        "Snacks",
    ]
    # The completeness counts a caveat refers to must survive to the consumer.
    assert category["distinct_values"] == 2
    assert category["truncated_values"] == 0
    assert category["redacted_values"] == 0

    citations = [
        entry["citation_id"] for entry in document["series"] + document["comparisons"]
    ]
    citations += [fact["citation_id"] for fact in document["facts"]]
    assert len(set(citations)) == len(citations)


def test_the_served_package_reconstructs_the_digest_it_is_addressed_by() -> None:
    body = prepared().client.post("/api/v1/beta/facts").json()

    assert _digest_of(body["document"]) == body["package_digest"]


def test_refusals_are_published_rather_than_omitted() -> None:
    body = prepared().client.post("/api/v1/beta/facts").json()

    refusals = {
        entry["metric"]: entry["reason"] for entry in body["document"]["refusals"]
    }
    assert refusals["cost"] == "required_input_unavailable"
    assert refusals["gross_margin"] == "required_input_unavailable"
    assert "cost" not in {fact["metric"] for fact in body["document"]["facts"]}


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
        assert row.profile_document_digest == profile.profile_digest
        assert row.source_sha256_hex == profile.source_sha256_hex


def test_a_stale_profile_refuses_the_package_rather_than_publishing_against_it() -> None:
    # The stored profile is internally consistent but no longer describes what
    # the current bytes and rules produce, which the rebuild comparison catches.
    test = prepared()

    with test.factory.begin() as database:
        stored = database.scalar(select(DatasetProfileRow))
        document = dict(stored.document)
        profile = dict(document["profile"])
        profile["row_count"] = 99
        document["profile"] = profile
        stored.document = document
        stored.row_count = 99
        stored.profile_digest = document_digest(document)

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

    document = body["document"]
    published = document["facts"] + document["series"] + document["comparisons"]
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
        successor_document = dict(original.document)
        successor_document["formula_version"] = "rra004.formula.v2"
        successor = FactPackageRecord(
            package_id="fct_next",
            owner_id=original.owner_id,
            session_id=original.session_id,
            profile_id=original.profile_id,
            package_version=original.package_version,
            formula_version="rra004.formula.v2",
            mapping_version=original.mapping_version,
            profile_document_digest=original.profile_document_digest,
            source_sha256_hex=original.source_sha256_hex,
            package_digest=_digest_of(successor_document),
            row_count=original.row_count,
            created_at=NOW + timedelta(minutes=1),
            document=successor_document,
        )

    stored = test.packages.add_package(successor)

    assert stored.package_id == "fct_next"
    with test.factory() as database:
        assert len(list(database.scalars(select(FactPackageRow)))) == 2
    # Both survive, and the session still reads the one this build publishes
    # rather than the newer row under a formula version it does not produce.
    assert test.client.get("/api/v1/beta/facts").json()["package_id"] == "fct_1"


def test_a_profile_produced_under_superseded_rules_refuses_the_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Supersession is a deployment moving on, so the stored rows stay exactly as
    # they were written and the governed constants advance instead.
    test = prepared()
    monkeypatch.setattr(packages, "MAPPING_VERSION", "rra003.mapping.v9")

    response = test.client.post("/api/v1/beta/facts")

    assert response.status_code == 409
    assert "superseded" in response.json()["detail"]
    with test.factory() as database:
        assert database.scalar(select(FactPackageRow)) is None


def test_a_profile_produced_under_a_superseded_profile_version_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Type inference, personal-data detection, and admissibility live in the
    # profiling rules, so that version can move while the mapping stays put.
    test = prepared()
    monkeypatch.setattr(packages, "PROFILE_VERSION", "rra003.profile.v9")

    assert test.client.post("/api/v1/beta/facts").status_code == 409


def test_a_superseded_profile_never_serves_an_older_package_as_current(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # With a package already published, the superseded profile must refuse
    # rather than hand back the earlier publication as though it were current.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201
    monkeypatch.setattr(packages, "MAPPING_VERSION", "rra003.mapping.v9")

    assert test.client.post("/api/v1/beta/facts").status_code == 409


def test_the_two_provenance_digests_are_named_apart_and_both_served() -> None:
    # One covers the profile alone and is what the package itself records; the
    # other covers the whole profile, mapping, and admissibility document and is
    # what binds the package to the decision it was published under. They are
    # different values and must not share a name.
    test = prepared()
    body = test.client.post("/api/v1/beta/facts").json()

    assert body["document"]["profile_digest"] != body["profile_document_digest"]
    with test.factory() as database:
        row = database.scalar(select(FactPackageRow))
        assert row.profile_document_digest == body["profile_document_digest"]
        assert row.document["profile_digest"] == body["document"]["profile_digest"]
        profile = database.scalar(select(DatasetProfileRow))
        assert row.profile_document_digest == profile.profile_digest


def test_a_tampered_package_is_refused_rather_than_served() -> None:
    # The package is content-addressed and presented as immutable, so an altered
    # figure must not reach a consumer under the original address.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201

    with test.factory.begin() as database:
        row = database.scalar(select(FactPackageRow))
        document = dict(row.document)
        facts = [dict(fact) for fact in document["facts"]]
        facts[0]["value"] = "999999.00"
        document["facts"] = facts
        row.document = document

    assert test.client.get("/api/v1/beta/facts").status_code == 503
    assert test.client.post("/api/v1/beta/facts").status_code == 503


def test_a_package_contradicting_its_own_document_is_refused() -> None:
    # The digest still verifies here; the row's metadata is what drifted.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201

    with test.factory.begin() as database:
        database.scalar(select(FactPackageRow)).row_count = 99

    assert test.client.get("/api/v1/beta/facts").status_code == 503


def test_a_package_under_any_superseded_governed_version_is_not_current() -> None:
    # Not only the mapping: whichever of the three governed versions moved, a
    # package the current builder would not publish is not this session's.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201
    _republish_under(test, formula_version="rra004.formula.v0")

    assert test.client.get("/api/v1/beta/facts").status_code == 404


def _republish_under(test: Harness, *, formula_version: str) -> None:
    """Rewrite the stored package as a self-consistent publication under a version."""
    with test.factory.begin() as database:
        row = database.scalar(select(FactPackageRow))
        document = dict(row.document)
        document["formula_version"] = formula_version
        row.document = document
        row.formula_version = formula_version
        row.package_digest = _digest_of(document)


def test_reading_never_serves_a_package_publishing_would_refuse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A package published under superseded rules is a valid historical
    # publication, but it is not this session's current one. Reading reports
    # that none is available; publishing explains why it cannot make one. The
    # one thing neither may do is hand back the superseded figures.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201
    monkeypatch.setattr(packages, "MAPPING_VERSION", "rra003.mapping.v9")

    read = test.client.get("/api/v1/beta/facts")
    written = test.client.post("/api/v1/beta/facts")

    assert read.status_code == 404
    assert written.status_code == 409
    assert "superseded" in written.json()["detail"]


def test_a_tampered_profile_provenance_is_refused_on_both_paths() -> None:
    # The profile document digest sits beside the package rather than inside
    # it, so the package's own content address cannot vouch for it.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201
    with test.factory.begin() as database:
        database.scalar(select(FactPackageRow)).profile_document_digest = "c" * 64

    assert test.client.get("/api/v1/beta/facts").status_code == 503
    assert test.client.post("/api/v1/beta/facts").status_code == 503


def test_a_tampered_profile_document_is_refused_on_both_paths() -> None:
    # The profile's own document is what every later claim cites, so altering
    # its admissibility section must not pass unnoticed.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201
    with test.factory.begin() as database:
        row = database.scalar(select(DatasetProfileRow))
        document = dict(row.document)
        admissibility = dict(document["admissibility"])
        admissibility["admissible"] = False
        document["admissibility"] = admissibility
        row.document = document

    assert test.client.get("/api/v1/beta/facts").status_code == 503
    assert test.client.post("/api/v1/beta/facts").status_code == 503


def test_the_inner_profile_digest_is_bound_to_the_cited_profile() -> None:
    # Recomputing package_digest after tampering makes the package
    # self-consistent, so only the profile it names can contradict it.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201
    with test.factory.begin() as database:
        row = database.scalar(select(FactPackageRow))
        document = dict(row.document)
        document["profile_digest"] = "d" * 64
        row.document = document
        row.package_digest = _digest_of(document)

    assert test.client.get("/api/v1/beta/facts").status_code == 503
    assert test.client.post("/api/v1/beta/facts").status_code == 503


def test_a_package_claiming_another_input_is_refused() -> None:
    # Self-consistent and citing the real profile, but claiming a different
    # source digest and row count than that profile describes.
    test = prepared()
    assert test.client.post("/api/v1/beta/facts").status_code == 201
    with test.factory.begin() as database:
        row = database.scalar(select(FactPackageRow))
        document = dict(row.document)
        document["source_sha256_hex"] = "e" * 64
        document["row_count"] = 999
        row.document = document
        row.source_sha256_hex = "e" * 64
        row.row_count = 999
        row.package_digest = _digest_of(document)

    assert test.client.get("/api/v1/beta/facts").status_code == 503
    assert test.client.post("/api/v1/beta/facts").status_code == 503


def test_reprofiling_under_different_semantics_is_refused() -> None:
    # A caller requiring `store` must not be handed an admissibility decision
    # taken without that requirement, on a dataset that has no store column.
    test = harness()
    redeem_and_consent(test)
    test.client.post(
        "/api/v1/beta/uploads",
        content=b"date,revenue\n2026-01-05,100.00\n2026-01-06,50.00\n",
    )
    first = test.client.post("/api/v1/beta/profile", json={})
    assert first.status_code == 201

    second = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": ["store"]},
    )

    assert second.status_code == 409
    assert "different requested semantics" in second.json()["detail"]


def test_reprofiling_under_the_same_semantics_is_still_idempotent() -> None:
    test = harness()
    redeem_and_consent(test)
    test.client.post("/api/v1/beta/uploads", content=GOLDEN_CSV)
    body = {"requested_semantics": ["store"]}

    first = test.client.post("/api/v1/beta/profile", json=body)
    second = test.client.post("/api/v1/beta/profile", json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()


class _BlindToExistingProfiles:
    """A profile repository whose pre-insert lookup misses, as a race does.

    Two `/profile` requests arriving together on an unprofiled upload both find
    nothing stored, so both reach the insert. Only the real `add_profile` can
    resolve that, and it does so by returning the record the winner wrote.
    """

    def __init__(self, inner: SqlProfileRepository) -> None:
        self._inner = inner

    def add_profile(self, record: DatasetProfileRecord) -> DatasetProfileRecord:
        return self._inner.add_profile(record)

    def get_profile_for_upload(
        self,
        upload_id: str,
        scope: SessionScope,
    ) -> DatasetProfileRecord | None:
        return None

    def get_profile_for_session(self, session_id: str) -> DatasetProfileRecord | None:
        return self._inner.get_profile_for_session(session_id)


def test_a_profile_race_lost_on_the_uniqueness_conflict_is_still_rechecked() -> None:
    # The loser of the race is handed the winner's profile by add_profile. That
    # record answers the winner's question, not this caller's, so it has to face
    # the same check as one found before insertion.
    test = harness()
    redeem_and_consent(test)
    test.client.post(
        "/api/v1/beta/uploads",
        content=b"date,revenue\n2026-01-05,100.00\n2026-01-06,50.00\n",
    )
    assert test.client.post("/api/v1/beta/profile", json={}).status_code == 201
    service = ProfilingService(
        sessions=SqlSessionStore(test.factory),
        uploads=SqlUploadRepository(test.factory),
        objects=test.objects,
        profiles=_BlindToExistingProfiles(SqlProfileRepository(test.factory)),
        new_profile_id=lambda: "prf_racer",
    )

    with pytest.raises(ProfileRequestConflict):
        service.profile_session_upload(
            session_id=_session(test),
            now=NOW,
            request=ReportRequest(requested_semantics=frozenset({"store"})),
        )


def test_a_profile_race_won_on_the_same_question_still_returns_the_stored_one() -> None:
    test = harness()
    redeem_and_consent(test)
    test.client.post("/api/v1/beta/uploads", content=GOLDEN_CSV)
    first = test.client.post("/api/v1/beta/profile", json={})
    assert first.status_code == 201
    service = ProfilingService(
        sessions=SqlSessionStore(test.factory),
        uploads=SqlUploadRepository(test.factory),
        objects=test.objects,
        profiles=_BlindToExistingProfiles(SqlProfileRepository(test.factory)),
        new_profile_id=lambda: "prf_racer",
    )

    stored, created = service.profile_session_upload(session_id=_session(test), now=NOW)

    assert created is False
    assert stored.profile_id == first.json()["profile_id"]


def test_reruns_over_the_same_input_are_byte_equivalent() -> None:
    first = prepared().client.post("/api/v1/beta/facts").json()
    second = prepared().client.post("/api/v1/beta/facts").json()

    assert first["package_digest"] == second["package_digest"]


def _digest_of(document: dict) -> str:
    return hashlib.sha256(canonical_json(document).encode()).hexdigest()


def _session(test: Harness) -> str:
    return test.client.cookies["khepri_beta_session"]
