"""The five predicates `C1-01` did not cover, and the one cause each raises.

`RRA-008` §Admission lists six. `C1-01` implemented `D-6`'s completeness inside
the period model, because a period's completeness is a property of that period.
The other five compare two packages' provenance, which is this slice: `D-1`
scope, `D-2` mapping version, `D-3` formula version, `D-4` package version, and
`D-5` currency with the aggregate scope or admitted store set and the filters.

**All six must hold before any figure is derived**, so this returns the first
cause rather than a list: `RRA-008` §Refusals and caveats freezes a set of
single causes, and a refusal naming two leaves a caller unable to say which to
fix. The order is `D-1` first because a cross-organization pair must disclose
nothing about the other scope -- not even which of its versions differed.

**`D-5` requires the store set be identical, not merely complete on both sides.**
Two sets each complete and different from each other are a breakdown across one
population's dimension members, which is `RRA-004`'s. `#394` removed that pair
from `G4-01` UC-2 for exactly this reason, and `#400` restated it in the frozen
contract, so the test for it asserts a refusal rather than an admission.
"""

from __future__ import annotations

from dataclasses import replace

from khepri.rra.analysis.compatibility import (
    CAUSE_CURRENCY,
    CAUSE_FILTERS,
    CAUSE_FORMULA_DRIFT,
    CAUSE_MAPPING_DRIFT,
    CAUSE_PACKAGE_DRIFT,
    CAUSE_SCOPE,
    CAUSE_STORE_SET,
    ComparisonCandidate,
    packages_compatible,
)

_BASE = ComparisonCandidate(
    organization_scope="org_a",
    mapping_version="rra003.mapping.v3",
    formula_version="rra004.formula.v2",
    package_version="rra004.package.v3",
    currency="SAR",
    aggregate_scope="all_stores",
    admitted_store_set=("store_1", "store_2"),
    event_kind_filters=("sale", "return"),
    status_filters=("posted",),
)

SUBJECT = replace(_BASE)
BASELINE = replace(_BASE)


class TestAdmitted:
    def test_identical_provenance_is_compatible(self) -> None:
        assert packages_compatible(SUBJECT, BASELINE) is None

    def test_filter_order_does_not_matter(self) -> None:
        """The filters are a set; `RRA-004` serializes them sorted."""
        reordered = replace(BASELINE, event_kind_filters=("return", "sale"))

        assert packages_compatible(SUBJECT, reordered) is None

    def test_store_order_does_not_matter(self) -> None:
        reordered = replace(BASELINE, admitted_store_set=("store_2", "store_1"))

        assert packages_compatible(SUBJECT, reordered) is None


class TestRefused:
    def test_cross_organization_refuses(self) -> None:
        assert packages_compatible(SUBJECT, replace(BASELINE, organization_scope="org_b")) == (
            CAUSE_SCOPE
        )

    def test_mapping_drift_refuses(self) -> None:
        assert (
            packages_compatible(SUBJECT, replace(BASELINE, mapping_version="rra003.mapping.v2"))
            == CAUSE_MAPPING_DRIFT
        )

    def test_formula_drift_refuses(self) -> None:
        assert (
            packages_compatible(SUBJECT, replace(BASELINE, formula_version="rra004.formula.v1"))
            == CAUSE_FORMULA_DRIFT
        )

    def test_package_drift_refuses(self) -> None:
        assert (
            packages_compatible(SUBJECT, replace(BASELINE, package_version="rra004.package.v2"))
            == CAUSE_PACKAGE_DRIFT
        )

    def test_currency_difference_refuses(self) -> None:
        assert packages_compatible(SUBJECT, replace(BASELINE, currency="USD")) == CAUSE_CURRENCY

    def test_differing_aggregate_scope_refuses(self) -> None:
        assert packages_compatible(SUBJECT, replace(BASELINE, aggregate_scope="riyadh")) == (
            CAUSE_SCOPE
        )

    def test_store_set_complete_on_both_sides_but_different_refuses(self) -> None:
        """`D-5`: identical, not merely complete. `#394`'s correction."""
        other = replace(BASELINE, admitted_store_set=("store_3", "store_4"))

        assert packages_compatible(SUBJECT, other) == CAUSE_STORE_SET

    def test_partly_overlapping_store_set_refuses(self) -> None:
        """The realistic drift: one store added between two extractions.

        Separate from the disjoint case because a disjoint pair cannot tell
        equality from *disjointness*. Mutation testing found this: replacing
        `!=` with "share no member" passed the disjoint test and would admit
        this overlapping pair, which `D-5` requires be refused.
        """
        overlapping = replace(BASELINE, admitted_store_set=("store_1", "store_3"))

        assert packages_compatible(SUBJECT, overlapping) == CAUSE_STORE_SET

    def test_store_subset_refuses(self) -> None:
        """A strict subset shares every member it has, and is still not identical."""
        fewer = replace(BASELINE, admitted_store_set=("store_1",))

        assert packages_compatible(SUBJECT, fewer) == CAUSE_STORE_SET

    def test_differing_event_kind_filters_refuse(self) -> None:
        """A dropped filter: still overlapping, still not identical."""
        assert packages_compatible(SUBJECT, replace(BASELINE, event_kind_filters=("sale",))) == (
            CAUSE_FILTERS
        )

    def test_disjoint_event_kind_filters_refuse(self) -> None:
        assert packages_compatible(SUBJECT, replace(BASELINE, event_kind_filters=("void",))) == (
            CAUSE_FILTERS
        )

    def test_differing_status_filters_refuse(self) -> None:
        assert packages_compatible(SUBJECT, replace(BASELINE, status_filters=())) == CAUSE_FILTERS


class TestOneCause:
    def test_scope_is_reported_before_any_version(self) -> None:
        """A cross-organization pair discloses nothing else about the other scope."""
        everything_wrong = replace(
            BASELINE,
            organization_scope="org_b",
            mapping_version="rra003.mapping.v1",
            currency="USD",
        )

        assert packages_compatible(SUBJECT, everything_wrong) == CAUSE_SCOPE

    def test_mapping_is_reported_before_formula(self) -> None:
        """Mapping drift explains formula drift; the reverse is not true."""
        both = replace(
            BASELINE,
            mapping_version="rra003.mapping.v2",
            formula_version="rra004.formula.v1",
        )

        assert packages_compatible(SUBJECT, both) == CAUSE_MAPPING_DRIFT

    def test_every_cause_is_a_distinct_string(self) -> None:
        causes = (
            CAUSE_SCOPE,
            CAUSE_MAPPING_DRIFT,
            CAUSE_FORMULA_DRIFT,
            CAUSE_PACKAGE_DRIFT,
            CAUSE_CURRENCY,
            CAUSE_STORE_SET,
            CAUSE_FILTERS,
        )

        assert len(set(causes)) == len(causes)
