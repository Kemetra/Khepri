"""Publication and retrieval of the governed retail fact package.

**What the integrity checks here do and do not cover.** A stored package is
verified against its own digest, and everything it claims about its provenance
is checked against the profile it cites. Both authenticators live in the same
database as the document they authenticate, so they detect accidental
corruption, partial writes, and a package drifting from its profile. They do
not detect a writer with database access who alters a figure and recomputes the
digest, and no check reading only from this store could.

Closing that would need a signature over the digest with a key held outside the
database. Authenticating instead against the uploaded object is not durable:
RRA-002 deletes it on request or at expiry, so the guarantee would lapse
exactly when a package is most likely to be cited. The limit is accepted
deliberately rather than by oversight.

**What happens when the governed versions advance.** A profile produced under
superseded profiling or mapping rules cannot back a package, and a session's
profile is written once per upload, so between a deployment and that session's
expiry its fact requests are refused with no way to re-profile. This is
deliberate: the alternative is publishing figures attributed to an
admissibility decision taken under rules that no longer hold. It resolves
itself, because RRA-002 expires the upload and deletes the content, after which
a fresh upload is profiled under the current rules. Making it recoverable
sooner needs versioned profiles, which is an RRA-003 contract change and not
decided here.
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from khepri.rra.admissibility import ReportRequest, assess_admissibility
from khepri.rra.datasets import (
    DatasetProfileRecord,
    ProfileObjectReader,
    ProfileRepository,
    build_document,
    document_digest,
)
from khepri.rra.facts import (
    FORMULA_VERSION,
    PACKAGE_VERSION,
    FactsRefused,
    build_fact_package,
)
from khepri.rra.intake import SessionReader, StoragePolicyViolation, UploadRepository
from khepri.rra.mapping import MAPPING_VERSION, build_mapping
from khepri.rra.profiling import PROFILE_VERSION, build_profile, canonical_json
from khepri.rra.sessions import (
    SessionExpired,
    SessionScope,
    assert_same_scope,
    require_upload_consent,
)
from khepri.rra.storage import StoredEnvelope
from khepri.rra.versions import REASON_PACKAGE_VERSION_UNADMITTED


class ProfileNotFound(LookupError):
    pass


class PackageRefused(ValueError):
    """The dataset cannot answer a governed fact package."""


#: What a caller is told when a package refusal's own text is not for them.
#:
#: Beside `PackageRefused` rather than in `api`, following `SESSION_UNAVAILABLE`: the seam that
#: raises a refusal owns the wording that replaces it, so a second surface cannot invent a
#: different one for the same cause.
PACKAGE_UNAVAILABLE = "Fact package is unavailable."


def package_refused_detail(error: PackageRefused) -> str:
    """The customer-facing text for a package refusal.

    **Selective rather than blanket, deliberately.** Most `PackageRefused` text is written *for*
    the caller -- a stored profile that no longer describes the input, a package published under a
    superseded version -- and replacing all of it would remove the only account of what to fix.
    One refusal is not: `assert_versions_admitted` names a governed reason code and all three
    internal version identifiers, and `build_session_package` forwards that text verbatim.

    **`RRA-009` tiers that reason Internal, and a tier is a claim about every path the text can
    travel.** The original justification -- "it fires while a package is being built, so no report
    is published and no customer can encounter it" -- was true of the report and silently assumed
    the report was the only surface. The `409` body is another. A later surface -- a CLI, a
    webhook, a support export -- inherits the same obligation rather than rediscovering it.

    Matched on the governed reason code rather than on prose, so rewording the message cannot
    start the leak again. The three other `raise PackageRefused` sites carry fixed customer-safe
    prose with no wrapping, so the prefix cannot be defeated by a message built around it.

    **Both `409` handlers route through this, and only one of them can reach the reason.**
    `read_retail_facts` reads an already-stored package and never calls `build_fact_package`, so
    its guard is defensive rather than exercised -- reverting that call site alone leaves the
    tests green, and no case is manufactured for an unreachable path. It is guarded anyway so a
    later read path that does construct cannot reintroduce the leak by inheriting the older
    `str(error)` form.
    """
    detail = str(error)
    if detail.startswith(f"{REASON_PACKAGE_VERSION_UNADMITTED}:"):
        return PACKAGE_UNAVAILABLE
    return detail


class PackageCorrupted(ValueError):
    """A stored package no longer matches the digest it is addressed by."""


@dataclass(frozen=True, slots=True)
class FactPackageRecord:
    package_id: str
    owner_id: str
    session_id: str
    profile_id: str
    package_version: str
    formula_version: str
    mapping_version: str
    # The digest of the whole RRA-003 document -- profile, mapping, and
    # admissibility -- which is what binds this package to the decision it was
    # published under. Distinct from the package document's own
    # `profile_digest`, which covers the profile alone.
    profile_document_digest: str
    source_sha256_hex: str
    package_digest: str
    row_count: int
    created_at: datetime
    document: dict[str, Any]

    @property
    def scope(self) -> SessionScope:
        return SessionScope(owner_id=self.owner_id, session_id=self.session_id)

    @property
    def profile_digest(self) -> str:
        """The profile digest the package itself records."""
        return str(self.document["profile_digest"])

    def verify(self) -> None:
        """Refuse a stored package that no longer matches its own digest.

        The package is content-addressed and presented as immutable, so serving
        a document that does not hash to its recorded address would publish
        altered figures under an address that vouches for the originals. This
        catches corruption and partial writes, not a writer who recomputes the
        digest -- see the module docstring for why that boundary is where it is.
        """
        if hashlib.sha256(canonical_json(self.document).encode()).hexdigest() != (
            self.package_digest
        ):
            raise PackageCorrupted("Stored fact package does not match its digest.")
        recorded = (
            self.package_version,
            self.formula_version,
            self.mapping_version,
            self.source_sha256_hex,
            self.row_count,
        )
        described = (
            self.document["package_version"],
            self.document["formula_version"],
            self.document["mapping_version"],
            self.document["source_sha256_hex"],
            self.document["row_count"],
        )
        if recorded != described:
            raise PackageCorrupted("Stored fact package contradicts its own document.")


@dataclass(frozen=True, slots=True)
class PackageVersions:
    """The governed versions a package is published under.

    RRA-004 makes a new input, mapping, formula, or correction a new *version*
    rather than a replacement, so these travel together as the identity of a
    publication and not merely as recorded metadata.
    """

    package_version: str
    formula_version: str
    mapping_version: str

    @classmethod
    def current(cls) -> PackageVersions:
        """The versions this build of the service publishes under."""
        return cls(
            package_version=PACKAGE_VERSION,
            formula_version=FORMULA_VERSION,
            mapping_version=MAPPING_VERSION,
        )

    @classmethod
    def of(cls, record: FactPackageRecord) -> PackageVersions:
        return cls(
            package_version=record.package_version,
            formula_version=record.formula_version,
            mapping_version=record.mapping_version,
        )


@dataclass(frozen=True, slots=True)
class PackageProvenance:
    """What a package claims about the input and the profile behind it.

    Assembled from the package on one side and from the profile on the other,
    then compared once. Enumerating the fields at the comparison site is what
    let the source digest and row count go unchecked while the two profile
    digests were checked -- a field added to one side now has to be added to
    the other for this to type-check at all.
    """

    profile_id: str
    profile_document_digest: str
    profile_digest: str
    source_sha256_hex: str
    row_count: int

    @classmethod
    def claimed(cls, record: FactPackageRecord) -> PackageProvenance:
        return cls(
            profile_id=record.profile_id,
            profile_document_digest=record.profile_document_digest,
            profile_digest=record.profile_digest,
            source_sha256_hex=record.source_sha256_hex,
            row_count=record.row_count,
        )

    @classmethod
    def expected(cls, record: DatasetProfileRecord) -> PackageProvenance:
        return cls(
            profile_id=record.profile_id,
            profile_document_digest=record.profile_digest,
            profile_digest=_profile_digest_of(record),
            source_sha256_hex=record.source_sha256_hex,
            row_count=record.row_count,
        )


class FactPackageRepository(Protocol):
    def add_package(self, record: FactPackageRecord) -> FactPackageRecord: ...

    def get_package_for_versions(
        self,
        profile_id: str,
        versions: PackageVersions,
        scope: SessionScope,
    ) -> FactPackageRecord | None: ...

    def get_package_for_session(
        self,
        session_id: str,
        versions: PackageVersions,
    ) -> FactPackageRecord | None: ...


class FactPackageService:
    """Publish the immutable fact package for a session's governed upload.

    RRA-004 makes the package the only numerical source for every later report
    surface, so it is computed from the stored bytes rather than from anything
    already derived, and the profile it is attributed to is checked to be the
    one those bytes produce.
    """

    def __init__(
        self,
        *,
        sessions: SessionReader,
        uploads: UploadRepository,
        objects: ProfileObjectReader,
        profiles: ProfileRepository,
        packages: FactPackageRepository,
        new_package_id: Callable[[], str] | None = None,
    ) -> None:
        self._sessions = sessions
        self._uploads = uploads
        self._objects = objects
        self._profiles = profiles
        self._packages = packages
        self._new_package_id = new_package_id or (
            lambda: f"fct_{secrets.token_urlsafe(18)}"
        )

    def build_session_package(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> tuple[FactPackageRecord, bool]:
        session = self._sessions.get_session(session_id)
        if session is None:
            raise SessionExpired("Session content has expired.")
        require_upload_consent(session, now=now)
        scope = SessionScope(owner_id=session.owner_id, session_id=session.session_id)

        profile_record = self._profiles.get_profile_for_session(session_id)
        if profile_record is None:
            raise ProfileNotFound("No dataset profile is available for this session.")
        assert_same_scope(scope, profile_record.scope)

        # The profile decided which semantics were required and whether the
        # dataset answers them. Accepting that request again here would let the
        # two disagree, so the package inherits the decision rather than
        # re-taking it.
        request = _requested_by(profile_record)
        _assert_profile_current(profile_record)
        # Keyed by the versions the stored row will actually carry. Keying the
        # lookup on anything else lets the check miss a row the insert then
        # collides with.
        versions = PackageVersions.current()
        existing = self._packages.get_package_for_versions(
            profile_record.profile_id,
            versions,
            scope,
        )
        if existing is not None:
            self._assert_current(existing, profile_record)
            return existing, False

        upload = self._uploads.get_upload_for_session(session_id)
        if upload is None:
            raise StoragePolicyViolation("Stored upload is no longer available.")
        assert_same_scope(scope, upload.scope)

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
        # The persisted profile is what the caller was shown and what governs
        # admissibility, so the package is refused rather than published against
        # a profile the current bytes and rules no longer produce.
        if document_digest(build_document(profile, request=request)) != (
            profile_record.profile_digest
        ):
            raise PackageRefused(
                "Stored profile does not describe the current governed input."
            )

        mapping = build_mapping(profile)
        decision = assess_admissibility(profile, mapping, request=request)
        try:
            package = build_fact_package(
                content=content,
                media_type=upload.media_type,
                profile=profile,
                mapping=mapping,
                decision=decision,
            )
        except FactsRefused as error:
            raise PackageRefused(str(error)) from error

        document = package.as_document()
        candidate = FactPackageRecord(
            package_id=self._new_package_id(),
            owner_id=scope.owner_id,
            session_id=scope.session_id,
            profile_id=profile_record.profile_id,
            package_version=package.package_version,
            formula_version=package.formula_version,
            mapping_version=package.mapping_version,
            profile_document_digest=profile_record.profile_digest,
            source_sha256_hex=package.source_sha256_hex,
            package_digest=package.digest,
            row_count=package.row_count,
            created_at=now,
            document=document,
        )
        stored = self._packages.add_package(candidate)
        return stored, stored.package_id == candidate.package_id

    def get_session_package(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> FactPackageRecord | None:
        session = self._sessions.get_session(session_id)
        if session is None:
            raise SessionExpired("Session content has expired.")
        require_upload_consent(session, now=now)
        # Selected by the versions this build publishes under, so a session
        # holding an older publication reads as having none rather than being
        # handed figures the current builder would not produce.
        record = self._packages.get_package_for_session(
            session_id,
            PackageVersions.current(),
        )
        if record is not None:
            self._assert_current(record)
        return record

    def _assert_current(
        self,
        record: FactPackageRecord,
        profile_record: DatasetProfileRecord | None = None,
    ) -> None:
        """The single test of whether a stored package may be served as current.

        Publication and reading are the same claim made twice, so both paths ask
        this one question rather than each keeping its own list of checks --
        which is how the read path came to be missing several of them.
        """
        profile = profile_record or self._profiles.get_profile_for_session(
            record.session_id
        )
        # Everything the package claims about its provenance, checked against
        # the profile it names. None of it is covered by the package's own
        # content address: some is stored beside the document, and the rest is
        # inside a document whose digest can be recomputed after tampering.
        if profile is None or PackageProvenance.claimed(record) != (
            PackageProvenance.expected(profile)
        ):
            raise PackageCorrupted(
                "Stored fact package does not match the profile it cites."
            )
        _assert_profile_current(profile)
        # Every governed version, not only the mapping: a package the current
        # builder would not publish must not be served as the current one,
        # whichever of the three moved. The repository is a Protocol, so this
        # stays the service's own invariant rather than relying on any
        # particular store to have filtered correctly.
        if PackageVersions.of(record) != PackageVersions.current():
            raise PackageRefused(
                "Stored package was published under a superseded governed version."
            )


def _assert_profile_current(record: DatasetProfileRecord) -> None:
    """A package cites the profile it was published against, so the two must
    have been decided under the same mapping rules. Serving or publishing under
    newer rules than the profile was mapped with would attribute the package's
    figures to an admissibility decision taken under the old ones.
    """
    # Both governed versions the profile was produced under. Type inference,
    # personal-data detection, and admissibility all live in the profiling
    # rules, so a profile version can move while the mapping version does not.
    if (record.profile_version, record.mapping_version) != (
        PROFILE_VERSION,
        MAPPING_VERSION,
    ):
        raise PackageRefused(
            "Stored profile was produced under superseded governed versions."
        )


def _profile_digest_of(record: DatasetProfileRecord) -> str:
    """The digest of the profile alone, as the package document records it."""
    return hashlib.sha256(
        canonical_json(record.document["profile"]).encode()
    ).hexdigest()


def _requested_by(record: DatasetProfileRecord) -> ReportRequest:
    admissibility = record.document["admissibility"]
    return ReportRequest(
        requested_semantics=frozenset(admissibility["requested_semantics"])
    )


__all__ = [
    "DatasetProfileRecord",
    "FactPackageRecord",
    "FactPackageRepository",
    "FactPackageService",
    "PACKAGE_UNAVAILABLE",
    "PackageCorrupted",
    "PackageRefused",
    "PackageVersions",
    "ProfileNotFound",
    "package_refused_detail",
]
