"""#593: a dataset profile outlives its raw upload, and names it only while it exists.

The owner decided on 2026-09-26 (recorded on #593, and in `KHEPRI-DEC-033` §1 by this slice)
that retention deleting a raw upload keeps its profile: `upload_id` becomes nullable and the
key is `ON DELETE SET NULL`, not `RESTRICT` (which would block the retention sweep) and not
`CASCADE` (which would delete the profile retention keeps).

Before `20260926_0033` the column carried no key at all, so every swept database already held
profiles naming an upload that no longer existed.

**Every deletion goes through the production verb.** The retention case drives
`RawUploadRetentionSweeper` over a real journey, not a raw `DELETE`, so it proves what the sweep
does to the profile rather than what the constraint would do in isolation.

**SQLite enforces nothing unless asked.** The journey's factory enables `PRAGMA foreign_keys`
(`w104_support`), so `SET NULL` really fires here. The PostgreSQL block proves the migration's
DDL and its orphan repair, which no SQLite fixture replays, and carries the `concurrency` marker
so a skip in CI fails the build.

**Not a `test_rra*` file.** `RCA-001` `FR-037` keeps RRA's existing tests unmodified.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from khepri.rra.datasets import DatasetProfileRecord
from khepri.rra.persistence import DatasetProfileRow, SqlProfileRepository, SqlSessionStore
from khepri.rra.sessions import open_commercial_session
from tests.w104_support import member
from tests.w107_support import journey

NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64
PROFILE_UPLOAD_FK = "fk_profile_upload"
PARENT_REVISION = "20260925_0032"
REPO_ROOT = Path(__file__).resolve().parents[1]
DATABASE_URL = os.environ.get("KHEPRI_TEST_DATABASE_URL")


def _profile(owner_id: str, session_id: str, upload_id: str | None) -> DatasetProfileRecord:
    return DatasetProfileRecord(
        profile_id=f"prf_{session_id}",
        owner_id=owner_id,
        session_id=session_id,
        upload_id=upload_id,
        profile_version="rra003.profile.v1",
        mapping_version="rra003.mapping.v1",
        source_sha256_hex=DIGEST,
        profile_digest=DIGEST,
        row_count=1,
        column_count=1,
        admissible=True,
        created_at=NOW,
        document={},
    )


def _profiles_for(factory: sessionmaker, owner_id: str) -> tuple[DatasetProfileRow, ...]:
    with factory() as database:
        statement = select(DatasetProfileRow).where(DatasetProfileRow.owner_id == owner_id)
        return tuple(database.scalars(statement))


class TestRetentionKeepsTheProfile:
    def test_the_sweep_keeps_the_profile_and_clears_its_upload(self) -> None:
        from khepri.runtime.workspace_retention import RawUploadRetentionSweeper
        from tests.w107_support import sealed_version, uploads_for

        j = journey()
        who = member(j.w)
        version, _run = sealed_version(j, who, with_run=True)
        assert version.sealed_at is not None
        (upload,) = uploads_for(j, who.owner_id)
        (before,) = _profiles_for(j.w.factory, who.owner_id)
        assert before.upload_id == upload.upload_id, "the fixture's profile names its upload"

        purged = RawUploadRetentionSweeper(
            factory=j.w.factory, objects=j.w.objects, audit=j.w.audit
        ).sweep(now=version.sealed_at + timedelta(days=7))

        assert purged.purged_uploads == 1
        assert uploads_for(j, who.owner_id) == ()
        (after,) = _profiles_for(j.w.factory, who.owner_id)
        assert after.profile_id == before.profile_id
        assert after.upload_id is None
        # And the stored profile still reads back, verified, with no upload.
        read = SqlProfileRepository(j.w.factory).get_profile_for_session(after.session_id)
        assert read is not None and read.upload_id is None


class TestTheProfileNamesOnlyARealUpload:
    def test_a_profile_naming_an_absent_upload_is_refused(self) -> None:
        j = journey()
        session = open_commercial_session(
            SqlSessionStore(j.w.factory), owner_id="own_scope_a", now=NOW
        )

        with pytest.raises(IntegrityError):
            SqlProfileRepository(j.w.factory).add_profile(
                _profile(session.owner_id, session.session_id, "upl_absent")
            )


requires_postgres = pytest.mark.skipif(
    not DATABASE_URL,
    reason="KHEPRI_TEST_DATABASE_URL is unset; this DDL cannot be proved on SQLite",
)


def _alembic_config() -> Config:
    assert DATABASE_URL is not None
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))
    return config


def _upload_key(engine: Engine) -> dict | None:
    keys = inspect(engine).get_foreign_keys("rra_dataset_profiles")
    return next((key for key in keys if key["name"] == PROFILE_UPLOAD_FK), None)


def _upload_id_nullable(engine: Engine) -> bool:
    columns = inspect(engine).get_columns("rra_dataset_profiles")
    return next(column for column in columns if column["name"] == "upload_id")["nullable"]


@pytest.fixture(name="postgres")
def postgres_fixture() -> Iterator[tuple[Config, Engine]]:
    """A database at head, left at head (the range `test_i432` documents)."""
    assert DATABASE_URL is not None
    engine = create_engine(DATABASE_URL)
    with engine.begin() as connection:
        connection.execute(text("drop schema public cascade"))
        connection.execute(text("create schema public"))
    config = _alembic_config()
    command.upgrade(config, "head")
    try:
        yield config, engine
    finally:
        with engine.begin() as connection:
            connection.execute(text("delete from rra_dataset_profiles"))
        command.upgrade(config, "head")
        engine.dispose()


_SESSION = (
    "insert into rra_beta_sessions (owner_id, session_id, created_at, content_expires_at) "
    "values ('own_a', 'ses_a', :now, :later)"
)
_PROFILE = (
    "insert into rra_dataset_profiles (profile_id, owner_id, session_id, upload_id, "
    "profile_version, mapping_version, source_sha256_hex, profile_digest, row_count, "
    "column_count, admissible, created_at, document) values ('prf_a', 'own_a', 'ses_a', "
    ":upload, 'rra003.profile.v1', 'rra003.mapping.v1', :digest, :digest, 1, 1, true, :now, "
    "'{}')"
)


def _insert_profile(engine: Engine, upload_id: str | None) -> None:
    with engine.begin() as connection:
        connection.execute(text(_SESSION), {"now": NOW, "later": NOW + timedelta(days=7)})
        connection.execute(text(_PROFILE), {"upload": upload_id, "digest": DIGEST, "now": NOW})


def _stored_upload_id(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return connection.execute(
            text("select upload_id from rra_dataset_profiles where profile_id = 'prf_a'")
        ).scalar_one()


@pytest.mark.concurrency
@requires_postgres
class TestTheMigrationOnPostgres:
    def test_head_carries_the_set_null_key_over_a_nullable_column(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        _config, engine = postgres
        key = _upload_key(engine)

        assert key is not None
        assert key["referred_table"] == "rra_uploads"
        assert key["options"].get("ondelete") == "SET NULL"
        assert _upload_id_nullable(engine)

    def test_the_upgrade_clears_an_upload_id_the_sweep_left_dangling(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        config, engine = postgres
        command.downgrade(config, PARENT_REVISION)
        _insert_profile(engine, "upl_swept_before_this_key_existed")

        command.upgrade(config, "head")

        assert _stored_upload_id(engine) is None

    def test_downgrade_restores_the_unkeyed_not_null_column(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        config, engine = postgres

        command.downgrade(config, PARENT_REVISION)

        assert _upload_key(engine) is None
        assert not _upload_id_nullable(engine)

    def test_downgrade_refuses_while_a_profile_has_outlived_its_upload(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        config, engine = postgres
        _insert_profile(engine, None)

        with pytest.raises(RuntimeError, match="outlived"):
            command.downgrade(config, PARENT_REVISION)
