"""The version gate, on the paths that actually publish.

`tests/test_rra004_version_compatibility.py` proves the tables answer correctly.
This module proves something the tables cannot prove about themselves: that
publication consults them. A predicate nothing calls refuses nothing, and the
skew it was written to catch reaches a reader as a plausible number under an
identity that did not produce it.

**Two seams, refused at different scopes, and the difference is load-bearing.**

A mapping/package/formula mismatch is caught while the package is built, so it
refuses the package: no report exists, and `RRA-009` classifies that reason as
Internal because no customer can encounter it.

A family/formula mismatch must refuse only its own family. `RRA-008` requires
that "a failure or missing optional input refuses only dependent results,
leaving independently answerable facts and the rest of the report intact", and
the mission's shrinking refusing set is only meaningful if families refuse one
at a time. Raising the package refusal for a family pairing would black out
every independently answerable result until the last family merged.

**Why these tests patch a version constant rather than a table entry.** Emptying
the table would prove only that an empty table refuses everything. Moving one
version is the defect in the field: a slice lands, one identifier advances, and
its consumers have not caught up yet.
"""

from __future__ import annotations

import pytest

from khepri.rra.versions import (
    REASON_FAMILY_VERSION_UNADMITTED,
    REASON_PACKAGE_VERSION_UNADMITTED,
)


def test_building_a_package_refuses_an_unadmitted_triple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A moved mapping against an unmoved package refuses the package.

    Driven through `build_fact_package` rather than through the gate function,
    because calling the gate directly proves only that the gate works. It cannot
    fail when the builder stops consulting it -- and a first draft of this test
    did exactly that: deleting the call from `_build` left it green.
    """
    from khepri.rra import facts

    monkeypatch.setattr(facts, "MAPPING_VERSION", "rra003.mapping.v3")

    with pytest.raises(facts.FactsRefused) as refused:
        _package_with_two_settled_periods()

    assert REASON_PACKAGE_VERSION_UNADMITTED in str(refused.value)


def test_building_a_package_admits_the_shipped_triple() -> None:
    """The versions this build publishes must pass its own gate.

    Without this the refusal above would pass against a gate that refused
    everything, and the product would refuse all of its own output.
    """
    package = _package_with_two_settled_periods()

    assert package.facts


def test_a_family_on_an_unadmitted_formula_refuses_only_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point of the family seam: the report survives.

    Growth is moved to a successor its formula does not admit. Growth refuses
    with the governed reason, and comparison -- which did not move -- still
    publishes. A package-level refusal here would return nothing at all.
    """
    from khepri.rra import bundle
    from khepri.rra.analysis import growth

    monkeypatch.setattr(growth, "GROWTH_FORMULA_VERSION", "rra008.growth.v2")

    package = _package_with_two_settled_periods()
    analysed = bundle._analysed(package)

    assert analysed.refusals.get(bundle.SECTION_GROWTH) == (
        REASON_FAMILY_VERSION_UNADMITTED
    )
    assert any(
        figure.section == bundle.SECTION_COMPARISON for figure in analysed.figures
    ), "comparison did not move, so it must still publish"


def _package_with_two_settled_periods() -> object:
    """Four consecutive days, which leaves two settled periods to compare."""
    import hashlib
    from datetime import date, timedelta

    from khepri.rra.admissibility import assess_admissibility
    from khepri.rra.facts import build_fact_package
    from khepri.rra.intake import CSV_MEDIA_TYPE
    from khepri.rra.mapping import build_mapping
    from khepri.rra.profiling import build_profile

    start = date(2026, 1, 5)
    rows = [("50.00", 5), ("100.00", 10), ("180.00", 12), ("60.00", 6)]
    body = b"".join(
        f"{(start + timedelta(days=index)).isoformat()},{amount},{units},INV-{index}\n".encode()
        for index, (amount, units) in enumerate(rows)
    )
    content = b"date,revenue,units,invoice_no\n" + body
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    mapping = build_mapping(profile)
    return build_fact_package(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        profile=profile,
        mapping=mapping,
        decision=assess_admissibility(profile, mapping),
    )
