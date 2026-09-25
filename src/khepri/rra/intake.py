from __future__ import annotations

import csv
import hashlib
import io
import posixpath
import secrets
import struct
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from xml.etree import ElementTree
from xml.parsers import expat

from khepri.rra.envelope import ALGORITHM_AES_256_GCM, ENVELOPE_VERSION
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
    """One stored object. `sha256_hex` is the plaintext digest and the content
    address; `ciphertext_sha256_hex` proves the bytes read back are the bytes
    written, and differs for every copy because encryption is randomised."""

    key: str
    size_bytes: int
    sha256_hex: str
    media_type: str
    encryption_algorithm: str
    envelope_version: int
    ciphertext_sha256_hex: str


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
    envelope_version: int
    ciphertext_sha256_hex: str

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
            envelope_version=stored.envelope_version,
            ciphertext_sha256_hex=stored.ciphertext_sha256_hex,
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
        and stored.encryption_algorithm == ALGORITHM_AES_256_GCM
        and stored.envelope_version == ENVELOPE_VERSION
        and len(stored.ciphertext_sha256_hex) == 64
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


#: Every way a hostile archive can fail to read. `struct.error` and `zlib.error` come from
#: `_inflates_as_declared`, which walks local headers and deflate streams itself.
_ARCHIVE_ERRORS = (
    KeyError,
    OSError,
    ElementTree.ParseError,
    zipfile.BadZipFile,
    struct.error,
    zlib.error,
)


def _validate_xlsx(content: bytes, *, max_expanded_bytes: int) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            names = [entry.filename for entry in entries]
            if (
                len(entries) > MAX_XLSX_ENTRIES
                or len(names) != len(set(names))
                or any(_unsafe_archive_entry(entry) for entry in entries)
                or not _inflates_as_declared(content, entries, max_expanded_bytes)
            ):
                raise IntakeRejected("Upload content is invalid or unsupported.")
            required = {_CONTENT_TYPES_PATH, _WORKBOOK_PATH, _WORKBOOK_RELS_PATH}
            if not required.issubset(names):
                raise IntakeRejected("Upload content is invalid or unsupported.")
            if any("vbaproject" in name.casefold() for name in names):
                raise IntakeRejected("Upload content is invalid or unsupported.")

            remaining_bytes = max_expanded_bytes

            def read_part(path: str) -> bytes:
                nonlocal remaining_bytes
                part = _read_xml_part(archive, path, max_bytes=remaining_bytes)
                remaining_bytes -= len(part)
                return part

            content_types = read_part(_CONTENT_TYPES_PATH)
            if b"macroenabled" in content_types.lower() or _declares_macros(content_types):
                raise IntakeRejected("Upload content is invalid or unsupported.")
            workbook = ElementTree.fromstring(read_part(_WORKBOOK_PATH))
            relationships = ElementTree.fromstring(read_part(_WORKBOOK_RELS_PATH))
            worksheet_paths = _worksheet_paths(workbook, relationships)
            populated = sum(
                _worksheet_is_populated(read_part(path))
                for path in worksheet_paths
            )
            if populated != 1:
                raise IntakeRejected("Upload content is invalid or unsupported.")
    except _ARCHIVE_ERRORS as error:
        raise IntakeRejected("Upload content is invalid or unsupported.") from error


#: The only member methods a workbook is read under. `read(max_bytes + 1)` bounds the output, not
#: the decompressor: BZIP2 and LZMA can allocate far beyond the budget before returning a byte
#: (CWE-400), and Excel writes neither, so any other method is refused before a member is opened.
_PERMITTED_COMPRESSION = frozenset({zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED})


def _unsafe_archive_entry(entry: zipfile.ZipInfo) -> bool:
    path = entry.filename.replace("\\", "/")
    normalized = posixpath.normpath(path)
    return (
        bool(entry.flag_bits & 0x1)
        or path.startswith("/")
        or normalized == ".."
        or normalized.startswith("../")
        or entry.file_size < 0
        or entry.compress_type not in _PERMITTED_COMPRESSION
    )


#: Output per inflate step, so a member's running count is checked long before it can reach the
#: budget's worth of memory in one call.
_INFLATE_STEP_BYTES = 1024 * 1024
_LOCAL_HEADER = struct.Struct("<4s22xHH")
_LOCAL_HEADER_SIGNATURE = b"PK\x03\x04"


def _inflates_as_declared(
    content: bytes, entries: list[zipfile.ZipInfo], max_expanded_bytes: int
) -> bool:
    """Whether every member inflates to exactly its declared size, within one running budget.

    `#434` §1. The parts intake parses are read under a byte budget, but calamine later reads the
    whole archive -- shared strings, styles, anything present -- so a member intake never opens
    is still inflated in the web process. Its `file_size` is only what its headers claim, and
    `ZipExtFile` stops at that claim and checks nothing past it but the CRC, which a forger can
    match to the prefix. So each member's raw stream is inflated here, counted independently of
    `file_size`, and refused unless it ends exactly at the size it declares.

    The declared sum is checked first, so an honestly oversized archive costs no inflate at all.
    Each member's inflate then stops one step past its own declared size. Every member must
    inflate exactly to what it declares, so the declared sum bounds the actual total, and no
    separate running count is needed. Runs after `_unsafe_archive_entry`, so only STORED and
    DEFLATED members reach it.
    """
    if sum(entry.file_size for entry in entries) > max_expanded_bytes:
        return False
    return all(
        _inflated_size(_member_stream(content, entry), entry) == entry.file_size
        for entry in entries
    )


def _member_stream(content: bytes, entry: zipfile.ZipInfo) -> bytes:
    """A member's raw (compressed) bytes, located through its local header."""
    start = entry.header_offset
    signature, name_length, extra_length = _LOCAL_HEADER.unpack_from(content, start)
    if signature != _LOCAL_HEADER_SIGNATURE:
        raise zipfile.BadZipFile("member local header is missing")
    data_start = start + _LOCAL_HEADER.size + name_length + extra_length
    return content[data_start : data_start + entry.compress_size]


def _inflated_size(stream: bytes, entry: zipfile.ZipInfo) -> int | None:
    """The member's actual inflated length. None once it passes its declared size, or when the
    stream is unterminated."""
    if entry.compress_type == zipfile.ZIP_STORED:
        return len(stream)
    inflater = zlib.decompressobj(-zlib.MAX_WBITS)
    produced = 0
    while True:
        step = inflater.decompress(stream, _INFLATE_STEP_BYTES)
        produced += len(step)
        stream = inflater.unconsumed_tail
        if produced > entry.file_size:
            return None
        if inflater.eof:
            return produced  # a final call may yield nothing: the end marker alone
        if not step and not stream:
            return None  # the stream ran out before its end marker


def _read_xml_part(archive: zipfile.ZipFile, path: str, *, max_bytes: int) -> bytes:
    with archive.open(path) as part:
        content = part.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise IntakeRejected("Upload content is invalid or unsupported.")
    if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise IntakeRejected("Upload content is invalid or unsupported.")
    if _declares_document_type(content):
        raise IntakeRejected("Upload content is invalid or unsupported.")
    return content


def _declares_macros(content_types: bytes) -> bool:
    """Whether any declared content type is macro-enabled, read as the parser decodes it.

    The byte check beside it misses a UTF-16 `[Content_Types].xml` for the same reason
    `_declares_document_type` exists (`#530` S-05): the markers are compared as ASCII
    bytes, while the parser decodes the part per its BOM.
    """
    root = ElementTree.fromstring(content_types)
    return any(
        "macroenabled" in element.get("ContentType", "").casefold() for element in root.iter()
    )


class _PrologEnded(Exception):
    """The root element began, so no document type declaration can follow."""


def _declares_document_type(content: bytes) -> bool:
    """Whether the part declares a DTD, as the parser that will read it decodes it.

    The byte check above compares raw bytes against ASCII markers, and a part
    encoded as UTF-16 never contains them while `ElementTree` -- expat -- decodes
    it per its BOM and parses the declaration anyway (`#530` S-05). Asking expat
    itself sees exactly what the consumer sees. Only the prolog is read: a
    declaration cannot follow the root element, so the parse stops there rather
    than reading every worksheet twice.
    """
    parser = expat.ParserCreate()
    declared = False

    def on_doctype(*_: object) -> None:
        nonlocal declared
        declared = True
        raise _PrologEnded

    def on_root(*_: object) -> None:
        raise _PrologEnded

    parser.StartDoctypeDeclHandler = on_doctype
    parser.StartElementHandler = on_root
    try:
        parser.Parse(content, True)
    except _PrologEnded:
        return declared
    except expat.ExpatError as error:
        raise IntakeRejected("Upload content is invalid or unsupported.") from error
    return declared


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
