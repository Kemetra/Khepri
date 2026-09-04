"""`20260822_0020` against a real PostgreSQL, which is the only place it can be proved.

**Why this file exists separately.** The revision swaps CHECK constraints and drops a
column a CHECK references. SQLite can do neither -- `NotImplementedError: No support
for ALTER of constraints in SQLite dialect`, and then `error in table
rra_report_artifacts after drop column` -- so the SQLite-backed guards in
`test_rca001_migration.py` account for the column delta as data and leave the DDL
unproven. This runs the real thing.

**What it proves, and why each part matters.**

The constraints must *exist* after upgrade, or `KHEPRI-DEC-008`'s governed algorithm is
a convention rather than a rule. They must *refuse* the values they name -- and the
`aws:kms` case is the load-bearing one, because the retired schema **required** that
exact string, so a migration that dropped the old CHECK without adding the new one
would leave the column accepting anything and every test here still passing.

Downgrade must restore what it replaced. A one-way migration is not reversible
evidence, and `RRA-002` deletion semantics depend on the schema meaning what the prior
revision said it meant.

**This runs in CI, and a skip there is a failure.** The `pytest` job already attaches a
pinned PostgreSQL service and exposes `KHEPRI_TEST_DATABASE_URL`, so this file reuses
that rather than asking for infrastructure of its own. It carries the `concurrency`
marker for one reason: `.github/scripts/require_concurrency_tests.py` fails the build if
any test with that marker skipped, which is exactly the protection DDL evidence needs.
Without the marker this file would pass by skipping and read as proved.

The marker is a slight stretch of its name -- nothing here is concurrent -- but the
guarantee it buys is the right one, and inventing a second marker plus a second guard
script to say "this needs the database" would duplicate a mechanism that already exists.

Locally the file skips when the variable is unset, so the offline suite still runs.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

REPO_ROOT = Path(__file__).resolve().parents[1]

REVISION = "20260822_0020"
PARENT = "20260821_0019"

TABLES = ("rra_uploads", "rra_report_artifacts")

# The constraints the revision must create, per table prefix.
ENVELOPE_CHECKS = {
    "rra_uploads": (
        "ck_upload_envelope_encryption",
        "ck_upload_ciphertext_sha256_length",
        "ck_upload_envelope_version",
    ),
    "rra_report_artifacts": (
        "ck_report_artifact_encryption",
        "ck_report_artifact_ciphertext_sha256_length",
        "ck_report_artifact_envelope_version",
    ),
}

RETIRED_CHECK = {
    "rra_uploads": "ck_upload_kms_encryption",
    "rra_report_artifacts": "ck_report_artifact_encryption",
}

# The variable CI already sets. Deliberately not a new one: a private variable would
# make this file local-only forever, which is how a migration regression test stops
# being a regression test.
DATABASE_URL_VARIABLE = "KHEPRI_TEST_DATABASE_URL"

# See the module docstring: this is what makes a skip in CI a build failure.
pytestmark = pytest.mark.concurrency

DATABASE_URL = os.environ.get(DATABASE_URL_VARIABLE)

requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason=f"{DATABASE_URL_VARIABLE} is unset; this DDL cannot be proved on SQLite",
)


def _drop_public_schema(engine) -> None:
    """Return the shared database to empty, whatever state a run left it in.

    `CASCADE` is correct here and only here: the target is a disposable test database,
    and the alternative is a fixture that cannot clean up after a failed migration.
    """
    with engine.begin() as connection:
        connection.execute(text("drop schema public cascade"))
        connection.execute(text("create schema public"))


@pytest.fixture(name="migrated")
def migrated_fixture():
    """A database at head, returned to head afterwards rather than to base.

    Teardown deliberately stops at this revision's own boundary. `downgrade` to
    `base` cannot run on this chain at all: `20260817_0017` (`#205`) drops
    `uq_session_owner_scope`, and `fk_upload_session_scope` and
    `fk_deletion_session_scope` depend on that index, so PostgreSQL refuses without
    `CASCADE`. That is a pre-existing defect in a revision this slice does not own
    and must not repair here, so the fixture stays inside the range it is testing.
    """
    assert DATABASE_URL is not None
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    engine = create_engine(DATABASE_URL)
    _drop_public_schema(engine)
    command.upgrade(config, "head")
    try:
        yield config, engine
    finally:
        # The schema is dropped rather than downgraded, and rather than left at head.
        #
        # Downgrading to `base` is impossible on this chain: `20260817_0017` (`#205`)
        # drops `uq_session_owner_scope` while `fk_upload_session_scope` and
        # `fk_deletion_session_scope` depend on it, and PostgreSQL refuses without
        # `CASCADE`. That defect belongs to that revision and is not repaired here.
        #
        # Leaving the schema in place is worse than either: this file shares CI's one
        # `KHEPRI_TEST_DATABASE_URL` database with the concurrency tests, whose fixture
        # calls `Base.metadata.drop_all`. That cannot drop an Alembic-created table
        # absent from the metadata it knows, so `rra_report_deliveries` fails on
        # `fk_report_artifact_delivery` and those tests error -- which this file
        # observed doing before the drop was added.
        _drop_public_schema(engine)
        engine.dispose()


def _check_names(engine, table: str) -> set[str]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "select con.conname from pg_constraint con "
                "join pg_class rel on rel.oid = con.conrelid "
                "where rel.relname = :table and con.contype = 'c'"
            ),
            {"table": table},
        )
        return {row[0] for row in rows}


def _columns(engine, table: str) -> set[str]:
    return {column["name"] for column in inspect(engine).get_columns(table)}


@requires_postgres
def test_the_chain_reaches_this_revision(migrated) -> None:
    """This revision is applied on the way to head -- not that it *is* head.

    It asserted equality with `REVISION` until `W1-02` added `20260904_0021` and the equality
    failed. That was the right failure for the wrong reason: the fixture upgrades to `"head"`, so
    the assertion was never about this module's revision at all. It was a third place recording
    which revision is head, in a file scoped to one revision's DDL -- and a global claim that any
    later migration falsifies.

    Two guards already own that claim and are updated by each slice that adds a migration:
    `test_the_head_is_the_session_revision` pins the identifier, and
    `test_the_stated_migration_head_is_the_real_head` compares the documented head to the tree's.
    This module's own docstring claims no head guardianship.

    What it needs is ancestry: `20260822_0020` must be in the chain the fixture actually ran, or
    the constraints the rest of this file asserts were never created. `REVISION` stays a literal
    because `test_the_downgrade_restores_the_prior_schema` downgrades to `PARENT` and back to it --
    bumping the constant would silently retarget this file's DDL evidence at a later revision.
    """
    config, engine = migrated
    with engine.connect() as connection:
        current = connection.execute(text("select version_num from alembic_version")).scalar()

    applied = {
        revision.revision
        for revision in ScriptDirectory.from_config(config).iterate_revisions(current, "base")
    }

    assert REVISION in applied, f"{REVISION} is not an ancestor of {current}"


@requires_postgres
@pytest.mark.parametrize("table", TABLES)
def test_the_envelope_columns_replace_the_kms_column(migrated, table: str) -> None:
    _, engine = migrated
    columns = _columns(engine, table)

    assert "kms_key_id" not in columns
    assert {"envelope_version", "ciphertext_sha256_hex"} <= columns


@requires_postgres
@pytest.mark.parametrize("table", TABLES)
def test_every_envelope_constraint_exists(migrated, table: str) -> None:
    _, engine = migrated
    names = _check_names(engine, table)

    for expected in ENVELOPE_CHECKS[table]:
        assert expected in names, f"{table} is missing {expected}"


@requires_postgres
def test_the_retired_aws_constraint_is_gone(migrated) -> None:
    """`ck_upload_kms_encryption` named `aws:kms` directly and must not survive."""
    _, engine = migrated

    assert RETIRED_CHECK["rra_uploads"] not in _check_names(engine, "rra_uploads")


@dataclass(frozen=True, slots=True)
class _Refusal:
    """One row that must not be insertable, and the constraint that stops it."""

    algorithm: str
    version: int
    digest: str
    constraint: str


REFUSALS = (
    # The load-bearing row: the retired schema *required* this value, so a migration
    # that dropped the old CHECK without adding the new one would accept it.
    _Refusal("aws:kms", 1, "c" * 64, "ck_upload_envelope_encryption"),
    _Refusal("AES256", 1, "c" * 64, "ck_upload_envelope_encryption"),
    _Refusal("AES-256-GCM", 1, "c" * 63, "ck_upload_ciphertext_sha256_length"),
    _Refusal("AES-256-GCM", 0, "c" * 64, "ck_upload_envelope_version"),
)


@requires_postgres
@pytest.mark.parametrize("refusal", REFUSALS, ids=lambda r: r.constraint)
def test_the_constraints_refuse_what_they_name(migrated, refusal: _Refusal) -> None:
    """Existence is not enforcement. Each constraint must reject a real insert."""
    from sqlalchemy.exc import IntegrityError  # noqa: PLC0415

    _, engine = migrated
    statement = text(
        "insert into rra_uploads (upload_id, owner_id, session_id, object_key, size_bytes,"
        " sha256_hex, media_type, created_at, expires_at, encryption_algorithm,"
        " envelope_version, ciphertext_sha256_hex) values ('u', 'o', 's', 'k', 1, :sha,"
        " 'text/csv', now(), now() + interval '1 day', :alg, :ver, :ct)"
    )
    with pytest.raises(IntegrityError) as raised, engine.begin() as connection:
        connection.execute(
            statement,
            {
                "sha": "a" * 64,
                "alg": refusal.algorithm,
                "ver": refusal.version,
                "ct": refusal.digest,
            },
        )

    assert refusal.constraint in str(raised.value)


@requires_postgres
@pytest.mark.parametrize("table", TABLES)
def test_downgrade_restores_the_previous_schema(migrated, table: str) -> None:
    """A migration that cannot be reversed is not reversible evidence."""
    config, engine = migrated
    command.downgrade(config, PARENT)

    columns = _columns(engine, table)
    assert "kms_key_id" in columns
    assert not {"envelope_version", "ciphertext_sha256_hex"} & columns
    assert RETIRED_CHECK[table] in _check_names(engine, table)

    # Back to head so the fixture's teardown starts from where it expects.
    command.upgrade(config, "head")
