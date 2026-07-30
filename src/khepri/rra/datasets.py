from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from khepri.rra.admissibility import (
    DEFAULT_REPORT_REQUEST,
    ReportRequest,
    assess_admissibility,
)
from khepri.rra.intake import SessionReader, StoragePolicyViolation, UploadRepository
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import (
    DatasetProfile,
    build_profile,
    canonical_json,
)
from khepri.rra.sessions import (
    SessionExpired,
    SessionScope,
    assert_same_scope,
    require_upload_consent,
)


class UploadNotFound(LookupError):
    pass


class ProfileCorrupted(ValueError):
    """A stored profile no longer matches the digest it is addressed by."""


class ProfileRequestConflict(ValueError):
    """The stored profile was decided under different requested semantics."""


@dataclass(frozen=True, slots=True)
class DatasetProfileRecord:
    profile_id: str
    owner_id: str
    session_id: str
    upload_id: str
    profile_version: str
    mapping_version: str
    source_sha256_hex: str
    profile_digest: str
    row_count: int
    column_count: int
    admissible: bool
    created_at: datetime
    document: dict[str, Any]

    @property
    def scope(self) -> SessionScope:
        return SessionScope(owner_id=self.owner_id, session_id=self.session_id)

    def verify(self) -> None:
        """Refuse a stored profile that no longer matches its own digest.

        Everything downstream cites this document as the decision a report was
        admitted under, so a mapping or admissibility section altered after
        storage would let a package claim provenance it does not have.
        """
        if document_digest(self.document) != self.profile_digest:
            raise ProfileCorrupted("Stored dataset profile does not match its digest.")
        profile = self.document["profile"]
        recorded = (
            self.profile_version,
            self.mapping_version,
            self.source_sha256_hex,
            self.row_count,
            self.column_count,
            self.admissible,
        )
        described = (
            profile["profile_version"],
            self.document["mapping"]["mapping_version"],
            profile["source_sha256_hex"],
            profile["row_count"],
            profile["column_count"],
            self.document["admissibility"]["admissible"],
        )
        if recorded != described:
            raise ProfileCorrupted("Stored dataset profile contradicts its own document.")


class ProfileRepository(Protocol):
    def add_profile(self, record: DatasetProfileRecord) -> DatasetProfileRecord: ...

    def get_profile_for_upload(
        self,
        upload_id: str,
        scope: SessionScope,
    ) -> DatasetProfileRecord | None: ...

    def get_profile_for_session(self, session_id: str) -> DatasetProfileRecord | None: ...


class ProfileObjectReader(Protocol):
    def get(self, key: str) -> bytes: ...


class ProfilingService:
    def __init__(
        self,
        *,
        sessions: SessionReader,
        uploads: UploadRepository,
        objects: ProfileObjectReader,
        profiles: ProfileRepository,
        new_profile_id: Callable[[], str] | None = None,
    ) -> None:
        self._sessions = sessions
        self._uploads = uploads
        self._objects = objects
        self._profiles = profiles
        self._new_profile_id = new_profile_id or (
            lambda: f"prf_{secrets.token_urlsafe(18)}"
        )

    def profile_session_upload(
        self,
        *,
        session_id: str,
        now: datetime,
        request: ReportRequest = DEFAULT_REPORT_REQUEST,
    ) -> tuple[DatasetProfileRecord, bool]:
        session = self._sessions.get_session(session_id)
        if session is None:
            raise SessionExpired("Session content has expired.")
        require_upload_consent(session, now=now)

        upload = self._uploads.get_upload_for_session(session_id)
        if upload is None:
            raise UploadNotFound("No governed upload is available for this session.")
        scope = SessionScope(owner_id=session.owner_id, session_id=session.session_id)
        assert_same_scope(scope, upload.scope)

        existing = self._profiles.get_profile_for_upload(upload.upload_id, scope)
        if existing is not None:
            # A profile records the admissibility decision for the semantics it
            # was asked about, and one is stored per upload. Returning it for a
            # different request would answer a question nobody asked: a caller
            # requiring `store` would be told the dataset is admissible on the
            # strength of a decision taken without that requirement.
            if _requested_semantics(existing) != tuple(
                sorted(request.requested_semantics)
            ):
                raise ProfileRequestConflict(
                    "This upload was profiled under different requested semantics."
                )
            return existing, False

        content = self._objects.get(upload.object_key)
        if hashlib.sha256(content).hexdigest() != upload.sha256_hex:
            raise StoragePolicyViolation("Stored upload does not match its recorded digest.")

        profile = build_profile(
            content=content,
            media_type=upload.media_type,
            source_sha256_hex=upload.sha256_hex,
        )
        document = build_document(profile, request=request)
        candidate = DatasetProfileRecord(
            profile_id=self._new_profile_id(),
            owner_id=upload.owner_id,
            session_id=upload.session_id,
            upload_id=upload.upload_id,
            profile_version=profile.profile_version,
            mapping_version=str(document["mapping"]["mapping_version"]),
            source_sha256_hex=upload.sha256_hex,
            profile_digest=document_digest(document),
            row_count=profile.row_count,
            column_count=profile.column_count,
            admissible=bool(document["admissibility"]["admissible"]),
            created_at=now,
            document=document,
        )
        stored = self._profiles.add_profile(candidate)
        return stored, stored.profile_id == candidate.profile_id

    def get_session_profile(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> DatasetProfileRecord | None:
        session = self._sessions.get_session(session_id)
        if session is None:
            raise SessionExpired("Session content has expired.")
        require_upload_consent(session, now=now)
        return self._profiles.get_profile_for_session(session_id)


def build_document(
    profile: DatasetProfile,
    *,
    request: ReportRequest = DEFAULT_REPORT_REQUEST,
) -> dict[str, Any]:
    mapping = build_mapping(profile)
    decision = assess_admissibility(profile, mapping, request=request)
    return {
        "profile": profile.as_document(),
        "mapping": mapping.as_document(),
        "admissibility": decision.as_document(),
    }


def _requested_semantics(record: DatasetProfileRecord) -> tuple[str, ...]:
    return tuple(record.document["admissibility"]["requested_semantics"])


def document_digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(document).encode()).hexdigest()
