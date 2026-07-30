from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

import polars as pl

from khepri.rra.intake import CSV_MEDIA_TYPE, XLSX_MEDIA_TYPE

PROFILE_VERSION = "rra003.profile.v2"

MAX_PROFILED_COLUMNS = 512
MAX_SAFE_LABEL_LENGTH = 64
HIGH_NULL_RATE = Decimal("0.5")
PERSONAL_DATA_SHAPE_RATE = Decimal("0.5")

TYPE_EMPTY = "empty"
TYPE_INTEGER = "integer"
TYPE_DECIMAL = "decimal"
TYPE_DATE = "date"
TYPE_TEXT = "text"

NUMERIC_TYPES = frozenset({TYPE_INTEGER, TYPE_DECIMAL})

_INTEGER = re.compile(r"[+-]?\d+")
_DECIMAL = re.compile(r"[+-]?(?:\d+\.\d*|\.\d+)")

_PHONE = re.compile(r"\+?\d[\d .\-()/]{7,18}\d")
# The same shape, bounded by anything that is not alphanumeric, so it can be
# located inside surrounding prose without matching part of a longer run of
# digits or letters. The guard is written to let an underscore act as a border.
_PHONE_SPAN = re.compile(r"(?<![^\W_])\+?\d[\d .\-()/]{7,18}\d(?![^\W_])")
# A card carries its grouping in spaces or hyphens, and concatenating every
# digit in the value loses it as soon as any other number sits nearby.
_CARD_SPAN = re.compile(r"(?<![^\W_])\d[\d \-]{11,25}\d(?![^\W_])")
_IBAN = re.compile(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}")
_DIGITS_ONLY = re.compile(r"\d+")
_FRAGMENT_SEPARATORS = re.compile(r"[\s<>,;:()\[\]{}\"'|]+")
_TRAILING_PUNCTUATION = ".,;:!?-"
# A mailbox written against a bracketed address literal is split apart by the
# fragment separators, so it is also sought as a span whose bracketed host is
# kept whole.
_EMAIL_CANDIDATE = re.compile(r"[^\s<>,;:()\[\]{}\"'|]+@(?:\[[^\]\s]*\]|[^\s<>,;:()\[\]{}\"'|]+)")

_DATE_FORMATS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("iso_date", ("%Y-%m-%d", "%Y/%m/%d")),
    ("iso_month", ("%Y-%m",)),
    ("iso_datetime", ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S")),
    ("day_first", ("%d/%m/%Y", "%d-%m-%Y")),
    ("month_first", ("%m/%d/%Y", "%m-%d-%Y")),
)

_PERSONAL_DATA_LABEL_TOKENS: dict[str, frozenset[str]] = {
    "email": frozenset({"email", "emails", "mail", "بريد", "ايميل"}),
    "phone": frozenset(
        {"phone", "phones", "mobile", "msisdn", "tel", "telephone", "whatsapp", "هاتف", "جوال"}
    ),
    "person_name": frozenset(
        {
            "firstname",
            "lastname",
            "fullname",
            "surname",
            "customername",
            "clientname",
            "buyername",
            "contactname",
            "cardholder",
            "cardholdername",
            "اسم",
            "الاسم",
        }
    ),
    "address": frozenset({"address", "street", "postcode", "zip", "عنوان", "العنوان"}),
    "national_id": frozenset(
        {"ssn", "nid", "nationalid", "iqama", "passport", "هوية", "الهوية", "جواز"}
    ),
    "financial_instrument": frozenset({"iban", "pan", "cardnumber", "creditcard", "ايبان"}),
    "date_of_birth": frozenset({"dob", "birthdate", "dateofbirth", "ميلاد"}),
}

_LABEL_UNSAFE_PREFIX = frozenset({"=", "+", "-", "@", "\t", "\r", "\n"})
_LABEL_ALLOWED_PUNCTUATION = frozenset(" _-()/%.&#:")


class ProfileRejected(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ColumnProfile:
    position: int
    safe_label: str
    source_label_digest: str
    inferred_type: str
    row_count: int
    non_null_count: int
    null_count: int
    null_rate: str
    distinct_count: int
    minimum: str | None
    maximum: str | None
    date_format: str | None
    personal_data_risk: bool
    personal_data_signals: tuple[str, ...]
    findings: tuple[str, ...]

    @property
    def is_numeric(self) -> bool:
        return self.inferred_type in NUMERIC_TYPES

    def as_document(self) -> dict[str, object]:
        return {
            "position": self.position,
            "safe_label": self.safe_label,
            "source_label_digest": self.source_label_digest,
            "inferred_type": self.inferred_type,
            "row_count": self.row_count,
            "non_null_count": self.non_null_count,
            "null_count": self.null_count,
            "null_rate": self.null_rate,
            "distinct_count": self.distinct_count,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "date_format": self.date_format,
            "personal_data_risk": self.personal_data_risk,
            "personal_data_signals": list(self.personal_data_signals),
            "findings": list(self.findings),
        }


@dataclass(frozen=True, slots=True)
class DatasetProfile:
    profile_version: str
    media_type: str
    source_sha256_hex: str
    row_count: int
    column_count: int
    columns: tuple[ColumnProfile, ...]
    findings: tuple[str, ...]

    def column_at(self, position: int) -> ColumnProfile:
        return self.columns[position]

    def as_document(self) -> dict[str, object]:
        return {
            "profile_version": self.profile_version,
            "media_type": self.media_type,
            "source_sha256_hex": self.source_sha256_hex,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [column.as_document() for column in self.columns],
            "findings": list(self.findings),
        }

    @property
    def digest(self) -> str:
        return hashlib.sha256(canonical_json(self.as_document()).encode()).hexdigest()


def canonical_json(document: object) -> str:
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def build_profile(
    *,
    content: bytes,
    media_type: str,
    source_sha256_hex: str,
) -> DatasetProfile:
    frame = materialize(content, media_type)
    if frame.width == 0:
        raise ProfileRejected("Upload content is invalid or unsupported.")
    if frame.width > MAX_PROFILED_COLUMNS:
        raise ProfileRejected("Upload has more columns than the profiler admits.")

    row_count = frame.height
    columns: list[ColumnProfile] = []
    labels: list[str] = []
    for position, name in enumerate(frame.columns):
        safe_label = _safe_label(name, position)
        labels.append(safe_label)
        columns.append(
            _profile_column(
                frame.get_column(name),
                position=position,
                safe_label=safe_label,
                source_label=name,
                row_count=row_count,
            )
        )

    findings: list[str] = []
    if row_count == 0:
        findings.append("no_data_rows")
    if len(set(labels)) != len(labels):
        findings.append("duplicate_safe_labels")
    if all(column.inferred_type == TYPE_EMPTY for column in columns):
        findings.append("all_columns_empty")

    return DatasetProfile(
        profile_version=PROFILE_VERSION,
        media_type=media_type,
        source_sha256_hex=source_sha256_hex,
        row_count=row_count,
        column_count=len(columns),
        columns=tuple(columns),
        findings=tuple(findings),
    )


def materialize(content: bytes, media_type: str) -> pl.DataFrame:
    """Read governed CSV/XLSX content with every column held as text."""
    try:
        if media_type == CSV_MEDIA_TYPE:
            return pl.read_csv(
                io.BytesIO(content),
                has_header=True,
                infer_schema_length=0,
                truncate_ragged_lines=False,
                rechunk=True,
            )
        if media_type == XLSX_MEDIA_TYPE:
            return pl.read_excel(
                io.BytesIO(content),
                engine="calamine",
                infer_schema_length=0,
            )
    except Exception as error:
        raise ProfileRejected("Upload content is invalid or unsupported.") from error
    raise ProfileRejected("Upload media type is not profilable.")


def _profile_column(
    series: pl.Series,
    *,
    position: int,
    safe_label: str,
    source_label: str,
    row_count: int,
) -> ColumnProfile:
    series = series.cast(pl.String)
    null_count = int(series.null_count())
    non_null_count = row_count - null_count
    values = series.drop_nulls().unique(maintain_order=True).to_list()
    stripped = [value.strip() for value in values]
    present = list(dict.fromkeys(value for value in stripped if value))

    findings: list[str] = []
    if any(value != original for value, original in zip(stripped, values, strict=True)):
        findings.append("whitespace_padded_values")
    if any(not value for value in stripped):
        findings.append("blank_text_values")

    inferred_type, date_format, type_findings = _infer_type(present)
    findings.extend(type_findings)

    signals = _personal_data_signals(safe_label, present)
    personal_data_risk = bool(signals)

    minimum, maximum = (None, None)
    if not personal_data_risk:
        minimum, maximum = _range(present, inferred_type, date_format)

    null_rate = _rate(null_count, row_count)
    if Decimal(null_rate) > HIGH_NULL_RATE and row_count:
        findings.append("high_null_rate")
    if inferred_type == TYPE_EMPTY:
        findings.append("all_values_null")

    return ColumnProfile(
        position=position,
        safe_label=safe_label,
        source_label_digest=hashlib.sha256(source_label.encode()).hexdigest(),
        inferred_type=inferred_type,
        row_count=row_count,
        non_null_count=non_null_count,
        null_count=null_count,
        null_rate=null_rate,
        distinct_count=len(present),
        minimum=minimum,
        maximum=maximum,
        date_format=date_format,
        personal_data_risk=personal_data_risk,
        personal_data_signals=tuple(signals),
        findings=tuple(dict.fromkeys(findings)),
    )


def _infer_type(values: list[str]) -> tuple[str, str | None, list[str]]:
    if not values:
        return TYPE_EMPTY, None, []

    if all(_INTEGER.fullmatch(value) for value in values):
        return TYPE_INTEGER, None, []
    if all(_is_decimal(value) for value in values):
        return TYPE_DECIMAL, None, []

    date_format, ambiguous = _resolve_date_format(values)
    if date_format is not None:
        return TYPE_DATE, date_format, []

    findings: list[str] = []
    if ambiguous:
        findings.append("ambiguous_date_order")
    numeric = sum(1 for value in values if _is_decimal(value) or _INTEGER.fullmatch(value))
    if 0 < numeric < len(values):
        findings.append("mixed_numeric_and_text")
    return TYPE_TEXT, None, findings


def _is_decimal(value: str) -> bool:
    return bool(_DECIMAL.fullmatch(value) or _INTEGER.fullmatch(value))


def _resolve_date_format(values: list[str]) -> tuple[str | None, bool]:
    parsed: dict[str, list[date]] = {}
    for name, patterns in _DATE_FORMATS:
        for pattern in patterns:
            candidate = _parse_all(values, pattern)
            if candidate is not None:
                parsed.setdefault(name, candidate)
                break
    if not parsed:
        return None, False
    names = list(parsed)
    reference = parsed[names[0]]
    if all(parsed[name] == reference for name in names[1:]):
        return names[0], False
    return None, True


def parse_date(value: str, date_format: str) -> date | None:
    """Parse one value under an already-resolved column date format."""
    for name, patterns in _DATE_FORMATS:
        if name != date_format:
            continue
        for pattern in patterns:
            try:
                return datetime.strptime(value, pattern).date()
            except ValueError:
                continue
    return None


def _parse_all(values: list[str], pattern: str) -> list[date] | None:
    parsed: list[date] = []
    for value in values:
        try:
            parsed.append(datetime.strptime(value, pattern).date())
        except ValueError:
            return None
    return parsed


def _range(
    values: list[str],
    inferred_type: str,
    date_format: str | None,
) -> tuple[str | None, str | None]:
    if inferred_type in NUMERIC_TYPES:
        try:
            numbers = [Decimal(value) for value in values]
        except InvalidOperation:
            return None, None
        return str(min(numbers)), str(max(numbers))
    if inferred_type == TYPE_DATE and date_format is not None:
        dates = _parse_dates(values, date_format)
        if dates:
            return min(dates).isoformat(), max(dates).isoformat()
    return None, None


def _parse_dates(values: list[str], date_format: str) -> list[date]:
    patterns = next(
        (patterns for name, patterns in _DATE_FORMATS if name == date_format),
        (),
    )
    for pattern in patterns:
        parsed = _parse_all(values, pattern)
        if parsed is not None:
            return parsed
    return []


def _personal_data_signals(safe_label: str, values: list[str]) -> list[str]:
    signals: list[str] = []
    tokens = label_tokens(safe_label)
    collapsed = "".join(tokens)
    for signal, vocabulary in _PERSONAL_DATA_LABEL_TOKENS.items():
        if vocabulary & set(tokens) or collapsed in vocabulary:
            signals.append(f"label_{signal}")

    if values:
        counts: dict[str, int] = {}
        for value in values:
            for shape in personal_value_shapes(value):
                counts[shape] = counts.get(shape, 0) + 1
        total = Decimal(len(values))
        signals.extend(
            signal
            for signal, matched in counts.items()
            if Decimal(matched) / total >= PERSONAL_DATA_SHAPE_RATE
        )
    return sorted(set(signals))


def personal_value_shapes(value: str) -> tuple[str, ...]:
    """The personal-data shapes one value carries, if any.

    Values are normalized first, so a representation difference — Unicode
    grouping spaces, compatibility digits, or letter case — cannot carry an
    identifier past detection when display sanitizing would later normalize it
    back into a recognizable form.
    """
    text = _normalized_value(value)
    if not text:
        return ()
    # An identifier is checked wherever it sits, not only when it is the whole
    # value: a display name, a note, or a bracketed address would otherwise
    # carry it to a published label intact.
    candidates = (text, *_fragments(text))
    shapes: list[str] = []
    if any(_is_email(part) for part in candidates) or _contains_email(text):
        shapes.append("value_email")
    if any(_is_phone(part) for part in candidates) or _contains_phone(text):
        shapes.append("value_phone")
    # An IBAN and a card number carry grouping spaces as part of the format, so
    # splitting on whitespace would destroy them. Both are also sought in the
    # value stripped of separators.
    if any(_is_iban(part) for part in candidates) or _IBAN.search(_alphanumeric(text)):
        shapes.append("value_iban")
    if (
        any(_is_payment_card(part) for part in candidates)
        or _contains_payment_card(text)
        or _is_payment_card("".join(character for character in text if character.isdigit()))
    ):
        shapes.append("value_payment_card")
    return tuple(shapes)


def _alphanumeric(text: str) -> str:
    return "".join(character for character in text if character.isalnum()).upper()


def _fragments(text: str) -> tuple[str, ...]:
    return tuple(part for part in _FRAGMENT_SEPARATORS.split(text) if part)


def is_personal_value(value: str) -> bool:
    """Whether one value carries a recognized personal-data shape.

    Column-level detection needs a majority of values to agree before it
    excludes a column, so an individual value must still be checked before it
    is published as a label.
    """
    return bool(personal_value_shapes(value))


def _normalized_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(
        " " if character.isspace() else character for character in normalized
    ).strip()


def _is_email(value: str) -> bool:
    """Match an address structurally rather than by an ASCII suffix pattern.

    Requiring an ASCII-letter suffix missed internationalized addresses in both
    punycode and Unicode form, publishing nearly the whole identifier once the
    label sanitizer stripped the separators.
    """
    local, separator, domain = value.partition("@")
    if not separator or not local or "@" in domain or " " in value:
        return False
    # A mailbox may name its host by address instead of by domain, in which case
    # there are no labels to check and no alphabetic suffix to require.
    if domain.startswith("[") and domain.endswith("]"):
        return _is_address_literal(domain[1:-1])
    labels = domain.split(".")
    if len(labels) < 2 or not all(_is_domain_label(label) for label in labels):
        return False
    if _is_ipv4(domain):
        return True
    suffix = labels[-1]
    return len(suffix) >= 2 and any(character.isalpha() for character in suffix)


def _contains_email(text: str) -> bool:
    """Locate a mailbox in surrounding prose.

    The candidate pattern is greedy on the host, so a sentence that ends in the
    address hands back a trailing stop that no domain can carry. Terminal
    punctuation is trimmed before the span is judged.
    """
    return any(
        _is_email(match.group()) or _is_email(match.group().rstrip(_TRAILING_PUNCTUATION))
        for match in _EMAIL_CANDIDATE.finditer(text)
    )


def _contains_payment_card(text: str) -> bool:
    return any(_is_payment_card(match.group()) for match in _CARD_SPAN.finditer(text))


def _is_address_literal(text: str) -> bool:
    candidate = text[5:] if text[:5].casefold() == "ipv6:" else text
    if _is_ipv4(candidate):
        return True
    return ":" in candidate and all(
        character in "0123456789abcdefABCDEF:." for character in candidate
    )


def _is_ipv4(text: str) -> bool:
    parts = text.split(".")
    return len(parts) == 4 and all(
        part.isdigit() and len(part) <= 3 and int(part) <= 255 for part in parts
    )


def _is_domain_label(label: str) -> bool:
    return (
        bool(label)
        and not label.startswith("-")
        and not label.endswith("-")
        and all(character.isalnum() or character == "-" for character in label)
    )


def _is_iban(value: str) -> bool:
    """Match an IBAN regardless of case or grouping whitespace."""
    return bool(_IBAN.fullmatch(value.replace(" ", "").upper()))


def _is_phone(value: str) -> bool:
    if not _PHONE.fullmatch(value):
        return False
    return _dialable(value)


def _contains_phone(text: str) -> bool:
    """Find a phone-shaped span inside a larger value.

    A phone number carries its grouping in whitespace, so splitting a value into
    fragments destroys the very shape being looked for and leaves a recognizable
    number to be published intact. The span is therefore sought in the text as
    it stands, bounded so that a slice of a longer identifier is never read as a
    number.
    """
    return any(_dialable(match.group()) for match in _PHONE_SPAN.finditer(text))


def _dialable(value: str) -> bool:
    digits = "".join(character for character in value if character.isdigit())
    return 9 <= len(digits) <= 15


def _is_payment_card(value: str) -> bool:
    digits = value.replace(" ", "").replace("-", "")
    if not _DIGITS_ONLY.fullmatch(digits) or not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, character in enumerate(reversed(digits)):
        digit = int(character)
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def label_tokens(label: str) -> tuple[str, ...]:
    normalized = normalize_label(label)
    return tuple(token for token in re.split(r"[^0-9a-zء-ي]+", normalized) if token)


def normalize_label(label: str) -> str:
    normalized = unicodedata.normalize("NFKC", label).casefold()
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character) and character != "ـ"
    )
    for source in "آأإ":
        normalized = normalized.replace(source, "ا")
    return normalized.replace("ى", "ي").replace("ة", "ه")


def safe_value_label(source: str, *, fallback: str) -> str:
    """Reduce a customer-derived value to a safe display label."""
    return _sanitize(source) or fallback


def _safe_label(source: str, position: int) -> str:
    return _sanitize(source) or f"column_{position + 1}"


def _sanitize(source: str) -> str:
    normalized = unicodedata.normalize("NFKC", source)
    while normalized[:1] in _LABEL_UNSAFE_PREFIX:
        normalized = normalized[1:]
    kept = [
        character
        for character in normalized
        if unicodedata.category(character)[0] in {"L", "N", "M"}
        or character in _LABEL_ALLOWED_PUNCTUATION
    ]
    return " ".join("".join(kept).split())[:MAX_SAFE_LABEL_LENGTH].strip()


def _rate(count: int, total: int) -> str:
    if total <= 0:
        return "0.0000"
    return str((Decimal(count) / Decimal(total)).quantize(Decimal("0.0001")))
