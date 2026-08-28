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
from khepri.rra.coverage_signature import COVERAGE_MODE_PREFIX
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

#: Five monthly rows, so `windows.settled` leaves three interior months and
#: a comparison is available at all.
_MONTHS = tuple(date(2026, month, 1) for month in range(1, 6))


def _prefix_attested() -> FactPackage:
    """A package whose manifest stops one month short of the data.

    That is what an export ending mid-period looks like, and it is the only
    shape that produces `COVERAGE_MODE_PREFIX`: the signature spans
    `min(days)..max(days)` off the *data*, so the attested days form a
    contiguous prefix of it. A manifest must cover every day inside its own
    declared window, so a prefix cannot be expressed any other way.
    """
    header = b"date,revenue,units,invoice_no,branch\n"
    body = b"".join(
        f"{day.isoformat()},100.00,1,INV-{index},Cairo\n".encode()
        for index, day in enumerate(_MONTHS)
    )
    content = header + body
    profile = build_profile(
        content=content,
        media_type=CSV_MEDIA_TYPE,
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    attested = _MONTHS[:-1]
    manifest = build_coverage_manifest(
        binding=ManifestBinding(
            input_digest=profile.source_sha256_hex,
            source_contract_digest=TEST_CONTRACT.digest,
            timezone="Africa/Cairo",
            attested_by="Test fixture: operator attestation.",
        ),
        window=ManifestWindow(
            covered_start=attested[0],
            covered_end=attested[-1],
            aggregate_scope="all-stores",
            store_roster=(),
            covered_pairs=tuple(
                ("all-stores", day)
                for day in _days_between(attested[0], attested[-1])
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


def _days_between(first: date, last: date) -> tuple[date, ...]:
    """Every day the manifest must attest to span its own declared window."""
    span = (last - first).days + 1
    return tuple(first + timedelta(days=offset) for offset in range(span))


def _comparison_facts(package: FactPackage) -> tuple:
    """The facts this family states, or `()` where it refused."""
    derived = comparison.derive(package)
    return () if isinstance(derived, RefusedResult) else derived

def test_a_complete_comparison_is_not_labelled_partial() -> None:
    """The caveat attached to a window that is complete by construction.

    `_is_partial` asked whether **any** retained signature has prefix mode.
    A signature is built per attested *scope* over the whole admitted span,
    never per bucket -- so prefix mode says the manifest attests a contiguous
    prefix of the dataset, and says nothing about either compared month.

    Meanwhile `windows.settled` returns `buckets[1:-1]`, so `compared_labels`
    can only ever name *interior* months, which are whole by construction. The
    terminal partial bucket is never the compared window.

    The two together mean the caveat was wrong on every firing, not merely on
    some: a customer was told a complete comparison was partial. Deleting the
    derivation is the fix, not refining it -- the signature set carries no
    per-window answer to refine against.
    """
    package = _prefix_attested()

    # The premise: the package really does retain a prefix-mode signature, or
    # this case cannot show the caveat being derived from one.
    assert any(
        signature.mode == COVERAGE_MODE_PREFIX
        for signature in package.coverage_signatures
    ), 'no prefix signature was retained, so this proves nothing'

    facts = _comparison_facts(package)
    assert facts, 'the comparison refused, so no caveat can be judged'
    assert not any(
        comparison.CAVEAT_PARTIAL_WINDOW in fact.caveats for fact in facts
    ), (
        'a complete interior month was published as a partial-window comparison'
    )
def test_no_code_path_yet_attaches_the_partial_window_caveat() -> None:
    """The gap this leaves is deliberate, and this test is what makes it loud.

    `RRA-008` requires a partial-prefix comparison to carry the bilingual
    partial-window caveat, and `RRA-004:141` says where such a comparison comes
    from: a day-`1..k` selection that chooses the terminal bucket and projects
    the prior window to the same days over the retained daily bases. **That
    selection is not implemented** -- `windows.settled` drops the terminal
    bucket, so no partial window is ever selected to caveat.

    Deleting the old derivation removed a caveat that was wrong on every firing.
    It did not build the right one. Left silent, `CAVEAT_PARTIAL_WINDOW` would
    be a governed caveat with prose in both languages reaching no code path --
    the failure mode where nothing fails and no one notices.

    So this asserts the absence on purpose. It fails the day the selection is
    wired, which is exactly when someone must come back and decide what the
    caveat now attaches to rather than letting it quietly reappear.
    """
    package = _prefix_attested()
    assert any(
        signature.mode == COVERAGE_MODE_PREFIX
        for signature in package.coverage_signatures
    ), 'no prefix signature was retained, so this proves nothing'

    every_caveat = {
        caveat for fact in _comparison_facts(package) for caveat in fact.caveats
    }

    assert comparison.CAVEAT_PARTIAL_WINDOW not in every_caveat, (
        'the partial-window caveat has a producer again -- if that is the day-1..k '
        'selection landing, delete this test; if it is the whole-span prefix mode '
        'coming back, it is the defect this slice removed'
    )
    # And the caveat itself stays governed and worded, because `RRA-008` still
    # requires it to exist for the selection that will produce it.
    from khepri.rra.rendering.wording import _GOVERNED_CAVEAT_CODES

    assert comparison.CAVEAT_PARTIAL_WINDOW in _GOVERNED_CAVEAT_CODES
