"""What a coverage attestation carries over the wire, and how it binds.

`RRA-003` requires completeness to be attested rather than observed:
"Completeness-dependent comparisons require a separate source-provided or
explicitly operator-attested coverage manifest." `khepri.rra.coverage` owns what
makes an attestation usable. This module owns only the translation from a JSON
body into that domain object, so a second surface cannot answer the question
differently.

**Flat over the wire, grouped in the domain**, the same split
`SourceContractBody` makes and for the same two reasons: a JSON body is easier
to post flat, while `coverage` groups a binding, a window, and its exceptions by
what they mean. The grouping exists because those fields travel together by
necessity, and a flat signature in the domain would let a caller supply one and
forget another.

**Days, not pairs.** The domain attests scope-day *pairs*, because a per-store
roster covers each store separately. Asking an operator to enumerate the cross
product would make a two-store fortnight a 28-entry payload whose every entry is
an opportunity to omit one silently. So the wire form takes the days and the
scopes, and the cross product is built here -- which also means a day attested
for one store and forgotten for another is impossible to express rather than
merely unlikely.

**The binding is not the operator's to declare.** `input_digest` and
`source_contract_digest` are absent from this model on purpose. They identify
which bytes, read which way, the attestation is bound to, and both are already
recorded at admission. Letting the body carry them would let an operator attest
coverage against a reading they had not declared -- and, worse, would make the
use-time refusal compare the manifest against a digest from the same payload,
which is a check that cannot fail.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from khepri.rra.coverage import (
    CoverageManifest,
    ManifestBinding,
    ManifestExceptions,
    ManifestWindow,
    build_coverage_manifest,
)


class CoverageManifestBody(BaseModel):
    """One operator-attested coverage manifest, as posted.

    `extra="forbid"` for the reason `SourceContractBody` records: a misspelled
    key in a permissive model is dropped silently, so an operator writing
    `closed_day` would receive the default empty tuple and have a shut day
    attested as ordinary trading. `RRA-003` refuses inference, and a silently
    ignored field is inference by another name.
    """

    model_config = ConfigDict(extra="forbid")

    #: Present so a caller building this model directly is not surprised by a
    #: required field, and ignored by `to_manifest`, which takes the binding
    #: from the admission instead. See the module docstring.
    source_contract_digest: str = ""
    timezone: str
    covered_start: date
    covered_end: date
    aggregate_scope: str | None = None
    store_roster: list[str] = []
    covered_days: list[date] = []
    event_kinds: list[str] = []
    statuses: list[str] = []
    closed_days: list[date] = []
    extraction_gap_days: list[date] = []
    partial_terminal_boundary: bool = False

    def to_manifest(self, *, binding: ManifestBinding) -> CoverageManifest:
        """The governed manifest, or `ManifestRefused` naming what is unusable.

        The binding is supplied by the caller rather than read off this body,
        because it identifies the admission the attestation is bound to and that
        is not the operator's to assert. Every structural rule -- a named scope,
        a window that does not end before it starts, days that span the window
        claimed, no day both closed and a gap -- is `build_coverage_manifest`'s,
        asked here rather than re-implemented.
        """
        return build_coverage_manifest(
            binding=binding,
            window=ManifestWindow(
                covered_start=self.covered_start,
                covered_end=self.covered_end,
                aggregate_scope=self.aggregate_scope,
                store_roster=tuple(self.store_roster),
                covered_pairs=self._pairs(self.covered_days),
            ),
            exceptions=ManifestExceptions(
                event_kinds=tuple(self.event_kinds),
                statuses=tuple(self.statuses),
                closures=self._pairs(self.closed_days),
                extraction_gaps=self._pairs(self.extraction_gap_days),
                partial_terminal_boundary=self.partial_terminal_boundary,
            ),
        )

    def _pairs(self, days: list[date]) -> tuple[tuple[str, date], ...]:
        """Each attested day, for every scope this attestation names.

        A day is attested for the whole of what the manifest covers or for none
        of it. Expanding here rather than on the wire is what makes "attested for
        Cairo and forgotten for Giza" inexpressible.
        """
        return tuple((scope, day) for scope in self._scopes() for day in days)

    def _scopes(self) -> tuple[str, ...]:
        """The scopes attested, mirroring `CoverageManifest.scopes`.

        Deliberately not a refusal when both are empty: that is
        `build_coverage_manifest`'s to refuse, and duplicating the rule here
        would let the two disagree about what an unscoped manifest is.
        """
        if self.aggregate_scope is not None:
            return (self.aggregate_scope,)
        return tuple(self.store_roster)
