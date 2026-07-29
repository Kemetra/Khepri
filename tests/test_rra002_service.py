from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from khepri.rra.intake import (
    CSV_MEDIA_TYPE,
    EncryptedObjectStore,
    IntakeService,
    StoragePolicyViolation,
    StoredObject,
    UploadAlreadyExists,
    UploadMetadata,
    UploadRepository,
)
from khepri.rra.sessions import (
    BetaSession,
    ConsentRequired,
    SessionExpired,
    SessionScope,
)

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)


class MemoryUploadRepository(UploadRepository):
    def __init__(self) -> None:
        self.uploads: dict[str, UploadMetadata] = {}

    def add_upload(self, upload: UploadMetadata) -> bool:
        if any(item.session_id == upload.session_id for item in self.uploads.values()):
            return False
        self.uploads[upload.upload_id] = upload
        return True

    def get_upload_for_session(self, session_id: str) -> UploadMetadata | None:
        return next(
            (item for item in self.uploads.values() if item.session_id == session_id),
            None,
        )

    def get_upload_in_scope(
        self,
        upload_id: str,
        scope: SessionScope,
    ) -> UploadMetadata | None:
        upload = self.uploads.get(upload_id)
        if upload is None or upload.scope != scope:
            return None
        return upload


class MemorySessionReader:
    def __init__(self, session: BetaSession) -> None:
        self.session = session

    def get_session(self, session_id: str) -> BetaSession | None:
        if session_id != self.session.session_id:
            return None
        return self.session


class MemoryEncryptedObjectStore(EncryptedObjectStore):
    def __init__(self, *, encryption_algorithm: str = "aws:kms") -> None:
        self.encryption_algorithm = encryption_algorithm
        self.objects: dict[str, bytes] = {}
        self.deleted_keys: list[str] = []

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
            encryption_algorithm=self.encryption_algorithm,
            kms_key_id="kms-beta-content",
        )

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)
        self.deleted_keys.append(key)


def consented_session() -> BetaSession:
    return BetaSession(
        owner_id="own_alpha",
        session_id="ses_alpha",
        created_at=NOW,
        content_expires_at=NOW + timedelta(days=7),
        consent_version="beta-privacy-v1",
        consented_at=NOW,
    )


def intake_service(
    session: BetaSession | None = None,
    *,
    objects: MemoryEncryptedObjectStore | None = None,
    uploads: MemoryUploadRepository | None = None,
) -> tuple[IntakeService, MemoryEncryptedObjectStore, MemoryUploadRepository]:
    session = session or consented_session()
    object_store = objects or MemoryEncryptedObjectStore()
    upload_repository = uploads or MemoryUploadRepository()
    service = IntakeService(
        sessions=MemorySessionReader(session),
        uploads=upload_repository,
        objects=object_store,
        new_upload_id=lambda: "upl_example",
    )
    return service, object_store, upload_repository


def test_consent_is_required_before_any_upload_is_buffered() -> None:
    session = replace(
        consented_session(),
        consent_version=None,
        consented_at=None,
    )
    service, objects, uploads = intake_service(session)

    with pytest.raises(ConsentRequired):
        service.begin(
            session_id=session.session_id,
            declared_size=10,
            now=NOW,
        )

    assert objects.objects == {}
    assert uploads.uploads == {}


def test_completed_upload_is_bound_to_one_opaque_scope_and_kms_metadata() -> None:
    service, objects, uploads = intake_service()
    intake = service.begin(
        session_id="ses_alpha",
        declared_size=23,
        now=NOW,
    )
    intake.append(b"date,revenue\n2026-01,1\n")

    metadata = intake.complete(now=NOW + timedelta(seconds=1))

    assert metadata == UploadMetadata(
        upload_id="upl_example",
        owner_id="own_alpha",
        session_id="ses_alpha",
        object_key="owners/own_alpha/sessions/ses_alpha/inputs/upl_example",
        size_bytes=23,
        sha256_hex="c7ba25578e7a4da1612a90a32602fc7a207eb286f2f41ccf41e9607d10c96c90",
        media_type=CSV_MEDIA_TYPE,
        created_at=NOW + timedelta(seconds=1),
        expires_at=NOW + timedelta(days=7),
        encryption_algorithm="aws:kms",
        kms_key_id="kms-beta-content",
    )
    assert objects.objects[metadata.object_key] == b"date,revenue\n2026-01,1\n"
    assert uploads.get_upload_in_scope(
        "upl_example",
        SessionScope(owner_id="own_alpha", session_id="ses_alpha"),
    ) == metadata
    assert (
        uploads.get_upload_in_scope(
            "upl_example",
            SessionScope(owner_id="own_other", session_id="ses_other"),
        )
        is None
    )


def test_second_upload_for_the_same_session_is_rejected_and_cleaned_up() -> None:
    uploads = MemoryUploadRepository()
    service, objects, _ = intake_service(uploads=uploads)
    first = service.begin(session_id="ses_alpha", declared_size=8, now=NOW)
    first.append(b"a,b\n1,2\n")
    first.complete(now=NOW)

    with pytest.raises(UploadAlreadyExists):
        service.begin(session_id="ses_alpha", declared_size=4, now=NOW)

    assert len(objects.objects) == 1
    assert len(uploads.uploads) == 1


def test_expired_session_is_rechecked_before_object_storage() -> None:
    session = replace(
        consented_session(),
        content_expires_at=NOW + timedelta(seconds=1),
    )
    service, objects, uploads = intake_service(session)
    intake = service.begin(session_id="ses_alpha", declared_size=8, now=NOW)
    intake.append(b"a,b\n1,2\n")

    with pytest.raises(SessionExpired):
        intake.complete(now=NOW + timedelta(seconds=1))

    assert objects.objects == {}
    assert uploads.uploads == {}


def test_non_kms_storage_response_is_rejected_and_object_is_removed() -> None:
    objects = MemoryEncryptedObjectStore(encryption_algorithm="AES256")
    service, _, uploads = intake_service(objects=objects)
    intake = service.begin(session_id="ses_alpha", declared_size=8, now=NOW)
    intake.append(b"a,b\n1,2\n")

    with pytest.raises(StoragePolicyViolation):
        intake.complete(now=NOW)

    assert objects.objects == {}
    assert objects.deleted_keys == [
        "owners/own_alpha/sessions/ses_alpha/inputs/upl_example"
    ]
    assert uploads.uploads == {}
