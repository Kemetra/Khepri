"""`W1-01` — the workspace domain contracts (`RCA-005` `FR-109`, `FR-110`, `FR-115`).

These tests are written before the module exists. They encode three things the specification
requires of the *types themselves*, before any persistence or service can rely on them.

**Why the field-set assertions are equalities, not absences.** `RCA-005` `FR-109` forbids a
commercial identifier on any workspace object and `FR-115` forbids a source profile from carrying
anything that could substitute for an admission check. An absence test — "there is no `email`
field" — cannot see a field *added*, which is the failure mode recorded across this repository:
a membership table widened silently because every test asserted what was present and what was
named-and-refused, and none asserted the extent. So each type's field set is asserted to *equal*
its allowlist. A new field fails the test until someone states, in the same commit, that it
belongs.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, datetime

import pytest

from khepri.rca.workspace.contracts import (
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    SourceProfile,
)

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
SCOPE = "own_3f7a9c21b4e85d06"


def _field_names(record_type: type) -> set[str]:
    return {f.name for f in fields(record_type)}


# --- FR-109: the opaque scope is the only key, and no field can name a customer -------------


def test_dataset_version_fields_are_exactly_its_allowlist() -> None:
    """A field added to this record must be argued for, not merely typed."""
    assert _field_names(DatasetVersion) == {
        "version_id",
        "owner_id",
        "upload_plaintext_digest",
        "upload_ciphertext_digest",
        "upload_size_bytes",
        "upload_media_type",
        "manifest_digest",
        "mapping_version",
        "admission_outcome",
        "created_at",
        "sealed_at",
    }


def test_analysis_run_fields_are_exactly_its_allowlist() -> None:
    assert _field_names(AnalysisRun) == {
        "run_id",
        "version_id",
        "owner_id",
        "package_digest",
        "package_version",
        "formula_version",
        "state",
        "started_at",
        "completed_at",
    }


def test_artifact_binding_fields_are_exactly_its_allowlist() -> None:
    assert _field_names(ArtifactBinding) == {
        "run_id",
        "owner_id",
        "surface",
        "artifact_digest",
        "published_at",
    }


@pytest.mark.parametrize(
    "record_type",
    [DatasetVersion, AnalysisRun, ArtifactBinding, SourceProfile],
)
def test_no_workspace_record_names_a_commercial_identifier(record_type: type) -> None:
    """`FR-109`: the isolation key is the opaque `owner_id` and nothing else identifies a customer.

    This checks names rather than values on purpose — a `str` field can hold anything at runtime,
    so the enforceable property is that no field *invites* a commercial identifier. The extent
    assertions above are what actually close the gap; this one states the rule the reviewer of a
    new field should apply.
    """
    forbidden = {
        "email",
        "organization_name",
        "name",
        "slug",
        "filename",
        "file_name",
        "organization_id",
        "account_id",
        "actor_email",
    }
    assert _field_names(record_type) & forbidden == set()


def test_every_workspace_record_is_keyed_by_the_opaque_scope() -> None:
    assert all(
        "owner_id" in _field_names(t)
        for t in (DatasetVersion, AnalysisRun, ArtifactBinding, SourceProfile)
    )


# --- FR-115: a source profile is descriptive, and cannot carry a decision -------------------


def test_source_profile_fields_are_exactly_its_allowlist() -> None:
    """`FR-115` is a *shape* constraint, not only a runtime one.

    If the type can carry an admission outcome, a later slice will read it and skip the check
    the specification says must always run. The equality is the guard: a field named
    `admission_outcome`, `admitted`, or `mapping_accepted` fails here before it can be consumed.
    """
    assert _field_names(SourceProfile) == {
        "profile_id",
        "owner_id",
        "source_version_id",
        "column_labels",
        "proposed_mapping",
        "created_at",
    }


@pytest.mark.parametrize(
    "forbidden",
    ["admission_outcome", "admitted", "mapping_accepted", "sealed_at", "skip_admission"],
)
def test_source_profile_cannot_carry_an_admission_decision(forbidden: str) -> None:
    assert forbidden not in _field_names(SourceProfile)


def test_source_profile_is_not_sealed() -> None:
    """A profile is metadata a surface reads, not a record the domain acts on.

    Sealing it would imply a door exists to construct profiles through, which is the shape that
    invites a later slice to treat one as authority. The same reasoning keeps
    `OrganizationMember` unsealed in `rca/organizations.py`.
    """
    from khepri.rca.records import Sealed

    assert not issubclass(SourceProfile, Sealed)


@pytest.mark.parametrize("record_type", [DatasetVersion, AnalysisRun, ArtifactBinding])
def test_records_the_domain_acts_on_are_sealed(record_type: type) -> None:
    from khepri.rca.records import Sealed

    assert issubclass(record_type, Sealed)


# --- FR-112 in its type form: these records are frozen --------------------------------------


def test_a_dataset_version_cannot_be_mutated() -> None:
    version = DatasetVersion.create(
        owner_id=SCOPE,
        upload_plaintext_digest="sha256:" + "a" * 64,
        upload_ciphertext_digest="sha256:" + "b" * 64,
        upload_size_bytes=2048,
        upload_media_type="text/csv",
        manifest_digest="sha256:" + "c" * 64,
        mapping_version="rra003.mapping.v3",
        admission_outcome="admitted",
        now=NOW,
    )
    with pytest.raises(FrozenInstanceError):
        version.upload_size_bytes = 4096  # type: ignore[misc]


def test_substitution_is_refused_on_a_sealed_workspace_record() -> None:
    """`dataclasses.replace` rebuilds through the constructor from ordinary code.

    `records.py` names this as the load-bearing rule: producing a modified record means going
    through a door again. A version whose digest could be swapped this way would let a caller
    re-point a sealed dataset at content it never admitted.
    """
    version = DatasetVersion.create(
        owner_id=SCOPE,
        upload_plaintext_digest="sha256:" + "a" * 64,
        upload_ciphertext_digest="sha256:" + "b" * 64,
        upload_size_bytes=2048,
        upload_media_type="text/csv",
        manifest_digest="sha256:" + "c" * 64,
        mapping_version="rra003.mapping.v3",
        admission_outcome="admitted",
        now=NOW,
    )
    with pytest.raises(Exception):  # noqa: B017 - the sealing error type is records.py's to name
        replace(version, upload_plaintext_digest="sha256:" + "f" * 64)


# --- Construction: an unsealed version, and the two doors -----------------------------------


def test_a_created_dataset_version_is_not_yet_sealed() -> None:
    """Sealing is an event (`RCA-005`: facts derived and reconciled), never a creation argument.

    `KHEPRI-DEC-033` starts the raw upload's seven-day purge clock at sealing, so a version that
    arrived already sealed would start that clock before its facts exist.
    """
    version = DatasetVersion.create(
        owner_id=SCOPE,
        upload_plaintext_digest="sha256:" + "a" * 64,
        upload_ciphertext_digest="sha256:" + "b" * 64,
        upload_size_bytes=2048,
        upload_media_type="text/csv",
        manifest_digest="sha256:" + "c" * 64,
        mapping_version="rra003.mapping.v3",
        admission_outcome="admitted",
        now=NOW,
    )
    assert version.sealed_at is None
    assert version.owner_id == SCOPE
    assert version.version_id.startswith("dsv_")


def test_create_has_no_parameter_for_a_stored_only_field() -> None:
    """The two-door rule: `create` allocates, `_from_storage` preserves, and they never meet."""
    with pytest.raises(TypeError):
        DatasetVersion.create(  # type: ignore[call-arg]
            version_id="dsv_forged",
            owner_id=SCOPE,
            upload_plaintext_digest="sha256:" + "a" * 64,
            upload_ciphertext_digest="sha256:" + "b" * 64,
            upload_size_bytes=2048,
            upload_media_type="text/csv",
            manifest_digest="sha256:" + "c" * 64,
            mapping_version="rra003.mapping.v3",
            admission_outcome="admitted",
            now=NOW,
        )


def test_a_run_is_created_incomplete_and_names_its_version() -> None:
    run = AnalysisRun.create(owner_id=SCOPE, version_id="dsv_abc123", now=NOW)
    assert run.completed_at is None
    assert run.package_digest is None
    assert run.version_id == "dsv_abc123"
    assert run.run_id.startswith("run_")


def test_a_source_profile_is_constructed_without_a_door() -> None:
    profile = SourceProfile(
        profile_id="prf_abc123",
        owner_id=SCOPE,
        source_version_id="dsv_abc123",
        column_labels=("date", "sku", "qty"),
        proposed_mapping=(("date", "transaction_date"),),
        created_at=NOW,
    )
    assert profile.owner_id == SCOPE
    assert profile.column_labels == ("date", "sku", "qty")
