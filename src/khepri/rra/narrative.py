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

import hashlib
import re
import unicodedata
from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from khepri.rra.facts import FactPackage
from khepri.rra.profiling import canonical_json

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
REASON_UNKNOWN_LABEL = "unknown_label"
REASON_LABEL_COVERAGE_DIFFERS = "label_coverage_differs_by_language"
REASON_UNSAFE_TEXT = "unsafe_text"
REASON_FACT_COVERAGE_DIFFERS = "fact_coverage_differs_by_language"
REASON_CAVEAT_COVERAGE_DIFFERS = "caveat_coverage_differs_by_language"
REASON_ADAPTER_MISMATCH = "adapter_response_mismatch"

# The whole set of reasons that may be recorded. A refusal reaching the attempt
# record has to be one of these: `NarrativeRefused` is a public exception, so an
# adapter can raise it carrying whatever text it likes, and the record claims to
# hold no customer content by construction. That claim needs a gate, not a
# convention.
GOVERNED_REASONS = frozenset(
    {
        REASON_PROVIDER_TIMEOUT,
        REASON_PROVIDER_FAILED,
        REASON_PROVIDER_REFUSED,
        REASON_EMPTY_NARRATIVE,
        REASON_MISSING_LANGUAGE,
        REASON_UNKNOWN_LANGUAGE,
        REASON_UNGROUNDED_NUMBER,
        REASON_UNKNOWN_CITATION,
        REASON_UNCITED_SECTION,
        REASON_UNKNOWN_CAVEAT,
        REASON_UNKNOWN_LABEL,
        REASON_LABEL_COVERAGE_DIFFERS,
        REASON_UNSAFE_TEXT,
        REASON_FACT_COVERAGE_DIFFERS,
        REASON_CAVEAT_COVERAGE_DIFFERS,
        REASON_ADAPTER_MISMATCH,
    }
)

OUTCOME_NARRATED = "narrated"
OUTCOME_REFUSED = "refused"

# Recorded when the adapter could not even say which build it is, so the
# attempt still has a version field rather than a hole.
_UNKNOWN_ADAPTER = "unknown"


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

    @property
    def digest(self) -> str:
        """Identity of *this* request, content and all.

        `package_version` names the schema — every package built by this
        release carries the same string — and a fact identifier is derived from
        metric, scope and formula version, so two different datasets produce
        identical identifiers. Neither distinguishes one request from another,
        which means a cached or misrouted answer written for somebody else's
        figures satisfied both. A digest over the whole document does.
        """
        return hashlib.sha256(canonical_json(self.document).encode()).hexdigest()

    def for_provider(self) -> NarrativeRequest:
        """A copy to cross the adapter boundary, so the authority cannot.

        `frozen=True` freezes the dataclass shell; the document and the lists
        inside it stay mutable, and an adapter handed the authority could edit
        a supplied value to whatever its prose was going to claim. The ground
        is built from the request afterwards, so that edit would rewrite the
        standard the answer is judged against — the provider would be marking
        its own paper.
        """
        return NarrativeRequest(document=deepcopy(self.document))

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
class GroundedEntry:
    """What one cited fact makes available to a sentence that cites it.

    Percent renderings are held apart from plain values because the suffix is
    part of the claim. A ratio supplied as `0.6000` and `60.0000%` says the
    same thing twice; `0.6000%` and `60.0000` say two different wrong things,
    and one set could not tell them apart.
    """

    numbers: frozenset[Decimal]
    percents: frozenset[Decimal]
    labels: frozenset[str]


@dataclass(frozen=True, slots=True)
class NarrativeGround:
    """Everything a narrative is permitted to state, taken from the request.

    Numbers are held *per cited fact* rather than in one pool. A pool answers
    "did this number appear anywhere in the package", which is not the question
    a reader needs answered: it accepts a sentence citing revenue while stating
    the units count, and the resulting report is cited and wrong. The question
    asked here is "did the fact this sentence cites carry this number".
    """

    entries: dict[str, GroundedEntry]
    identities: dict[str, str]
    caveats: frozenset[str]
    labels: frozenset[str]

    @property
    def identifiers(self) -> frozenset[str]:
        return frozenset(self.entries)

    def identity(self, cited: Sequence[str]) -> frozenset[str]:
        """The facts these citations name, whichever identifier was used.

        Comparing raw identifiers across languages would refuse a draft that
        cites the same fact by `fact_id` in one and `citation_id` in the other.
        Both are accepted names for it, so coverage has to be compared in terms
        of the fact rather than the spelling.
        """
        return frozenset(self.identities[name] for name in cited if name in self.identities)

    def stateable(self, cited: Sequence[str]) -> GroundedEntry:
        """What a section citing exactly these facts may state.

        Raises rather than returning a default when a citation resolves to
        nothing, so an unknown citation cannot quietly narrow the permitted set
        and look like a grounding failure instead.
        """
        numbers: set[Decimal] = set()
        percents: set[Decimal] = set()
        labels: set[str] = set()
        for identifier in cited:
            entry = self.entries.get(identifier)
            if entry is None:
                raise NarrativeRefused(REASON_UNKNOWN_CITATION)
            numbers |= entry.numbers
            percents |= entry.percents
            labels |= entry.labels
        return GroundedEntry(
            numbers=frozenset(numbers),
            percents=frozenset(percents),
            labels=frozenset(labels),
        )

    @classmethod
    def of(cls, request: NarrativeRequest) -> NarrativeGround:
        document = request.document
        entries: dict[str, GroundedEntry] = {}
        identities: dict[str, str] = {}
        caveats: set[str] = set(document["caveats"])

        for entry in (*document["facts"], *document["series"], *document["comparisons"]):
            caveats.update(entry.get("caveats", ()))
            numbers: set[Decimal] = set()
            labels: set[str] = set()
            numbers.update(_as_numbers(entry.get("value")))
            percents = set(_as_numbers(entry.get("value_percent")))
            # `precision` is deliberately absent. It says how a figure is
            # written, not what it is, and admitting it would let a sentence
            # citing a `500.00` revenue state `Revenue was 2` — a formatting
            # detail passing as the value of the fact beside it.
            for key in ("distinct_values", "truncated_values", "redacted_values"):
                if key in entry:
                    numbers.add(Decimal(int(entry[key])))
            for bucket in (*entry.get("points", ()), *entry.get("buckets", ())):
                label = str(bucket["label"])
                # Stored in the form prose will be compared in, so a label is
                # matched by what a reader sees rather than by which script it
                # was written in.
                labels.add(_normalize_digits(label))
                # A label is supplied whole, so the numbers inside it are
                # supplied too. Without this, prose could name the period it is
                # describing only by quoting `2026-01-05` in full — "in 2026"
                # would read as a number nobody gave, which is a refusal in the
                # direction that costs a governed figure rather than protects
                # one. Quoting part of a supplied string is not a derivation.
                numbers.update(_numbers_within(label))
                numbers.update(_as_numbers(bucket.get("value")))
                numbers.add(Decimal(int(bucket["rows"])))

            grounded = GroundedEntry(
                numbers=frozenset(numbers),
                percents=frozenset(percents),
                labels=frozenset(labels),
            )
            # A fact is citable by either identifier, and both must reach the
            # same permitted set — otherwise which name a provider happened to
            # use would decide what it is allowed to say.
            fact_id = str(entry["fact_id"])
            for name in (fact_id, str(entry["citation_id"])):
                entries[name] = grounded
                identities[name] = fact_id

        return cls(
            entries=entries,
            identities=identities,
            caveats=frozenset(caveats),
            labels=frozenset(
                label for grounded in entries.values() for label in grounded.labels
            ),
        )


@dataclass(frozen=True, slots=True)
class NarrativeSection:
    """One passage, and the structured claims it says it is making.

    `labels` is declared rather than inferred. A bucket label is an ordinary
    word — `Cairo`, `Beverages` — so prose naming one carries no marker a
    scanner could find, and a narrative could name a store that appears nowhere
    in the data. Declaring them turns "which places does this sentence talk
    about" into a question with an answer.
    """

    section_id: str
    text: str
    cited_fact_ids: tuple[str, ...]
    caveats: tuple[str, ...]
    labels: tuple[str, ...] = ()


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

    @property
    def declared_labels(self) -> frozenset[str]:
        return frozenset(
            _normalize_digits(label) for section in self.sections for label in section.labels
        )


@dataclass(frozen=True, slots=True)
class NarrativeDraft:
    """What an adapter returns. Untrusted until `validate` has accepted it.

    It echoes the digest of the request it answers rather than a version
    string. A version names the schema; the digest names this request, so an
    answer written for another package cannot satisfy it.
    """

    adapter_version: str
    request_digest: str
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
        requested = tuple(languages)
        try:
            # Reading the version is already the adapter's code running, so it
            # is inside the failure policy rather than in front of it.
            adapter_version = self._adapter.adapter_version
        except Exception:  # noqa: BLE001 - a misconfigured provider is a refusal
            return self._refuse(
                started,
                _UNKNOWN_ADAPTER,
                package,
                requested,
                REASON_PROVIDER_FAILED,
            )

        try:
            request = NarrativeRequest.of(
                package,
                adapter_version=adapter_version,
                languages=requested,
            )
        except NarrativeRefused as refusal:
            return self._refuse(started, adapter_version, package, requested, refusal.reason)

        try:
            # The adapter is given a copy; `request` stays the authority that
            # `validate` grounds against.
            draft = self._adapter.draft(
                request.for_provider(),
                timeout_seconds=self._timeout_seconds,
            )
            validate(draft, request=request)
        except NarrativeRefused as refusal:
            return self._refuse(started, adapter_version, package, requested, refusal.reason)
        except Exception as error:  # noqa: BLE001 - see below
            # Everything from here out is a refusal, deliberately including
            # exceptions nobody anticipated. A provider raising `ConnectionError`
            # or returning an object malformed enough to break `validate` is
            # still just a provider that did not answer, and the narrative is
            # the optional part of the report — letting it propagate would take
            # down a delivery that the deterministic facts could have carried.
            # The reason code is coarse on purpose: it says only that the
            # provider failed, so nothing the provider produced is echoed.
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
                # Anything not on the governed list is recorded as a provider
                # failure rather than repeated. The text is discarded, not
                # truncated: a shortened sentence is still a sentence.
                reason=reason if reason in GOVERNED_REASONS else REASON_PROVIDER_FAILED,
            ),
            narrative=None,
        )


def validate(draft: NarrativeDraft, *, request: NarrativeRequest) -> None:
    """Refuse a draft that states anything the request did not supply."""
    if draft.request_digest != request.digest:
        # One question, and it subsumes the version: the digest covers every
        # byte of the request, `package_version` among them.
        raise NarrativeRefused(REASON_ADAPTER_MISMATCH)
    if draft.adapter_version != str(request.document["adapter_version"]):
        raise NarrativeRefused(REASON_ADAPTER_MISMATCH)

    ground = NarrativeGround.of(request)
    offered = [entry.language for entry in draft.languages]
    if len(set(offered)) != len(offered):
        # Collapsing duplicates into a mapping would validate the last entry
        # and hand back the draft still carrying the others, so a second copy
        # of a language could smuggle through anything at all.
        raise NarrativeRefused(REASON_ADAPTER_MISMATCH)
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
        # facts a reader is told and which caveats they are warned about. The
        # comparison is on the facts, not on which of a fact's two accepted
        # names each language happened to cite.
        if ground.identity(other.cited_fact_ids) != ground.identity(first.cited_fact_ids):
            raise NarrativeRefused(REASON_FACT_COVERAGE_DIFFERS)
        if other.covered_caveats != first.covered_caveats:
            raise NarrativeRefused(REASON_CAVEAT_COVERAGE_DIFFERS)
        # Declared labels are machine-readable claims, so naming Cairo in one
        # language and Giza in the other is two different leaders asserted to
        # two readers — a contradiction this can actually see, unlike the ones
        # buried in prose.
        if other.declared_labels != first.declared_labels:
            raise NarrativeRefused(REASON_LABEL_COVERAGE_DIFFERS)


def _validate_language(entry: LanguageNarrative, ground: NarrativeGround) -> None:
    if not entry.sections:
        raise NarrativeRefused(REASON_EMPTY_NARRATIVE)
    for section in entry.sections:
        if not section.text.strip():
            raise NarrativeRefused(REASON_EMPTY_NARRATIVE)
        if not section.cited_fact_ids:
            # Prose with no citation is an uncited claim whatever it says.
            raise NarrativeRefused(REASON_UNCITED_SECTION)
        for caveat in section.caveats:
            if caveat not in ground.caveats:
                raise NarrativeRefused(REASON_UNKNOWN_CAVEAT)
        stateable = ground.stateable(section.cited_fact_ids)
        for label in section.labels:
            if _normalize_digits(label) not in stateable.labels:
                raise NarrativeRefused(REASON_UNKNOWN_LABEL)
        _assert_safe(section.text)
        # `stateable` resolves the citations and derives the permitted numbers
        # in one step, so a sentence is measured against what it cites rather
        # than against everything the package happens to contain.
        _assert_grounded_numbers(section.text, stateable)


def _assert_grounded_numbers(text: str, allowed: GroundedEntry) -> None:
    """Refuse any numeric claim the cited facts did not carry.

    The unit checked is the whole *candidate* — a maximal run of digits and the
    characters that can belong to a number — not whatever a pattern happens to
    match inside it. Matching a pattern leaves everything it fails to recognize
    unexamined, which is a hole shaped exactly like the forms nobody thought
    of: `.5` yields no match at all, and `500k` yields a `500` that grounds
    while the sentence claims five hundred thousand. A candidate must be
    recognized *entirely* or it is refused.

    A candidate is carried if it is a supplied label, or if it is a complete
    number whose value a cited fact supplied. So `2026-01-05` passes as the
    label it is, `2026` passes as a number that label contains, and `500k`,
    `.5`, `500.00x`, and `-500.00` do not pass at all.
    """
    normalized = _normalize_digits(text)
    _assert_no_unreadable_numerals(normalized)
    for match in _NUMERIC_CANDIDATE.finditer(normalized):
        candidate = match.group()
        before = normalized[match.start() - 1] if match.start() else ""
        tail = normalized[match.end() :]
        after = tail[:1]
        if before.isalpha() or after.isalpha():
            # `500k` and `INV-1`: digits fused to letters mean something the
            # number alone does not say.
            raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)
        _assert_unmodified(normalized[: match.start()], tail)
        # A trailing full stop or comma ends a sentence rather than the number.
        trimmed = candidate.rstrip(".,")
        if trimmed in allowed.labels:
            continue
        if not _COMPLETE_NUMBER.fullmatch(trimmed):
            raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)
        value = _parse_number(trimmed)
        if value is None:
            raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)
        # A percent sign changes what the digits assert, so it is part of the
        # claim rather than decoration after it. `500.00%` is not the revenue
        # `500.00`, and `0.6000%` is not the margin `0.6000` however close it
        # looks — each has to match a rendering that was actually supplied.
        # The space in `500.00 %` is typography, not a boundary: reading the
        # suffix only when it is flush against the digits would let the most
        # ordinary way of writing a percentage escape the check entirely.
        stated = allowed.percents if _states_percent(tail) else allowed.numbers
        if value not in stated:
            raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)


def _states_percent(tail: str) -> bool:
    """Whether what follows a figure turns it into a rate.

    The sign is a property — `%` and its script variants normalize to one
    character. The words are a vocabulary, with the same bound as the scale
    words: `percent` and `بالمئة` are covered, a phrasing outside the list is
    not.
    """
    rest = tail.lstrip(_INLINE_SPACE)
    if rest[:1] == "%":
        return True
    return _first_word(rest).casefold() in _PERCENT_WORDS


def _assert_unmodified(before: str, after: str) -> None:
    """Refuse a figure standing next to something that changes what it asserts.

    `500 thousand` is not the supplied `500`, and `$500.00` names a currency
    this package never declares — it raises `currency_not_declared` precisely
    because it does not know one. Both were accepted because the modifier sits
    outside the candidate, which is where `%` was too.

    **The guarantee here is not uniform, and the difference matters.** Currency
    symbols are recognized by Unicode category, so that half is a property and
    is complete. Scale words are a *vocabulary* for the two governed languages,
    so a word outside the list would pass — this is a bound, not a proof, and
    it is the kind of enumeration that has already failed three times on this
    branch for dashes and digits. It is here because natural-language
    magnitude words have no character property to ask about, and refusing the
    common ones is better than refusing none.
    """
    leading = before.rstrip(_INLINE_SPACE)
    trailing = after.lstrip(_INLINE_SPACE)
    # `(500.00)` is accounting notation for a negative amount. Parentheses
    # *enclosing* a figure are a sign; a parenthetical after one — `500.00
    # (final)` — is an aside, and the two are told apart by whether the
    # bracket closes immediately after the digits.
    if leading[-1:] == "(" and trailing[:1] == ")":
        raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)
    if _is_currency(leading[-1:]) or _is_currency(trailing[:1]):
        raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)
    # `<500.00` and `≠500.00` contradict the very figure they quote. A maths
    # symbol beside a value is an operator on it, not punctuation next to it,
    # and Unicode already knows which characters those are.
    if _is_operator(leading[-1:]) or _is_operator(trailing[:1]):
        raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)
    for word in (_last_word(leading), _first_word(trailing)):
        if word and (word.casefold() in _SCALE_WORDS or _is_currency_code(word)):
            raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)


def _is_currency_code(word: str) -> bool:
    """Whether a word beside a figure names a currency.

    Two tests, because neither alone works. Three capitals is the *shape* a
    currency code is written in, so `XYZ` is refused without being listed. And
    a real ISO 4217 code is refused whatever its case, so `usd` does not slip
    past the shape test — but only codes that are not ordinary words, because
    `ALL`, `TRY` and `CUP` are currencies *and* everyday English, and refusing
    `500.00 all told` would cost far more than it protects.
    """
    if _ISO_CURRENCY_CODE.fullmatch(word):
        return True
    return word.casefold() in _UNAMBIGUOUS_CURRENCY_CODES


def _is_currency(character: str) -> bool:
    return bool(character) and unicodedata.category(character) == "Sc"


def _is_operator(character: str) -> bool:
    return bool(character) and unicodedata.category(character) == "Sm"


def _first_word(text: str) -> str:
    return _WORD.match(text).group() if _WORD.match(text) else ""


def _last_word(text: str) -> str:
    found = _WORD.search(text[::-1])
    return found.group()[::-1] if found and found.start() == 0 else ""


def _numbers_within(label: str) -> tuple[Decimal, ...]:
    found = (
        _parse_number(token) for token in _LABEL_NUMBER.findall(_normalize_digits(label))
    )
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
    """Map every decimal digit and numeric separator onto its ASCII equivalent.

    An Arabic narrative writes `٥٠٠٫٠٠` for the same figure an English one
    writes `500.00`. Comparing the rendered forms would make grounding depend
    on the script; comparing the values does not.

    Unicode is asked which characters are decimal digits rather than a table
    naming the blocks this module happens to know about. Enumerating them left
    fullwidth `９９９` unrecognized, so it produced no candidate and escaped
    grounding entirely — a scanner that silently sees nothing is worse than one
    that refuses, because it reports success.
    """
    return "".join(_normalized(character) for character in text)


def _normalized(character: str) -> str:
    replacement = _PUNCTUATION_TABLE.get(ord(character))
    if replacement is not None:
        return replacement
    if character.isdecimal():
        return str(unicodedata.decimal(character))
    if unicodedata.category(character) == "Pd":
        # Every dash punctuation there is, asked of Unicode rather than listed.
        # Listing them is what let U+2212 through, and then U+2012, U+2010, and
        # U+2011 after that: the third time the same enumeration failed. A dash
        # attached to digits is a sign whatever its code point.
        return "-"
    return character


def _assert_no_unreadable_numerals(text: str) -> None:
    """Refuse numeric characters that are not digits and carry a value anyway.

    `½`, `²`, and `Ⅳ` state quantities while forming no part of any candidate,
    so leaving them alone would let a figure travel in prose the scanner never
    examines. There is no supplied rendering they could match, so refusing is
    the only answer available.
    """
    for character in text:
        if character.isdecimal():
            # Already an ASCII digit by this point, and part of a candidate.
            continue
        if unicodedata.numeric(character, None) is not None:
            raise NarrativeRefused(REASON_UNGROUNDED_NUMBER)


def _provider_reason(error: Exception) -> str:
    if isinstance(error, TimeoutError):
        return REASON_PROVIDER_TIMEOUT
    if isinstance(error, ProviderRefused):
        return REASON_PROVIDER_REFUSED
    return REASON_PROVIDER_FAILED


_UNIT_RATIO = "ratio"
_FORMULA_PREFIXES = frozenset({"=", "+", "-", "@"})
# A maximal run of digits and the characters that can belong to a number. The
# run is the unit checked, so nothing numeric-looking escapes by falling
# outside a narrower pattern.
_NUMERIC_CANDIDATE = re.compile(r"[0-9.,+\-]*[0-9][0-9.,+\-]*")

# The complete forms a value may take. Grouping must be in threes, so an
# ambiguous `500,00` is refused rather than read as one convention or the other.
_COMPLETE_NUMBER = re.compile(r"[+-]?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?")

# Inside a label the question is which numbers it contains, not whether the
# label as a whole is a number: `2026-01-05` contains 2026, and a sentence may
# name the year without quoting the whole label.
_LABEL_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_INLINE_SPACE = " \t  "
_WORD = re.compile(r"\w+")

# An ISO 4217 code is exactly three capitals, which is a shape rather than a
# list, so `EGP` and `USD` are refused beside a figure without naming either.
# It costs the odd three-letter acronym next to a number; that costs a
# sentence, where inventing a currency costs a governed figure.
_ISO_CURRENCY_CODE = re.compile(r"[A-Z]{3}")

# Real ISO 4217 codes, matched case-insensitively so `usd` cannot slip past the
# shape test above. Codes that are also ordinary words in the governed
# languages are deliberately absent — ALL, TRY, TOP, CUP, MAD, BAM, SOS, LAK —
# because refusing `500.00 all told` costs a sentence to catch a currency
# nobody writes in lower case anyway.
_UNAMBIGUOUS_CURRENCY_CODES = frozenset(
    {
        "aed", "afn", "amd", "ang", "aoa", "aud", "awg", "azn", "bbd", "bdt", "bgn", "bhd",
        "bif", "bmd", "bnd", "bob", "brl", "bsd", "btn", "bwp", "byn", "bzd", "cad", "cdf",
        "chf", "clp", "cny", "cop", "crc", "cuc", "cve", "czk", "djf", "dkk", "dop", "dzd",
        "egp", "ern", "etb", "eur", "fjd", "fkp", "gbp", "gel", "ghs", "gip", "gmd", "gnf",
        "gtq", "gyd", "hkd", "hnl", "hrk", "htg", "huf", "idr", "ils", "inr", "iqd", "irr",
        "isk", "jmd", "jod", "jpy", "kgs", "khr", "kmf", "kpw", "krw", "kwd", "kyd", "kzt",
        "lbp", "lkr", "lrd", "lsl", "lyd", "mdl", "mga", "mkd", "mmk", "mnt", "mop", "mru",
        "mur", "mvr", "mwk", "mxn", "myr", "mzn", "nad", "ngn", "nio", "nok", "npr", "nzd",
        "omr", "pab", "pen", "pgk", "php", "pkr", "pln", "pyg", "qar", "ron", "rsd", "rub",
        "rwf", "sbd", "scr", "sdg", "sek", "sgd", "shp", "sll", "srd", "ssp", "stn", "svc",
        "syp", "szl", "thb", "tjs", "tmt", "tnd", "ttd", "twd", "tzs", "uah", "ugx", "usd",
        "uyu", "uzs", "ves", "vnd", "vuv", "wst", "xaf", "xcd", "xof", "xpf", "yer", "zar",
        "zmw", "zwl",
    }
)

# Words that turn a figure into a rate. A vocabulary, like the scale words.
_PERCENT_WORDS = frozenset(
    {
        "percent",
        "percentage",
        "pct",
        "\u0628\u0627\u0644\u0645\u0626\u0629",
        "\u0628\u0627\u0644\u0645\u0627\u0626\u0629",
        "\u0627\u0644\u0645\u0626\u0629",
        "\u0627\u0644\u0645\u0627\u0626\u0629",
    }
)

# Magnitude words for the two governed languages. Unlike everything else in
# this module this is a vocabulary rather than a property — see the note in
# `_assert_unmodified` about what that does and does not buy.
_SCALE_WORDS = frozenset(
    {
        "thousand",
        "thousands",
        "million",
        "millions",
        "billion",
        "billions",
        "trillion",
        "trillions",
        "k",
        "m",
        "bn",
        "\u0623\u0644\u0641",
        "\u0627\u0644\u0641",
        "\u0622\u0644\u0627\u0641",
        "\u0645\u0644\u064a\u0648\u0646",
        "\u0645\u0644\u0627\u064a\u064a\u0646",
        "\u0645\u0644\u064a\u0627\u0631",
        "\u0645\u0644\u064a\u0627\u0631\u0627\u062a",
        "\u062a\u0631\u064a\u0644\u064a\u0648\u0646",
    }
)

# Characters that are not digits but carry numeric meaning. Digits themselves
# are handled by asking Unicode, not by listing blocks.
_PUNCTUATION_TABLE: dict[int, str] = {
    # Arabic decimal and thousands separators.
    0x066B: ".",
    0x066C: ",",
    # Every dash a reader would take for a minus. Recognizing only ASCII `-`
    # would let `−500.00` (U+2212) validate as positive `500.00`, which is the
    # sign hole reopened under a different code point. A dash attached to
    # digits is a sign; one standing alone between spaces still is not.
    # U+2212 is the one minus that is a maths symbol rather than dash
    # punctuation, so the category test in `_normalized` does not reach it.
    0x2212: "-",
    # Percent signs, for the same reason: the suffix carries the claim.
    0x066A: "%",
    0xFF05: "%",
}
