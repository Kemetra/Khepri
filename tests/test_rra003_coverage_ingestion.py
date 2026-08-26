"""The coverage-manifest ingestion path: schema, route, storage, and use.

`RRA-003` puts coverage-manifest confirmation inside `rra003.mapping.v3`:
"Completeness-dependent comparisons require a separate source-provided or
explicitly operator-attested coverage manifest." `khepri.rra.coverage` has
implemented the domain rules since before this slice -- `build_coverage_manifest`
refuses a structurally unusable manifest, and `admits_completeness` refuses one
bound to other bytes or to a different reading of them. What was absent is
everything outside that module: no route accepted a manifest, nothing stored
one, and nothing asked `admits_completeness` in production.

These are `V-mapping`'s RED cases for M4. The three the execution ledger's M4
gate names are:

1. a missing manifest refuses -- `test_a_session_with_no_manifest_refuses_completeness`;
2. an attested zero-activity manifest is accepted --
   `test_an_attested_closure_admits_the_window_it_covers`;
3. a wrong contract identity refuses --
   `test_a_manifest_attested_under_another_reading_refuses_at_use_time`.

**Why the manifest arrives on the profile request rather than its own POST.**
The stored profile document is content-addressed: `DatasetProfileRecord.verify`
refuses a document whose digest moved, and `packages._readmit` rebuilds the
document from the bytes plus the stored contract and refuses a package when the
rebuild digests differently. Attaching a manifest to an *existing* profile would
therefore have to rewrite `profile_digest`, which
`PackageProvenance.expected()` compares against every already-published
package -- turning a valid package into `PackageCorrupted`. Measured, not
assumed: adding a `coverage_manifest` key to a built document changes its digest,
and the manifest-unaware rebuild then no longer reproduces it.

So the manifest is declared where the contract is declared, baked into the
document once, and read back on the rebuild. It stays *optional* because
completeness-dependent comparison is one consumer of a profile among several,
and `RRA-003` refuses those comparisons rather than refusing the profile.

**Validated on use, not only on write.** A manifest checked only as it is stored
leaves the binding unproven at the moment it matters. The use-time test seeds a
stored profile whose manifest names a different reading of the same bytes and
drives the production read path, which is the technique
`test_a_stored_profile_with_no_contract_is_refused_not_crashed` already uses on
`_stored_contract`. The query is built from the *profile's* recorded contract
digest, never from the manifest's own field, or the check would compare the
manifest to itself and could not fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.coverage import COVERAGE_MANIFEST_VERSION
from khepri.rra.coverage_request import CoverageManifestBody
from khepri.rra.datasets import (
    CoverageUnproven,
    DatasetProfileRecord,
    ProfilingService,
    session_completeness,
)
from khepri.rra.deletion import DeletionService
from khepri.rra.intake import IntakeService, StoredObject
from khepri.rra.packages import FactPackageService
from khepri.rra.persistence import (
    Base,
    SqlDeletionRepository,
    SqlFactPackageRepository,
    SqlProfileRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.sessions import InvitationService
from khepri.rra.source_contract import SourceContractBody

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

_START = date(2026, 3, 4)
_END = date(2026, 3, 5)
_SCOPE = "all-stores"

#: Two days, two stores, and every column the contract below names, so a refusal
#: can never be blamed on a column the operator declared and did not ship.
COVERAGE_CSV = (
    b"date,invoice,event_kind,status,amount,qty,branch,currency\n"
    b"2026-03-04,INV-1,sale,posted,400.00,10,Cairo,EGP\n"
    b"2026-03-04,INV-2,sale,posted,150.00,3,Cairo,EGP\n"
    b"2026-03-05,INV-3,sale,posted,220.00,4,Giza,EGP\n"
)


def contract_body() -> dict[str, object]:
    """A complete declaration: every governed semantic proven exactly once.

    Built through `SourceContractBody` rather than hand-written as JSON so the
    payload cannot drift from the wire model, and `to_contract()` raises here if
    the declaration is incomplete -- which makes a malformed fixture fail loudly
    in this module rather than arriving at the route as an indistinguishable 4xx.
    """
    body = SourceContractBody(
        contract_id="src_coverage_1",
        evidence="Declared by the operator during onboarding, ticket OPS-512.",
        event_kind_column="event_kind",
        status_column="status",
        currency_column="currency",
        event_key_columns=["invoice"],
        transaction_id_column="invoice",
        transaction_id_unique_package_wide=True,
    )
    body.to_contract()
    return body.model_dump()


def manifest_body(**overrides: object) -> dict[str, object]:
    """A complete attestation over both days of one aggregate scope.

    Flat over the wire like `SourceContractBody`, for the same reason: a JSON
    body is easier to post flat while the domain groups the same declarations by
    what they mean. Validated on the way out so a malformed override fails in
    this module instead of as an indistinguishable 4xx at the route.
    """
    body = CoverageManifestBody(
        timezone="Africa/Cairo",
        covered_start=_START,
        covered_end=_END,
        aggregate_scope=_SCOPE,
        covered_days=[_START, _END],
        event_kinds=["sale"],
        statuses=["posted"],
    )
    return {**body.model_dump(mode="json"), **overrides}


class MemoryObjectStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(
        self,
        *,
        key: str,
        content: bytes,
        media_type: str,
        sha256_hex: str,
    ) -> StoredObject:
        self.objects[key] = content
        return StoredObject(
            key=key,
            size_bytes=len(content),
            sha256_hex=sha256_hex,
            media_type=media_type,
            encryption_algorithm="AES-256-GCM",
            envelope_version=1,
            ciphertext_sha256_hex="c" * 64,
        )

    def get(self, key: str, **_: object) -> bytes:
        return self.objects[key]

    def abort_multipart_uploads(self, prefix: str) -> None:
        return None

    def delete_prefix(self, prefix: str) -> None:
        for key in tuple(self.objects):
            if key.startswith(prefix):
                self.objects.pop(key)

    def delete(self, key: str) -> None:
        self.objects.pop(key, None)


@dataclass
class Harness:
    client: TestClient
    invitations: InvitationService
    profiles: SqlProfileRepository

    @property
    def session_id(self) -> str:
        return self.client.cookies["khepri_beta_session"]

    def stored(self) -> DatasetProfileRecord:
        record = self.profiles.get_profile_for_session(self.session_id)
        assert record is not None
        return record


def harness() -> Harness:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    sessions = SqlSessionStore(factory)
    uploads = SqlUploadRepository(factory)
    profiles = SqlProfileRepository(factory)
    objects = MemoryObjectStore()
    invitations = InvitationService(sessions)
    upload_ids = iter(f"upl_{index}" for index in range(1, 32))
    profile_ids = iter(f"prf_{index}" for index in range(1, 32))
    package_ids = iter(f"fct_{index}" for index in range(1, 32))
    app = create_app(
        service=invitations,
        clock=lambda: NOW,
        intake_service=IntakeService(
            sessions=sessions,
            uploads=uploads,
            objects=objects,
            new_upload_id=lambda: next(upload_ids),
        ),
        deletion_service=DeletionService(
            sessions=sessions,
            deletions=SqlDeletionRepository(factory),
            objects=objects,
            new_deletion_id=lambda: "del_example",
            new_evidence_id=lambda: "dev_example",
        ),
        profiling_service=ProfilingService(
            sessions=sessions,
            uploads=uploads,
            objects=objects,
            profiles=profiles,
            new_profile_id=lambda: next(profile_ids),
        ),
        # Registered so the stored-manifest round trip has a real consumer. The
        # fact-package path rebuilds the profile document from the bytes plus
        # what was stored and refuses on a digest mismatch, which is the check a
        # manifest-unaware rebuild silently fails.
        package_service=FactPackageService(
            sessions=sessions,
            uploads=uploads,
            objects=objects,
            profiles=profiles,
            packages=SqlFactPackageRepository(factory),
            new_package_id=lambda: next(package_ids),
        ),
    )
    return Harness(
        client=TestClient(app, base_url="https://testserver"),
        invitations=invitations,
        profiles=profiles,
    )


def ready(content: bytes = COVERAGE_CSV) -> Harness:
    """A consented session with one governed upload waiting to be profiled."""
    test = harness()
    token = test.invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    test.client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    consented = test.client.post(
        "/api/v1/beta/consent",
        json={"consent_version": "beta-privacy-v1"},
    )
    assert consented.status_code == 204
    uploaded = test.client.post("/api/v1/beta/uploads", content=content)
    assert uploaded.status_code == 201
    return test


def profile_with(manifest: dict[str, object] | None) -> dict[str, object]:
    """A profile request body, with or without an attestation."""
    body: dict[str, object] = {
        "requested_semantics": [],
        "source_contract": contract_body(),
    }
    if manifest is not None:
        body["coverage_manifest"] = manifest
    return body


def completeness_query(
    *,
    scope: str = _SCOPE,
    start: date = _START,
    end: date = _END,
) -> dict[str, str]:
    return {
        "scope": scope,
        "start": start.isoformat(),
        "end": end.isoformat(),
    }


# ---------------------------------------------------------------------------
# The three RED cases the M4 gate names.
# ---------------------------------------------------------------------------


def test_a_session_with_no_manifest_refuses_completeness() -> None:
    """RED case 1. Without a manifest, completeness is refused, not inferred.

    `RRA-003`: "Without a valid manifest, observed trends may survive, but
    completeness-dependent period comparisons and growth refuse." The oracle's
    `MANIFEST_ABSENT_EXPECTED` states the same split. This asserts the refusal
    half: nothing about a profile with no attestation may report a covered
    window, because absence of events is not proof of absence of activity.
    """
    test = ready()
    profiled = test.client.post("/api/v1/beta/profile", json=profile_with(None))
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "coverage_manifest_absent"


def test_an_attested_closure_admits_the_window_it_covers() -> None:
    """RED case 2. An attested closure proves complete zero activity.

    `RRA-003`: "An attested closure proves complete zero activity; an extraction
    gap does not." The oracle's `ATTESTED_ZERO_ACTIVITY_EXPECTED` records the
    same rule with `comparison_admitted: True` for the closure and
    `extraction_gap_comparison_admitted: False` for the same absent day recorded
    as a gap. Both halves are asserted -- the acceptance here, the gap's refusal
    in the test below -- because a read that admitted everything would pass the
    acceptance half alone.
    """
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body(closed_days=[_END.isoformat()])),
    )
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(),
    )

    assert response.status_code == 200
    assert response.json()["complete"] is True
    assert response.json()["manifest_version"] == COVERAGE_MANIFEST_VERSION


def test_a_manifest_attested_under_another_reading_refuses_at_use_time() -> None:
    """RED case 3. A wrong contract identity refuses when the manifest is USED.

    This is the piece most easily faked. A binding checked only as the manifest
    is stored leaves it unproven at the moment it matters, so this drives the
    production read path against a *stored* profile whose manifest names a
    different reading of the same bytes.

    The mismatch is planted in storage rather than posted, because the write
    path refuses it -- which is correct and separately asserted below. The
    technique is the one
    `test_a_stored_profile_with_no_contract_is_refused_not_crashed` already uses:
    seed the record, call the production function, assert the governed refusal.
    """
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body()),
    )
    assert profiled.status_code == 201
    record = test.stored()

    #: The same bytes, re-declared. `RRA-003` names the source contract
    #: separately from the input digest for exactly this case: an old
    #: attestation says nothing about a corrected reading.
    tampered = dict(record.document)
    manifest = dict(tampered["coverage_manifest"])  # type: ignore[arg-type]
    manifest["source_contract_digest"] = "f" * 64
    tampered["coverage_manifest"] = manifest
    reattested = DatasetProfileRecord(
        profile_id=record.profile_id,
        owner_id=record.owner_id,
        session_id=record.session_id,
        upload_id=record.upload_id,
        profile_version=record.profile_version,
        mapping_version=record.mapping_version,
        source_sha256_hex=record.source_sha256_hex,
        profile_digest=record.profile_digest,
        row_count=record.row_count,
        column_count=record.column_count,
        admissible=record.admissible,
        created_at=record.created_at,
        document=tampered,
    )

    with pytest.raises(CoverageUnproven) as refused:
        session_completeness(
            reattested,
            scope=_SCOPE,
            start=_START,
            end=_END,
        )

    assert refused.value.reason == "coverage_manifest_contract_mismatch"


# ---------------------------------------------------------------------------
# The other half of each rule, so no test above can pass by admitting or
# refusing everything.
# ---------------------------------------------------------------------------


def test_an_extraction_gap_refuses_the_window_it_falls_in() -> None:
    """The mirror of the closure case: absence of events is not proof.

    Same day, same window, recorded as a gap instead of a closure. If this
    admitted, the closure test above would be proving that the read admits
    anything rather than that it distinguishes the two claims `RRA-003`
    separates.
    """
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body(extraction_gap_days=[_END.isoformat()])),
    )
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "coverage_manifest_window_unproven"


def test_a_manifest_is_bound_to_the_reading_it_was_attested_under() -> None:
    """The stored manifest carries the profile's own contract digest.

    The use-time refusal above is only meaningful if the digest it compares
    against is the *contract's*, recorded at admission. A manifest storing a
    digest of its own choosing would be compared to itself and could never
    refuse.
    """
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body()),
    )
    assert profiled.status_code == 201

    record = test.stored()
    stored_manifest = record.document["coverage_manifest"]
    recorded_contract = record.document["source_contract"]

    assert stored_manifest["source_contract_digest"] == recorded_contract["digest"]
    assert stored_manifest["input_digest"] == record.source_sha256_hex
    assert stored_manifest["timezone"] == "Africa/Cairo"


def test_a_scope_the_manifest_never_attested_is_refused() -> None:
    """Fail-closed: an unrecognised scope is a refusal, not an absence."""
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body()),
    )
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(scope="Alexandria"),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "coverage_manifest_window_unproven"


def test_a_day_outside_the_attested_window_is_refused() -> None:
    """A manifest proves the window it attested, not the one it is asked."""
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body()),
    )
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(end=date(2026, 3, 6)),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "coverage_manifest_window_unproven"


# ---------------------------------------------------------------------------
# The boundary. `extra="forbid"` and the structural refusals, at the route.
# ---------------------------------------------------------------------------


def test_the_route_refuses_an_unknown_manifest_field() -> None:
    """`extra="forbid"`: a misspelled key is inference by another name.

    The same reasoning `SourceContractBody` records. An operator writing
    `closed_day` and receiving the default empty tuple would have a window
    attested as ordinary trading on a declaration they never made.
    """
    test = ready()
    misspelled = manifest_body()
    misspelled["closed_day"] = [_END.isoformat()]

    response = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(misspelled),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("binding_field", ["input_digest", "source_contract_digest"])
def test_the_route_refuses_an_operator_declared_binding(binding_field: str) -> None:
    """The two digests identify the admission, so the body may not carry them.

    Refused outright by `extra="forbid"` rather than accepted and overwritten. An
    ignored digest would let an operator believe they had attested coverage
    against a reading they named, and would invite the use-time check to compare
    the manifest against a value from its own payload -- which cannot fail.
    """
    test = ready()
    overreaching = manifest_body()
    overreaching[binding_field] = "a" * 64

    response = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(overreaching),
    )

    assert response.status_code == 422


def test_the_route_refuses_a_manifest_that_omits_a_day_in_its_own_window() -> None:
    """A structurally unusable manifest is refused before it is stored.

    `build_coverage_manifest` already refuses this; the assertion here is that
    the refusal reaches the route as a governed 400 rather than a 500. 400 and
    not 422 for the reason `declared_contract` records: the body is well-formed
    and every field is the right type, so what is wrong is the *attestation*.
    """
    test = ready()

    response = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body(covered_days=[_START.isoformat()])),
    )

    assert response.status_code == 400


def test_the_route_refuses_a_manifest_naming_no_scope() -> None:
    """A manifest that names nothing attests nothing."""
    test = ready()

    response = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body(aggregate_scope=None, store_roster=[])),
    )

    assert response.status_code == 400


def test_the_route_refuses_a_day_both_closed_and_a_gap() -> None:
    """Opposite claims about one day are a contradiction, not a preference."""
    test = ready()

    response = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(
            manifest_body(
                closed_days=[_END.isoformat()],
                extraction_gap_days=[_END.isoformat()],
            )
        ),
    )

    assert response.status_code == 400


def test_a_per_store_roster_attests_each_store_it_names() -> None:
    """The roster form, so the aggregate form is not the only one proven."""
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(
            manifest_body(
                aggregate_scope=None,
                store_roster=["Cairo", "Giza"],
                covered_days=[_START.isoformat(), _END.isoformat()],
            )
        ),
    )
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(scope="Giza"),
    )

    assert response.status_code == 200
    assert response.json()["complete"] is True


def test_a_partial_terminal_boundary_refuses_completeness() -> None:
    """A window whose last bucket is admittedly partial proves nothing whole."""
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body(partial_terminal_boundary=True)),
    )
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(),
    )

    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "coverage_manifest_window_unproven"


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
    both this file's other fifteen tests and all 35 of
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
    coverage manifest". A mutant making that swap passed all 24 other tests in
    this module and all 13 in `test_rra003_profile_source_contract.py`, so this
    is the only thing pinning it.
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
