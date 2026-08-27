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
    CompletenessQuery,
    CoverageManifest,
    ManifestBinding,
    ManifestExceptions,
    ManifestRefused,
    ManifestWindow,
    admits_completeness,
    assert_bound,
    build_coverage_manifest,
)

_INPUT = "a" * 64
_CONTRACT = "b" * 64
_SCOPE = "all-stores"
_ATTESTED_BY = "operations manager, 2026-08-27"
_START = date(2026, 1, 1)
_MIDDLE = date(2026, 1, 2)
_END = date(2026, 1, 3)


def _pairs(scope: str, days: list[date]) -> tuple[tuple[str, date], ...]:
    return tuple((scope, day) for day in days)


def _manifest(
    *,
    window: ManifestWindow | None = None,
    exceptions: ManifestExceptions | None = None,
) -> CoverageManifest:
    """A manifest covering three whole days of one aggregate scope."""
    return build_coverage_manifest(
        binding=ManifestBinding(
            input_digest=_INPUT,
            source_contract_digest=_CONTRACT,
            timezone="Africa/Cairo",
            attested_by=_ATTESTED_BY,
        ),
        window=window
        or ManifestWindow(
            covered_start=_START,
            covered_end=_END,
            aggregate_scope=_SCOPE,
            store_roster=(),
            covered_pairs=_pairs(_SCOPE, [_START, _MIDDLE, _END]),
        ),
        exceptions=exceptions
        or ManifestExceptions(event_kinds=("sale", "return"), statuses=("posted",)),
    )


def _query(**overrides: object) -> CompletenessQuery:
    """The default question, with any one field replaced."""
    fields: dict[str, object] = {
        "input_digest": _INPUT,
        "source_contract_digest": _CONTRACT,
        "scope": _SCOPE,
        "start": _START,
        "end": _END,
    }
    fields.update(overrides)
    return CompletenessQuery(**fields)  # type: ignore[arg-type]


def _admits(manifest: CoverageManifest, **overrides: object) -> bool:
    """Ask the default question, varying only what a test is about.

    One call site rather than one per test, so a test reads as the single
    condition it changes instead of six repeated lines that hide it.
    """
    return admits_completeness(manifest, _query(**overrides))


def test_a_manifest_records_its_governed_version() -> None:
    assert _manifest().manifest_version == COVERAGE_MANIFEST_VERSION


def test_a_manifest_admits_the_window_it_covers() -> None:
    assert _admits(_manifest())


def test_a_manifest_bound_to_other_bytes_is_refused() -> None:
    """A manifest describes one file and cannot be carried to another."""
    assert not _admits(_manifest(), input_digest="c" * 64)


def test_the_same_bytes_under_a_corrected_contract_are_refused() -> None:
    """The reuse `RRA-003` names the source contract separately to prevent.

    Identical bytes, re-declared. The old manifest attested event-kind and
    status coverage against semantics that no longer apply, so it proves
    nothing about this admission.
    """
    assert not _admits(_manifest(), source_contract_digest="d" * 64)


def test_a_day_the_manifest_does_not_cover_is_refused() -> None:
    """Asking about a window wider than what was attested."""
    assert not _admits(_manifest(), end=date(2026, 1, 4))


def test_an_extraction_gap_refuses_the_window_it_falls_in() -> None:
    """A gap is missing data of unknown size, so completeness is not proven."""
    manifest = _manifest(
        exceptions=ManifestExceptions(
            event_kinds=("sale",),
            statuses=("posted",),
            extraction_gaps=((_SCOPE, _MIDDLE),),
        )
    )

    assert not _admits(manifest)


def test_an_attested_closure_still_admits_the_window() -> None:
    """A closure proves complete zero activity; zero is the true answer.

    This is the assertion that keeps the previous one honest. If closures and
    gaps were treated alike, the suite would pass while the product refused
    every legitimately shut day.
    """
    manifest = _manifest(
        exceptions=ManifestExceptions(
            event_kinds=("sale",),
            statuses=("posted",),
            closures=((_SCOPE, _MIDDLE),),
        )
    )

    assert _admits(manifest)


def test_a_partial_terminal_boundary_refuses_completeness() -> None:
    """The last day is known to be cut off mid-stream."""
    manifest = _manifest(
        exceptions=ManifestExceptions(
            event_kinds=("sale",),
            statuses=("posted",),
            partial_terminal_boundary=True,
        )
    )

    assert not _admits(manifest)


def test_a_scope_the_manifest_never_attested_is_refused() -> None:
    assert not _admits(_manifest(), scope="branch-7")


def test_a_manifest_without_scope_or_roster_is_refused_at_construction() -> None:
    """`RRA-003`: without a store dimension the manifest must name one scope.

    Refused when built rather than when read, so an unusable manifest cannot be
    persisted and then discovered at comparison time.
    """
    with pytest.raises(ManifestRefused):
        _manifest(
            window=ManifestWindow(
                covered_start=_START,
                covered_end=_END,
                aggregate_scope=None,
                store_roster=(),
                covered_pairs=_pairs(_SCOPE, [_START, _MIDDLE, _END]),
            )
        )


def test_a_manifest_missing_a_day_inside_its_own_window_is_refused() -> None:
    """Covered pairs must actually cover the range the manifest claims."""
    with pytest.raises(ManifestRefused):
        _manifest(
            window=ManifestWindow(
                covered_start=_START,
                covered_end=_END,
                aggregate_scope=_SCOPE,
                store_roster=(),
                covered_pairs=_pairs(_SCOPE, [_START, _END]),
            )
        )


def test_a_day_can_not_be_both_closed_and_a_gap() -> None:
    """They are contradictory attestations about the same day."""
    with pytest.raises(ManifestRefused):
        _manifest(
            exceptions=ManifestExceptions(
                event_kinds=("sale",),
                statuses=("posted",),
                closures=((_SCOPE, _MIDDLE),),
                extraction_gaps=((_SCOPE, _MIDDLE),),
            )
        )


def test_a_manifest_stamped_with_an_unrecognised_version_is_refused() -> None:
    """The stamp is evidence, not decoration, so it is checked at use.

    `build_coverage_manifest` stamps `COVERAGE_MANIFEST_VERSION`, and
    `manifest_from_document` reads back whatever a stored document recorded --
    deliberately, so a rebuild reproduces exactly what was written. That makes
    the constructor's stamp no proof at all at use time: a document carrying an
    unrecognised version reaches `admits_completeness` intact. `RRA-003` requires
    the manifest to be "versioned", which is only meaningful if an unknown
    version refuses rather than being trusted.
    """
    unrecognised = CoverageManifest(
        manifest_version="rra003.coverage-manifest.v9",
        input_digest=_INPUT,
        source_contract_digest=_CONTRACT,
        attested_by=_ATTESTED_BY,
        timezone="Africa/Cairo",
        covered_start=_START,
        covered_end=_END,
        aggregate_scope=_SCOPE,
        store_roster=(),
        covered_pairs=frozenset(_pairs(_SCOPE, [_START, _MIDDLE, _END])),
        event_kinds=("sale",),
        statuses=("posted",),
        closures=frozenset(),
        extraction_gaps=frozenset(),
        partial_terminal_boundary=False,
    )

    assert not _admits(unrecognised)


def test_a_manifest_bound_to_empty_digests_is_refused() -> None:
    """Two empty strings match each other, so a manifest bound to nothing
    would admit everything.

    `admits_completeness` compares the manifest's digests against the query's.
    Blank on both sides satisfies that comparison while proving no binding to
    any file or any reading, which is the opposite of what `RRA-003` requires
    of an attestation "bound to the exact input digest".
    """
    unbound = build_coverage_manifest(
        binding=ManifestBinding(
            input_digest="",
            source_contract_digest="",
            timezone="Africa/Cairo",
        ),
        window=ManifestWindow(
            covered_start=_START,
            covered_end=_END,
            aggregate_scope=_SCOPE,
            store_roster=(),
            covered_pairs=_pairs(_SCOPE, [_START, _MIDDLE, _END]),
        ),
        exceptions=ManifestExceptions(event_kinds=("sale",), statuses=("posted",)),
    )

    # Structurally fine, which is why `build_coverage_manifest` accepts it:
    # `profile_request._unbound` validates a posted payload's shape against
    # placeholder digests before the real ones exist. The binding proof is a
    # later phase, and that is the door under test.
    with pytest.raises(ManifestRefused):
        assert_bound(unbound)


def test_a_partial_terminal_boundary_refuses_only_windows_that_contain_it() -> None:
    """`RRA-003` names the boundary as one known exception, not a blanket veto.

    A partial terminal boundary is by definition at the end of the covered
    window: the extract stopped mid-way through that last period. A window that
    closed days earlier is unaffected by it, and refusing that window states a
    gap where the manifest attests none -- which loses exactly the completeness
    proof the operator did give.
    """
    manifest = _manifest(
        exceptions=ManifestExceptions(
            event_kinds=("sale",),
            statuses=("posted",),
            partial_terminal_boundary=True,
        )
    )

    assert _admits(manifest, start=_START, end=_MIDDLE)
    assert not _admits(manifest, start=_START, end=_END)


def test_a_manifest_without_attribution_evidence_is_refused() -> None:
    """`RRA-003` requires the attestation's own evidence, not only the
    contract's.

    The manifest already records `source_contract_digest`, which is the identity
    of the *reading* it was attested under. That is a different fact from who
    attested it and on what basis: `RRA-003` lists "the source-contract or
    attestation identity **and its evidence**" among the fields a manifest
    records, and the source contract's evidence attributes the contract rather
    than the coverage claim. An operator-attested closure is a statement someone
    made, and an attestation nobody signed cannot be weighed later.
    """
    unattributed = build_coverage_manifest(
        binding=ManifestBinding(
            input_digest=_INPUT,
            source_contract_digest=_CONTRACT,
            timezone="Africa/Cairo",
            attested_by="   ",
        ),
        window=ManifestWindow(
            covered_start=_START,
            covered_end=_END,
            aggregate_scope=_SCOPE,
            store_roster=(),
            covered_pairs=_pairs(_SCOPE, [_START, _MIDDLE, _END]),
        ),
        exceptions=ManifestExceptions(event_kinds=("sale",), statuses=("posted",)),
    )

    with pytest.raises(ManifestRefused):
        assert_bound(unattributed)


def test_attribution_evidence_travels_into_the_stored_document() -> None:
    """Recorded, or it cannot be read back to attribute the claim."""
    document = _manifest().as_document()

    assert document["attested_by"] == _ATTESTED_BY
