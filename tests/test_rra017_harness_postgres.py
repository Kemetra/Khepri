"""The RRA-017 role guard refuses a superuser and a `SET ROLE` shortcut (`#595`).

**Not RED.** This tests the instrument, not the slice, and it holds at `0c1475f`. It is the
mutation check `tests/rra017_support.py`'s guard needs: every RLS test there runs on an engine
whose connections call `assert_connected_as` first, and a superuser connection passing it would
make every one of them vacuous, because a superuser bypasses row-level security even under
`FORCE`. A guard that raised an `AssertionError` would be absorbed by the RED `xfail`, so it
raises `HarnessError`, which no RED test names.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from tests.rra017_support import (
    APPLICATION,
    POSTGRES,
    HarnessError,
    assert_connected_as,
    guarded_engine,
)
from tests.w110_postgres_support import DATABASE_URL

pytestmark = list(POSTGRES)


def test_a_superuser_connection_fails_the_guard() -> None:
    engine = guarded_engine(DATABASE_URL, APPLICATION)
    try:
        with pytest.raises(HarnessError), engine.connect():
            pass
    finally:
        engine.dispose()


def test_a_set_role_on_a_superuser_connection_fails_the_guard() -> None:
    """`current_user` becomes the role; `session_user` stays the superuser, and gives it away.

    `pg_read_all_data` is a built-in role every cluster has, so nothing is created here.
    """
    engine = create_engine(DATABASE_URL)
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.execute(text("SET ROLE pg_read_all_data").text)
        cursor.close()
        with pytest.raises(HarnessError):
            assert_connected_as(raw, "pg_read_all_data")
    finally:
        raw.close()
        engine.dispose()
