"""The structural coverage signature `rra004.package.v3` retains.

`RRA-004` requires a deterministic signature over the manifest binding, scope,
filters, coverage mode and "relative covered calendar-day ordinals", excluding
"absolute calendar dates and all revenue, unit, and other measure values".

**The case that matters most is `test_two_windows_of_one_shape_share_a_signature`.**
A signature computed from observed data would be perfectly deterministic and
would pass every other test here while being exactly the date-spine inference
`RRA-004` forbids. Only comparing two structurally identical windows with
different absolute dates catches it.
"""

from __future__ import annotations

from datetime import date

import pytest

from khepri.rra.coverage import (
    ManifestBinding,
    ManifestExceptions,
    ManifestWindow,
    build_coverage_manifest,
)
from khepri.rra.coverage_signature import (
    COVERAGE_MODE_FULL_CALENDAR,
    COVERAGE_MODE_PREFIX,
    SignatureRefused,
    build_coverage_signature,
    project_prefix,
)

_INPUT = "a" * 64
_CONTRACT = "b" * 64
_SCOPE = "all-stores"


def _manifest(
    *,
    start: date,
    end: date,
    gaps: list[date] | None = None,
    input_digest: str = _INPUT,
):
    """A manifest attesting every day of the window it declares.

    **A prefix is a shorter manifest, not an incomplete one.**
    `coverage._assert_spans_its_own_window` refuses a manifest that omits a day
    inside its own declared window, so an operator attesting less declares less.
    A prefix therefore arises when the *query* window reaches past what the
    manifest covers, which is how a partial current period really presents.
    """
    days = [
        date.fromordinal(start.toordinal() + offset)
        for offset in range((end - start).days + 1)
    ]
    return build_coverage_manifest(
        binding=ManifestBinding(
            input_digest=input_digest,
            source_contract_digest=_CONTRACT,
            timezone="Africa/Cairo",
            attested_by="operations manager",
        ),
        window=ManifestWindow(
            covered_start=start,
            covered_end=end,
            aggregate_scope=_SCOPE,
            store_roster=(),
            covered_pairs=tuple((_SCOPE, day) for day in days),
        ),
        exceptions=ManifestExceptions(
            event_kinds=("sale", "return"),
            statuses=("posted",),
            extraction_gaps=tuple((_SCOPE, day) for day in (gaps or ())),
        ),
    )


def _signature(**overrides):
    start = overrides.pop("start", date(2026, 4, 1))
    end = overrides.pop("end", date(2026, 4, 3))
    manifest = overrides.pop("manifest", None) or _manifest(start=start, end=end)
    return build_coverage_signature(
        manifest,
        scope=overrides.pop("scope", _SCOPE),
        start=start,
        end=end,
    )


def test_a_fully_covered_window_records_every_ordinal() -> None:
    signature = _signature()

    assert signature.covered_ordinals == (1, 2, 3)
    assert signature.window_days == 3
    assert signature.mode == COVERAGE_MODE_FULL_CALENDAR


def test_the_signature_carries_no_absolute_date() -> None:
    """`RRA-004` excludes absolute calendar dates by name.

    Asserted over the whole serialized document rather than field by field, so a
    date added later in any field fails here rather than travelling silently.
    """
    document = _signature().as_document()

    rendered = repr(document)
    assert "2026" not in rendered
    assert "04-01" not in rendered


def test_two_windows_of_one_shape_share_a_signature() -> None:
    """The property the whole design exists for, and the one a data-derived
    signature would fail.

    Two different months, each fully covered over the same scope and filters,
    are structurally the same window. `RRA-008` asks whether two windows are
    comparable; that question is unanswerable if every month has a unique
    signature because its dates differ.
    """
    april = _signature(start=date(2026, 4, 1), end=date(2026, 4, 3))
    july = _signature(start=date(2026, 7, 14), end=date(2026, 7, 16))

    assert april.identity == july.identity


def test_a_window_of_a_different_length_does_not_share_a_signature() -> None:
    """A fully covered three days and a fully covered four days are different
    structures, even though both are contiguous from day one."""
    assert _signature(end=date(2026, 4, 3)).identity != _signature(
        end=date(2026, 4, 4)
    ).identity


def test_a_prefix_is_recorded_as_a_prefix_and_not_as_a_whole_window() -> None:
    """Days 1-2 of a three-day window is a prefix, and saying otherwise would
    let a truncated window be compared against a complete one."""
    manifest = _manifest(start=date(2026, 4, 1), end=date(2026, 4, 2))

    signature = build_coverage_signature(
        manifest, scope=_SCOPE, start=date(2026, 4, 1), end=date(2026, 4, 3)
    )

    assert signature.mode == COVERAGE_MODE_PREFIX
    assert signature.covered_ordinals == (1, 2)


def test_a_window_covered_with_a_hole_in_it_is_refused() -> None:
    """Neither a whole window nor a contiguous prefix.

    `RRA-004` admits only those two shapes for alignment, so a window missing
    its middle day has no structure to record -- recording it as a prefix would
    make it comparable to a complete two-day window it is not.
    """
    manifest = _manifest(
        start=date(2026, 4, 1), end=date(2026, 4, 3), gaps=[date(2026, 4, 2)]
    )

    with pytest.raises(SignatureRefused):
        build_coverage_signature(
            manifest, scope=_SCOPE, start=date(2026, 4, 1), end=date(2026, 4, 3)
        )


def test_an_extraction_gap_is_not_covered() -> None:
    """`RRA-003` separates a gap, whose size is unknown, from a closure.

    The gap is on the last day, so what remains is a contiguous prefix rather
    than a hole -- which is what makes this case about the gap and not about
    contiguity.
    """
    manifest = _manifest(
        start=date(2026, 4, 1), end=date(2026, 4, 3), gaps=[date(2026, 4, 3)]
    )

    signature = build_coverage_signature(
        manifest, scope=_SCOPE, start=date(2026, 4, 1), end=date(2026, 4, 3)
    )

    assert signature.covered_ordinals == (1, 2)
    assert signature.mode == COVERAGE_MODE_PREFIX


def test_a_scope_the_manifest_never_attested_is_refused() -> None:
    with pytest.raises(SignatureRefused):
        _signature(scope="a-store-nobody-attested")


def test_an_inverted_window_is_refused() -> None:
    """Never proven vacuously: with no days to check, every manifest would
    prove the window complete."""
    manifest = _manifest(start=date(2026, 4, 1), end=date(2026, 4, 3))

    with pytest.raises(SignatureRefused):
        build_coverage_signature(
            manifest, scope=_SCOPE, start=date(2026, 4, 3), end=date(2026, 4, 1)
        )


def test_a_different_input_does_not_share_a_signature() -> None:
    """The binding is part of the structure: the same shape attested over other
    bytes is not the same evidence."""
    other = _manifest(
        start=date(2026, 4, 1), end=date(2026, 4, 3), input_digest="c" * 64
    )

    assert (
        build_coverage_signature(
            other, scope=_SCOPE, start=date(2026, 4, 1), end=date(2026, 4, 3)
        ).identity
        != _signature().identity
    )


# --- projections -----------------------------------------------------------


def test_a_projection_restricts_the_parent_rather_than_generating_a_range() -> None:
    parent = _signature(start=date(2026, 4, 1), end=date(2026, 4, 5))

    projected = project_prefix(parent, days=3)

    assert projected.covered_ordinals == (1, 2, 3)
    assert projected.window_days == 3
    assert projected.mode == COVERAGE_MODE_PREFIX


def test_a_projection_preserves_every_binding_of_its_parent() -> None:
    """`RRA-004`: a projection preserves the bindings, scope and filters "in
    provenance"."""
    parent = _signature(start=date(2026, 4, 1), end=date(2026, 4, 5))

    projected = project_prefix(parent, days=3)

    assert projected.manifest_input_digest == parent.manifest_input_digest
    assert projected.source_contract_digest == parent.source_contract_digest
    assert projected.scope == parent.scope
    assert projected.event_kinds == parent.event_kinds
    assert projected.statuses == parent.statuses


def test_a_projection_may_not_reach_past_what_its_parent_attested() -> None:
    """"never infers missing coverage, synthesizes an unproven day"."""
    parent = _signature(start=date(2026, 4, 1), end=date(2026, 4, 3))

    with pytest.raises(SignatureRefused):
        project_prefix(parent, days=4)


def test_only_a_complete_signature_may_be_projected() -> None:
    """Projecting a prefix would compound an unproven boundary."""
    manifest = _manifest(start=date(2026, 4, 1), end=date(2026, 4, 2))
    prefix = build_coverage_signature(
        manifest, scope=_SCOPE, start=date(2026, 4, 1), end=date(2026, 4, 3)
    )

    with pytest.raises(SignatureRefused):
        project_prefix(prefix, days=1)


def test_a_projection_of_a_whole_window_still_reads_as_a_prefix() -> None:
    """Structurally it covers days 1..k of a longer attestation, and a reader
    comparing it against a genuinely complete window of that length must be able
    to tell the two apart."""
    parent = _signature(start=date(2026, 4, 1), end=date(2026, 4, 3))

    assert project_prefix(parent, days=3).mode == COVERAGE_MODE_PREFIX


def test_a_projection_covers_at_least_one_day() -> None:
    parent = _signature(start=date(2026, 4, 1), end=date(2026, 4, 3))

    with pytest.raises(SignatureRefused):
        project_prefix(parent, days=0)


# --- guards proven in isolation ---------------------------------------------
#
# Each case below exists because a mutant of its guard survived the cases above:
# a *downstream* refusal caught the same input for a different reason, so the
# guard could be deleted with the suite still green. `RRA-004` reasons are not
# interchangeable -- an operator told "no day is covered" when the real fault is
# an unattested scope is told something false -- so each guard is isolated here
# by asserting the reason it gives, not merely that it refuses.


def test_an_unattested_scope_refuses_for_the_scope_and_not_for_the_days() -> None:
    """Isolates the scope guard from the empty-ordinals refusal below it.

    Both refuse this input. Only one of them says why: with the scope check
    removed, every day lookup misses and the window is reported as proving no
    day covered, which would send an operator to fix a calendar that is fine.
    """
    manifest = _manifest(start=date(2026, 4, 1), end=date(2026, 4, 3))

    with pytest.raises(SignatureRefused) as refused:
        build_coverage_signature(
            manifest, scope="a-store-nobody-attested",
            start=date(2026, 4, 1), end=date(2026, 4, 3),
        )

    assert "scope" in str(refused.value).lower()


def test_an_inverted_window_refuses_for_its_shape_and_not_for_its_coverage() -> None:
    """Isolates the ordering guard from the same empty-ordinals refusal.

    `range(1, 0)` is empty, so a signature that dropped this check would refuse
    with "proves no day covered" -- describing the manifest, when the fault is
    in the question asked of it.
    """
    manifest = _manifest(start=date(2026, 4, 1), end=date(2026, 4, 3))

    with pytest.raises(SignatureRefused) as refused:
        build_coverage_signature(
            manifest, scope=_SCOPE, start=date(2026, 4, 3), end=date(2026, 4, 1)
        )

    assert "before it starts" in str(refused.value).lower()


def test_a_projection_past_its_parent_refuses_for_reaching_past_it() -> None:
    """Isolates the length guard from the completeness check below it.

    Both refuse `days=4` over a three-day parent. The completeness check reports
    that the parent does not prove every projected day, which reads as a gap in
    the attestation rather than as a projection asking for more than exists.
    """
    parent = _signature(start=date(2026, 4, 1), end=date(2026, 4, 3))

    with pytest.raises(SignatureRefused) as refused:
        project_prefix(parent, days=4)

    assert "more days than its parent" in str(refused.value).lower()


def test_the_window_length_is_part_of_the_identity() -> None:
    """A prefix and a whole window covering the same ordinals are different.

    `test_a_window_of_a_different_length_...` varies the end date, which moves
    the ordinals too, so it passes on the ordinals alone and a signature that
    dropped `window_days` from its identity survived it. These two share
    ordinals `(1, 2)` exactly and differ only in how long the window was, which
    is the whole distinction between a complete two-day window and the first two
    days of a three-day one.
    """
    shorter = build_coverage_signature(
        _manifest(start=date(2026, 4, 1), end=date(2026, 4, 2)),
        scope=_SCOPE, start=date(2026, 4, 1), end=date(2026, 4, 3),
    )
    longer = build_coverage_signature(
        _manifest(start=date(2026, 4, 1), end=date(2026, 4, 2)),
        scope=_SCOPE, start=date(2026, 4, 1), end=date(2026, 4, 4),
    )

    # Same ordinals AND the same mode, so `window_days` is the only field left
    # that separates them. Comparing a prefix against a complete window instead
    # would differ on `mode` as well, and the identity would still change with
    # `window_days` removed -- which is exactly how the first version of this
    # test let that mutant survive.
    assert shorter.covered_ordinals == longer.covered_ordinals == (1, 2)
    assert shorter.mode == longer.mode == COVERAGE_MODE_PREFIX
    assert shorter.window_days != longer.window_days
    assert shorter.identity != longer.identity
