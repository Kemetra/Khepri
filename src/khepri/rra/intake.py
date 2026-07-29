from __future__ import annotations

import csv
import hashlib
import io
import posixpath
import secrets
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from xml.etree import ElementTree

from khepri.rra.sessions import (
    BetaSession,
    SessionExpired,
    SessionScope,
    require_upload_consent,
)

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_XLSX_EXPANDED_BYTES = 250 * 1024 * 1024
MAX_XLSX_ENTRIES = 2_048

CSV_MEDIA_TYPE = "text/csv"
XLSX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

_CONTENT_TYPES_PATH = "[Content_Types].xml"
_WORKBOOK_PATH = "xl/workbook.xml"
_WORKBOOK_RELS_PATH = "xl/_rels/workbook.xml.rels"
_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
_WORKSHEET_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"
)
_ENCRYPTED_OFFICE_PREFIX = bytes.fromhex("d0cf11e0a1b11ae1")


class IntakeRejected(ValueError):
    pass


class UploadTooLarge(IntakeRejected):
    pass


class UploadAlreadyExists(IntakeRejected):
    pass


class StoragePolicyViolation(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    content: bytes
    size_bytes: int
    sha256_hex: str
    media_type: str


@dataclass(frozen=True, slots=True)
class StoredObject:
    key: str
    size_bytes: int
    sha256_hex: str
    media_type: str
    encryption_algorithm: str
    kms_key_id: str


@dataclass(frozen=True, slots=True)
class UploadMetadata:
    upload_id: str
    owner_id: str
    session_id: str
    object_key: str
    size_bytes: int
    sha256_hex: str
    media_type: str
    created_at: datetime
    expires_at: datetime
    encryption_algorithm: str
    kms_key_id: str

    @property
    def scope(self) -> SessionScope:
        return SessionScope(owner_id=self.owner_id, session_id=self.session_id)


class SessionReader(Protocol):
    def get_session(self, session_id: str) -> BetaSession | None: ...


class UploadRepository(Protocol):
    def add_upload(self, upload: UploadMetadata) -> bool: ...

    def get_upload_for_session(self, session_id: str) -> UploadMetadata | None: ...

    def get_upload_in_scope(
        self,
        upload_id: str,
        scope: SessionScope,
    ) -> UploadMetadata | None: ...


class EncryptedObjectStore(Protocol):
    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
        encryption_context: dict[str, str],
    ) -> StoredObject: ...

    def delete(self, key: str) -> None: ...


class UploadAccumulator:
    def __init__(
        self,
        *,
        declared_size: int | None,
        max_bytes: int = MAX_UPLOAD_BYTES,
        max_expanded_bytes: int = MAX_XLSX_EXPANDED_BYTES,
    ) -> None:
        if declared_size is not None and (declared_size < 0 or declared_size > max_bytes):
            raise UploadTooLarge("Upload exceeds the 50 MB limit.")
        self._declared_size = declared_size
        self._max_bytes = max_bytes
        self._max_expanded_bytes = max_expanded_bytes
        self._content = bytearray()
        self._digest = hashlib.sha256()

    def append(self, chunk: bytes) -> None:
        if len(self._content) + len(chunk) > self._max_bytes:
            raise UploadTooLarge("Upload exceeds the 50 MB limit.")
        self._content.extend(chunk)
        self._digest.update(chunk)

    def finish(self) -> ValidatedUpload:
        content = bytes(self._content)
        if self._declared_size is not None and len(content) != self._declared_size:
            raise IntakeRejected("Upload length does not match Content-Length.")
        media_type = _detect_and_validate(
            content,
            max_expanded_bytes=self._max_expanded_bytes,
        )
        return ValidatedUpload(
            content=content,
            size_bytes=len(content),
            sha256_hex=self._digest.hexdigest(),
            media_type=media_type,
        )


class IntakeService:
    def __init__(
        self,
        *,
        sessions: SessionReader,
        uploads: UploadRepository,
        objects: EncryptedObjectStore,
        new_upload_id: Callable[[], str] | None = None,
    ) -> None:
        self._sessions = sessions
        self._uploads = uploads
        self._objects = objects
        self._new_upload_id = new_upload_id or (
            lambda: f"upl_{secrets.token_urlsafe(18)}"
        )

    def begin(
        self,
        *,
        session_id: str,
        declared_size: int | None,
        now: datetime,
    ) -> PendingUpload:
        session = self._sessions.get_session(session_id)
        if session is None:
            raise SessionExpired("Session content has expired.")
        require_upload_consent(session, now=now)
        if self._uploads.get_upload_for_session(session_id) is not None:
            raise UploadAlreadyExists("This beta session already has an upload.")
        return PendingUpload(
            service=self,
            session=session,
            accumulator=UploadAccumulator(declared_size=declared_size),
        )

    def _complete(
        self,
        *,
        session: BetaSession,
        validated: ValidatedUpload,
        now: datetime,
    ) -> UploadMetadata:
        require_upload_consent(session, now=now)
        upload_id = self._new_upload_id()
        object_key = (
            f"owners/{session.owner_id}/sessions/{session.session_id}/inputs/{upload_id}"
        )
        stored = self._objects.put(
            key=object_key,
            content=validated.content,
            media_type=validated.media_type,
            sha256_hex=validated.sha256_hex,
            encryption_context={
                "owner_id": session.owner_id,
                "session_id": session.session_id,
                "upload_id": upload_id,
            },
        )
        if not _storage_response_is_valid(stored, object_key, validated):
            self._objects.delete(object_key)
            raise StoragePolicyViolation("Object storage did not prove the required policy.")
        metadata = UploadMetadata(
            upload_id=upload_id,
            owner_id=session.owner_id,
            session_id=session.session_id,
            object_key=object_key,
            size_bytes=validated.size_bytes,
            sha256_hex=validated.sha256_hex,
            media_type=validated.media_type,
            created_at=now,
            expires_at=session.content_expires_at,
            encryption_algorithm=stored.encryption_algorithm,
            kms_key_id=stored.kms_key_id,
        )
        try:
            created = self._uploads.add_upload(metadata)
        except Exception:
            self._objects.delete(object_key)
            raise
        if not created:
            self._objects.delete(object_key)
            raise UploadAlreadyExists("This beta session already has an upload.")
        return metadata


class PendingUpload:
    def __init__(
        self,
        *,
        service: IntakeService,
        session: BetaSession,
        accumulator: UploadAccumulator,
    ) -> None:
        self._service = service
        self._session = session
        self._accumulator = accumulator
        self._completed = False

    def append(self, chunk: bytes) -> None:
        if self._completed:
            raise IntakeRejected("Upload has already completed.")
        self._accumulator.append(chunk)

    def complete(self, *, now: datetime) -> UploadMetadata:
        if self._completed:
            raise IntakeRejected("Upload has already completed.")
        validated = self._accumulator.finish()
        metadata = self._service._complete(
            session=self._session,
            validated=validated,
            now=now,
        )
        self._completed = True
        return metadata


def _storage_response_is_valid(
    stored: StoredObject,
    expected_key: str,
    upload: ValidatedUpload,
) -> bool:
    return (
        stored.key == expected_key
        and stored.size_bytes == upload.size_bytes
        and stored.sha256_hex == upload.sha256_hex
        and stored.media_type == upload.media_type
        and stored.encryption_algorithm == "aws:kms"
        and bool(stored.kms_key_id)
    )


def _detect_and_validate(content: bytes, *, max_expanded_bytes: int) -> str:
    if not content or not content.strip():
        raise IntakeRejected("Upload content is invalid or unsupported.")
    if content.startswith(_ENCRYPTED_OFFICE_PREFIX):
        raise IntakeRejected("Upload content is invalid or unsupported.")
    if content.startswith(b"PK"):
        _validate_xlsx(content, max_expanded_bytes=max_expanded_bytes)
        return XLSX_MEDIA_TYPE
    _validate_csv(content)
    return CSV_MEDIA_TYPE


def _validate_csv(content: bytes) -> None:
    if b"\x00" in content:
        raise IntakeRejected("Upload content is invalid or unsupported.")
    try:
        text = content.decode("utf-8-sig")
        rows = csv.reader(io.StringIO(text, newline=""), strict=True)
        populated_rows = 0
        expected_columns: int | None = None
        for row in rows:
            if not any(value.strip() for value in row):
                continue
            populated_rows += 1
            if expected_columns is None:
                expected_columns = len(row)
            elif len(row) != expected_columns:
                raise IntakeRejected("Upload content is invalid or unsupported.")
        if populated_rows < 2 or expected_columns is None or expected_columns < 2:
            raise IntakeRejected("Upload content is invalid or unsupported.")
    except (UnicodeDecodeError, csv.Error) as error:
        raise IntakeRejected("Upload content is invalid or unsupported.") from error


def _validate_xlsx(content: bytes, *, max_expanded_bytes: int) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if (
                len(entries) > MAX_XLSX_ENTRIES
                or len(names) != len(set(names))
                or any(_unsafe_archive_entry(entry) for entry in entries)
                or sum(entry.file_size for entry in entries) > max_expanded_bytes
            ):
                raise IntakeRejected("Upload content is invalid or unsupported.")
            required = {_CONTENT_TYPES_PATH, _WORKBOOK_PATH, _WORKBOOK_RELS_PATH}
            if not required.issubset(names):
                raise IntakeRejected("Upload content is invalid or unsupported.")
            if any("vbaproject" in name.casefold() for name in names):
                raise IntakeRejected("Upload content is invalid or unsupported.")

            content_types = _read_xml_part(archive, _CONTENT_TYPES_PATH)
            if b"macroenabled" in content_types.lower():
                raise IntakeRejected("Upload content is invalid or unsupported.")
            workbook = ElementTree.fromstring(_read_xml_part(archive, _WORKBOOK_PATH))
            relationships = ElementTree.fromstring(
                _read_xml_part(archive, _WORKBOOK_RELS_PATH)
            )
            worksheet_paths = _worksheet_paths(workbook, relationships)
            populated = sum(
                _worksheet_is_populated(_read_xml_part(archive, path))
                for path in worksheet_paths
            )
            if populated != 1:
                raise IntakeRejected("Upload content is invalid or unsupported.")
    except (KeyError, OSError, ElementTree.ParseError, zipfile.BadZipFile) as error:
        raise IntakeRejected("Upload content is invalid or unsupported.") from error


def _unsafe_archive_entry(entry: zipfile.ZipInfo) -> bool:
    path = entry.filename.replace("\\", "/")
    normalized = posixpath.normpath(path)
    return (
        bool(entry.flag_bits & 0x1)
        or path.startswith("/")
        or normalized == ".."
        or normalized.startswith("../")
        or entry.file_size < 0
    )


def _read_xml_part(archive: zipfile.ZipFile, path: str) -> bytes:
    content = archive.read(path)
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise IntakeRejected("Upload content is invalid or unsupported.")
    return content


def _worksheet_paths(
    workbook: ElementTree.Element,
    relationships: ElementTree.Element,
) -> list[str]:
    relationship_targets = {
        relation.attrib["Id"]: relation.attrib["Target"]
        for relation in relationships.findall(f"{{{_PACKAGE_REL_NS}}}Relationship")
        if (
            "Id" in relation.attrib
            and "Target" in relation.attrib
            and relation.attrib.get("Type") == _WORKSHEET_REL_TYPE
        )
    }
    paths: list[str] = []
    for sheet in workbook.findall(f".//{{{_MAIN_NS}}}sheet"):
        relationship_id = sheet.attrib.get(f"{{{_OFFICE_REL_NS}}}id")
        if relationship_id is None or relationship_id not in relationship_targets:
            raise IntakeRejected("Upload content is invalid or unsupported.")
        target = relationship_targets[relationship_id].replace("\\", "/")
        path = posixpath.normpath(posixpath.join("xl", target))
        if not path.startswith("xl/worksheets/"):
            raise IntakeRejected("Upload content is invalid or unsupported.")
        paths.append(path)
    if not paths:
        raise IntakeRejected("Upload content is invalid or unsupported.")
    return paths


def _worksheet_is_populated(content: bytes) -> bool:
    worksheet = ElementTree.fromstring(content)
    for cell in worksheet.findall(f".//{{{_MAIN_NS}}}c"):
        value = cell.find(f"{{{_MAIN_NS}}}v")
        if value is not None and value.text is not None:
            return True
        for text in cell.findall(f".//{{{_MAIN_NS}}}t"):
            if text.text:
                return True
    return False
