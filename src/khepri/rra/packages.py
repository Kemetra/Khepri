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
from khepri.rra.datasets import (
    DatasetProfileRecord,
    ProfileObjectReader,
    ProfileRepository,
    build_document,
    document_digest,
)
from khepri.rra.facts import FactsRefused, build_fact_package
from khepri.rra.intake import SessionReader, StoragePolicyViolation, UploadRepository
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
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


@dataclass(frozen=True, slots=True)
class FactPackageRecord:
    package_id: str
    owner_id: str
    session_id: str
    profile_id: str
    package_version: str
    formula_version: str
    mapping_version: str
    profile_digest: str
    source_sha256_hex: str
    package_digest: str
    row_count: int
    created_at: datetime
    document: dict[str, Any]

    @property
    def scope(self) -> SessionScope:
        return SessionScope(owner_id=self.owner_id, session_id=self.session_id)


class FactPackageRepository(Protocol):
    def add_package(self, record: FactPackageRecord) -> FactPackageRecord: ...

    def get_package_for_profile(
        self,
        profile_id: str,
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
        request: ReportRequest = DEFAULT_REPORT_REQUEST,
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

        existing = self._packages.get_package_for_profile(
            profile_record.profile_id,
            scope,
        )
        if existing is not None:
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
            profile_digest=profile_record.profile_digest,
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
        return self._packages.get_package_for_session(session_id)


__all__ = [
    "DatasetProfileRecord",
    "FactPackageRecord",
    "FactPackageRepository",
    "FactPackageService",
    "PackageRefused",
    "ProfileNotFound",
]
