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

COVERAGE_MANIFEST_VERSION = "rra003.coverage-manifest.v1"


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


def build_coverage_manifest(
    *,
    input_digest: str,
    source_contract_digest: str,
    timezone: str,
    covered_start: date,
    covered_end: date,
    aggregate_scope: str | None,
    store_roster: tuple[str, ...],
    covered_pairs: tuple[ScopeDay, ...],
    event_kinds: tuple[str, ...],
    statuses: tuple[str, ...],
    closures: tuple[ScopeDay, ...],
    extraction_gaps: tuple[ScopeDay, ...],
    partial_terminal_boundary: bool,
) -> CoverageManifest:
    """One manifest, or a refusal naming what makes it unusable."""
    manifest = CoverageManifest(
        manifest_version=COVERAGE_MANIFEST_VERSION,
        input_digest=input_digest,
        source_contract_digest=source_contract_digest,
        timezone=timezone,
        covered_start=covered_start,
        covered_end=covered_end,
        aggregate_scope=aggregate_scope,
        store_roster=store_roster,
        covered_pairs=frozenset(covered_pairs),
        event_kinds=event_kinds,
        statuses=statuses,
        closures=frozenset(closures),
        extraction_gaps=frozenset(extraction_gaps),
        partial_terminal_boundary=partial_terminal_boundary,
    )
    _assert_usable(manifest)
    return manifest


def _assert_usable(manifest: CoverageManifest) -> None:
    """Every structural defect that makes a manifest prove nothing."""
    if not manifest.scopes:
        raise ManifestRefused(
            "A coverage manifest must name one aggregate scope or a store roster."
        )
    if manifest.covered_end < manifest.covered_start:
        raise ManifestRefused("A coverage manifest ends before it starts.")
    contradictory = manifest.closures & manifest.extraction_gaps
    if contradictory:
        raise ManifestRefused(
            "A day cannot be both an attested closure and an extraction gap."
        )
    _assert_spans_its_own_window(manifest)


def _assert_spans_its_own_window(manifest: CoverageManifest) -> None:
    """Covered pairs must reach every scope-day the manifest claims."""
    for scope in manifest.scopes:
        for day in _days(manifest.covered_start, manifest.covered_end):
            if (scope, day) not in manifest.covered_pairs:
                raise ManifestRefused(
                    "A coverage manifest omits a day inside its own window."
                )


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def admits_completeness(
    manifest: CoverageManifest,
    *,
    input_digest: str,
    source_contract_digest: str,
    scope: str,
    start: date,
    end: date,
) -> bool:
    """Whether this manifest proves this window completely covered.

    Fail-closed: every condition must hold, and an unrecognised scope or an
    unattested day is a refusal rather than an absence of evidence.
    """
    if manifest.input_digest != input_digest:
        return False
    if manifest.source_contract_digest != source_contract_digest:
        return False
    if manifest.partial_terminal_boundary:
        return False
    if scope not in manifest.scopes:
        return False
    return _every_day_proven(manifest, scope=scope, start=start, end=end)


def _every_day_proven(
    manifest: CoverageManifest,
    *,
    scope: str,
    start: date,
    end: date,
) -> bool:
    """Each day attested and none of them a gap.

    A closure is deliberately not consulted here: it is already a covered pair,
    and it proves zero activity rather than missing activity.
    """
    for day in _days(start, end):
        if (scope, day) not in manifest.covered_pairs:
            return False
        if (scope, day) in manifest.extraction_gaps:
            return False
    return True
