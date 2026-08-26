from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Protocol

from khepri.rra.admissibility import (
    DEFAULT_REPORT_REQUEST,
    ReportRequest,
    assess_admissibility,
)
from khepri.rra.coverage import (
    CompletenessQuery,
    CoverageManifest,
    ManifestBinding,
    admits_completeness,
    manifest_from_document,
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
from khepri.rra.source_contract import SourceContract
from khepri.rra.storage import StoredEnvelope

#: Governed reasons a completeness question is refused. Closed vocabulary: a
#: caller distinguishing "nobody attested this" from "the attestation covers a
#: different reading" from "it does not reach this window" needs three codes, and
#: collapsing any two would make an operator's fix unguessable.
REASON_MANIFEST_ABSENT = "coverage_manifest_absent"
REASON_MANIFEST_CONTRACT_MISMATCH = "coverage_manifest_contract_mismatch"
REASON_MANIFEST_WINDOW_UNPROVEN = "coverage_manifest_window_unproven"


class UploadNotFound(LookupError):
    pass


class ProfileCorrupted(ValueError):
    """A stored profile no longer matches the digest it is addressed by."""


class CoverageUnproven(ValueError):
    """Completeness was asked for and no attestation proves it.

    Carries a governed reason code rather than only a sentence, because the
    caller has to distinguish an absent attestation from one bound to another
    reading: the first is fixed by attesting coverage, the second by re-attesting
    under the declaration actually recorded. A single message would leave the
    operator guessing which.
    """

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


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


class CoverageAttestation(Protocol):
    """An attestation that still needs the admission it is bound to.

    A Protocol rather than the request model itself, so this service depends on
    the two things it uses and not on the HTTP layer.
    `khepri.rra.coverage_request.CoverageManifestBody` satisfies it.

    `timezone` is on the Protocol because the day boundary is the operator's to
    declare -- nothing in the admission can supply it. See `manifest_binding`.
    """

    timezone: str

    def to_manifest(self, *, binding: ManifestBinding) -> CoverageManifest: ...


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
        contract: SourceContract,
        now: datetime,
        request: ReportRequest = DEFAULT_REPORT_REQUEST,
        attestation: CoverageAttestation | None = None,
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
            return _answering(existing, request, contract), False

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
            contract=contract,
            manifest=_bound_manifest(attestation, profile=profile, contract=contract),
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
            _answering(stored, request, contract),
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
    contract: SourceContract,
    request: ReportRequest = DEFAULT_REPORT_REQUEST,
    manifest: CoverageManifest | None = None,
) -> dict[str, Any]:
    """The stored profile document, including the reading it was admitted under.

    The contract is recorded beside the profile rather than alongside it,
    because the digest is what later binds a coverage manifest to *this*
    admission. `khepri.rra.coverage` refuses a manifest whose
    `source_contract_digest` names a different reading of the same bytes, and
    that refusal is only possible if the digest is written here.

    **The manifest is baked in here or nowhere.** This document is
    content-addressed: `DatasetProfileRecord.verify` refuses one whose digest
    moved, and `packages._readmit` rebuilds it from the bytes plus what was
    stored and refuses a package when the rebuild digests differently. Writing an
    attestation into an existing document would therefore have to rewrite
    `profile_digest`, which `PackageProvenance.expected` compares against every
    already-published package -- turning a valid package into `PackageCorrupted`.
    So an attestation arrives with the declaration it is bound to, once.

    **Absent means absent.** With no manifest the key is omitted rather than set
    to an empty section, because an empty attestation is indistinguishable
    downstream from one covering nothing, and because omitting it keeps every
    profile written without a manifest digesting exactly as it did before
    attestations existed.
    """
    mapping = build_mapping(profile, contract=contract)
    decision = assess_admissibility(profile, mapping, request=request)
    document: dict[str, Any] = {
        "profile": profile.as_document(),
        "mapping": mapping.as_document(),
        "admissibility": decision.as_document(),
        "source_contract": {
            **contract.as_document(),
            "digest": contract.digest,
        },
    }
    if manifest is not None:
        document["coverage_manifest"] = manifest.as_document()
    return document


def _bound_manifest(
    attestation: CoverageAttestation | None,
    *,
    profile: DatasetProfile,
    contract: SourceContract,
) -> CoverageManifest | None:
    """The attested manifest bound to this admission, or nothing attested."""
    if attestation is None:
        return None
    return attestation.to_manifest(
        binding=manifest_binding(
            profile=profile,
            contract=contract,
            timezone=attestation.timezone,
        )
    )


def manifest_binding(
    *,
    profile: DatasetProfile,
    contract: SourceContract,
    timezone: str,
) -> ManifestBinding:
    """What an attestation on this admission is bound to.

    **Two of the three come from the admission, and the third cannot.** The two
    digests are assembled here rather than read off the operator's payload, which
    is the whole of why the use-time check can fail: an attestation carrying its
    own idea of which bytes and which reading it covers would be compared against
    itself, and `RRA-003`'s separation of the input digest from the source
    contract would stop discriminating.

    The timezone is the operator's, and taking it from them is not a weakening of
    that rule but the same rule applied. A retail day boundary is not a property
    of the bytes -- `RRA-003` is explicit that coverage is never established from
    observed values -- so there is nothing here to derive it from. Substituting a
    constant would store an attestation the operator did not make, over a window
    whose every attested day means something different under another zone, in a
    document that is digested and cannot be corrected in place.
    """
    return ManifestBinding(
        input_digest=profile.source_sha256_hex,
        source_contract_digest=contract.digest,
        timezone=timezone,
    )


def stored_manifest(record: DatasetProfileRecord) -> CoverageManifest | None:
    """The attestation a stored profile carries, or `None` for one with none.

    `None` rather than a refusal, because a profile without an attestation is
    ordinary: `RRA-003` refuses the completeness-dependent *comparisons* on such
    a profile, not the profile. The refusal belongs at the point of use, which is
    `session_completeness`.
    """
    section = record.document.get("coverage_manifest")
    if not isinstance(section, dict):
        return None
    return manifest_from_document(section)


def session_completeness(
    record: DatasetProfileRecord,
    *,
    scope: str,
    start: date,
    end: date,
) -> CoverageManifest:
    """The attestation proving this window complete, or a governed refusal.

    **This is where the binding is checked, and it has to be here.** A manifest
    validated only as it was written leaves the binding unproven at the moment it
    matters: the attestation is stored inside the document, and everything about
    which bytes and which reading it covers is a claim that must hold when a
    caller relies on it, not merely when it arrived.

    The query is built from the *profile's* recorded contract digest and its own
    source digest, never from the manifest's fields. That is the difference
    between a check and a tautology -- comparing the manifest's
    `source_contract_digest` to itself would admit every attestation, including
    one carried over from a corrected reading of identical bytes, which is the
    exact reuse `RRA-003` names the source contract to prevent.
    """
    manifest = stored_manifest(record)
    if manifest is None:
        raise CoverageUnproven(
            REASON_MANIFEST_ABSENT,
            "No coverage manifest was attested for this dataset.",
        )
    recorded = _attested_reading(record, manifest)
    query = CompletenessQuery(
        input_digest=record.source_sha256_hex,
        source_contract_digest=recorded,
        scope=scope,
        start=start,
        end=end,
    )
    if not admits_completeness(manifest, query):
        raise CoverageUnproven(
            REASON_MANIFEST_WINDOW_UNPROVEN,
            "The coverage manifest does not prove this window completely covered.",
        )
    return manifest


def _attested_reading(
    record: DatasetProfileRecord,
    manifest: CoverageManifest,
) -> str:
    """The contract digest this attestation must be bound to, or a refusal.

    Split from `session_completeness` so the identity check reads as its own
    named question rather than as two more branches in the window check. Both
    refusals carry one reason code because both mean the same thing to an
    operator: this attestation does not belong to the reading recorded here, and
    the fix is to re-attest under the declaration actually admitted.
    """
    recorded = _recorded_contract_digest(record)
    if recorded is None:
        raise CoverageUnproven(
            REASON_MANIFEST_CONTRACT_MISMATCH,
            "This dataset records no source contract to bind an attestation to.",
        )
    if manifest.source_contract_digest != recorded:
        raise CoverageUnproven(
            REASON_MANIFEST_CONTRACT_MISMATCH,
            "The coverage manifest was attested under a different reading of this file.",
        )
    return recorded


def _answering(
    record: DatasetProfileRecord,
    request: ReportRequest,
    contract: SourceContract,
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
    if _recorded_contract_digest(record) != contract.digest:
        # The same reasoning as the semantics guard, for the other half of what
        # a profile records. A stored profile answers the declaration it was
        # admitted under; handing it back for a different one would report a
        # mapping built from a reading this caller did not declare, and the
        # digest they are shown would address neither.
        raise ProfileRequestConflict(
            "This upload was profiled under a different source contract."
        )
    return record


def _recorded_contract_digest(record: DatasetProfileRecord) -> str | None:
    """The digest of the contract a stored profile was admitted under.

    `None` for a profile written before contracts existed, which never equals a
    real digest -- so a legacy profile is a conflict here rather than a silent
    match, and the caller is told to re-profile rather than handed a mapping
    built without their declaration.
    """
    stored = record.document.get("source_contract")
    if not isinstance(stored, dict):
        return None
    digest = stored.get("digest")
    return None if digest is None else str(digest)


def _requested_semantics(record: DatasetProfileRecord) -> tuple[str, ...]:
    return tuple(record.document["admissibility"]["requested_semantics"])


def document_digest(document: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(document).encode()).hexdigest()
