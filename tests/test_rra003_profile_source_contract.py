"""The source contract the profile route requires, and what it binds to.

`RRA-003` admits nothing on the strength of a header: "Generic headers and
observed values never establish event kind, status, currency, gross/net basis,
VAT treatment, additivity, allocation, or coverage." `rra003.mapping.v3` is the
version that makes that real on the ingestion path, so the contract stops being
an object the code *can* read and becomes one the route *requires*.

These are `V-mapping`'s RED cases for M1 and M2. They assert three things the
route does not do at `739d474`:

1. a profile request without a source contract is refused, rather than profiled
   on inferred semantics;
2. an accepted contract is persisted with its digest and bound to the profile,
   so `khepri.rra.coverage` can later refuse a manifest declared against a
   different reading of the same bytes;
3. `build_mapping` is deterministic from profile *plus* contract and stamps
   `rra003.mapping.v3`.

**Why the contract is required rather than defaulted.** A default would be
indistinguishable downstream from a declaration the operator chose, which is the
inference `RRA-003` refuses. `SourceContractBody` already forbids extra keys for
the same reason -- a misspelled `revenue_vat_inclusive` must not silently yield
the default basis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra.api import create_app
from khepri.rra.datasets import ProfilingService
from khepri.rra.deletion import DeletionService
from khepri.rra.intake import IntakeService, StoredObject
from khepri.rra.mapping import MAPPING_VERSION
from khepri.rra.persistence import (
    Base,
    SqlDeletionRepository,
    SqlProfileRepository,
    SqlSessionStore,
    SqlUploadRepository,
)
from khepri.rra.sessions import InvitationService
from khepri.rra.source_contract import SourceContractBody

NOW = datetime(2026, 7, 29, 12, 0, tzinfo=UTC)

#: Two stores, two periods, an explicit transaction column, and a status column
#: -- everything the contract below declares is actually present in the file, so
#: a refusal cannot be blamed on a column the operator named and did not ship.
CONTRACT_CSV = (
    b"date,invoice,event_kind,status,amount,qty,branch,currency\n"
    b"2026-03-04,INV-1,sale,posted,400.00,10,Cairo,EGP\n"
    b"2026-03-04,INV-2,sale,posted,150.00,3,Cairo,EGP\n"
    b"2026-03-05,INV-3,sale,posted,220.00,4,Giza,EGP\n"
)


def contract_body() -> dict[str, object]:
    """A complete declaration: every governed semantic proven exactly once.

    Built through `SourceContractBody` rather than hand-written as JSON so the
    payload cannot drift from the wire model it must satisfy. `to_contract()`
    raises `ContractRefused` here if the declaration is incomplete, which makes
    a malformed fixture fail loudly in this module instead of arriving at the
    route as an indistinguishable 4xx.
    """
    body = SourceContractBody(
        contract_id="src_contract_1",
        evidence="Declared by the operator during onboarding, ticket OPS-411.",
        event_kind_column="event_kind",
        status_column="status",
        currency_column="currency",
        event_key_columns=["invoice"],
        transaction_id_column="invoice",
        transaction_id_unique_package_wide=True,
    )
    body.to_contract()
    return body.model_dump()


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
    )
    return Harness(
        client=TestClient(app, base_url="https://testserver"),
        invitations=invitations,
        profiles=profiles,
    )


def ready(content: bytes = CONTRACT_CSV) -> Harness:
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


def test_profile_refuses_a_request_with_no_source_contract() -> None:
    """No contract, no admission -- the semantics are not in the file."""
    test = ready()

    response = test.client.post("/api/v1/beta/profile", json={})

    assert response.status_code == 422


def test_profile_refuses_a_contract_that_leaves_a_semantic_unproven() -> None:
    """Neither a column nor a package-level claim proves the event kind."""
    test = ready()
    incomplete = contract_body()
    incomplete["event_kind_column"] = None
    incomplete["sale_only"] = False

    response = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "source_contract": incomplete},
    )

    assert response.status_code == 400


def test_profile_refuses_a_contract_declaring_a_semantic_twice() -> None:
    """A column *and* a constant is a contradiction, not a preference."""
    test = ready()
    doubled = contract_body()
    doubled["sale_only"] = True

    response = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "source_contract": doubled},
    )

    assert response.status_code == 400


def test_profile_refuses_an_unknown_source_contract_field() -> None:
    """`extra="forbid"`: a misspelled key is inference by another name."""
    test = ready()
    misspelled = contract_body()
    misspelled["revenue_vat_inclusive"] = True

    response = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "source_contract": misspelled},
    )

    assert response.status_code == 422


def test_profile_accepts_a_complete_contract_and_stamps_mapping_v3() -> None:
    """The version this whole slice publishes, on the route that admits.

    **The planted `strict` xfail is gone, and its removal is this commit's
    publication step.** An earlier slice committed this assertion ahead of the
    constant so it could not be lost, marked `strict` so that whichever pull
    request moved `MAPPING_VERSION` would fail here and be forced to notice.
    That request is this one: the marker said "expiring this marker on schedule
    is the point", and the schedule is now. The assertion itself is unchanged --
    relaxing it was forbidden, and it was not relaxed.
    """
    test = ready()

    response = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "source_contract": contract_body()},
    )

    assert response.status_code == 201
    assert MAPPING_VERSION == "rra003.mapping.v3"
    assert response.json()["mapping_version"] == "rra003.mapping.v3"


def test_accepted_contract_is_persisted_with_its_digest() -> None:
    """Persisted inside the profile document, bound by digest.

    `khepri.rra.coverage` refuses a manifest whose `source_contract_digest` does
    not match the contract the events were admitted under. That refusal is only
    possible if the digest is recorded here, at admission time.
    """
    test = ready()
    body = contract_body()

    response = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "source_contract": body},
    )
    assert response.status_code == 201

    stored = test.profiles.get_profile_for_session(
        test.client.cookies["khepri_beta_session"]
    )
    assert stored is not None
    recorded = stored.document["source_contract"]
    expected = SourceContractBody(**body).to_contract()
    assert recorded["contract_id"] == "src_contract_1"
    assert recorded["digest"] == expected.digest


def test_a_different_reading_of_the_same_bytes_digests_differently() -> None:
    """The digest identifies a reading, not a file.

    Same upload, same columns, one basis declaration flipped. If these digested
    alike, a manifest attested against one reading would silently satisfy the
    other -- which is exactly what `coverage` must be able to refuse.
    """
    first = SourceContractBody(**contract_body()).to_contract()
    rebased = contract_body()
    rebased["revenue_vat_exclusive"] = False
    second = SourceContractBody(**rebased).to_contract()

    assert first.digest != second.digest


@pytest.mark.parametrize("missing", ["contract_id", "evidence"])
def test_profile_refuses_a_contract_with_no_attribution(missing: str) -> None:
    """An identifier without evidence names an attestation nobody signed."""
    test = ready()
    unsigned = contract_body()
    unsigned[missing] = ""

    response = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "source_contract": unsigned},
    )

    assert response.status_code == 400


def test_a_stored_profile_with_no_contract_is_refused_not_crashed() -> None:
    """A profile written before declarations existed cannot be re-derived.

    `RRA-003` makes the declaration the basis of admission, so there is no
    reading to rebuild the mapping from and guessing one would admit the events
    under a contract nobody declared. The plan requires historical `v2`
    artifacts to stay immutable and never reinterpreted; refusing to
    reinterpret one is that rule. A `KeyError` would be neither.
    """
    from khepri.rra.datasets import DatasetProfileRecord, ProfileCorrupted
    from khepri.rra.packages import _stored_contract

    legacy = DatasetProfileRecord(
        profile_id="prf_legacy",
        owner_id="own_1",
        session_id="ses_1",
        upload_id="upl_1",
        profile_version="rra003.profile.v1",
        mapping_version="rra003.mapping.v2",
        source_sha256_hex="a" * 64,
        profile_digest="b" * 64,
        row_count=2,
        column_count=2,
        admissible=True,
        created_at=NOW,
        document={"profile": {}, "mapping": {}, "admissibility": {}},
    )

    with pytest.raises(ProfileCorrupted) as refused:
        _stored_contract(legacy)

    assert "source contract" in str(refused.value)


def test_reprofiling_under_a_different_contract_is_refused() -> None:
    """A stored profile answers the declaration it was admitted under.

    The same reasoning as the requested-semantics guard beside it: handing back
    a profile built from a different reading would report a mapping this caller
    never declared, and the digest they are shown would address neither
    contract. `RRA-003` makes the declaration part of what a profile *is*.
    """
    test = ready()
    first = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "source_contract": contract_body()},
    )
    assert first.status_code == 201
    rebased = contract_body()
    rebased["revenue_vat_exclusive"] = False

    second = test.client.post(
        "/api/v1/beta/profile",
        json={"requested_semantics": [], "source_contract": rebased},
    )

    assert second.status_code == 409
    assert "source contract" in second.json()["detail"]


def test_reprofiling_under_the_same_contract_stays_idempotent() -> None:
    """The guard discriminates, rather than refusing every second request."""
    test = ready()
    body = {"requested_semantics": [], "source_contract": contract_body()}

    first = test.client.post("/api/v1/beta/profile", json=body)
    second = test.client.post("/api/v1/beta/profile", json=body)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json() == first.json()


def test_a_declared_column_the_file_lacks_leaves_the_semantic_unavailable() -> None:
    """A declaration must not be quietly replaced by an inference.

    The contract names `external_id` and the file carries `invoice`. Publishing
    transaction facts from the inferred column would establish identity from a
    header, under a contract that named a different one -- exactly what
    `RRA-003` refuses. The semantic goes unavailable instead.
    """
    import hashlib

    from khepri.rra.mapping import SEMANTIC_TRANSACTION_ID, build_mapping
    from khepri.rra.profiling import build_profile

    content = CONTRACT_CSV
    profile = build_profile(
        content=content,
        media_type="text/csv",
        source_sha256_hex=hashlib.sha256(content).hexdigest(),
    )
    body = contract_body()
    body["transaction_id_column"] = "external_id"
    body["event_key_columns"] = ["external_id"]

    mapping = build_mapping(
        profile,
        contract=SourceContractBody(**body).to_contract(),
    )

    assert mapping.for_semantic(SEMANTIC_TRANSACTION_ID).column is None
