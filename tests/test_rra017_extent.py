"""RRA-017 Verification 9, 10 and 11: the table extent and its classification (`#595`).

**Not RED, deliberately.** These properties already hold at `0c1475f`, so a strict `xfail` would
XPASS and fail the run. They are plain tests that pin the extent the policies are built over:

- **Verification 11.** Importing every module under `khepri.rra` (`pkgutil.walk_packages`, not
  `khepri.rra.persistence` alone, which misses `rra_operational_events`) yields a set of tables,
  and the migrated catalogue holds the same set. The catalogue half runs on PostgreSQL.
- **Verification 9.** The tables in that extent without `owner_id` are exactly `FR-231`'s five.
- **Verification 10.** `FR-237`'s import tests are the existing ones and are not restated here:
  `tests/test_r707_commercial_bridge.py` and `tests/test_rca001_boundary.py`.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.rra017_support import (
    COVERED_TABLES,
    PARENT_WALLED,
    PRE_SCOPE_TABLES,
    migrated_owner_engine,
    rra_tables,
)
from tests.w110_postgres_support import requires_postgres

#: `FR-231`'s table, as the specification states it.
WITHOUT_OWNER = frozenset(PARENT_WALLED) | frozenset(PRE_SCOPE_TABLES)


def test_the_metadata_extent_is_the_eight_owned_and_five_unowned_tables() -> None:
    tables = rra_tables()
    assert set(tables) == set(COVERED_TABLES) | set(PRE_SCOPE_TABLES)


def test_the_tables_without_owner_id_are_exactly_fr231s_five() -> None:
    unowned = {name for name, table in rra_tables().items() if "owner_id" not in table.columns}
    assert unowned == WITHOUT_OWNER


def test_persistence_alone_misses_a_table_so_the_walk_is_required() -> None:
    """The reason `FR-230` derives the extent by walking the package."""
    from khepri.rra.persistence import Base

    walked = set(rra_tables())
    assert "rra_operational_events" in walked
    assert walked >= set(Base.metadata.tables)


@pytest.mark.concurrency
@requires_postgres
def test_the_migrated_catalogue_holds_the_same_rra_tables() -> None:
    engine = migrated_owner_engine()
    try:
        with engine.connect() as connection:
            names = connection.scalars(
                text(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' "
                    "AND tablename LIKE 'rra\\_%'"
                )
            ).all()
    finally:
        engine.dispose()
    assert set(names) == set(rra_tables())
