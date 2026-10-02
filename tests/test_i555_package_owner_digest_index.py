"""#555 D-01: `get_owned_package` is served by `ix_package_owner_digest`.

`20261002_0035` indexes `rra_fact_packages (owner_id, package_digest)`. The evidence that it earns
its place (a 32.9 ms parallel sequential scan becoming a 0.05 ms index scan at 200,000 packages) is
in `docs/superpowers/plans/2026-10-02-555-d01-index-evidence.md`. These tests prove the index
exists at head, is gone after a downgrade, and is what the production statement uses.

The DDL tests need PostgreSQL and run under the `concurrency` marker, so a skip in CI fails the
build. The model test runs everywhere.
"""

from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.dialects import postgresql

from khepri.rra.persistence import FactPackageRow
from tests.test_i593_profile_outlives_upload import (
    postgres_fixture,  # noqa: F401 -- the `postgres` fixture, shared with #593's DDL tests
    requires_postgres,
)

PARENT_REVISION = "20260926_0034"
INDEX = "ix_package_owner_digest"
COLUMNS = ["owner_id", "package_digest"]


def _index(engine: Engine) -> dict | None:
    indexes = inspect(engine).get_indexes("rra_fact_packages")
    return next((entry for entry in indexes if entry["name"] == INDEX), None)


def test_the_model_declares_the_index_the_migration_creates() -> None:
    indexes = FactPackageRow.__table__.indexes
    declared = {index.name: [column.name for column in index.columns] for index in indexes}

    assert declared[INDEX] == COLUMNS


@pytest.mark.concurrency
@requires_postgres
class TestTheIndexOnPostgres:
    def test_head_carries_the_index_over_both_columns(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        _config, engine = postgres
        entry = _index(engine)

        assert entry is not None
        assert entry["column_names"] == COLUMNS
        assert not entry["unique"], "two profiles with identical facts can share a digest"

    def test_downgrade_removes_it_and_upgrade_restores_it(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        config, engine = postgres

        command.downgrade(config, PARENT_REVISION)
        assert _index(engine) is None

        command.upgrade(config, "head")
        assert _index(engine) is not None

    def test_upgrade_is_safe_to_repeat_after_an_interrupted_build(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        """`if_not_exists`: a retry over an index that is already there does not fail."""
        config, engine = postgres
        command.downgrade(config, PARENT_REVISION)
        with engine.begin() as connection:
            connection.execute(
                text(f"create index {INDEX} on rra_fact_packages (owner_id, package_digest)")
            )

        command.upgrade(config, "head")

        assert _index(engine) is not None

    def test_the_owned_package_statement_can_use_it(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        """The index serves the predicate the store emits, not just a hand-written one."""
        _config, engine = postgres
        statement = select(FactPackageRow).where(
            FactPackageRow.package_digest == "d" * 64,
            FactPackageRow.owner_id == "own_a",
        )
        sql = str(
            statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
        )

        with engine.begin() as connection:
            connection.execute(text("set local enable_seqscan = off"))
            plan = "\n".join(row[0] for row in connection.execute(text("explain " + sql)))

        assert INDEX in plan, plan
