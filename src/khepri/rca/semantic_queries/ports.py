"""The `RRA-014` seam, declared by the consumer (`SV1-04`; `RCA-006` §Request flow).

`RCA-006`: "The future RCA implementation calls an injected protocol and does not
import a concrete RRA implementation, following `rca/workspace/comparisons.py`'s
`ComparisonAssembly` precedent." This module is that protocol and the value types
it speaks in.

**The consumer owns the Protocol; the composition root binds the implementation.**
That direction is what keeps `khepri.rca` free of `khepri.rra`, which `FR-150`
requires be independently tested. `ComparisonAssembly` established it and
`comparison_assembly.py` is the shape of the binding half.

The types here were pinned by the `SV1` allocation plan §2 before `SV1-02`
published anything, because the protocol's shape constrains a definition's
`output_field_order` and `request_filter_allowlist`, and `FR-134` makes a later
reshape a new view version rather than an edit.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

__all__ = [
    "KIND_ADMITTED",
    "KIND_REFUSED",
    "KIND_UNAVAILABLE",
    "EffectiveRequest",
    "SemanticViewPort",
    "SemanticViewRequest",
    "ViewOutcome",
    "ViewProjection",
    "ViewRefusal",
]

#: The three outcome kinds, `ComparisonOutcome`'s own. An admitted projection, a
#: governed view refusal, or the uniform content-free miss `FR-146` requires.
KIND_ADMITTED = "admitted"
KIND_REFUSED = "refused"
KIND_UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SemanticViewRequest:
    """The explicit request: exact identity, explicit selection, explicit filters.

    `FR-143` -- the version is named exactly and there is no `latest`, so it is
    never defaulted. `FR-137` -- every requested filter is named here, so the
    result can state it back.

    `metrics` is here because `FR-141` names *unknown metric* as a refusal cause:
    a request that cannot name a metric could never name an unknown one, and the
    cause would be declared, worded, and unreachable. `SV1-03` found that while
    building the validator and the allocation plan records the amendment.

    `filters` is an ordered tuple of pairs, never a mapping: `FR-137` requires
    every effective filter be visible in request *and* result, and a mapping's
    iteration order is an implementation detail rather than a published one.
    """

    view_id: str
    view_version: str
    metrics: tuple[str, ...] = ()
    dimensions: tuple[str, ...] = ()
    filters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class EffectiveRequest:
    """`FR-137` -- what actually applied, requested and definition-fixed alike."""

    dimensions: tuple[str, ...] = ()
    requested_filters: tuple[tuple[str, str], ...] = ()
    fixed_filters: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class ViewRefusal:
    """`FR-141` -- a stable contract refusal with bilingual wording, no partial result.

    Wording is carried as ordered pairs and read back as a mapping. `frozen=True`
    freezes the reference, not the referent: while this was a `dict` field a
    caller could rewrite the wording of a refusal already returned, and two
    refusals built from one mapping shared it, so mutating either changed both.

    Pairs rather than a `MappingProxyType` assigned in `__post_init__`, because
    that assignment needs `object.__setattr__`, which `RCA-001`'s forgery scan
    bars from every production module. §2 already reached for pairs over a
    mapping on `filters`, for the neighbouring reason.
    """

    cause: str
    wording_pairs: tuple[tuple[str, str], ...] = ()

    @property
    def wording(self) -> dict[str, str]:
        """Both governed languages, as a fresh mapping the caller may keep."""
        return dict(self.wording_pairs)


@dataclass(frozen=True, slots=True)
class ViewProjection:
    """`FR-139`/`FR-140` -- projected values plus everything that must survive."""

    view_id: str
    view_version: str
    fields: tuple[str, ...] = ()
    rows: tuple[tuple[object, ...], ...] = ()
    version_pairs: tuple[tuple[str, str], ...] = ()
    caveats: tuple[object, ...] = ()
    population_qualifiers: tuple[object, ...] = ()
    evidence: tuple[object, ...] = ()
    evidence_absences: tuple[str, ...] = ()
    is_empty: bool = False

    @property
    def versions(self) -> dict[str, str]:
        """Mapping, package, formula, family, bundle and view versions.

        Pairs behind a mapping for `ViewRefusal.wording`'s reason. `FR-139`
        requires these equal the source records; a projection whose versions a
        caller could edit after the fact could not carry that guarantee.
        """
        return dict(self.version_pairs)


@dataclass(frozen=True, slots=True)
class ViewOutcome:
    """Admitted, refused, or the uniform isolation miss -- `ComparisonOutcome`'s shape."""

    kind: str
    refusal: ViewRefusal | None = None
    projection: ViewProjection | None = None
    effective: EffectiveRequest | None = None

    @property
    def admitted(self) -> bool:
        """A projection the reader may see."""
        return self.kind == KIND_ADMITTED

    @property
    def refused(self) -> bool:
        """A governed view refusal (`FR-141`), carrying no partial result."""
        return self.kind == KIND_REFUSED

    @property
    def unavailable(self) -> bool:
        """The uniform content-free miss (`FR-146`), naming no condition."""
        return self.kind == KIND_UNAVAILABLE


class SemanticViewPort(Protocol):
    """The RRA half, injected so `khepri.rca` never imports `khepri.rra`.

    `sources` is `tuple[object, ...]` deliberately. `RCA-006` §Exclusions bars
    this package from importing a concrete RRA implementation, and the admitted
    source shape is an `RRA-014`-side type; the RCA side passes what it scoped
    and the RRA side validates the shape (`FR-136`) and refuses an incompatible
    one. `ComparisonOutcome.bundle` uses the same `object` for the same reason.

    `None` is part of the contract, not an escape from it: it says the RRA half
    could not read these sources at all, which is `FR-146`'s *corrupt* condition.
    The RCA half maps it to the one uniform unavailable outcome, so that outcome
    is built in exactly one place and cannot drift from the absent, deleted and
    cross-scope answers. Annotating it here is what lets an implementation say so
    without a type suppression.

    One `project` call, not a validate-then-project pair. `FR-137` and `FR-141`
    require refusal *before* projection, which is a guarantee about the callee's
    internal order rather than about the number of calls; two calls would let a
    caller skip validation.
    """

    def project(
        self, request: SemanticViewRequest, sources: tuple[object, ...]
    ) -> ViewOutcome | None:
        """Validate and project, or answer `None` when the sources cannot be read."""
        ...
