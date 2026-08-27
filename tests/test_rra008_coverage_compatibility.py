"""Which coverage shapes `rra008.comparison.v2` treats as comparable.

Separate from `test_rra008_comparison.py`, which is about the family's arithmetic
-- the deltas it states and the reasons it refuses. This file is about the
structural question underneath that: whether two windows are covered the same
way at all, which `RRA-008` settles from the manifest and the retained signatures
rather than from any measure.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import date, timedelta

from khepri.rra.admissibility import assess_admissibility
from khepri.rra.analysis import comparison
from khepri.rra.coverage import (
    ManifestBinding,
    ManifestExceptions,
    ManifestWindow,
    build_coverage_manifest,
)
from khepri.rra.facts import AdmittedInput, FactPackage, RefusedResult, build_fact_package
from khepri.rra.intake import CSV_MEDIA_TYPE
from khepri.rra.mapping import build_mapping
from khepri.rra.profiling import build_profile
from tests.rra003_contract_fixtures import TEST_CONTRACT, published_mapping_identity

FOUR_DAYS = tuple(date(2026, 1, 5) + timedelta(days=offset) for offset in range(4))


def multi_store_package(*, stores: tuple[str, ...]) -> FactPackage:
    """One package whose manifest attests coverage per store rather than in aggregate.

    `RRA-008` admits "the same governed aggregate scope **or** complete admitted
    store set". A roster is one scope expressed as a set of stores, so a manifest
    naming several of them is the second form -- not several competing scopes.
    """
    header = b"date,revenue,units,invoice_no,branch\n"
    body = b"".join(
        f"{day.isoformat()},{100 + index * 10}.00,1,INV-{index}-{store},{store}\n".encode()
        for index, day in enumerate(FOUR_DAYS)
        for store in stores
    )
    content = header + body
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    manifest = build_coverage_manifest(
        binding=ManifestBinding(
            input_digest=profile.source_sha256_hex,
            source_contract_digest=TEST_CONTRACT.digest,
            timezone="Africa/Cairo",
            attested_by="Test fixture: operator attestation.",
        ),
        window=ManifestWindow(
            covered_start=FOUR_DAYS[0],
            covered_end=FOUR_DAYS[-1],
            aggregate_scope=None,
            store_roster=stores,
            covered_pairs=tuple(
                (store, day) for store in stores for day in FOUR_DAYS
            ),
        ),
        exceptions=ManifestExceptions(
            closures=(),
            extraction_gaps=(),
            partial_terminal_boundary=None,
            event_kinds=("sale",),
            statuses=("posted",),
        ),
    )
    with published_mapping_identity():
        mapping = build_mapping(profile, contract=TEST_CONTRACT)
        return build_fact_package(
            AdmittedInput(
                manifest=manifest,
                content=content,
                media_type=CSV_MEDIA_TYPE,
                profile=profile,
                mapping=mapping,
                decision=assess_admissibility(profile, mapping),
                contract=TEST_CONTRACT,
            )
        )


def test_a_complete_store_roster_is_one_scope_not_several() -> None:
    """`RRA-008` admits "the same governed aggregate scope **or** complete
    admitted store set".

    **A two-store manifest refused comparison entirely**, which is an ordinary
    retail export rather than an edge case. `_structurally_compatible` required
    one scope string across the whole package and a per-store manifest emits one
    signature per store, so the roster read as a scope disagreement rather than
    as the single scope-set the specification names. Found in review.

    The one-store case is asserted beside it, so a fix that merely widened the
    check to accept anything would not pass: the two must behave the same way.
    """
    for stores in (("Cairo",), ("Cairo", "Giza"), ("Cairo", "Giza", "Alexandria")):
        package = multi_store_package(stores=stores)
        assert len(package.coverage_signatures) == len(stores), stores
        stated = comparison.derive(package)
        assert not isinstance(stated, RefusedResult), (stores, stated)


def test_windows_covered_by_different_store_sets_are_still_incompatible() -> None:
    """The converse: a roster is one scope, and two *different* rosters are two.

    Without this the fix above would be "accept every scope set", which would
    compare a two-store period against a three-store one and report the extra
    branch's trading as growth.
    """
    package = multi_store_package(stores=("Cairo", "Giza"))
    mismatched = replace(
        package,
        coverage_signatures=(
            package.coverage_signatures[0],
            replace(package.coverage_signatures[1], event_kinds=("sale", "return")),
        ),
    )
    assert isinstance(comparison.derive(mismatched), RefusedResult)


def test_stores_covering_different_days_are_not_one_complete_set() -> None:
    """`RRA-008` admits "complete admitted store set", and complete binds.

    A roster is one scope only when every store in it is attested over the same
    days. One branch proven through the 8th beside another proven through the
    6th is two different coverages wearing one roster, and comparing them reports
    the missing branch-days as a change in trading.

    Asserted by shortening one store's covered ordinals directly, because a
    manifest that attested fewer days for one store would also change the window
    -- and this must refuse on the *shape*, not on the window length.
    """
    package = multi_store_package(stores=("Cairo", "Giza"))
    first, second = package.coverage_signatures
    assert first.covered_ordinals == second.covered_ordinals, "the fixture starts equal"

    ragged = replace(
        package,
        coverage_signatures=(
            first,
            replace(second, covered_ordinals=second.covered_ordinals[:-1]),
        ),
    )
    refused = comparison.derive(ragged)
    assert isinstance(refused, RefusedResult), refused
    assert refused.reason == comparison.REASON_COVERAGE_INCOMPATIBLE
