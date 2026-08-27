"""What a package proves about the calendar it covered, without the calendar.

`RRA-004`'s "Structural coverage signatures and aligned daily bases" requires a
deterministic structural signature over the coverage-manifest identity and
input binding, the scope identity, the event-kind and status filters, the
coverage mode, and "relative covered calendar-day ordinals" -- and requires it
to exclude "absolute calendar dates and all revenue, unit, and other measure
values".

**Why relative ordinals, and why this is not a detail.** Two months of identical
shape -- fully covered, same scope, same filters -- must produce the same
signature so `RRA-008` can ask whether they are structurally comparable. Absolute
dates would make every month's signature unique and the question unanswerable.
Measure values would make the signature a function of the data, so a quiet month
and a busy one of the same shape would look structurally different.

**Derived from the attestation, never from the rows.** Every field here comes
from the `CoverageManifest`. `RRA-004` says the observed evidence -- "observed
day counts, distinct-date counts, date bounds, equal row counts, and generated
date spines" -- "are evidence but are not coverage-manifest completeness proof",
and `RRA-003` refuses coverage inferred from observed values. A signature that
read the frame would be exactly that inference, and it would pass any test that
only checked determinism, because reading the data is perfectly deterministic.

**The identity proves structure, not comparability.** `RRA-004`: "Its identity
proves the recorded structure; cross-window comparability follows the
field-level compatibility rules in `RRA-008`, not raw signature equality." So
this module answers "what shape was attested here", and never "may these two be
compared".
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date

from khepri.rra.coverage import CoverageManifest
from khepri.rra.profiling import canonical_json

#: A window the manifest attests from its first covered day, with no gap.
COVERAGE_MODE_FULL_CALENDAR = "full_calendar"
#: A contiguous run of days `1..k` from the window's start, which `RRA-004`
#: admits for partial-window alignment.
COVERAGE_MODE_PREFIX = "contiguous_day_one_prefix"


class SignatureRefused(ValueError):
    """A structure that cannot be recorded as attested."""


@dataclass(frozen=True, slots=True)
class CoverageSignature:
    """One window's attested structure, with no date and no measure in it."""

    manifest_version: str
    manifest_input_digest: str
    source_contract_digest: str
    scope: str
    event_kinds: tuple[str, ...]
    statuses: tuple[str, ...]
    mode: str
    #: 1-based day numbers relative to the window's own first day. Day 1 is the
    #: start of *this* window, not of the manifest, so a projection over a later
    #: prefix and the parent it came from stay distinguishable.
    covered_ordinals: tuple[int, ...]
    #: The window's length in days, so a fully covered short month and a
    #: half-covered long one cannot collide on ordinals alone.
    window_days: int

    def as_document(self) -> dict[str, object]:
        return {
            "manifest_version": self.manifest_version,
            "manifest_input_digest": self.manifest_input_digest,
            "source_contract_digest": self.source_contract_digest,
            "scope": self.scope,
            "event_kinds": sorted(self.event_kinds),
            "statuses": sorted(self.statuses),
            "mode": self.mode,
            "covered_ordinals": list(self.covered_ordinals),
            "window_days": self.window_days,
            "identity": self.identity,
        }

    @property
    def identity(self) -> str:
        """The stable identity of this structure.

        `identity` is deliberately absent from the digested payload: including a
        field derived from the payload would be self-referential, and the
        document carries it only so a stored signature can be read back without
        recomputation.
        """
        return hashlib.sha256(
            canonical_json(
                {
                    "manifest_version": self.manifest_version,
                    "manifest_input_digest": self.manifest_input_digest,
                    "source_contract_digest": self.source_contract_digest,
                    "scope": self.scope,
                    "event_kinds": sorted(self.event_kinds),
                    "statuses": sorted(self.statuses),
                    "mode": self.mode,
                    "covered_ordinals": list(self.covered_ordinals),
                    "window_days": self.window_days,
                }
            ).encode()
        ).hexdigest()


def build_coverage_signature(
    manifest: CoverageManifest,
    *,
    scope: str,
    start: date,
    end: date,
) -> CoverageSignature:
    """The attested structure of one window, or a refusal naming what is unproven.

    Every day in the window is looked up in the manifest's `covered_pairs`, so a
    day the operator did not attest is simply absent from the ordinals rather
    than being inferred present. An extraction gap is likewise absent: `RRA-003`
    separates a gap, whose size is unknown, from an attested closure, which
    proves complete zero activity and is therefore covered.
    """
    if end < start:
        raise SignatureRefused("A coverage signature cannot end before it starts.")
    if scope not in manifest.scopes:
        raise SignatureRefused(
            f"The coverage manifest attests nothing for scope {scope!r}."
        )
    span = (end - start).days + 1
    ordinals = tuple(
        ordinal
        for ordinal in range(1, span + 1)
        for day in ((start.toordinal() + ordinal - 1),)
        if (scope, date.fromordinal(day)) in manifest.covered_pairs
        and (scope, date.fromordinal(day)) not in manifest.extraction_gaps
    )
    if not ordinals:
        raise SignatureRefused(
            "The coverage manifest proves no day of this window covered."
        )
    return CoverageSignature(
        manifest_version=manifest.manifest_version,
        manifest_input_digest=manifest.input_digest,
        source_contract_digest=manifest.source_contract_digest,
        scope=scope,
        event_kinds=tuple(manifest.event_kinds),
        statuses=tuple(manifest.statuses),
        mode=_mode_of(ordinals, span),
        covered_ordinals=ordinals,
        window_days=span,
    )


def _mode_of(ordinals: tuple[int, ...], span: int) -> str:
    """Whether this is a whole window or a contiguous prefix of one.

    Anything else -- a gap in the middle, a run that starts late -- is neither,
    and `RRA-004` admits only these two for alignment. Recording it as a prefix
    anyway would let a window missing its middle be compared against a complete
    one of the same length.
    """
    contiguous_from_one = ordinals == tuple(range(1, len(ordinals) + 1))
    if contiguous_from_one and len(ordinals) == span:
        return COVERAGE_MODE_FULL_CALENDAR
    if contiguous_from_one:
        return COVERAGE_MODE_PREFIX
    raise SignatureRefused(
        "A coverage signature records a whole window or a contiguous prefix of "
        "one; this window is covered in neither shape."
    )


def project_prefix(parent: CoverageSignature, *, days: int) -> CoverageSignature:
    """The days `1..k` prefix of a complete signature, per `RRA-004`.

    A projection "preserves the parent signature and basis identities, input and
    manifest bindings, governed aggregate scope or complete store set, and
    event-kind and status filters in provenance", and "never infers missing
    coverage, synthesizes an unproven day, or changes a parent measure value".
    So every field but the mode, the ordinals and the length is carried over
    unchanged, and the ordinals are a subset of the parent's rather than a
    freshly generated range.
    """
    if days < 1:
        raise SignatureRefused("A projection covers at least its first day.")
    if parent.mode != COVERAGE_MODE_FULL_CALENDAR:
        raise SignatureRefused(
            "Only a complete full-calendar signature may be projected; a "
            "projection of a prefix would compound an unproven boundary."
        )
    if days > parent.window_days:
        raise SignatureRefused(
            "A projection cannot cover more days than its parent attested."
        )
    kept = tuple(ordinal for ordinal in parent.covered_ordinals if ordinal <= days)
    if len(kept) != days:
        raise SignatureRefused(
            "The parent signature does not prove every day of this projection."
        )
    return CoverageSignature(
        manifest_version=parent.manifest_version,
        manifest_input_digest=parent.manifest_input_digest,
        source_contract_digest=parent.source_contract_digest,
        scope=parent.scope,
        event_kinds=parent.event_kinds,
        statuses=parent.statuses,
        mode=COVERAGE_MODE_PREFIX,
        covered_ordinals=kept,
        window_days=days,
    )
