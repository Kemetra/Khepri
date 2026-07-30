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
from khepri.rra.profiling import build_profile, canonical_json
from khepri.rra.sessions import (
    SessionExpired,
    SessionScope,
    assert_same_scope,
    require_upload_consent,
)


class ProfileNotFound(LookupError):
    pass


class PackageRefused(ValueError):
    """The dataset cannot answer a governed fact package."""


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
        altered figures under an address that vouches for the originals.
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


class FactPackageRepository(Protocol):
    def add_package(self, record: FactPackageRecord) -> FactPackageRecord: ...

    def get_package_for_versions(
        self,
        profile_id: str,
        versions: PackageVersions,
        scope: SessionScope,
    ) -> FactPackageRecord | None: ...

    def get_package_for_session(self, session_id: str) -> FactPackageRecord | None: ...


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
        # A package cites the profile it was published against, so the two must
        # have been decided under the same mapping rules. Publishing under newer
        # rules than the profile was mapped with would attribute this package's
        # figures to an admissibility decision taken under the old ones.
        if profile_record.mapping_version != MAPPING_VERSION:
            raise PackageRefused(
                "Stored profile was mapped under a superseded mapping version."
            )
        # Keyed by the versions the stored row will actually carry. Keying the
        # lookup on anything else lets the check miss a row the insert then
        # collides with.
        versions = PackageVersions(
            package_version=PACKAGE_VERSION,
            formula_version=FORMULA_VERSION,
            mapping_version=MAPPING_VERSION,
        )
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

        content = self._objects.get(upload.object_key)
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
        record = self._packages.get_package_for_session(session_id)
        if record is not None:
            self._assert_current(record)
        return record

    def _assert_current(
        self,
        record: FactPackageRecord,
        profile_record: DatasetProfileRecord | None = None,
    ) -> None:
        """Check a stored package before it is served as the session's current one.

        Publication and reading are the same claim made twice, so a package the
        service would refuse to publish today must not be handed back as current
        merely because it was published earlier.
        """
        profile = profile_record or self._profiles.get_profile_for_session(
            record.session_id
        )
        # The profile document digest is stored beside the package rather than
        # inside it, so it is outside the package's own content address and has
        # to be checked against the profile it names.
        if (
            profile is None
            or profile.profile_id != record.profile_id
            or profile.profile_digest != record.profile_document_digest
        ):
            raise PackageCorrupted(
                "Stored fact package does not match the profile it cites."
            )
        if record.mapping_version != MAPPING_VERSION:
            raise PackageRefused(
                "Stored package was published under a superseded mapping version."
            )


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
    "PackageCorrupted",
    "PackageRefused",
    "PackageVersions",
    "ProfileNotFound",
]
