"""Coverage-manifest storage and re-profiling: the content-addressed round trip.

Split from `test_rra003_coverage_ingestion.py`, which keeps the RED cases, the
boundary conditions, and route-level validation. This module covers what
happens once a manifest is admitted: it must survive `DatasetProfileRecord`'s
digest, publish through `packages._readmit`'s rebuild, and a stored profile
must answer the attestation it was admitted under rather than the one on a
later request. Fixtures (`ready`, `profile_with`, `manifest_body`,
`contract_body`) are shared from the ingestion module rather than duplicated,
the same cross-module import pattern `test_m2_persistent_frame.py` already
uses for `client` from `test_rra_journey_api.py`.
"""

from __future__ import annotations

import pytest

from khepri.rra.coverage import COVERAGE_MANIFEST_VERSION
from tests.rra003_contract_fixtures import REFUSAL_WINDOW
from tests.test_rra003_coverage_ingestion import (
    _END,
    _START,
    contract_body,
    manifest_body,
    profile_with,
    ready,
)

# ---------------------------------------------------------------------------
# Storage: the manifest must survive the content-addressed round trip.
# ---------------------------------------------------------------------------


def test_a_stored_manifest_survives_the_profile_document_digest() -> None:
    """The manifest is inside the digested document, so the read must verify.

    `_profile_from_row` calls `record.verify()`, which refuses a document whose
    digest moved. A manifest written into the document after the digest was
    taken would make every subsequent read raise `ProfileCorrupted`. This proves
    it is baked in at construction instead.
    """
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body()),
    )
    assert profiled.status_code == 201

    record = test.stored()
    record.verify()

    assert record.document["coverage_manifest"]["manifest_version"] == (
        COVERAGE_MANIFEST_VERSION
    )


def test_the_stored_manifest_serializes_in_sorted_order() -> None:
    """Every scope-day collection is emitted sorted, and that is load-bearing.

    The manifest's day collections are `frozenset` in the domain, whose
    iteration order is not stable across processes, and `canonical_json` sorts
    keys but never the values inside a list. An unsorted section would give one
    attestation several digests, so `packages._readmit`'s rebuild would refuse a
    package it had itself just published -- intermittently, and only in
    production, where the hash seed differs from a test run's.

    **Asserted as the sorted literal rather than as two equal digests.** Two
    equal `frozenset`s iterate identically *within one process*, so a test that
    posts the same days in two orders and compares digests passes whether or not
    the code sorts anything. That version of this test was written first, and a
    mutant deleting the `sorted()` call survived it. This asserts the order
    itself, which no in-process coincidence supplies.
    """
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(
            manifest_body(
                aggregate_scope=None,
                #: Deliberately reverse-sorted on both axes, so the assertion
                #: below fails if the stored order is the posted one.
                store_roster=["Giza", "Cairo"],
                covered_days=[_END.isoformat(), _START.isoformat()],
            )
        ),
    )
    assert profiled.status_code == 201

    stored = test.stored().document["coverage_manifest"]

    assert stored["covered_pairs"] == [
        ["Cairo", "2026-03-04"],
        ["Cairo", "2026-03-05"],
        ["Giza", "2026-03-04"],
        ["Giza", "2026-03-05"],
    ]


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_an_attested_profile_still_publishes_a_fact_package() -> None:
    """The stored attestation must survive `packages._readmit`'s rebuild.

    This is the blast radius of putting the manifest inside the digested
    document, and it is the one a coverage-only test file cannot see. `_readmit`
    re-derives the profile document from the bytes plus what was stored and
    refuses the package when the rebuild digests differently. A rebuild that did
    not read the attestation back would digest without it and refuse **every**
    package for **every** attested profile -- reporting its own construction
    rather than the mismatch the digest exists to detect.

    Written because a mutant setting `manifest=None` in that rebuild survived
    every other test in this module and in `test_rra003_coverage_ingestion.py`
    (fifteen at the time, before the two were split) and all 35 of
    `tests/test_rra004_packages.py`, none of which attests coverage.
    """
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body()),
    )
    assert profiled.status_code == 201

    published = test.client.post("/api/v1/beta/facts")

    assert published.status_code == 201


# ---------------------------------------------------------------------------
# Re-profiling. A stored profile answers the attestation it was admitted under.
# ---------------------------------------------------------------------------


def test_reprofiling_under_a_different_manifest_is_refused() -> None:
    """A stored profile answers the attestation it was admitted under.

    The same reasoning the contract guard beside it already records: handing back
    a profile admitted under a different declaration "would report a mapping
    built from a reading this caller did not declare". Under `RRA-003` the
    attestation is the third thing a profile records, so leaving it unguarded is
    an inconsistency the existing code refutes.

    Measured before it was fixed: this returned **200** with the first profile,
    and the second request's closures were silently discarded. The operator
    receives a success for an attestation that never took effect, and every later
    completeness answer is computed from the manifest they believe they replaced.
    """
    test = ready()
    first = test.client.post("/api/v1/beta/profile", json=profile_with(manifest_body()))
    assert first.status_code == 201

    second = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body(closed_days=[_END.isoformat()])),
    )

    assert second.status_code == 409
    assert "coverage manifest" in second.json()["detail"]


def test_reprofiling_an_attested_upload_with_no_manifest_is_refused() -> None:
    """Withdrawing an attestation is a different request, not the same one.

    Stored with a manifest, re-requested without one. Returning the attested
    profile would hand back completeness proof this caller did not ask for and
    may be entitled to; returning it as unattested would silently drop proof that
    was validly given. Both are answers to a question nobody asked, so it
    refuses.
    """
    test = ready()
    first = test.client.post("/api/v1/beta/profile", json=profile_with(manifest_body()))
    assert first.status_code == 201

    second = test.client.post("/api/v1/beta/profile", json=profile_with(None))

    assert second.status_code == 409
    assert "coverage manifest" in second.json()["detail"]


def test_reprofiling_an_unattested_upload_with_a_manifest_is_refused() -> None:
    """The case worth deciding deliberately, and the worst one to get wrong.

    Stored WITHOUT a manifest, re-requested WITH one. Measured before the fix:
    **200**, and `coverage_manifest` never appeared in the document at all. So an
    operator attested coverage, was told the request succeeded, and then received
    `coverage_manifest_absent` from the completeness route -- a success followed
    by a contradiction, with nothing naming the cause.

    **Ruled a refusal rather than an amendment.** The tempting reading is that
    adding an attestation to a profile that has none takes nothing away, so it
    could be admitted as an upgrade. It cannot, and the reason is the digest:
    baking the manifest in changes the profile document, so honouring this would
    have to rewrite `profile_digest` -- which
    `packages.PackageProvenance.expected` compares against every already
    published package, turning each into `PackageCorrupted`. That is the exact
    breakage that put the manifest on the profile request in the first place.

    A 409 naming the manifest tells the operator what to do about it: delete the
    session content and upload again with the attestation. Silence told them
    nothing.
    """
    test = ready()
    first = test.client.post("/api/v1/beta/profile", json=profile_with(None))
    assert first.status_code == 201

    second = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body()),
    )

    assert second.status_code == 409
    assert "coverage manifest" in second.json()["detail"]


def test_a_changed_contract_reports_the_contract_not_the_manifest() -> None:
    """Two conflicts are possible at once; the operator is told the real one.

    Same attestation, re-declared contract. The manifest guard binds its
    comparison to the **stored** profile's contract digest, so a contract change
    does not also register as a manifest change. Binding it to the incoming
    contract instead makes the stored manifest's `source_contract_digest` stop
    matching, and the operator is told their *manifest* differs when only their
    *declaration* did -- the wrong actionable fact, and the harder one to debug
    because the manifest they posted is byte-identical to the stored one.

    Measured both ways: bound to the stored digest this reports "a different
    source contract"; bound to the incoming digest it reports "a different
    coverage manifest". A mutant making that swap passed every other test in
    this module and in `test_rra003_coverage_ingestion.py` (24 at the time,
    before the two were split) and all 13 in
    `test_rra003_profile_source_contract.py`, so this is the only thing pinning
    it.
    """
    test = ready()
    first = test.client.post(
        "/api/v1/beta/profile",
        json={
            "requested_semantics": [],
            "source_contract": contract_body(),
            "coverage_manifest": manifest_body(),
        },
    )
    assert first.status_code == 201
    rebased = contract_body()
    rebased["revenue_vat_exclusive"] = False

    second = test.client.post(
        "/api/v1/beta/profile",
        json={
            "requested_semantics": [],
            "source_contract": rebased,
            "coverage_manifest": manifest_body(),
        },
    )

    assert second.status_code == 409
    assert "source contract" in second.json()["detail"]
    assert "coverage manifest" not in second.json()["detail"]


def test_reprofiling_under_the_same_manifest_stays_idempotent() -> None:
    """The guard discriminates rather than refusing every second request.

    Without this, all three refusals above would pass against a guard that
    rejected any re-POST -- which would break the idempotence
    `test_rerunning_the_profile_returns_the_preserved_provenance` requires. The
    comparison is over the canonical document, so two attestations posting the
    same days in different orders are the same attestation.
    """
    test = ready()
    body = profile_with(manifest_body(covered_days=[_START.isoformat(), _END.isoformat()]))
    reordered = profile_with(
        manifest_body(covered_days=[_END.isoformat(), _START.isoformat()])
    )

    first = test.client.post("/api/v1/beta/profile", json=body)
    second = test.client.post("/api/v1/beta/profile", json=reordered)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()


def test_an_unattested_upload_stays_idempotent() -> None:
    """The guard does not turn two identical unattested requests into a conflict.

    `None` compared against `None` is a match, not a mismatch. This is the case
    `tests/test_rra003_api.py` exercises throughout with `profile_payload()`, and
    it is why the manifest guard cannot simply refuse whenever the stored and
    requested attestations are not both present.
    """
    test = ready()

    first = test.client.post("/api/v1/beta/profile", json=profile_with(None))
    second = test.client.post("/api/v1/beta/profile", json=profile_with(None))

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()


def test_a_profile_with_no_manifest_stores_no_manifest_section() -> None:
    """The manifest is optional, and absent means absent.

    An empty section would be indistinguishable downstream from an attestation
    covering nothing, which is the inference `RRA-003` refuses. It also keeps
    every profile written without a manifest digesting exactly as it did before
    this task.
    """
    test = ready()
    profiled = test.client.post("/api/v1/beta/profile", json=profile_with(None))
    assert profiled.status_code == 201

    assert "coverage_manifest" not in test.stored().document
