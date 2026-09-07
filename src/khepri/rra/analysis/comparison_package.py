"""The two-population fact `rra008.crossversion.v1` states, with its composite provenance.

`RRA-008` §Composite provenance requires four disclosures the four
single-population families do not need -- both versions' identifiers, both cited
retained bases, both coverage-manifest identities, and the operand order -- and
**declines to say how they are carried**: `Fact.inputs` "keeps its existing
meaning and is not repurposed" and the `RRA-004` `Fact` type "is not modified",
so the carrier belongs to the slice that first serializes these facts.

**The repository had already answered it.** `FactComparison` is a *sibling* of
`Fact` rather than a modification of it: it repeats the identity and unit fields,
composes a value object, and merges that object's document with
`**self.comparison.as_document(...)`. `CrossVersionFact` is the same shape with
`PairProvenance` as the composed value. So no `Fact` field is added, `Fact.inputs`
keeps its meaning, and this module invents no third convention.

**Operand order is part of fact identity**, and the mechanism is the governed
helper rather than a new one. `fact_identity` hashes `scope` as an ordered list,
so passing `(subject_version_id, baseline_version_id)` makes the reversed pair a
different fact with a different identifier -- which is what §Composite provenance
requires, and why the pair is never stored as a set nor sorted on the way in.

**The version is its own.** `rra008.crossversion.v1`, not
`COMPARISON_FORMULA_VERSION`: `#400` froze these as different derivations
answering different questions, and a fact that cannot say which produced it is
not provenance. It is both *hashed into* identity and *recorded on* the fact --
the distinction `comparison.py` drew and `#402`'s item-20 note carries forward,
because hashing names a fact and cannot be read back off one.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from khepri.rra.facts import fact_identity

__all__ = [
    "COMPARISON_CROSSVERSION_VERSION",
    "CrossVersionFact",
    "MeasuredPair",
    "PairProvenance",
    "build_cross_version_fact",
]

#: `RRA-008` §Stable contract and versions: new, succeeding nothing, and *not* a
#: successor to `rra008.comparison.v2`, which continues to govern period
#: comparison within one population.
COMPARISON_CROSSVERSION_VERSION = "rra008.crossversion.v1"

#: §Composite provenance discloses the order "such that subject and baseline are
#: distinguishable and not merely a set". Recorded literally so a reader of one
#: serialized fact needs no convention to interpret its two halves.
OPERAND_ORDER: tuple[str, ...] = ("subject", "baseline")


@dataclass(frozen=True, slots=True)
class PairProvenance:
    """Which two populations a cross-version fact compared, and in which order.

    Six fields rather than two nested triples: `RRA-004`'s provenance documents
    are flat, and a nested shape would make `as_document` disagree with every
    sibling in `facts.py`.
    """

    subject_version_id: str
    subject_basis_id: str
    subject_manifest_id: str
    baseline_version_id: str
    baseline_basis_id: str
    baseline_manifest_id: str

    @property
    def scope(self) -> tuple[str, str]:
        """The ordered pair `fact_identity` hashes, subject first."""
        return (self.subject_version_id, self.baseline_version_id)

    def as_document(self) -> dict[str, object]:
        return {
            "subject_version_id": self.subject_version_id,
            "subject_basis_id": self.subject_basis_id,
            "subject_manifest_id": self.subject_manifest_id,
            "baseline_version_id": self.baseline_version_id,
            "baseline_basis_id": self.baseline_basis_id,
            "baseline_manifest_id": self.baseline_manifest_id,
            "operand_order": list(OPERAND_ORDER),
        }


@dataclass(frozen=True, slots=True)
class CrossVersionFact:
    """One governed number comparing two dataset versions, and what produced it.

    A sibling of `Fact` on `FactComparison`'s precedent, not a modification of
    it. `inputs` is deliberately absent: this fact's inputs are two *populations*
    rather than two semantic measures, and §Composite provenance forbids
    repurposing the field that names measures.
    """

    fact_id: str
    citation_id: str
    metric: str
    subject_value: Decimal
    baseline_value: Decimal
    precision: int
    unit_kind: str
    provenance: PairProvenance
    formula_version: str = COMPARISON_CROSSVERSION_VERSION

    @property
    def absolute_delta(self) -> Decimal:
        """`subject - baseline`, surviving a zero or negative baseline."""
        return self.subject_value - self.baseline_value

    @property
    def percentage_delta(self) -> Decimal | None:
        """`(subject - baseline) / baseline`, or `None` unless `baseline > 0`.

        `None` rather than a raise: §Admission refuses a *pair*, while this is one
        derived value declining to state itself. `RRA-008`'s single-population
        rule is the same -- a percentage refuses and the absolute delta survives.
        """
        if self.baseline_value <= 0:
            return None
        return (self.absolute_delta / self.baseline_value) * Decimal(100)

    def as_document(self) -> dict[str, object]:
        return {
            "fact_id": self.fact_id,
            "citation_id": self.citation_id,
            "metric": self.metric,
            "subject_value": str(self.subject_value),
            "baseline_value": str(self.baseline_value),
            "precision": self.precision,
            "unit_kind": self.unit_kind,
            "formula_version": self.formula_version,
            **self.provenance.as_document(),
        }


@dataclass(frozen=True, slots=True)
class MeasuredPair:
    """The two values compared, and how the metric they belong to is stated.

    A missing abstraction the checker found: passing metric, both values,
    precision and unit kind alongside the provenance gave the constructor six
    arguments against a threshold of four. They are one thing -- *what was
    measured* -- and the provenance is the other, *which populations it came
    from*.
    """

    metric: str
    subject_value: Decimal
    baseline_value: Decimal
    precision: int
    unit_kind: str


def build_cross_version_fact(
    measured: MeasuredPair,
    provenance: PairProvenance,
) -> CrossVersionFact:
    """One cross-version fact, named by the governed identity helper.

    The identity comes from `fact_identity` rather than a hash computed here: two
    derivations of the same name would be a second chance to collide, which is
    the reason that helper is public.
    """
    fact_id, citation_id = fact_identity(
        metric=measured.metric,
        scope=provenance.scope,
        formula_version=COMPARISON_CROSSVERSION_VERSION,
    )
    return CrossVersionFact(
        fact_id=fact_id,
        citation_id=citation_id,
        metric=measured.metric,
        subject_value=measured.subject_value,
        baseline_value=measured.baseline_value,
        precision=measured.precision,
        unit_kind=measured.unit_kind,
        provenance=provenance,
    )
