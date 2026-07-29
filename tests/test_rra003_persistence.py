from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.datasets import DatasetProfileRecord
from khepri.rra.deletion import DeletionEvidence
from khepri.rra.intake import CSV_MEDIA_TYPE, UploadMetadata
from khepri.rra.persistence import (
    Base,
    DatasetProfileRow,
    SqlDeletionRepository,
    SqlProfileRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.sessions import InvitationService, SessionScope

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)
CONTENT_DIGEST = "492d5ea496056f1a6a6592241032fab764c321596317930b4fa0e1e8bc3b7470"
LOCATION_DIGEST = "83390a61bb59fdbfad2f36666488f781ef73ddcf8042b4bd7315e82a535c1682"
PROFILE_DIGEST = "3f2b4c1d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f809"

DOCUMENT: dict[str, object] = {
    "profile": {"columns": [{"position": 0, "safe_label": "date"}]},
    "mapping": {"mapping_version": "rra003.mapping.v1", "mappings": []},
    "admissibility": {"admissible": True, "reasons": []},
}


def repositories() -> tuple[
    sessionmaker,
    SqlSessionStore,
    SqlUploadRepository,
    SqlProfileRepository,
    SqlDeletionRepository,
]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    return (
        factory,
        SqlSessionStore(factory),
        SqlUploadRepository(factory),
        SqlProfileRepository(factory),
        SqlDeletionRepository(factory),
    )


def session_and_upload(
    sessions: SqlSessionStore,
    uploads: SqlUploadRepository,
    *,
    upload_id: str = "upl_alpha",
) -> tuple[SessionScope, UploadMetadata]:
    invitations = InvitationService(sessions)
    beta_session = invitations.redeem(
        invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)),
        now=NOW,
    )
    invitations.record_consent(
        beta_session.session_id,
        consent_version="beta-privacy-v1",
        now=NOW,
    )
    metadata = UploadMetadata(
        upload_id=upload_id,
        owner_id=beta_session.owner_id,
        session_id=beta_session.session_id,
        object_key=(
            f"owners/{beta_session.owner_id}/sessions/"
            f"{beta_session.session_id}/inputs/{upload_id}"
        ),
        size_bytes=8,
        sha256_hex=CONTENT_DIGEST,
        media_type=CSV_MEDIA_TYPE,
        created_at=NOW,
        expires_at=NOW + timedelta(days=7),
        encryption_algorithm="aws:kms",
        kms_key_id="kms-beta-content",
    )
    assert uploads.add_upload(metadata) is True
    return (
        SessionScope(
            owner_id=beta_session.owner_id,
            session_id=beta_session.session_id,
        ),
        metadata,
    )


def record(
    upload: UploadMetadata,
    *,
    profile_id: str = "prf_alpha",
) -> DatasetProfileRecord:
    return DatasetProfileRecord(
        profile_id=profile_id,
        owner_id=upload.owner_id,
        session_id=upload.session_id,
        upload_id=upload.upload_id,
        profile_version="rra003.profile.v1",
        mapping_version="rra003.mapping.v1",
        source_sha256_hex=upload.sha256_hex,
        profile_digest=PROFILE_DIGEST,
        row_count=3,
        column_count=1,
        admissible=True,
        created_at=NOW,
        document=DOCUMENT,
    )


def test_dataset_profile_table_binds_scope_and_digest_controls() -> None:
    factory, *_ = repositories()
    inspector = inspect(factory.kw["bind"])

    assert "rra_dataset_profiles" in inspector.get_table_names()
    constraints = {
        constraint["name"] for constraint in inspector.get_check_constraints(
            "rra_dataset_profiles"
        )
    }
    assert {
        "ck_profile_row_count",
        "ck_profile_column_count",
        "ck_profile_source_digest",
        "ck_profile_digest",
    } <= constraints
    unique = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("rra_dataset_profiles")
    }
    assert {"uq_profile_upload", "uq_profile_session"} <= unique


def test_profile_round_trips_by_upload_and_by_session() -> None:
    _, sessions, uploads, profiles, _ = repositories()
    scope, upload = session_and_upload(sessions, uploads)

    stored = profiles.add_profile(record(upload))

    assert stored.profile_id == "prf_alpha"
    assert profiles.get_profile_for_upload(upload.upload_id, scope) == stored
    assert profiles.get_profile_for_session(scope.session_id) == stored
    assert stored.document == DOCUMENT
    assert stored.created_at == NOW


def test_second_profile_for_one_upload_returns_the_stored_profile() -> None:
    _, sessions, uploads, profiles, _ = repositories()
    _, upload = session_and_upload(sessions, uploads)
    first = profiles.add_profile(record(upload))

    second = profiles.add_profile(record(upload, profile_id="prf_beta"))

    assert second.profile_id == first.profile_id


def test_profile_is_invisible_outside_its_session_scope() -> None:
    _, sessions, uploads, profiles, _ = repositories()
    _, upload = session_and_upload(sessions, uploads)
    profiles.add_profile(record(upload))

    foreign = SessionScope(owner_id="own_other", session_id="ses_other")

    assert profiles.get_profile_for_upload(upload.upload_id, foreign) is None
    assert profiles.get_profile_for_session("ses_other") is None


def test_content_deletion_removes_the_derived_profile() -> None:
    factory, sessions, uploads, profiles, deletions = repositories()
    scope, upload = session_and_upload(sessions, uploads)
    profiles.add_profile(record(upload))

    job = deletions.begin(
        scope=scope,
        deletion_id="del_alpha",
        reason="immediate",
        requested_at=NOW,
    )
    completed = deletions.complete(
        job=job,
        evidence=DeletionEvidence(
            evidence_id="dev_alpha",
            deletion_id=job.deletion_id,
            target_kind="input",
            target_id=upload.upload_id,
            location_digest=LOCATION_DIGEST,
            content_digest=CONTENT_DIGEST,
            attempted_at=NOW,
            attempt_number=1,
            outcome="deleted",
            error_code=None,
        ),
        completed_at=NOW,
    )

    assert completed.state == "complete"
    assert profiles.get_profile_for_session(scope.session_id) is None
    with factory() as database:
        assert database.scalars(select(DatasetProfileRow)).all() == []


def test_expiry_deletion_without_a_stored_upload_still_clears_profiles() -> None:
    _, sessions, uploads, profiles, deletions = repositories()
    scope, upload = session_and_upload(sessions, uploads)
    profiles.add_profile(record(upload))
    with_evidence = deletions.begin(
        scope=scope,
        deletion_id="del_alpha",
        reason="expiry",
        requested_at=NOW,
    )
    deletions.complete(
        job=with_evidence,
        evidence=DeletionEvidence(
            evidence_id="dev_alpha",
            deletion_id=with_evidence.deletion_id,
            target_kind="input",
            target_id=upload.upload_id,
            location_digest=LOCATION_DIGEST,
            content_digest=CONTENT_DIGEST,
            attempted_at=NOW,
            attempt_number=1,
            outcome="deleted",
            error_code=None,
        ),
        completed_at=NOW,
    )

    assert profiles.get_profile_for_session(scope.session_id) is None


def test_stored_document_is_independent_of_the_caller_mapping() -> None:
    _, sessions, uploads, profiles, _ = repositories()
    scope, upload = session_and_upload(sessions, uploads)
    original = record(upload)
    profiles.add_profile(replace(original, document=dict(DOCUMENT)))

    loaded = profiles.get_profile_for_session(scope.session_id)

    assert loaded is not None
    loaded.document["admissibility"] = {"admissible": False}
    assert profiles.get_profile_for_session(scope.session_id) == original
