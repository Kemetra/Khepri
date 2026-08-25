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
from khepri.rra.storage import StoredEnvelope


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
    def get(self, key: str, *, envelope: StoredEnvelope) -> bytes: ...


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
        source_contract_digest: str = "",
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
            return _answering(existing, request, source_contract_digest), False

        content = self._objects.get(
            upload.object_key,
            envelope=StoredEnvelope(
                ciphertext_sha256_hex=upload.ciphertext_sha256_hex,
                sha256_hex=upload.sha256_hex,
                encryption_algorithm=upload.encryption_algorithm,
                envelope_version=upload.envelope_version,
            ),
        )
        if hashlib.sha256(content).hexdigest() != upload.sha256_hex:
            raise StoragePolicyViolation("Stored upload does not match its recorded digest.")

        profile = build_profile(
            content=content,
            media_type=upload.media_type,
            source_sha256_hex=upload.sha256_hex,
        )
        document = build_document(
            profile,
            request=request,
            source_contract_digest=source_contract_digest,
        )
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
        return (
            _answering(stored, request, source_contract_digest),
            stored.profile_id == candidate.profile_id,
        )

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
    source_contract_digest: str = "",
) -> dict[str, Any]:
    """The stored profile, including the reading it was admitted under.

    The contract digest is persisted rather than recomputed on read. Recomputing
    would make a stored profile agree with whatever the current code produces,
    which is exactly the drift the binding exists to detect: `RRA-003` requires
    a coverage manifest to be refused when the contract the events were admitted
    under is not the one it was attested against.
    """
    mapping = build_mapping(profile)
    decision = assess_admissibility(profile, mapping, request=request)
    return {
        "profile": profile.as_document(),
        "mapping": mapping.as_document(),
        "admissibility": decision.as_document(),
        "source_contract_digest": source_contract_digest,
    }


def _answering(
    record: DatasetProfileRecord,
    request: ReportRequest,
    source_contract_digest: str = "",
) -> DatasetProfileRecord:
    """Return the stored profile only if it answers the question being asked.

    A profile records the admissibility decision for the semantics it was asked
    about, and one is stored per upload. Handing it back for a different request
    would answer a question nobody asked: a caller requiring `store` would be
    told the dataset is admissible on the strength of a decision taken without
    that requirement.

    Every path that returns a profile somebody else's request produced goes
    through here — the lookup before insertion, and the record `add_profile`
    substitutes when a concurrent insert won the uniqueness conflict. Guarding
    only the first left the second open, because two callers racing on an
    unprofiled upload both find nothing to check.
    """
    if _requested_semantics(record) != tuple(sorted(request.requested_semantics)):
        raise ProfileRequestConflict(
            "This upload was profiled under different requested semantics."
        )
    stored_contract = str(record.document.get("source_contract_digest", ""))
    if stored_contract != source_contract_digest:
        # The same bytes, re-declared. `RRA-003` treats a corrected contract as
        # a different admission, so handing back the stored profile would answer
        # under a declaration the caller has just replaced -- and would leave a
        # coverage manifest bound to semantics nobody is asserting any more.
        raise ProfileRequestConflict(
            "This upload was profiled under a different source contract."
        )
    return record


def _requested_semantics(record: DatasetProfileRecord) -> tuple[str, ...]:
    return tuple(record.document["admissibility"]["requested_semantics"])


def document_digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(document).encode()).hexdigest()
