"""Run completion under `FR-111`: what a completed run must carry, and when it may not complete.

Split from `test_w102_workspace_guards.py` on `#370`. Three layers enforce the same rule and each
has its own test -- `RunOutcome` at the door, the `CHECK` at the schema, and the guard on the ORM
completion path -- plus the terminal-state rule that a tombstoned run cannot be completed, and the
positive direction that a live one still can.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.workspace.contracts import (
    RUN_COMPLETED,
    RUN_FAILED,
    AdmittedSource,
    AnalysisRun,
    DatasetVersion,
    RunOutcome,
)
from khepri.rca.workspace.persistence import (
    RETENTION_ACTIVE,
    RETENTION_TOMBSTONED,
    AnalysisRunRow,
    SqlWorkspaceStore,
)
from tests.rca_lifecycle_support import (  # noqa: F401 -- factory is a pytest fixture
    CREDENTIAL,
    EMAIL,
    factory_fixture,
)

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 4, 13, 0, tzinfo=UTC)

SOURCE = AdmittedSource(
    plaintext_digest="sha256:" + "a" * 64,
    ciphertext_digest="sha256:" + "b" * 64,
    size_bytes=2048,
    media_type="text/csv",
    manifest_digest="sha256:" + "c" * 64,
    mapping_version="rra003.mapping.v3",
    admission_outcome="admitted",
)

WORKSPACE_TABLES = (
    "rca_workspace_dataset_versions",
    "rca_workspace_analysis_runs",
    "rca_workspace_artifact_bindings",
    "rca_workspace_source_profiles",
    "rca_workspace_tombstones",
)


def _scope(factory: sessionmaker, email: str = EMAIL, name: str = "Acme Pharmacy") -> str:
    """One organization, returning the opaque isolation scope every workspace row is keyed by.

    Built through the real service rather than by inserting a row, because the workspace tables
    carry a foreign key onto `rca_isolation_scopes.owner_id` and a hand-made scope would not
    satisfy it -- which is the constraint several tests here are about.

    Parameterized by email so an isolation test can raise a *second* scope, which is the only way
    to see a missing `WHERE`: with one organization's rows in the table, an unfiltered query
    returns exactly what a filtered one does.
    """
    accounts = SqlAccountStore(factory)
    account = AccountService(accounts).create_account(email, CREDENTIAL)
    organizations = SqlOrganizationStore(factory)
    organization = OrganizationService(organizations).create_organization(
        name, account.account_id, now=NOW
    )
    scope = organizations.get_scope(organization.organization_id)
    assert scope is not None, "creating an organization allocates its isolation scope"
    return scope.owner_id


def _version(store: SqlWorkspaceStore, scope: str) -> DatasetVersion:
    return store.add_dataset_version(DatasetVersion.create(owner_id=scope, source=SOURCE, now=NOW))


# --- FR-111: a completion carries its provenance, once, and never on a deleted run -------------


def test_a_run_that_never_completed_cannot_have_a_package_written_to_it(
    factory: sessionmaker,
) -> None:
    """`FR-111` puts the digest on the pipeline, and only the completion transition records it.

    Writing a package field without moving the state is not a completion -- it is a run claiming a
    result it never declared finishing -- so it is refused even while the run is still `started`.
    `complete_analysis_run` is the one path that writes these columns.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )

    with (
        pytest.raises(ValueError, match="cannot be completed again"),
        factory.begin() as database,
    ):
        row = database.get(AnalysisRunRow, run.run_id)
        row.package_digest = "sha256:" + "8" * 64


def test_a_completion_must_carry_the_provenance_fr_111_requires() -> None:
    """`RunOutcome(state="completed")` validated with every provenance field `None`.

    `complete_analysis_run` then wrote it permanently and the append-only guard refused to fill
    the digest in later, leaving an immutable completed run naming no package. `FR-111` binds a run
    to what it produced, so an outcome that cannot name it is not a completion. Review on `#370`
    found it.
    """
    with pytest.raises(ValueError, match="must carry the package digest"):
        RunOutcome(state=RUN_COMPLETED)


@pytest.mark.parametrize(
    "missing", ["package_digest", "package_version", "formula_version", "completed_at"]
)
def test_a_completion_needs_every_provenance_field(missing: str) -> None:
    """One case per field, because a check reading only the digest passes three of these.

    Verified as a mutant: narrowing `_has_provenance` to `package_digest` alone leaves the
    single-case version of this test green.
    """
    complete = {
        "package_digest": "sha256:abc",
        "package_version": "1.0.0",
        "formula_version": "1.0.0",
        "completed_at": LATER,
    }
    complete[missing] = None

    with pytest.raises(ValueError, match="must carry the package digest"):
        RunOutcome(state=RUN_COMPLETED, **complete)


def test_a_failed_run_needs_no_provenance() -> None:
    """State-specific, not blanket: `failed` produced no package, so it names none."""
    assert RunOutcome(state=RUN_FAILED).package_digest is None


def test_a_tombstoned_run_cannot_be_completed(factory: sessionmaker) -> None:
    """The terminal check ran *inside* the completion branch's alternative, so it never fired.

    A tombstoned run still reads `started`, so `_refuse_content_update` took the completion branch
    and returned before `_check_terminal_state` -- and a deleted run could be given a package
    digest and a completion instant. Confirmed against the guard before fixing. Review on `#370`
    found it, and the fix is ordering: terminal state is a precondition on every path, not one
    more append-only rule.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    with factory.begin() as database:
        database.get(AnalysisRunRow, run.run_id).retention_state = RETENTION_TOMBSTONED

    with (
        pytest.raises(ValueError, match="accepts no further update"),
        factory.begin() as database,
    ):
        row = database.get(AnalysisRunRow, run.run_id)
        row.state = RUN_COMPLETED
        row.package_digest = "sha256:abc"
        row.package_version = "1.0.0"
        row.formula_version = "1.0.0"
        row.completed_at = LATER


def test_a_live_run_can_still_be_completed(factory: sessionmaker) -> None:
    """The ordering fix must not have made completion itself unreachable.

    The append-only guard had already made run completion impossible once on this PR; a check
    hoisted to run before every branch is exactly the shape that does it again.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )

    completed = store.complete_analysis_run(
        run.run_id,
        RunOutcome(
            state=RUN_COMPLETED,
            package_digest="sha256:abc",
            package_version="1.0.0",
            formula_version="1.0.0",
            completed_at=LATER,
        ),
    )

    assert completed is True


@pytest.mark.parametrize(
    "missing", ["package_digest", "package_version", "formula_version", "completed_at"]
)
def test_a_completed_row_without_provenance_is_refused_by_the_schema(
    factory: sessionmaker,
    missing: str,
) -> None:
    """Stated in the schema as well as in `RunOutcome`, and the duplication is the point.

    Enforced only in the dataclass, a malformed row still reaches the database -- and then raises
    on *read*, when `_run_from_row` constructs the `RunOutcome`. `analysis_runs_for_scope` fails
    for the whole scope, so one bad row becomes an outage for every run in the organization.
    Review on `#370` traced that path.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    provenance = {
        "package_digest": "sha256:abc",
        "package_version": "1.0.0",
        "formula_version": "1.0.0",
        "completed_at": LATER,
    }
    provenance[missing] = None

    # One case per field: a `CHECK` naming only `package_digest` satisfies three of these, and a
    # single all-fields-null case cannot tell that apart. Confirmed as mutant `K3`, which survived
    # the unparametrized version of this test.
    with pytest.raises(IntegrityError), factory.begin() as database:
        database.add(
            AnalysisRunRow(
                run_id=f"run_no{missing[:5]}",
                version_id=version.version_id,
                owner_id=scope,
                state=RUN_COMPLETED,
                started_at=NOW,
                retention_state=RETENTION_ACTIVE,
                **provenance,
            )
        )


@pytest.mark.parametrize("state", ["started", "failed"])
def test_a_non_completed_row_needs_no_provenance(factory: sessionmaker, state: str) -> None:
    """Conditional rather than `NOT NULL`: those states produced no package."""
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)

    with factory.begin() as database:
        database.add(
            AnalysisRunRow(
                run_id=f"run_{state}p",
                version_id=version.version_id,
                owner_id=scope,
                state=state,
                started_at=NOW,
                retention_state=RETENTION_ACTIVE,
            )
        )

    with factory() as database:
        assert database.get(AnalysisRunRow, f"run_{state}p") is not None


@pytest.mark.parametrize(
    "missing", ["package_digest", "package_version", "formula_version", "completed_at"]
)
def test_an_orm_writer_cannot_complete_a_run_without_provenance(
    factory: sessionmaker,
    missing: str,
) -> None:
    """The third layer, and the one the other two miss.

    `RunOutcome.__post_init__` guards the door and `ck_rca_workspace_run_completion_provenance`
    guards the schema, but an ORM writer can load a `started` row and assign **only**
    `state = "completed"` -- which satisfies `_check_completion`'s changed-column allowlist while
    every provenance column stays null, and the `CHECK` is not re-evaluated for columns the
    statement does not touch. The row commits, then raises on *read* when `_run_from_row` builds
    the outcome, failing the whole scope's listing. Review on `#370` found it after the
    `RunOutcome` fix -- the same rule, one layer up.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )

    provenance = {
        "package_digest": "sha256:abc",
        "package_version": "1.0.0",
        "formula_version": "1.0.0",
        "completed_at": LATER,
    }
    provenance.pop(missing)

    # One case per field. This is the third place the same rule lives and the third time a single
    # all-fields-missing case proved too weak to pin it: mutant `L7`, narrowing the guard to
    # `package_digest` alone, survived that version. Any multi-field requirement needs a case per
    # field, because one omission cannot distinguish "checks one" from "checks all".
    with (
        pytest.raises(ValueError, match="must carry the package digest"),
        factory.begin() as database,
    ):
        row = database.get(AnalysisRunRow, run.run_id)
        row.state = RUN_COMPLETED
        for column, value in provenance.items():
            setattr(row, column, value)


def test_the_scope_listing_survives_every_run_a_writer_can_commit(
    factory: sessionmaker,
) -> None:
    """The consequence the finding named, asserted rather than reasoned about.

    A malformed completed row makes `analysis_runs_for_scope` raise for *every* run in the
    organization -- one bad row becomes an outage. With all three layers in place no writer can
    commit one, so the listing is total.
    """
    scope = _scope(factory)
    store = SqlWorkspaceStore(factory)
    version = _version(store, scope)
    run = store.add_analysis_run(
        AnalysisRun.create(owner_id=scope, version_id=version.version_id, now=NOW)
    )
    store.complete_analysis_run(
        run.run_id,
        RunOutcome(
            state=RUN_COMPLETED,
            package_digest="sha256:abc",
            package_version="1.0.0",
            formula_version="1.0.0",
            completed_at=LATER,
        ),
    )

    listed = store.analysis_runs_for_scope(scope)

    assert [entry.run_id for entry in listed] == [run.run_id]
