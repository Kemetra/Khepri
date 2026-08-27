"""The coverage-manifest ingestion path: schema, route, and use.

Storage and re-profiling behavior -- the manifest's survival through the
content-addressed round trip once a request is admitted -- is
`test_rra003_coverage_storage.py`, split out to keep each module a manageable
size. That module imports its fixtures from here.

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


@pytest.mark.parametrize(
    ("manifest_overrides", "query_overrides"),
    [
        # Fail-closed: an unrecognised scope is a refusal, not an absence.
        pytest.param({}, {"scope": "Alexandria"}, id="unattested_scope"),
        # A manifest proves the window it attested, not the one it is asked.
        pytest.param({}, {"end": date(2026, 3, 6)}, id="day_outside_window"),
        # A window whose last bucket is admittedly partial proves nothing whole.
        pytest.param(
            {"partial_terminal_boundary": True}, {}, id="partial_terminal_boundary"
        ),
    ],
)
def test_an_unproven_window_refuses_completeness(
    manifest_overrides: dict[str, object],
    query_overrides: dict[str, object],
) -> None:
    """Every way a query can fall outside what the manifest attested is refused."""
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body(**manifest_overrides)),
    )
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(**query_overrides),
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


@pytest.mark.parametrize(
    "overrides",
    [
        # `build_coverage_manifest` already refuses each of these; the assertion
        # is that the refusal reaches the route as a governed 400 rather than a
        # 500. 400 and not 422 for the reason `declared_contract` records: the
        # body is well-formed and every field is the right type, so what is
        # wrong is the *attestation*.
        #
        # A window the covered days do not span.
        pytest.param({"covered_days": [_START.isoformat()]}, id="omits_a_day_in_its_window"),
        # A manifest that names nothing attests nothing.
        pytest.param(
            {"aggregate_scope": None, "store_roster": []}, id="names_no_scope"
        ),
        # Opposite claims about one day are a contradiction, not a preference.
        pytest.param(
            {
                "closed_days": [_END.isoformat()],
                "extraction_gap_days": [_END.isoformat()],
            },
            id="day_both_closed_and_a_gap",
        ),
        # Both scope modes at once: `CoverageManifest.scopes` would silently
        # prefer the aggregate and discard the roster, so the roster's stores
        # would be attested by nothing while appearing declared.
        pytest.param(
            {"aggregate_scope": _SCOPE, "store_roster": ["Cairo"]},
            id="both_scope_modes",
        ),
        # A blank identity is not a scope. The resulting set is nonempty, so
        # only an explicit check refuses it.
        pytest.param(
            {"aggregate_scope": "", "store_roster": []}, id="blank_aggregate_scope"
        ),
        pytest.param(
            {"aggregate_scope": None, "store_roster": [""]}, id="blank_store_identity"
        ),
        # A timezone that does not exist proves nothing about when a day began
        # or ended -- the exact gap `RRA-003` requires the timezone to close.
        pytest.param({"timezone": "Mars/Base"}, id="unrecognised_timezone"),
        pytest.param({"timezone": ""}, id="empty_timezone"),
        # `RRA-003` requires the manifest to record "included event kinds and
        # statuses". An empty declaration records neither while still admitting
        # completeness, which is the population boundary failing open.
        pytest.param({"event_kinds": []}, id="no_event_kinds"),
        pytest.param({"statuses": []}, id="no_statuses"),
        # A day beyond `covered_end` would let one extra pair satisfy a query
        # for a window the operator never declared.
        pytest.param(
            {
                "covered_days": [
                    _START.isoformat(),
                    _END.isoformat(),
                    date(2026, 3, 6).isoformat(),
                ]
            },
            id="day_outside_declared_window",
        ),
    ],
)
def test_the_route_refuses_a_structurally_unusable_manifest(
    overrides: dict[str, object],
) -> None:
    """Every structural defect that makes an attestation prove nothing."""
    test = ready()

    response = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body(**overrides)),
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


def test_an_inverted_window_is_refused_not_proven_vacuously() -> None:
    """`end` before `start` is a caller error, never a proof.

    `_days` returns no dates for an inverted range, so "every day is attested
    and none is a gap" holds of every manifest -- proving a window nobody
    attested. Asserted as 400 rather than 409 because the request is malformed,
    not a dataset in a state that cannot answer; a 409 would tell the operator
    their attestation was short when their query was backwards.
    """
    test = ready()
    profiled = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(manifest_body()),
    )
    assert profiled.status_code == 201

    response = test.client.get(
        "/api/v1/beta/coverage/completeness",
        params=completeness_query(start=_END, end=_START),
    )

    assert response.status_code == 400


def test_reposting_unordered_collections_is_the_same_attestation() -> None:
    """`store_roster`, `event_kinds` and `statuses` are sets, not sequences.

    Their posted order was previously retained in the digested document, so an
    operator re-posting the same stores or filters in a different sequence had
    the re-request refused as a different attestation. Sorting them in
    `as_document` makes the two digest identically.

    Driven through the route rather than compared as two digests, because the
    conflict this pins is `_assert_same_attestation`'s, which only the second
    POST reaches.
    """
    test = ready()
    first = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(
            manifest_body(
                aggregate_scope=None,
                store_roster=["Cairo", "Giza"],
                covered_days=[_START.isoformat(), _END.isoformat()],
                event_kinds=["sale", "return"],
                statuses=["posted", "void"],
            )
        ),
    )
    assert first.status_code == 201

    second = test.client.post(
        "/api/v1/beta/profile",
        json=profile_with(
            manifest_body(
                aggregate_scope=None,
                store_roster=["Giza", "Cairo"],
                covered_days=[_END.isoformat(), _START.isoformat()],
                event_kinds=["return", "sale"],
                statuses=["void", "posted"],
            )
        ),
    )

    assert second.status_code == 200
    assert second.json() == first.json()


def test_an_attested_profile_builds_a_package_that_carries_its_coverage() -> None:
    """`packages._readmit` read the stored manifest and then did not pass it on.

    It was read to rebuild the profile *document* for the digest comparison, and
    the `AdmittedInput` beside it was constructed without the field -- which
    defaults to `None`. Every package built from a real session therefore carried
    no coverage signature, `comparison._structurally_compatible` found none and
    returned `False`, and the comparison and growth families refused every
    customer report.

    **Both published families would have been inert in production** while the
    whole suite passed, because the `RRA-008` fixtures attest their own coverage
    and the production path did not. Found in review, and only visible from a
    test that drives the service rather than building a package by hand.
    """
    test = ready()
    profiled = test.client.post("/api/v1/beta/profile", json=profile_with(manifest_body()))
    assert profiled.status_code == 201, profiled.text

    built = test.client.post("/api/v1/beta/facts")
    assert built.status_code == 201, built.text
    document = built.json()["document"]

    assert document["coverage_manifest_identity"], (
        "the package records no manifest identity, so it saw no attestation"
    )
    assert document["coverage_signatures"], (
        "the package retained no coverage signature, so comparison and growth "
        "refuse every report this session produces"
    )
