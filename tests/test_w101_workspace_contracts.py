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
    RUN_COMPLETED,
    RUN_STATES,
    AdmittedSource,
    AnalysisRun,
    ArtifactBinding,
    DatasetVersion,
    PublishedArtifact,
    RunOutcome,
    RunSubject,
    SourceProfile,
    VersionLifecycle,
)

NOW = datetime(2026, 9, 3, 12, 0, tzinfo=UTC)
SCOPE = "own_3f7a9c21b4e85d06"

SOURCE = AdmittedSource(
    plaintext_digest="sha256:" + "a" * 64,
    ciphertext_digest="sha256:" + "b" * 64,
    size_bytes=2048,
    media_type="text/csv",
    manifest_digest="sha256:" + "c" * 64,
    mapping_version="rra003.mapping.v3",
    admission_outcome="admitted",
)


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
    version = DatasetVersion.create(owner_id=SCOPE, source=SOURCE, now=NOW)
    with pytest.raises(FrozenInstanceError):
        version.upload_size_bytes = 4096  # type: ignore[misc]


def test_substitution_is_refused_on_a_sealed_workspace_record() -> None:
    """`dataclasses.replace` rebuilds through the constructor from ordinary code.

    `records.py` names this as the load-bearing rule: producing a modified record means going
    through a door again. A version whose digest could be swapped this way would let a caller
    re-point a sealed dataset at content it never admitted.
    """
    version = DatasetVersion.create(owner_id=SCOPE, source=SOURCE, now=NOW)
    with pytest.raises(Exception):  # noqa: B017 - the sealing error type is records.py's to name
        replace(version, upload_plaintext_digest="sha256:" + "f" * 64)


# --- Construction: an unsealed version, and the two doors -----------------------------------


def test_a_created_dataset_version_is_not_yet_sealed() -> None:
    """Sealing is an event (`RCA-005`: facts derived and reconciled), never a creation argument.

    `KHEPRI-DEC-033` starts the raw upload's seven-day purge clock at sealing, so a version that
    arrived already sealed would start that clock before its facts exist.
    """
    version = DatasetVersion.create(owner_id=SCOPE, source=SOURCE, now=NOW)
    assert version.sealed_at is None
    assert version.owner_id == SCOPE
    assert version.version_id.startswith("dsv_")


def test_create_cannot_be_given_a_seal() -> None:
    """`create` must have no `sealed_at` parameter at all — not merely default it to `None`.

    Added after a mutation test survived. Giving `create` a `sealed_at=None` keyword and passing
    it through left every other test in this module green, because they all check the *default*
    path: `test_a_created_dataset_version_is_not_yet_sealed` calls `create` without the argument
    and still sees `None`. A caller could then seal a version at creation, and
    `KHEPRI-DEC-033` starts the raw upload's seven-day purge clock at sealing — so the mutant
    silently starts a deletion clock for content whose facts do not exist yet.

    Asserted against the signature rather than by calling with the argument, because a `TypeError`
    from a wrong call is also what an unrelated typo produces; the signature is the property.
    """
    import inspect

    assert "sealed_at" not in inspect.signature(DatasetVersion.create).parameters


def test_create_cannot_be_given_a_completion() -> None:
    """The same property for a run: `FR-111` puts the digest and versions on the real pipeline.

    A `create` that accepted `package_digest` would let a run record a result it never derived.
    """
    import inspect

    forbidden = {"package_digest", "package_version", "formula_version", "completed_at", "state"}
    assert set(inspect.signature(AnalysisRun.create).parameters) & forbidden == set()


def test_create_has_no_parameter_for_a_stored_only_field() -> None:
    """The two-door rule: `create` allocates, `_from_storage` preserves, and they never meet."""
    with pytest.raises(TypeError):
        DatasetVersion.create(  # type: ignore[call-arg]
            version_id="dsv_forged",
            owner_id=SCOPE,
            source=SOURCE,
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


def test_the_admitted_source_value_object_carries_no_stored_only_field() -> None:
    """Grouping parameters must not smuggle back what `create` may not accept.

    `AdmittedSource` exists to keep `create`'s argument count within the
    repository's threshold, following the value-object grouping the design
    notes require. That refactor would be a regression if the value object
    itself could carry `version_id` or `sealed_at`, because a caller would then
    supply through `source=` exactly what the two-door rule keeps out of
    `create`.
    """
    assert _field_names(AdmittedSource) == {
        "plaintext_digest",
        "ciphertext_digest",
        "size_bytes",
        "media_type",
        "manifest_digest",
        "mapping_version",
        "admission_outcome",
    }


@pytest.mark.parametrize("record_type", [DatasetVersion, AnalysisRun, ArtifactBinding])
def test_the_shared_builder_cannot_construct_outside_a_door(record_type: type) -> None:
    """Extracting the duplicated door bodies must not create a fourth construction channel.

    `_build` holds the constructor call both doors share, so a caller reaching it directly would
    have `create`'s effect without `create`'s signature — the stored-only fields `create` refuses
    would arrive positionally. It is safe only because it is called *inside* an already-open door
    and `records.py` refuses a bare constructor call otherwise; this asserts that refusal rather
    than assuming it, because the guard lives in another module and a change there would disarm
    this one silently.
    """
    arguments = {
        DatasetVersion: ("dsv_forged", SCOPE, SOURCE, VersionLifecycle(created_at=NOW)),
        AnalysisRun: (
            RunSubject(run_id="run_forged", owner_id=SCOPE, version_id="dsv_abc123"),
            RunOutcome(state="started"),
            NOW,
        ),
        ArtifactBinding: (
            "run_abc123",
            SCOPE,
            PublishedArtifact(surface="web", artifact_digest="sha256:" + "d" * 64),
            NOW,
        ),
    }[record_type]
    with pytest.raises(TypeError, match="through create"):
        record_type._build(*arguments)


# --- The run-state vocabulary is enforced, not merely published -----------------------------


@pytest.mark.parametrize("state", ["started", "completed", "failed"])
def test_every_published_run_state_is_accepted(state: str) -> None:
    """Each state, carrying the minimum that state legally requires.

    Not a bare `RunOutcome(state=...)` for all three: `#370` added an `FR-111` rule that a
    `completed` outcome must name the package it produced, so the bare form is refused for that
    one. Passing the provenance keeps this assertion about the *vocabulary* -- is this state
    named? -- rather than silently also asserting that every state is constructible empty, which
    is a different and now false claim.
    """
    provenance = (
        {
            "package_digest": "sha256:abc",
            "package_version": "1.0.0",
            "formula_version": "1.0.0",
            "completed_at": datetime(2026, 9, 4, 13, 0, tzinfo=UTC),
        }
        if state == RUN_COMPLETED
        else {}
    )

    assert RunOutcome(state=state, **provenance).state == state


def test_a_completed_outcome_without_provenance_is_refused() -> None:
    """The other half of the state check, added on `#370`.

    A state being *named* and an outcome being *complete* are different properties, and the
    vocabulary test above asserts only the first. `FR-111` binds a run to the package it produced,
    so a `completed` outcome that names none cannot be constructed -- the store writes it
    permanently and the append-only guard then refuses to fill the digest in later.
    """
    with pytest.raises(ValueError, match="must carry the package digest"):
        RunOutcome(state=RUN_COMPLETED)


@pytest.mark.parametrize("state", ["cancelled", "STARTED", "", "pending", "deleted"])
def test_a_state_the_domain_does_not_define_is_refused(state: str) -> None:
    """`RUN_STATES` published a vocabulary and nothing read it (CodeRabbit, #368).

    `RunOutcome(state="cancelled")` was accepted and `_from_storage` copied it into a sealed
    `AnalysisRun`, so a state no surface can render reached a record that looks authoritative.
    This is the *defined but never attached* shape: the constraint had a comment claiming the
    domain, the store and the schema restrict the same values, and no code path enforcing it.

    Sealing could not have caught it. A door proves a record was constructed through it; it
    never proves the door checked its arguments.
    """
    with pytest.raises(ValueError, match="not one of the states"):
        RunOutcome(state=state)


def test_the_refusal_does_not_echo_the_rejected_value() -> None:
    """Content-free refusals, per `rca/errors.py`: a message must not carry caller input."""
    with pytest.raises(ValueError) as caught:
        RunOutcome(state="acme-pharmacy-cancelled")
    assert "acme" not in str(caught.value).lower()


def test_a_started_run_reports_a_state_the_vocabulary_names() -> None:
    run = AnalysisRun.create(owner_id=SCOPE, version_id="dsv_abc123", now=NOW)
    assert run.state in RUN_STATES


# --- The grouping value objects are held to the same field-set equality --------------------


def test_the_version_lifecycle_value_object_carries_only_its_two_instants() -> None:
    """`VersionLifecycle` groups `created_at` and `sealed_at` to keep `_build` at four arguments.

    Asserted as an equality rather than an absence, for the reason this whole module is written
    that way: an absence test cannot see a field *added*. A `VersionLifecycle` that grew a
    `purged_at` or a `retention_state` would be `W1-02`'s store state arriving through a door
    that only allocates, and the equality fails before such a field can be read.
    """
    assert _field_names(VersionLifecycle) == {"created_at", "sealed_at"}


def test_the_run_subject_value_object_carries_no_outcome() -> None:
    """`RunSubject` names which run over which version in which scope -- never what it produced.

    `FR-111` puts the package digest and the versions on the real pipeline. If this value object
    could carry one, `AnalysisRun.create` would accept a completed run through `subject=` exactly
    as `test_create_cannot_be_given_a_completion` forbids through a flat parameter -- which is the
    regression a grouping refactor is capable of introducing silently.
    """
    assert _field_names(RunSubject) == {"run_id", "owner_id", "version_id"}


def test_the_published_artifact_value_object_cannot_backdate_a_publication() -> None:
    """`PublishedArtifact` pairs a surface with its digest, and carries no instant.

    `published_at` stays a parameter of the door. A value object that carried it would let a
    caller supply a publication time through `artifact=`, and `ArtifactBinding.create` is a real
    door rather than an internal helper -- so this is the one grouping where a smuggled field
    would be reachable from outside the module.
    """
    assert _field_names(PublishedArtifact) == {"surface", "artifact_digest"}


def test_grouping_did_not_widen_what_a_creation_door_accepts() -> None:
    """The refactor's own risk, asserted directly: no door gained a stored-only parameter.

    Parameter grouping was applied to bring eleven functions within the repository's
    four-argument threshold. The threshold is a code-health measure and the two-door rule is a
    correctness one, so satisfying the first must not spend the second. Each creation door is
    re-checked here against the field sets its value objects can express.
    """
    import inspect

    creation_parameters = {
        name
        for door in (DatasetVersion.create, AnalysisRun.create, ArtifactBinding.create)
        for name in inspect.signature(door).parameters
    }
    reachable = set(creation_parameters)
    for group in (AdmittedSource, PublishedArtifact):
        reachable |= _field_names(group)

    assert "sealed_at" not in reachable
    assert "version_id" not in _field_names(AdmittedSource)
    assert reachable & {"package_digest", "package_version", "formula_version"} == set()
