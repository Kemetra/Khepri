"""The fail-closed gate over the versions one published result combines.

`RRA-004` says a new input, mapping, formula, population, interpretation,
correction, or serialized shape creates a new recorded version and stable
identity. Nothing in the runtime enforced the other half of that: that the
versions actually combined agree. `packages.py` stamped `PACKAGE_VERSION`,
`FORMULA_VERSION` and `MAPPING_VERSION` from three independent constants, and
`bundle._FAMILIES` dispatched four families that each stamped their own
`rra008.*` constant without consulting the package's `formula_version`.

So every slice of the calculation correction opened a window where a moved
version published changed numbers under its consumers' unmoved identities.
This module proves the gate that closes it.

**An explicit table, never a comparison.** The identifiers are independent
namespaces -- `rra003.mapping.v3`, `rra004.formula.v2` and `rra008.basket.v2`
share a numbering convention and nothing else -- so their suffixes define no
ordering to compare. A "newer than" rule would also guard one direction only,
and would leave an unrecognised version's handling undefined where a table
refuses it by construction.
"""

from __future__ import annotations

import pytest

from khepri.rra.versions import (
    ADMITTED_FAMILY_PAIRS,
    ADMITTED_PACKAGE_PAIRS,
    REASON_FAMILY_VERSION_UNADMITTED,
    REASON_PACKAGE_VERSION_UNADMITTED,
    admits_family,
    admits_package,
)


def test_the_shipped_package_triple_is_admitted() -> None:
    """`V-package` closed the package-scope refusal window it opened.

    `V-mapping` moved the mapping and deliberately added no row, so the triple
    this build combined was unlisted and every package refused. `V-package`
    publishes `rra004.package.v3` and adds `(mapping.v3, package.v3,
    formula.v1)` -- its own row and only its own -- so the package seam is whole
    again while the four `RRA-008` families stay refused until each lands.

    This assertion was inverted for exactly one commit. That it reads normally
    again is the evidence that the window was closed rather than widened: no row
    another commit owns was touched, and the predecessor triple below is
    untouched too.
    """
    from khepri.rra.facts import FORMULA_VERSION, PACKAGE_VERSION
    from khepri.rra.mapping import MAPPING_VERSION

    assert admits_package(
        mapping_version=MAPPING_VERSION,
        package_version=PACKAGE_VERSION,
        formula_version=FORMULA_VERSION,
    )


def test_the_published_predecessor_triple_stays_admitted() -> None:
    """The immutable row, which no publication commit may edit.

    `RRA-004` keeps historical packages "immutable under their recorded
    versions", so this row outlives every successor. Asserted against
    hardcoded literals rather than against `ADMITTED_PACKAGE_PAIRS`, because a
    test that reads the table it is checking would pass whatever the table
    said.
    """
    assert admits_package(
        mapping_version="rra003.mapping.v2",
        package_version="rra004.package.v2",
        formula_version="rra004.formula.v1",
    )


def test_only_the_families_that_have_landed_are_admitted() -> None:
    """The refusing set, shrinking exactly one family per commit.

    `V-formula` admitted none of the four; each family commit adds its own
    `(formula.v2, family.v2)` pair when it lands, and `V-concentration` empties
    the set. This assertion is the shrinking itself: a commit that widened the
    gate to publish early would admit a family whose successor has not landed,
    and a commit that forgot its own row would leave its family refusing its own
    results.

    Listed explicitly rather than derived from `ADMITTED_FAMILY_PAIRS`, because
    a test reading the table it checks passes whatever the table says.
    """
    from khepri.rra.analysis import basket, comparison, concentration, growth
    from khepri.rra.facts import FORMULA_VERSION

    landed = {
        comparison.COMPARISON_FORMULA_VERSION,
        growth.GROWTH_FORMULA_VERSION,
    }
    for family_version in (
        comparison.COMPARISON_FORMULA_VERSION,
        growth.GROWTH_FORMULA_VERSION,
        basket.BASKET_FORMULA_VERSION,
        concentration.CONCENTRATION_FORMULA_VERSION,
    ):
        assert (
            admits_family(
                formula_version=FORMULA_VERSION,
                family_version=family_version,
            )
            is (family_version in landed)
        )


def test_the_published_predecessor_family_pairs_stay_admitted() -> None:
    """The immutable rows, which no publication commit may edit."""
    for family_version in (
        "rra008.comparison.v1",
        "rra008.growth.v1",
        "rra008.basket.v1",
        "rra008.concentration.v1",
    ):
        assert admits_family(
            formula_version="rra004.formula.v1",
            family_version=family_version,
        )



def test_a_moved_mapping_against_an_unmoved_package_is_refused() -> None:
    """The exact window `V-mapping` opens, closed.

    `rra003.mapping.v3` with `rra004.package.v2` is the skew that would
    otherwise publish changed admission under a legacy package identity.
    """
    assert not admits_package(
        mapping_version="rra003.mapping.v3",
        package_version="rra004.package.v2",
        formula_version="rra004.formula.v1",
    )


def test_a_moved_formula_against_an_unmoved_family_is_refused() -> None:
    """The window `V-formula` opens: families still stamping `v1`."""
    assert not admits_family(
        formula_version="rra004.formula.v2",
        family_version="rra008.growth.v1",
    )


def test_a_moved_family_against_an_unmoved_formula_is_refused() -> None:
    """The direction a one-sided "newer than" rule would miss.

    A successor family identity stamped onto a package still carrying
    `rra004.formula.v1` is as wrong as the reverse, and a comparison that only
    asked "is the formula newer" would admit it.
    """
    assert not admits_family(
        formula_version="rra004.formula.v1",
        family_version="rra008.growth.v2",
    )


@pytest.mark.parametrize(
    "mapping_version,package_version,formula_version",
    [
        ("rra003.mapping.v9", "rra004.package.v2", "rra004.formula.v1"),
        ("rra003.mapping.v2", "rra004.package.v9", "rra004.formula.v1"),
        ("rra003.mapping.v2", "rra004.package.v2", "rra004.formula.v9"),
        ("", "", ""),
    ],
)
def test_an_unrecognised_package_version_is_refused_by_construction(
    mapping_version: str,
    package_version: str,
    formula_version: str,
) -> None:
    """A table refuses what it does not name; it never defaults to admitting."""
    assert not admits_package(
        mapping_version=mapping_version,
        package_version=package_version,
        formula_version=formula_version,
    )


def test_an_unrecognised_family_version_is_refused_by_construction() -> None:
    assert not admits_family(
        formula_version="rra004.formula.v1",
        family_version="rra008.growth.v9",
    )


def test_the_tables_are_not_empty() -> None:
    """A scan that admits nothing would pass every refusal test vacuously.

    An emptied table would make every `admits_*` call return False, and every
    refusal assertion above would still pass while the product refused all of
    its own output.
    """
    assert ADMITTED_PACKAGE_PAIRS
    assert ADMITTED_FAMILY_PAIRS


def test_the_family_refusal_carries_bilingual_customer_wording() -> None:
    """A refusal a reader cannot understand is not a governed refusal.

    This one reaches a reader: `RRA-008` requires a family mismatch to refuse
    only its own section, so the report is still published with the rest of it
    intact and a customer sees the gap.
    """
    from khepri.rra.rendering.wording import (
        LANGUAGE_ARABIC,
        LANGUAGE_ENGLISH,
        refusal_message,
    )

    for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH):
        message = refusal_message(
            REASON_FAMILY_VERSION_UNADMITTED,
            context="result",
            language=language,
        )
        assert message.strip()


def test_the_package_refusal_is_internal_and_carries_no_customer_wording() -> None:
    """Its sibling is a different tier, and the difference is not cosmetic.

    `RRA-009` classifies a reason as Internal when "no report is published, so a
    customer cannot encounter one in a delivered report and no customer-facing
    catalogue lists them". A package pairing mismatch is caught while the package
    is built, so the request is refused outright and no report exists. Giving it
    customer prose would place it in a catalogue whose completeness checks then
    demand it be rendered somewhere no customer can reach.
    """
    from khepri.rra.rendering.wording import LANGUAGE_ENGLISH, refusal_message

    with pytest.raises(KeyError):
        refusal_message(
            REASON_PACKAGE_VERSION_UNADMITTED,
            context="result",
            language=LANGUAGE_ENGLISH,
        )
