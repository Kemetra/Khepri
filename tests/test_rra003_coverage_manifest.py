"""The separate proof that a period was completely covered.

`RRA-003` will not let a comparison infer completeness from the data it is
comparing. A date spine, an observed minimum or maximum date, equal row or day
counts, and the absence of events "never synthesize coverage proof" -- because
each of them is equally consistent with a period that was genuinely quiet and
one whose extract silently stopped early. So completeness-dependent comparisons
require a *separate* artifact: a manifest, versioned, bound to the exact input
digest, that someone attested.

Two bindings, and the second is the one worth stating.

**Input digest.** A manifest describes one file. Bound to its digest, it cannot
be carried to a different upload.

**Source contract.** `RRA-003` names this separately from the input digest, and
the reason is reuse: identical bytes re-uploaded under a *corrected* semantic
contract would otherwise match an old manifest whose event-kind and status
coverage was attested against different semantics. The bytes did not change; what
they were declared to mean did. Admitting comparison and growth on that pairing
would publish completeness proof nobody gave.

**An attested closure is not an extraction gap.** A closure proves complete zero
activity -- the store was shut, and zero is the true answer. A gap proves the
opposite: something is missing and its size is unknown. `RRA-003` separates them,
so this module does too.
"""

from __future__ import annotations

from datetime import date

import pytest

from khepri.rra.coverage import (
    COVERAGE_MANIFEST_VERSION,
    CoverageManifest,
    ManifestRefused,
    admits_completeness,
    build_coverage_manifest,
)


def _pairs(scope: str, days: list[date]) -> tuple[tuple[str, date], ...]:
    return tuple((scope, day) for day in days)


def _manifest(**overrides: object) -> CoverageManifest:
    defaults: dict[str, object] = {
        "input_digest": "a" * 64,
        "source_contract_digest": "b" * 64,
        "timezone": "Africa/Cairo",
        "covered_start": date(2026, 1, 1),
        "covered_end": date(2026, 1, 3),
        "aggregate_scope": "all-stores",
        "store_roster": (),
        "covered_pairs": _pairs(
            "all-stores",
            [date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3)],
        ),
        "event_kinds": ("sale", "return"),
        "statuses": ("posted",),
        "closures": (),
        "extraction_gaps": (),
        "partial_terminal_boundary": False,
    }
    defaults.update(overrides)
    return build_coverage_manifest(**defaults)  # type: ignore[arg-type]


def test_a_manifest_records_its_governed_version() -> None:
    assert _manifest().manifest_version == COVERAGE_MANIFEST_VERSION


def test_a_manifest_admits_the_window_it_covers() -> None:
    manifest = _manifest()

    assert admits_completeness(
        manifest,
        input_digest="a" * 64,
        source_contract_digest="b" * 64,
        scope="all-stores",
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
    )


def test_a_manifest_bound_to_other_bytes_is_refused() -> None:
    """A manifest describes one file and cannot be carried to another."""
    assert not admits_completeness(
        _manifest(),
        input_digest="c" * 64,
        source_contract_digest="b" * 64,
        scope="all-stores",
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
    )


def test_the_same_bytes_under_a_corrected_contract_are_refused() -> None:
    """The reuse `RRA-003` names the source contract separately to prevent.

    Identical bytes, re-declared. The old manifest attested event-kind and
    status coverage against semantics that no longer apply, so it proves
    nothing about this admission.
    """
    assert not admits_completeness(
        _manifest(),
        input_digest="a" * 64,
        source_contract_digest="d" * 64,
        scope="all-stores",
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
    )


def test_a_day_the_manifest_does_not_cover_is_refused() -> None:
    """Asking about a window wider than what was attested."""
    assert not admits_completeness(
        _manifest(),
        input_digest="a" * 64,
        source_contract_digest="b" * 64,
        scope="all-stores",
        start=date(2026, 1, 1),
        end=date(2026, 1, 4),
    )


def test_an_extraction_gap_refuses_the_window_it_falls_in() -> None:
    """A gap is missing data of unknown size, so completeness is not proven."""
    manifest = _manifest(extraction_gaps=(("all-stores", date(2026, 1, 2)),))

    assert not admits_completeness(
        manifest,
        input_digest="a" * 64,
        source_contract_digest="b" * 64,
        scope="all-stores",
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
    )


def test_an_attested_closure_still_admits_the_window() -> None:
    """A closure proves complete zero activity; zero is the true answer.

    This is the assertion that keeps the previous one honest. If closures and
    gaps were treated alike, a test suite could pass while the product refused
    every legitimately shut day.
    """
    manifest = _manifest(closures=(("all-stores", date(2026, 1, 2)),))

    assert admits_completeness(
        manifest,
        input_digest="a" * 64,
        source_contract_digest="b" * 64,
        scope="all-stores",
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
    )


def test_a_partial_terminal_boundary_refuses_completeness() -> None:
    """The last day is known to be cut off mid-stream."""
    assert not admits_completeness(
        _manifest(partial_terminal_boundary=True),
        input_digest="a" * 64,
        source_contract_digest="b" * 64,
        scope="all-stores",
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
    )


def test_a_scope_the_manifest_never_attested_is_refused() -> None:
    assert not admits_completeness(
        _manifest(),
        input_digest="a" * 64,
        source_contract_digest="b" * 64,
        scope="branch-7",
        start=date(2026, 1, 1),
        end=date(2026, 1, 3),
    )


def test_a_manifest_without_scope_or_roster_is_refused_at_construction() -> None:
    """`RRA-003`: without a store dimension the manifest must name one scope.

    Refused when built rather than when read, so an unusable manifest cannot be
    persisted and then discovered at comparison time.
    """
    with pytest.raises(ManifestRefused):
        _manifest(aggregate_scope=None, store_roster=())


def test_a_manifest_missing_a_day_inside_its_own_window_is_refused() -> None:
    """Covered pairs must actually cover the range the manifest claims."""
    with pytest.raises(ManifestRefused):
        _manifest(
            covered_pairs=_pairs(
                "all-stores",
                [date(2026, 1, 1), date(2026, 1, 3)],
            )
        )


def test_a_day_can_not_be_both_closed_and_a_gap() -> None:
    """They are contradictory attestations about the same day."""
    with pytest.raises(ManifestRefused):
        _manifest(
            closures=(("all-stores", date(2026, 1, 2)),),
            extraction_gaps=(("all-stores", date(2026, 1, 2)),),
        )
