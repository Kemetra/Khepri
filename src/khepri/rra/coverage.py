"""The separate proof that a period was completely covered.

`RRA-003` refuses to let a comparison infer completeness from the data it is
comparing: a date spine, an observed minimum or maximum date, equal row or day
counts, and the absence of events "never synthesize coverage proof". Each is
equally consistent with a period that was genuinely quiet and one whose extract
stopped early, and nothing in the bytes distinguishes them. Completeness is
therefore an attestation carried alongside the data, never a property read out
of it.

**Two bindings, because bytes alone do not identify an admission.**

The input digest binds a manifest to one file. The source-contract digest binds
it to one *reading* of that file, and `RRA-003` names it separately for a
reason worth keeping visible: identical bytes re-uploaded under a corrected
semantic contract would otherwise match an old manifest whose event-kind and
status coverage was attested against different semantics. The bytes did not
change; what they were declared to mean did, and the old attestation says
nothing about the new declaration.

**A closure is not a gap.** An attested closure proves complete zero activity --
the shop was shut and zero is the true answer, so the day is covered. An
extraction gap proves the opposite: something is missing and its size is
unknown. Treating them alike in either direction is wrong, so they are separate
fields and separate rules.

**Refused at construction where the defect is structural.** A manifest that
names no scope, or whose covered pairs do not span the window it claims, is
unusable no matter who reads it later. Refusing at build time keeps it from
being persisted and then discovered at comparison time, when the useful context
is gone.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

COVERAGE_MANIFEST_VERSION = "rra003.coverage-manifest.v1"

#: Every manifest version this build knows how to interpret. Checked at *use*
#: rather than only at construction, because `manifest_from_document` reads a
#: stored document back verbatim -- deliberately, so a rebuild reproduces what
#: was written -- and therefore carries whatever version that document recorded.
#: A stamp nothing verifies is not evidence, and `RRA-003` requires the
#: attestation to be versioned.
RECOGNISED_MANIFEST_VERSIONS: frozenset[str] = frozenset({COVERAGE_MANIFEST_VERSION})

#: What a manifest stored before `attested_by` existed reads back as.
#:
#: The field was added to the shape without moving `COVERAGE_MANIFEST_VERSION`,
#: so old and new documents share `rra003.coverage-manifest.v1` and a direct
#: lookup raised `KeyError` for every previously stored attested profile --
#: failing package rebuild and every coverage check that read one.
#:
#: A distinct marker rather than a plausible attester name: an attestation that
#: recorded no attribution has none, and inventing one would make it
#: indistinguishable from a manifest that named its source. `_assert_bound`
#: still refuses a *blank* attester, so this cannot become a way to accept a new
#: manifest with nothing recorded -- readback is not admission.
UNRECORDED_ATTESTER = "attribution not recorded"


#: A scope-day pair is exactly a scope and a day. Named so the read-back refusal
#: of a malformed stored pair reads as a width check rather than a bare `2`.
_SCOPE_DAY_WIDTH = 2


class ManifestRefused(ValueError):
    """A manifest that cannot prove anything, refused before it is stored."""


ScopeDay = tuple[str, date]


@dataclass(frozen=True, slots=True)
class CoverageManifest:
    """One attestation of what a file completely covers.

    Immutable, and every field `RRA-003` enumerates is present rather than
    optional-with-a-default, so a manifest missing an attestation is a
    construction error instead of a silently permissive read.
    """

    manifest_version: str
    input_digest: str
    source_contract_digest: str
    #: Who attested this coverage claim and on what basis. `RRA-003` records
    #: "the source-contract or attestation identity and its evidence" among a
    #: manifest's fields, and `source_contract_digest` is not it: that identifies
    #: the *reading* the attestation was made under, while this attributes the
    #: coverage claim itself. An attested closure is a statement somebody made,
    #: and one nobody signed cannot be weighed when it is later relied on.
    attested_by: str
    timezone: str
    covered_start: date
    covered_end: date
    aggregate_scope: str | None
    store_roster: tuple[str, ...]
    covered_pairs: frozenset[ScopeDay]
    event_kinds: tuple[str, ...]
    statuses: tuple[str, ...]
    closures: frozenset[ScopeDay]
    extraction_gaps: frozenset[ScopeDay]
    partial_terminal_boundary: bool

    @property
    def scopes(self) -> frozenset[str]:
        """Every scope this manifest attested, aggregate or per-store."""
        if self.aggregate_scope is not None:
            return frozenset({self.aggregate_scope})
        return frozenset(self.store_roster)

    def as_document(self) -> dict[str, object]:
        """The canonical shape a stored profile records this attestation in.

        **Every collection is sorted, and that is load-bearing rather than
        tidy.** Three fields are `frozenset`, whose iteration order is not
        stable across processes, and this document is nested inside the profile
        document whose digest addresses it. Emitting a set in iteration order
        would give one attestation several digests, so `packages` would refuse a
        fact package it had itself just published, at random.

        The remaining collections -- `store_roster`, `event_kinds`, `statuses`
        -- are semantically unordered too, so they are sorted here for the same
        reason rather than emitted in posted order: two attestations naming the
        same stores or filters in a different sequence must digest identically,
        or `_assert_same_attestation` treats an equivalent re-post as a
        conflict.

        `canonical_json` sorts keys and cannot help here: it never reorders the
        values inside a list.
        """
        return {
            "manifest_version": self.manifest_version,
            "input_digest": self.input_digest,
            "source_contract_digest": self.source_contract_digest,
            # Absence serializes as absence. A document stored before this field
            # existed reads back as `UNRECORDED_ATTESTER`, and `_readmit`
            # re-serializes the manifest to compare the stored profile digest --
            # so emitting the key here would make every legacy profile digest
            # differently and refuse its package. The manifest version does not
            # move for this: an unattributed document is the same document, not
            # a new shape.
            **(
                {}
                if self.attested_by == UNRECORDED_ATTESTER
                else {"attested_by": self.attested_by}
            ),
            "timezone": self.timezone,
            "covered_start": self.covered_start.isoformat(),
            "covered_end": self.covered_end.isoformat(),
            "aggregate_scope": self.aggregate_scope,
            "store_roster": sorted(self.store_roster),
            "covered_pairs": _pairs_as_document(self.covered_pairs),
            "event_kinds": sorted(self.event_kinds),
            "statuses": sorted(self.statuses),
            "closures": _pairs_as_document(self.closures),
            "extraction_gaps": _pairs_as_document(self.extraction_gaps),
            "partial_terminal_boundary": self.partial_terminal_boundary,
        }


def _pairs_as_document(pairs: frozenset[ScopeDay]) -> list[list[str]]:
    """Scope-day pairs in one stable order, as JSON-native values."""
    return [
        [scope, day.isoformat()]
        for scope, day in sorted(pairs, key=lambda pair: (pair[0], pair[1]))
    ]


def manifest_from_document(document: dict[str, object]) -> CoverageManifest:
    """The attestation a stored profile recorded, read back verbatim.

    **Read, not re-admitted**, for the reason `contract_from_document` records
    about the contract beside it: `packages` re-derives the stored profile
    document and compares its digest, so this read has to reproduce exactly what
    was written. Re-validating the attestation here would refuse a stored
    manifest whose construction rules have since tightened, rather than
    reporting the digest mismatch the rebuild exists to report.

    The attestation was validated when it was accepted. What is checked at
    rebuild time is the digest, and what is checked at *use* time is the
    binding -- `admits_completeness`, which is not this function.
    """
    return CoverageManifest(
        manifest_version=str(document["manifest_version"]),
        input_digest=str(document["input_digest"]),
        source_contract_digest=str(document["source_contract_digest"]),
        attested_by=str(document.get("attested_by") or UNRECORDED_ATTESTER),
        timezone=str(document["timezone"]),
        covered_start=date.fromisoformat(str(document["covered_start"])),
        covered_end=date.fromisoformat(str(document["covered_end"])),
        aggregate_scope=_optional_scope(document["aggregate_scope"]),
        store_roster=tuple(str(store) for store in _sequence(document, "store_roster")),
        covered_pairs=_pairs_from_document(document, "covered_pairs"),
        event_kinds=tuple(str(kind) for kind in _sequence(document, "event_kinds")),
        statuses=tuple(str(status) for status in _sequence(document, "statuses")),
        closures=_pairs_from_document(document, "closures"),
        extraction_gaps=_pairs_from_document(document, "extraction_gaps"),
        partial_terminal_boundary=bool(document["partial_terminal_boundary"]),
    )


def _optional_scope(value: object) -> str | None:
    return None if value is None else str(value)


def _sequence(document: dict[str, object], key: str) -> list[object]:
    section = document[key]
    if not isinstance(section, list):
        raise ManifestRefused(f"A stored coverage manifest has a malformed {key}.")
    return section


def _pairs_from_document(
    document: dict[str, object],
    key: str,
) -> frozenset[ScopeDay]:
    """Scope-day pairs read back, refusing a shape that is not a pair."""
    pairs: set[ScopeDay] = set()
    for entry in _sequence(document, key):
        if not isinstance(entry, list | tuple) or len(entry) != _SCOPE_DAY_WIDTH:
            raise ManifestRefused(f"A stored coverage manifest has a malformed {key}.")
        scope, day = entry
        pairs.add((str(scope), date.fromisoformat(str(day))))
    return frozenset(pairs)


@dataclass(frozen=True, slots=True)
class ManifestBinding:
    """What a manifest is bound to: one file, read one way, in one timezone.

    Grouped rather than passed flat because these travel together by necessity.
    A digest without the contract it was attested under is exactly the reuse
    `RRA-003` names the source contract to prevent, so a signature that let a
    caller supply one and forget the other would invite the defect back.
    """

    input_digest: str
    source_contract_digest: str
    timezone: str
    #: Defaulted so the many fixtures that build a binding for a reason
    #: unrelated to attribution keep reading as one call. A blank value is
    #: refused by `_assert_bound`, so the default cannot become a way to skip
    #: the attestation -- it only keeps the required value out of call sites
    #: that have nothing to say about it.
    attested_by: str = "operator attestation"


@dataclass(frozen=True, slots=True)
class ManifestWindow:
    """What a manifest attests: a span, over scopes, day by day."""

    covered_start: date
    covered_end: date
    aggregate_scope: str | None
    store_roster: tuple[str, ...]
    covered_pairs: tuple[ScopeDay, ...]


@dataclass(frozen=True, slots=True)
class ManifestExceptions:
    """The days that are not ordinary, and what kind of not-ordinary they are.

    Closures and gaps are opposite claims about a day with no events, so they
    are grouped where the contrast is visible rather than separated by unrelated
    parameters.
    """

    event_kinds: tuple[str, ...]
    statuses: tuple[str, ...]
    closures: tuple[ScopeDay, ...] = ()
    extraction_gaps: tuple[ScopeDay, ...] = ()
    partial_terminal_boundary: bool = False


def build_coverage_manifest(
    *,
    binding: ManifestBinding,
    window: ManifestWindow,
    exceptions: ManifestExceptions,
) -> CoverageManifest:
    """One manifest, or a refusal naming what makes it unusable."""
    manifest = CoverageManifest(
        manifest_version=COVERAGE_MANIFEST_VERSION,
        input_digest=binding.input_digest,
        source_contract_digest=binding.source_contract_digest,
        attested_by=binding.attested_by,
        timezone=binding.timezone,
        covered_start=window.covered_start,
        covered_end=window.covered_end,
        aggregate_scope=window.aggregate_scope,
        store_roster=window.store_roster,
        covered_pairs=frozenset(window.covered_pairs),
        event_kinds=exceptions.event_kinds,
        statuses=exceptions.statuses,
        closures=frozenset(exceptions.closures),
        extraction_gaps=frozenset(exceptions.extraction_gaps),
        partial_terminal_boundary=exceptions.partial_terminal_boundary,
    )
    _assert_usable(manifest)
    return manifest


def _assert_usable(manifest: CoverageManifest) -> None:
    """Every structural defect that makes a manifest prove nothing."""
    _assert_one_scope_mode(manifest)
    if manifest.covered_end < manifest.covered_start:
        raise ManifestRefused("A coverage manifest ends before it starts.")
    _assert_valid_timezone(manifest)
    if not manifest.event_kinds or not manifest.statuses:
        raise ManifestRefused(
            "A coverage manifest must record its included event kinds and statuses."
        )
    contradictory = manifest.closures & manifest.extraction_gaps
    if contradictory:
        raise ManifestRefused(
            "A day cannot be both an attested closure and an extraction gap."
        )
    _assert_spans_its_own_window(manifest)
    _assert_pairs_within_window(manifest)


def assert_bound(manifest: CoverageManifest) -> None:
    """Both bindings present and attributed, for a manifest about to be relied on.

    **Deliberately not part of `_assert_usable`.** That function answers the
    *structural* questions -- a named scope, a window that does not end before it
    starts, no day both shut and missing -- and `profile_request._unbound` asks
    exactly those against placeholder digests, because the real ones are not
    known until the upload has been read. Folding a binding rule into it would
    refuse every posted manifest before its digests could exist, turning a
    validation-phase distinction the request path depends on into a 400.

    So this is the *storage and use* phase: called where a manifest is built
    against the real binding. `admits_completeness` proves that binding by
    comparing these digests against the query's, and two empty strings satisfy
    that comparison -- so a manifest bound to nothing would admit every file and
    every reading, the exact reuse `RRA-003` names the input digest and the
    source contract to prevent.
    """
    if not manifest.input_digest.strip():
        raise ManifestRefused(
            "A coverage manifest must be bound to the digest of the input it covers."
        )
    if not manifest.source_contract_digest.strip():
        raise ManifestRefused(
            "A coverage manifest must be bound to the source contract it was "
            "attested under."
        )
    if not manifest.attested_by.strip():
        raise ManifestRefused(
            "A coverage manifest must record who attested it."
        )
    if manifest.attested_by.strip() == UNRECORDED_ATTESTER:
        # The sentinel is what *absence* reads back as, and `as_document()`
        # re-emits it as absence. Left admissible here, a caller could submit
        # the literal string and have a manifest attested now persist as one
        # written before attribution existed -- forging the very provenance gap
        # `UNRECORDED_ATTESTER` exists to mark. It is a read-back value, never
        # an attestation, so it is refused where attestations are stored.
        raise ManifestRefused(
            "A coverage manifest must record a real attester, not the marker "
            "reserved for documents stored before attribution."
        )


def _assert_one_scope_mode(manifest: CoverageManifest) -> None:
    """Exactly one scope mode, and every identity in it nonblank.

    `RRA-003` treats an aggregate scope and a per-store roster as alternatives.
    Accepting both would let `CoverageManifest.scopes` silently prefer the
    aggregate and discard the roster, and a blank identity in either would let
    an empty string stand in for a scope nothing attested.
    """
    if manifest.aggregate_scope is not None and manifest.store_roster:
        raise ManifestRefused(
            "A coverage manifest must name an aggregate scope or a store roster, "
            "not both."
        )
    if not manifest.scopes:
        raise ManifestRefused(
            "A coverage manifest must name one aggregate scope or a store roster."
        )
    if any(not scope for scope in manifest.scopes):
        raise ManifestRefused("A coverage manifest scope identity may not be blank.")


def _assert_valid_timezone(manifest: CoverageManifest) -> None:
    """The reporting timezone must be a real zone, not merely a nonempty string.

    A day boundary attested under a timezone that does not exist proves nothing
    about when a day began or ended -- the exact gap `RRA-003` requires the
    timezone to close.
    """
    try:
        ZoneInfo(manifest.timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ManifestRefused(
            f"A coverage manifest names an unrecognised timezone: {manifest.timezone!r}."
        ) from error


def _assert_spans_its_own_window(manifest: CoverageManifest) -> None:
    """Covered pairs must reach every scope-day the manifest claims."""
    for scope in manifest.scopes:
        for day in _days(manifest.covered_start, manifest.covered_end):
            if (scope, day) not in manifest.covered_pairs:
                raise ManifestRefused(
                    "A coverage manifest omits a day inside its own window."
                )


def _assert_pairs_within_window(manifest: CoverageManifest) -> None:
    """No covered pair may fall outside the window the manifest declares.

    `_assert_spans_its_own_window` proves the window is a subset of what is
    covered; this proves the reverse. Without it, a manifest could attest a day
    beyond `covered_end` and have that extra pair alone satisfy a completeness
    query for a window the operator never declared.
    """
    window_days = frozenset(_days(manifest.covered_start, manifest.covered_end))
    for _scope, day in manifest.covered_pairs:
        if day not in window_days:
            raise ManifestRefused(
                "A coverage manifest attests a day outside its declared window."
            )


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


@dataclass(frozen=True, slots=True)
class CompletenessQuery:
    """One window, asked about under one binding."""

    input_digest: str
    source_contract_digest: str
    scope: str
    start: date
    end: date


def admits_completeness(
    manifest: CoverageManifest,
    query: CompletenessQuery,
) -> bool:
    """Whether this manifest proves this window completely covered.

    Fail-closed: every condition must hold, and an unrecognised scope or an
    unattested day is a refusal rather than an absence of evidence.

    **An inverted window is refused outright, never proven vacuously.** With
    `end < start`, `_days` returns no dates, and a check that every day in an
    empty list is attested and gap-free is true of every manifest -- proving
    nothing about a window nobody attested. So the shape is refused before it
    reaches that check.
    """
    if query.end < query.start:
        return False
    if manifest.manifest_version not in RECOGNISED_MANIFEST_VERSIONS:
        return False
    if manifest.input_digest != query.input_digest:
        return False
    if manifest.source_contract_digest != query.source_contract_digest:
        return False
    if _boundary_cuts_the_window(manifest, query):
        return False
    if query.scope not in manifest.scopes:
        return False
    return _every_day_proven(manifest, query)


def _boundary_cuts_the_window(
    manifest: CoverageManifest,
    query: CompletenessQuery,
) -> bool:
    """Whether a declared partial terminal boundary falls inside this window.

    `RRA-003` lists the boundary among the *known exceptions* a manifest records,
    beside closures and extraction gaps, and those refuse the days they touch
    rather than the whole attestation. The boundary is by construction at the end
    of the covered window -- the extract stopped part-way through that final
    period -- so a query ending before `covered_end` is not cut by it.

    Refusing every window instead would state a gap where the operator attested
    none, discarding completeness proof that was actually given. That is the
    same over-refusal the inverted-window check above avoids in the other
    direction.
    """
    if not manifest.partial_terminal_boundary:
        return False
    return query.end >= manifest.covered_end


def _every_day_proven(manifest: CoverageManifest, query: CompletenessQuery) -> bool:
    """Each day attested and none of them a gap.

    A closure is deliberately not consulted here: it is already a covered pair,
    and it proves zero activity rather than missing activity.
    """
    for day in _days(query.start, query.end):
        if (query.scope, day) not in manifest.covered_pairs:
            return False
        if (query.scope, day) in manifest.extraction_gaps:
            return False
    return True
