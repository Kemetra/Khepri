from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.intake import CSV_MEDIA_TYPE, UploadMetadata
from khepri.rra.persistence import (
    Base,
    SqlSessionStore,
    SqlUploadRepository,
    UploadRow,
)
from khepri.rra.sessions import InvitationService, SessionScope

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


def repositories() -> tuple[SqlSessionStore, SqlUploadRepository]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    return SqlSessionStore(factory), SqlUploadRepository(factory)


def persisted_session(store: SqlSessionStore) -> tuple[str, str]:
    invitations = InvitationService(store)
    session = invitations.redeem(
        invitations.issue_invitation(expires_at=NOW + timedelta(hours=1)),
        now=NOW,
    )
    invitations.record_consent(
        session.session_id,
        consent_version="beta-privacy-v1",
        now=NOW,
    )
    return session.owner_id, session.session_id


def metadata(owner_id: str, session_id: str, *, upload_id: str) -> UploadMetadata:
    return UploadMetadata(
        upload_id=upload_id,
        owner_id=owner_id,
        session_id=session_id,
        object_key=f"owners/{owner_id}/sessions/{session_id}/inputs/{upload_id}",
        size_bytes=23,
        sha256_hex="c7ba25578e7a4da1612a90a32602fc7a207eb286f2f41ccf41e9607d10c96c90",
        media_type=CSV_MEDIA_TYPE,
        created_at=NOW,
        expires_at=NOW + timedelta(days=7),
        encryption_algorithm="AES-256-GCM",
        envelope_version=1,
        ciphertext_sha256_hex="c" * 64,
    )


def test_sql_repository_roundtrips_content_free_upload_metadata_in_scope() -> None:
    sessions, uploads = repositories()
    owner_id, session_id = persisted_session(sessions)
    expected = metadata(owner_id, session_id, upload_id="upl_alpha")

    assert uploads.add_upload(expected)

    assert uploads.get_upload_in_scope(
        "upl_alpha",
        SessionScope(owner_id=owner_id, session_id=session_id),
    ) == expected
    assert (
        uploads.get_upload_in_scope(
            "upl_alpha",
            SessionScope(owner_id="own_other", session_id="ses_other"),
        )
        is None
    )
    assert "content" not in inspect(UploadRow).columns
    assert "filename" not in inspect(UploadRow).columns


def test_sql_repository_enforces_one_upload_per_session() -> None:
    sessions, uploads = repositories()
    owner_id, session_id = persisted_session(sessions)
    first = metadata(owner_id, session_id, upload_id="upl_first")
    second = metadata(owner_id, session_id, upload_id="upl_second")

    assert uploads.add_upload(first)
    assert not uploads.add_upload(second)

    assert uploads.get_upload_for_session(session_id) == first
