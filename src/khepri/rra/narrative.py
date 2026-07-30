"""Grounded Arabic and English narrative over an approved fact package.

**What leaves this process.** A narrative request is *projected* from the fact
package through `_REQUEST_SCHEMA` rather than filtered against a list of things
to strip. Anything the package gains later — a new field on a fact, a new
section of the document — is absent from the request until somebody adds it to
the schema deliberately. A blocklist would have the opposite default, and the
field that mattered would be the one nobody thought to name.

The profile digest and the source digest are withheld along with everything
else not named. They authenticate customer content rather than describe it, and
a narrative provider has no use for them.

**What may be said.** `NarrativeGround` is derived from the request that was
actually sent, never from the package. If the two ever disagreed, validating
against the package would admit a number the provider was never given — so the
question "was this supplied?" has exactly one answer, and it is the one the
provider saw.

**What this validator does and does not check.** It checks that every number
stated is a value that was supplied, that every citation resolves to a supplied
identifier, that no section makes a claim without citing anything, that no text
smuggles a spreadsheet formula through a label, and that Arabic and English
cover the same facts and the same caveats. It does not check that the prose
*means* what the facts say. Semantic entailment is not decidable here, so the
guarantee offered is grounding and coverage, not truth of paraphrase.

**Percentages.** A ratio is supplied both as its exact decimal and as an exact
percent rendering computed here with `Decimal`. The provider therefore never
has to convert anything: a narrative that says `66.67%` is quoting a supplied
value, not performing a calculation. Deriving that conversion inside the
validator instead would have let it accept a number the request never carried.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from khepri.rra.facts import FactPackage

NARRATIVE_VERSION = "rra005.narrative.v1"

LANGUAGE_ARABIC = "ar"
LANGUAGE_ENGLISH = "en"
REQUIRED_LANGUAGES = (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)

REASON_PROVIDER_TIMEOUT = "provider_timeout"
REASON_PROVIDER_FAILED = "provider_failed"
REASON_PROVIDER_REFUSED = "provider_refused"
REASON_EMPTY_NARRATIVE = "empty_narrative"
REASON_MISSING_LANGUAGE = "missing_language"
REASON_UNKNOWN_LANGUAGE = "unknown_language"
REASON_UNGROUNDED_NUMBER = "ungrounded_number"
REASON_UNKNOWN_CITATION = "unknown_citation"
REASON_UNCITED_SECTION = "uncited_section"
REASON_UNKNOWN_CAVEAT = "unknown_caveat"
REASON_UNSAFE_TEXT = "unsafe_text"
REASON_FACT_COVERAGE_DIFFERS = "fact_coverage_differs_by_language"
REASON_CAVEAT_COVERAGE_DIFFERS = "caveat_coverage_differs_by_language"
REASON_ADAPTER_MISMATCH = "adapter_response_mismatch"

OUTCOME_NARRATED = "narrated"
OUTCOME_REFUSED = "refused"


class NarrativeRefused(ValueError):
    """The narrative could not be produced or could not be trusted.

    Carries a governed reason code rather than provider text, so a refusal can
    be recorded and reported without echoing anything the provider wrote.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class NarrativeUnavailable(Exception):
    """The provider did not answer. Raised by adapters, never by this module."""


class ProviderRefused(Exception):
    """The provider declined to answer. Raised by adapters, never by this module."""


# The whole of what a provider is given. Nested tuples name the fields kept at
# each level; a key absent from an entry is simply not emitted, so an optional
# field costs no special case. Projection and the minimality assertion both
# read this, so they cannot drift apart.
_REQUEST_SCHEMA: dict[str, Any] = {
    "narrative_version": None,
    "adapter_version": None,
    "package_version": None,
    "formula_version": None,
    "mapping_version": None,
    "languages": None,
    "monetary_precision": None,
    "facts": (
        "fact_id",
        "citation_id",
        "metric",
        "value",
        "value_percent",
        "precision",
        "unit_kind",
        "inputs",
        "caveats",
    ),
    "series": (
        "fact_id",
        "citation_id",
        "metric",
        "measure",
        "precision",
        "unit_kind",
        "granularity",
        {"points": ("label", "value", "rows")},
        "caveats",
    ),
    "comparisons": (
        "fact_id",
        "citation_id",
        "metric",
        "measure",
        "precision",
        "unit_kind",
        "dimension",
        "distinct_values",
        "truncated_values",
        "redacted_values",
        {"buckets": ("label", "value", "rows")},
        "caveats",
    ),
    "refusals": ("metric", "reason"),
    "caveats": None,
}


@dataclass(frozen=True, slots=True)
class NarrativeRequest:
    """Exactly what a provider is sent, and nothing the package also holds."""

    document: dict[str, Any]

    @property
    def package_version(self) -> str:
        return str(self.document["package_version"])

    @property
    def languages(self) -> tuple[str, ...]:
        return tuple(self.document["languages"])

    @classmethod
    def of(
        cls,
        package: FactPackage,
        *,
        adapter_version: str,
        languages: Sequence[str] = REQUIRED_LANGUAGES,
    ) -> NarrativeRequest:
        requested = tuple(languages)
        if set(requested) - set(REQUIRED_LANGUAGES):
            raise NarrativeRefused(REASON_UNKNOWN_LANGUAGE)
        if set(requested) != set(REQUIRED_LANGUAGES):
            # Parity is the point of the requirement; asking for one language
            # would produce a report that reads differently to two readers.
            raise NarrativeRefused(REASON_MISSING_LANGUAGE)

        source = package.as_document()
        document = {
            "narrative_version": NARRATIVE_VERSION,
            "adapter_version": adapter_version,
            "package_version": source["package_version"],
            "formula_version": source["formula_version"],
            "mapping_version": source["mapping_version"],
            "languages": list(requested),
            "monetary_precision": source["monetary_precision"],
            "facts": [_stated(entry) for entry in source["facts"]],
            "series": [_project(entry, _REQUEST_SCHEMA["series"]) for entry in source["series"]],
            "comparisons": [
                _project(entry, _REQUEST_SCHEMA["comparisons"])
                for entry in source["comparisons"]
            ],
            "refusals": [
                _project(entry, _REQUEST_SCHEMA["refusals"]) for entry in source["refusals"]
            ],
            "caveats": list(source["caveats"]),
        }
        _assert_minimal(document)
        return cls(document=document)


@dataclass(frozen=True, slots=True)
class NarrativeGround:
    """Everything a narrative is permitted to state, taken from the request."""

    fact_ids: frozenset[str]
    citation_ids: frozenset[str]
    numbers: frozenset[Decimal]
    labels: frozenset[str]
    caveats: frozenset[str]

    @classmethod
    def of(cls, request: NarrativeRequest) -> NarrativeGround:
        document = request.document
        fact_ids: set[str] = set()
        citation_ids: set[str] = set()
        numbers: set[Decimal] = set()
        labels: set[str] = set()
        caveats: set[str] = set(document["caveats"])

        entries = (*document["facts"], *document["series"], *document["comparisons"])
        for entry in entries:
            fact_ids.add(str(entry["fact_id"]))
            citation_ids.add(str(entry["citation_id"]))
            caveats.update(entry.get("caveats", ()))
            for key in ("value", "value_percent"):
                numbers.update(_as_numbers(entry.get(key)))
            numbers.add(Decimal(int(entry["precision"])))
            for key in ("distinct_values", "truncated_values", "redacted_values"):
                if key in entry:
                    numbers.add(Decimal(int(entry[key])))
            for bucket in (*entry.get("points", ()), *entry.get("buckets", ())):
                label = str(bucket["label"])
                labels.add(label)
                # A label is supplied whole, so the numbers inside it are
                # supplied too. Without this, prose could name the period it is
                # describing only by quoting `2026-01-05` in full — "in 2026"
                # would read as a number nobody gave, which is a refusal in the
                # direction that costs a governed figure rather than protects
                # one. Quoting part of a supplied string is not a derivation.
                numbers.update(_numbers_within(label))
                numbers.update(_as_numbers(bucket.get("value")))
                numbers.add(Decimal(int(bucket["rows"])))

        numbers.add(Decimal(int(document["monetary_precision"])))
        return cls(
            fact_ids=frozenset(fact_ids),
            citation_ids=frozenset(citation_ids),
            numbers=frozenset(numbers),
            labels=frozenset(labels),
            caveats=frozenset(caveats),
        )


@dataclass(frozen=True, slots=True)
class NarrativeSection:
    section_id: str
    text: str
    cited_fact_ids: tuple[str, ...]
    caveats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LanguageNarrative:
    language: str
    sections: tuple[NarrativeSection, ...]

    @property
    def cited_fact_ids(self) -> frozenset[str]:
        return frozenset(
            fact_id for section in self.sections for fact_id in section.cited_fact_ids
        )

    @property
    def covered_caveats(self) -> frozenset[str]:
        return frozenset(caveat for section in self.sections for caveat in section.caveats)


@dataclass(frozen=True, slots=True)
class NarrativeDraft:
    """What an adapter returns. Untrusted until `validate` has accepted it."""

    adapter_version: str
    package_version: str
    languages: tuple[LanguageNarrative, ...]


@dataclass(frozen=True, slots=True)
class NarrativeAttempt:
    """The record of one attempt, carrying no customer content by construction.

    Every field is a governed version string, a language code, a reason code, or
    a duration. There is no field a caveat, label, value, or provider sentence
    could occupy, so the record cannot leak one by being filled in carelessly.
    """

    narrative_version: str
    adapter_version: str
    package_version: str
    languages: tuple[str, ...]
    duration_ms: int
    outcome: str
    reason: str | None

    def as_document(self) -> dict[str, object]:
        return {
            "narrative_version": self.narrative_version,
            "adapter_version": self.adapter_version,
            "package_version": self.package_version,
            "languages": list(self.languages),
            "duration_ms": self.duration_ms,
            "outcome": self.outcome,
            "reason": self.reason,
        }


class NarrativeAdapter(Protocol):
    """A replaceable provider. Selection needs its own architecture decision."""

    @property
    def adapter_version(self) -> str: ...

    def draft(self, request: NarrativeRequest, *, timeout_seconds: Decimal) -> NarrativeDraft: ...


@dataclass(frozen=True, slots=True)
class NarrativeResult:
    attempt: NarrativeAttempt
    narrative: NarrativeDraft | None

    @property
    def refused(self) -> bool:
        return self.narrative is None


class NarrativeService:
    def __init__(
        self,
        *,
        adapter: NarrativeAdapter,
        timeout_seconds: Decimal = Decimal("20"),
        monotonic_ms: Callable[[], int],
    ) -> None:
        self._adapter = adapter
        self._timeout_seconds = timeout_seconds
        self._monotonic_ms = monotonic_ms

    def compose(
        self,
        package: FactPackage,
        *,
        languages: Sequence[str] = REQUIRED_LANGUAGES,
    ) -> NarrativeResult:
        """Return a validated narrative, or a refusal — never a substitute.

        A provider that times out, fails, or declines produces a refusal with a
        reason. Nothing is written in its place: a facts-only report is a
        deterministic artifact the delivery contract may authorize, not
        something this service may invent on a provider's behalf.
        """
        started = self._monotonic_ms()
        adapter_version = self._adapter.adapter_version
        requested = tuple(languages)
        try:
            request = NarrativeRequest.of(
                package,
                adapter_version=adapter_version,
                languages=requested,
            )
            draft = self._adapter.draft(request, timeout_seconds=self._timeout_seconds)
            validate(draft, request=request)
        except NarrativeRefused as refusal:
            return self._refuse(started, adapter_version, package, requested, refusal.reason)
        except (TimeoutError, NarrativeUnavailable, ProviderRefused) as error:
            return self._refuse(
                started,
                adapter_version,
                package,
                requested,
                _provider_reason(error),
            )
        return NarrativeResult(
            attempt=NarrativeAttempt(
                narrative_version=NARRATIVE_VERSION,
                adapter_version=adapter_version,
                package_version=package.package_version,
                languages=request.languages,
                duration_ms=self._monotonic_ms() - started,
                outcome=OUTCOME_NARRATED,
                reason=None,
            ),
            narrative=draft,
        )

    def _refuse(
        self,
        started: int,
        adapter_version: str,
        package: FactPackage,
        languages: tuple[str, ...],
        reason: str,
    ) -> NarrativeResult:
        return NarrativeResult(
            attempt=NarrativeAttempt(
                narrative_version=NARRATIVE_VERSION,
                adapter_version=adapter_version,
                package_version=package.package_version,
                languages=languages,
                duration_ms=self._monotonic_ms() - started,
                outcome=OUTCOME_REFUSED,
                reason=reason,
            ),
            narrative=None,
        )


def validate(draft: NarrativeDraft, *, request: NarrativeRequest) -> None:
    """Refuse a draft that states anything the request did not supply."""
    if draft.package_version != request.package_version:
        raise NarrativeRefused(REASON_ADAPTER_MISMATCH)
    if draft.adapter_version != str(request.document["adapter_version"]):
        raise NarrativeRefused(REASON_ADAPTER_MISMATCH)

    ground = NarrativeGround.of(request)
    seen = {entry.language: entry for entry in draft.languages}
    if set(seen) - set(request.languages):
        raise NarrativeRefused(REASON_UNKNOWN_LANGUAGE)
    if set(seen) != set(request.languages):
        raise NarrativeRefused(REASON_MISSING_LANGUAGE)

    for entry in seen.values():
        _validate_language(entry, ground)

    coverage = [seen[language] for language in sorted(seen)]
    first = coverage[0]
    for other in coverage[1:]:
        # Wording may differ between languages; what may not differ is which
        # facts a reader is told and which caveats they are warned about.
        if other.cited_fact_ids != first.cited_fact_ids:
            raise NarrativeRefused(REASON_FACT_COVERAGE_DIFFERS)
        if other.covered_caveats != first.covered_caveats:
            raise NarrativeRefused(REASON_CAVEAT_COVERAGE_DIFFERS)


def _validate_language(entry: LanguageNarrative, ground: NarrativeGround) -> None:
    if not entry.sections:
        raise NarrativeRefused(REASON_EMPTY_NARRATIVE)
    for section in entry.sections:
        if not section.text.strip():
            raise NarrativeRefused(REASON_EMPTY_NARRATIVE)
        if not section.cited_fact_ids:
            # Prose with no citation is an uncited claim whatever it says.
            raise NarrativeRefused(REASON_UNCITED_SECTION)
        for fact_id in section.cited_fact_ids:
            if fact_id not in ground.fact_ids and fact_id not in ground.citation_ids:
                raise NarrativeRefused(REASON_UNKNOWN_CITATION)
        for caveat in section.caveats:
            if caveat not in ground.caveats:
                raise NarrativeRefused(REASON_UNKNOWN_CAVEAT)
        _assert_safe(section.text)
        _assert_grounded_numbers(section.text, ground)


def _assert_grounded_numbers(text: str, ground: NarrativeGround) -> None:
    """Refuse any number in the prose that was not one of the supplied values.

    A number is supplied if it was given as a value or occurs inside a label
    that was given, so a period label such as `2026-01-05` grounds both the
    whole label and the year a sentence names on its own. One question, asked
    once: was this number in the request?
    """
    for token in _NUMBER_TOKEN.findall(_normalize_digits(text)):
        value = _parse_number(token)
        if value is None or value not in ground.numbers:
            raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)


def _numbers_within(label: str) -> tuple[Decimal, ...]:
    found = (_parse_number(token) for token in _NUMBER_TOKEN.findall(_normalize_digits(label)))
    return tuple(value for value in found if value is not None)


def _assert_safe(text: str) -> None:
    """Refuse text that a downstream renderer would treat as active content.

    RRA-006 renders this prose into a workbook, where a leading `=`, `+`, `-`,
    or `@` on a cell is a formula rather than a sentence. Control characters
    are refused for the same reason: the safety of a label is a property of the
    characters that reach the renderer, not of where the string came from.
    """
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped[:1] in _FORMULA_PREFIXES:
            raise NarrativeRefused(REASON_UNSAFE_TEXT)
    if any(unicodedata.category(character) == "Cc" and character != "\n" for character in text):
        raise NarrativeRefused(REASON_UNSAFE_TEXT)


def _stated(entry: dict[str, Any]) -> dict[str, Any]:
    """Project one fact, adding the percent rendering a ratio will be read in.

    The conversion is exact and happens here, in the request, so that a
    narrative quoting `66.67%` is quoting something it was given. Doing it in
    the validator instead would mean accepting a number nobody supplied.
    """
    projected = _project(entry, _REQUEST_SCHEMA["facts"])
    value = entry.get("value")
    if entry.get("unit_kind") == _UNIT_RATIO and isinstance(value, str):
        try:
            scaled = Decimal(value) * 100
        except InvalidOperation:
            return projected
        projected["value_percent"] = format(
            scaled.quantize(Decimal(1).scaleb(-int(entry["precision"]))),
            "f",
        )
    return projected


def _project(entry: dict[str, Any], schema: tuple[Any, ...]) -> dict[str, Any]:
    projected: dict[str, Any] = {}
    for field in schema:
        if isinstance(field, dict):
            for key, nested in field.items():
                if key in entry:
                    projected[key] = [_project(item, nested) for item in entry[key]]
        elif field in entry:
            projected[field] = entry[field]
    return projected


def _assert_minimal(document: dict[str, Any]) -> None:
    """Refuse to send a request carrying anything the schema does not name.

    Projection already builds from the schema, so this cannot fail on a request
    built by `NarrativeRequest.of`. It exists so that it also cannot fail
    silently: a future builder that assembles a request some other way meets
    the same gate rather than inheriting an unchecked one.
    """
    if set(document) != set(_REQUEST_SCHEMA):
        raise NarrativeRefused(REASON_ADAPTER_MISMATCH)
    for key, schema in _REQUEST_SCHEMA.items():
        if schema is None:
            continue
        for entry in document[key]:
            _assert_only(entry, schema)


def _assert_only(entry: dict[str, Any], schema: tuple[Any, ...]) -> None:
    allowed = {field for field in schema if isinstance(field, str)}
    nested = {
        key: value
        for field in schema
        if isinstance(field, dict)
        for key, value in field.items()
    }
    if set(entry) - allowed - set(nested):
        raise NarrativeRefused(REASON_ADAPTER_MISMATCH)
    for key, inner in nested.items():
        for item in entry.get(key, ()):
            _assert_only(item, inner)


def _as_numbers(value: object) -> tuple[Decimal, ...]:
    if not isinstance(value, str):
        return ()
    parsed = _parse_number(value)
    return () if parsed is None else (parsed,)


def _parse_number(token: str) -> Decimal | None:
    candidate = token.replace(",", "")
    try:
        return Decimal(candidate)
    except InvalidOperation:
        return None


def _normalize_digits(text: str) -> str:
    """Map Arabic-Indic digits and separators onto their ASCII equivalents.

    An Arabic narrative writes `٥٠٠٫٠٠` for the same figure an English one
    writes `500.00`. Comparing the rendered forms would make grounding depend
    on the script; comparing the values does not.
    """
    return text.translate(_DIGIT_TABLE)


def _provider_reason(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return REASON_PROVIDER_TIMEOUT
    if isinstance(error, ProviderRefused):
        return REASON_PROVIDER_REFUSED
    return REASON_PROVIDER_FAILED


_UNIT_RATIO = "ratio"
_FORMULA_PREFIXES = frozenset({"=", "+", "-", "@"})
_NUMBER_TOKEN = re.compile(r"\d[\d,]*(?:\.\d+)?")
_DIGIT_TABLE: dict[int, int] = {
    # Arabic-Indic (U+0660) and Extended Arabic-Indic (U+06F0) digit blocks,
    # plus the Arabic decimal and thousands separators.
    **{0x0660 + offset: ord("0") + offset for offset in range(10)},
    **{0x06F0 + offset: ord("0") + offset for offset in range(10)},
    0x066B: ord("."),
    0x066C: ord(","),
}
