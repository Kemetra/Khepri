"""The immutable two-population fact package, and the provenance it must disclose.

`RRA-008` §Composite provenance names four disclosures and declines to say how
they are carried: `Fact.inputs` "keeps its existing meaning and is not
repurposed" and the `RRA-004` `Fact` type "is not modified", so the carrier is
this slice's to choose.

**The repository already answered it.** `FactComparison` is a sibling of `Fact`,
not a modification of it, composing a value object and merging its document with
`**self.comparison.as_document(...)`. `CrossVersionFact` follows that shape
exactly, which is why no `Fact` field is added here and `Fact.inputs` keeps its
meaning.

Two rules carry the weight, and each is asserted against the real
`fact_identity` rather than a restatement of it:

**Operand order is part of fact identity.** §Composite provenance: "the same pair
with the order reversed is a different fact with a different identity, not the
same fact negated." So the pair's two identifiers go into `scope` as an ordered
tuple, and the reversed pair must hash differently. A carrier that stored the
pair as a set, or sorted it, would produce one identity for two different facts.

**Reruns are byte-equivalent only for the same ordered pair.** The same inputs
must serialize identically twice, and the reversed pair must not.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from khepri.rra.analysis.comparison_package import (
    COMPARISON_CROSSVERSION_VERSION,
    CrossVersionFact,
    IdentityMismatch,
    MeasuredPair,
    PairProvenance,
    build_cross_version_fact,
)
from khepri.rra.facts import fact_identity
from khepri.rra.profiling import canonical_json

PROVENANCE = PairProvenance(
    subject_version_id="dsv_202603",
    subject_basis_id="basis_mar",
    subject_manifest_id="manifest_mar",
    baseline_version_id="dsv_202602",
    baseline_basis_id="basis_feb",
    baseline_manifest_id="manifest_feb",
)


MEASURED = MeasuredPair(
    metric="sales_revenue",
    subject_value=Decimal("1100"),
    baseline_value=Decimal("1000"),
    precision=2,
    unit_kind="monetary",
)


def _fact(*, provenance: PairProvenance = PROVENANCE, **measured: object) -> CrossVersionFact:
    """One fact, varying only the field a test is about.

    `replace` on the two frozen inputs rather than a keyword per field -- the
    shape `#401` and `#402` settled on, and the reason `build_cross_version_fact`
    itself takes two objects instead of six arguments.
    """
    return build_cross_version_fact(replace(MEASURED, **measured), provenance)  # type: ignore[arg-type]


class TestCompositeProvenance:
    """§Composite provenance: four disclosures, none of them in `Fact.inputs`."""

    def test_discloses_both_version_identifiers(self) -> None:
        document = _fact().as_document()

        assert document["subject_version_id"] == "dsv_202603"
        assert document["baseline_version_id"] == "dsv_202602"

    def test_discloses_both_retained_bases(self) -> None:
        document = _fact().as_document()

        assert document["subject_basis_id"] == "basis_mar"
        assert document["baseline_basis_id"] == "basis_feb"

    def test_discloses_both_coverage_manifests(self) -> None:
        """`D-6` is asserted against each version separately."""
        document = _fact().as_document()

        assert document["subject_manifest_id"] == "manifest_mar"
        assert document["baseline_manifest_id"] == "manifest_feb"

    def test_discloses_the_operand_order(self) -> None:
        assert _fact().as_document()["operand_order"] == ["subject", "baseline"]

    def test_records_the_governed_formula_version(self) -> None:
        assert _fact().as_document()["formula_version"] == "rra008.crossversion.v1"

    def test_does_not_repurpose_fact_inputs(self) -> None:
        """`Fact.inputs` names semantic measures; identifiers never enter it."""
        document = _fact().as_document()

        assert "dsv_202603" not in document.get("inputs", [])
        assert "dsv_202602" not in document.get("inputs", [])


class TestOperandOrderIsIdentity:
    def test_reversed_pair_has_a_different_identity(self) -> None:
        forward = _fact()
        reversed_provenance = PairProvenance(
            subject_version_id=PROVENANCE.baseline_version_id,
            subject_basis_id=PROVENANCE.baseline_basis_id,
            subject_manifest_id=PROVENANCE.baseline_manifest_id,
            baseline_version_id=PROVENANCE.subject_version_id,
            baseline_basis_id=PROVENANCE.subject_basis_id,
            baseline_manifest_id=PROVENANCE.subject_manifest_id,
        )
        backward = _fact(
            subject_value=Decimal("1000"),
            baseline_value=Decimal("1100"),
            provenance=reversed_provenance,
        )

        assert forward.fact_id != backward.fact_id
        assert forward.citation_id != backward.citation_id

    def test_identity_matches_the_governed_helper(self) -> None:
        """Asserted against `fact_identity` itself, not a restatement of it."""
        expected, _ = fact_identity(
            metric="sales_revenue",
            scope=("dsv_202603", "dsv_202602"),
            formula_version=COMPARISON_CROSSVERSION_VERSION,
        )

        assert _fact().fact_id == expected

    def test_identity_is_stable_across_two_builds(self) -> None:
        assert _fact().fact_id == _fact().fact_id


class TestDeltas:
    """§Operand order: `subject - baseline`, percentage refusing on a zero base."""

    def test_absolute_delta_is_subject_minus_baseline(self) -> None:
        assert _fact().absolute_delta == Decimal("100")

    def test_absolute_delta_survives_a_negative_baseline(self) -> None:
        fact = _fact(subject_value=Decimal("10"), baseline_value=Decimal("-5"))

        assert fact.absolute_delta == Decimal("15")

    def test_percentage_delta_is_stated_against_the_baseline(self) -> None:
        assert _fact().percentage_delta == Decimal("10")

    @pytest.mark.parametrize("baseline", [Decimal("0"), Decimal("-5")])
    def test_percentage_delta_refuses_a_non_positive_baseline(self, baseline: Decimal) -> None:
        fact = _fact(subject_value=Decimal("10"), baseline_value=baseline)

        assert fact.percentage_delta is None


class TestImmutableAndDeterministic:
    def test_assigning_a_field_raises(self) -> None:
        """Frozen, asserted on the specific error rather than any `Exception`.

        A first draft wrapped `replace(...)` and an assignment in one bare
        `pytest.raises(Exception)`. `replace` *succeeds* -- constructing a new
        object is what it is for -- so that test passed on the second statement
        alone and would have passed with the dataclass unfrozen.
        """
        fact = _fact()

        with pytest.raises(AttributeError):
            fact.metric = "other"  # type: ignore[misc]

    def test_replace_with_a_changed_metric_refuses(self) -> None:
        """`replace` cannot smuggle a stale identity past the constructor.

        Frozen prevents mutation and prevents nothing else: `replace` legally
        builds a copy with a different `metric` while carrying the original
        `fact_id` forward. A first draft of this test **asserted that stale
        identifier as expected** and called it documentation; `#404`'s review
        pointed out that two different facts could then claim one identity.
        `__post_init__` now refuses it.
        """
        original = _fact()

        with pytest.raises(IdentityMismatch):
            replace(original, metric="other_metric")

    def test_replace_with_a_changed_pair_refuses(self) -> None:
        """The same hazard through the provenance rather than the metric."""
        original = _fact()
        other_pair = replace(PROVENANCE, subject_version_id="dsv_202604")

        with pytest.raises(IdentityMismatch):
            replace(original, provenance=other_pair)

    def test_replace_with_a_changed_version_refuses(self) -> None:
        """`formula_version` is hashed, so changing it invalidates the identity."""
        original = _fact()

        with pytest.raises(IdentityMismatch):
            replace(original, formula_version="rra008.comparison.v2")

    def test_a_mismatched_citation_id_alone_refuses(self) -> None:
        """`citation_id` is checked independently of `fact_id`.

        Mutation testing found this twice. Dropping `citation_id` from the
        comparison first passed every test, because none built a fact whose
        `fact_id` was right and whose citation was wrong; then dropping
        `fact_id` passed, because the replacement test got *both* wrong at once
        and could not say which half caught it. Each half now has a case that
        leaves the other valid -- the two identifiers share one digest under
        different prefixes, so that is expressible.

        A citation is how a rendered figure points back at its fact, so a stale
        one misroutes provenance without invalidating the fact it cites.
        """
        good = _fact()

        with pytest.raises(IdentityMismatch):
            replace(good, citation_id="cit_0000000000000000")

    def test_a_mismatched_fact_id_alone_refuses(self) -> None:
        good = _fact()

        with pytest.raises(IdentityMismatch):
            replace(good, fact_id="fct_000000000000000000000000")

    def test_replace_of_a_value_is_permitted(self) -> None:
        """Values are not identity inputs, so a corrected figure keeps its name.

        This is the boundary of the guard, and it is deliberate: `fact_identity`
        hashes metric, pair and version, so re-deriving the same metric over the
        same ordered pair under the same version must reach the same identity
        whatever the numbers turn out to be.
        """
        original = _fact()
        corrected = replace(original, subject_value=Decimal("1200"))

        assert corrected.fact_id == original.fact_id
        assert corrected.absolute_delta == Decimal("200")

    def test_two_builds_serialize_byte_identically(self) -> None:
        assert canonical_json(_fact().as_document()) == canonical_json(_fact().as_document())

    def test_reversed_pair_does_not_serialize_identically(self) -> None:
        reversed_provenance = PairProvenance(
            subject_version_id=PROVENANCE.baseline_version_id,
            subject_basis_id=PROVENANCE.baseline_basis_id,
            subject_manifest_id=PROVENANCE.baseline_manifest_id,
            baseline_version_id=PROVENANCE.subject_version_id,
            baseline_basis_id=PROVENANCE.subject_basis_id,
            baseline_manifest_id=PROVENANCE.subject_manifest_id,
        )
        backward = _fact(provenance=reversed_provenance)

        assert canonical_json(_fact().as_document()) != canonical_json(backward.as_document())


class TestFormulaVersionIsNotTheSingleFamilyVersion:
    def test_crossversion_is_not_the_period_comparison_version(self) -> None:
        """`#400`: a cross-version delta must not be confusable with a PoP one."""
        from khepri.rra.analysis.comparison import COMPARISON_FORMULA_VERSION

        assert COMPARISON_CROSSVERSION_VERSION != COMPARISON_FORMULA_VERSION
        assert COMPARISON_CROSSVERSION_VERSION == "rra008.crossversion.v1"

    def test_every_fact_carries_it_explicitly(self) -> None:
        """The `C1-03` obligation from item 20: hashed *and* recorded."""
        fact = _fact()

        assert fact.formula_version == COMPARISON_CROSSVERSION_VERSION
        assert fact.as_document()["formula_version"] == COMPARISON_CROSSVERSION_VERSION
