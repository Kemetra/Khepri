"""Every row lock the `W1-02` workspace takes, and the guard each one protects.

Gathered from three modules on `#370` because the argument for each lock is the same argument:
SQLite emits no `FOR UPDATE` and SQLAlchemy silently omits it for that dialect, so a lock removed
leaves the whole suite green. Each statement is therefore *named*, compiled here against the
PostgreSQL dialect to prove the clause, and asserted at its call site by source -- the honest
maximum when the engine cannot show the race. `test_rca001_lock_scope.py` is the other half: only
methods it names may reach one of these.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import sessionmaker

from khepri.rca.accounts import AccountService
from khepri.rca.organizations import OrganizationService
from khepri.rca.persistence import SqlAccountStore, SqlOrganizationStore
from khepri.rca.workspace.contracts import (
    AdmittedSource,
    DatasetVersion,
)
from khepri.rca.workspace.persistence import (
    SqlWorkspaceStore,
    run_for_update,
    version_for_update,
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


# --- Named locking statements, compiled and asserted at their call sites --------------------


@pytest.mark.parametrize(
    ("statement", "table"),
    [
        (run_for_update("run_abc123"), "rca_workspace_analysis_runs"),
        (version_for_update("dsv_abc123"), "rca_workspace_dataset_versions"),
    ],
)
def test_the_locking_statements_emit_for_update_on_postgres(statement, table: str) -> None:
    """Compiled against the PostgreSQL dialect, because SQLite cannot show this.

    `rca/persistence.py` states the reason at `account_for_update`: SQLite emits no `FOR UPDATE`
    and SQLAlchemy silently omits it for that dialect, so a lock someone later removed would leave
    the whole suite green. Naming the statement is what makes it compilable here without a
    database, and this test is the half that makes the naming worth anything.
    """
    from sqlalchemy.dialects import postgresql

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in compiled
    assert table in compiled


def test_completing_a_run_locks_the_row_it_reads(factory: sessionmaker) -> None:
    """`complete_analysis_run` reads the state and then writes on it, which is not atomic.

    Two workers could both read `started`, both pass the check, and the second overwrite the
    first's package digest and version provenance while both reported success. `FR-111` binds a run
    to the versions it actually derived under, so a lost write there is lost provenance. Review on
    `#370` found it.

    Asserted on the *statement* rather than by racing two threads, because SQLite serializes writes
    anyway and a concurrency test on this engine would pass with the lock removed -- the guard
    would be green against the defect it exists to catch.
    """
    import inspect as py_inspect

    source = py_inspect.getsource(SqlWorkspaceStore.complete_analysis_run)

    assert "run_for_update" in source
    assert "database.get(AnalysisRunRow" not in source


@pytest.mark.parametrize(
    ("statement", "table"),
    [
        (run_for_update("run_abc123", "own_abc123"), "rca_workspace_analysis_runs"),
        (version_for_update("dsv_abc123", "own_abc123"), "rca_workspace_dataset_versions"),
    ],
)
def test_a_scoped_lock_names_the_scope_in_its_predicate(statement, table: str) -> None:
    """When the caller passes `owner_id`, the lock statement constrains it -- so a cross-tenant
    identifier locks nothing rather than holding another tenant's row for the transaction.

    Compiled against PostgreSQL like its unscoped sibling above, and asserted on the predicate's
    presence: SQLite cannot show a lock, and a race across two tenants here would pass regardless.
    """
    from sqlalchemy.dialects import postgresql

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in compiled
    assert table in compiled
    assert "owner_id =" in compiled


def test_the_retention_transition_locks_the_row_it_reads() -> None:
    """The clock cannot move on a concurrent duplicate, and only a lock can promise that.

    Asserted on the source rather than by racing two sessions, and the reason is the defect's own
    history: SQLite serializes writes, so two calls run in sequence, the second genuinely reads
    `tombstoned`, and the no-op check returns early -- a concurrency test on this engine passes
    with the lock removed. I removed the lock on this PR on exactly that evidence, and two
    reviewers found the PostgreSQL interleaving the engine had hidden: both transactions read
    `active`, both find the check false, and the second overwrites the first deletion instant.

    `test_the_locking_statements_emit_for_update_on_postgres` is the other half -- it compiles the
    statement and asserts the clause is really there.
    """
    import inspect as py_inspect

    source = py_inspect.getsource(SqlWorkspaceStore.set_retention_state)

    assert "version_for_update" in source
    assert "database.get(DatasetVersionRow" not in source


def test_adding_a_derivative_locks_its_parent(factory: sessionmaker) -> None:
    """The liveness check is a read-then-insert, and only a lock closes that window.

    Asserted on the source, for the reason recorded at `account_for_update` and at every other
    lock in this slice: SQLite serializes writes, so a two-session race here passes with the lock
    removed. `tombstone_dataset_version` takes the same `version_for_update`, so the two serialize
    -- a run lands either before the deletion, and cascades with it, or is refused after.
    `test_rca001_lock_scope.py` names both methods for this.
    """
    import inspect as py_inspect

    run_source = py_inspect.getsource(SqlWorkspaceStore.add_analysis_run)
    binding_source = py_inspect.getsource(SqlWorkspaceStore.add_artifact_binding)

    # The scope argument is asserted too: without it a cross-tenant identifier would hold another
    # tenant's row for the transaction, and no SQLite test can observe that lock either.
    assert "version_for_update(run.version_id, run.owner_id)" in run_source
    assert "run_for_update(binding.run_id, binding.owner_id)" in binding_source
