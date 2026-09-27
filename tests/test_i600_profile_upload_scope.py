"""#600: the upload a dataset profile names is in the profile's own scope.

`20260926_0033` (#599) keyed `rra_dataset_profiles.upload_id` onto `rra_uploads.upload_id`. That
proves the upload exists, not that it belongs to the profile's `(owner_id, session_id)`: a profile
in scope A could name scope B's upload and satisfy both keys, the shape #578 closed for packages.

`20260926_0034` replaces that key with `fk_profile_upload_scope`, over all three columns, with
`ON DELETE SET NULL (upload_id)`. Retention deleting an upload still nulls only `upload_id` (the
#593 decision), because the column-list form leaves the scope columns alone. That form is
PostgreSQL 15+ and SQLite cannot express it, so the key exists only on PostgreSQL. It is proved
here against PostgreSQL, under the `concurrency` marker, so a skip in CI fails the build.

**Not reachable from production.** `ProfilingService` takes the upload from the profile's own
session. This is the database backstop.

**Not a `test_rra*` file.** `RCA-001` `FR-037` keeps RRA's existing tests unmodified.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from tests.test_i593_profile_outlives_upload import (
    DIGEST,
    NOW,
    postgres_fixture,  # noqa: F401 -- the `postgres` fixture, shared with #593's DDL tests
    requires_postgres,
)

PARENT_REVISION = "20260926_0033"
COMPOSITE = "fk_profile_upload_scope"
LEGACY = "fk_profile_upload"
SCOPE = ["owner_id", "session_id", "upload_id"]

_SESSION = (
    "insert into rra_beta_sessions (owner_id, session_id, created_at, content_expires_at) "
    "values (:owner, :session, :now, :later)"
)
_UPLOAD = (
    "insert into rra_uploads (upload_id, owner_id, session_id, object_key, size_bytes, "
    "sha256_hex, media_type, created_at, expires_at, encryption_algorithm, envelope_version, "
    "ciphertext_sha256_hex) values (:upload, :owner, :session, :upload, 10, :digest, 'text/csv', "
    ":now, :later, 'AES-256-GCM', 1, :digest)"
)
_PROFILE = (
    "insert into rra_dataset_profiles (profile_id, owner_id, session_id, upload_id, "
    "profile_version, mapping_version, source_sha256_hex, profile_digest, row_count, "
    "column_count, admissible, created_at, document) values ('prf_a', 'own_a', 'ses_a', "
    ":upload, 'rra003.profile.v1', 'rra003.mapping.v1', :digest, :digest, 1, 1, true, :now, "
    "'{}')"
)
_STORED = (
    "select owner_id, session_id, upload_id from rra_dataset_profiles where profile_id = 'prf_a'"
)


def _values(**extra: object) -> dict[str, object]:
    return {"now": NOW, "later": NOW + timedelta(days=7), "digest": DIGEST, **extra}


def _two_scopes_with_uploads(engine: Engine) -> None:
    """Scope A and scope B, each a session holding one upload."""
    with engine.begin() as connection:
        for owner, session, upload in (("own_a", "ses_a", "upl_a"), ("own_b", "ses_b", "upl_b")):
            connection.execute(text(_SESSION), _values(owner=owner, session=session))
            connection.execute(
                text(_UPLOAD), _values(owner=owner, session=session, upload=upload)
            )


def _insert_profile(engine: Engine, upload_id: str | None) -> None:
    with engine.begin() as connection:
        connection.execute(text(_PROFILE), _values(upload=upload_id))


def _stored(engine: Engine) -> tuple[str, str, str | None]:
    with engine.connect() as connection:
        return tuple(connection.execute(text(_STORED)).one())


def _keys(engine: Engine) -> dict[str, dict]:
    return {key["name"]: key for key in inspect(engine).get_foreign_keys("rra_dataset_profiles")}


@pytest.mark.concurrency
@requires_postgres
class TestTheProfileNamesAnUploadInItsOwnScope:
    def test_head_carries_the_composite_key_and_not_the_single_column_one(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        _config, engine = postgres
        keys = _keys(engine)

        assert LEGACY not in keys, "two keys stating one fact are how they come to disagree"
        key = keys[COMPOSITE]
        assert key["referred_table"] == "rra_uploads"
        assert key["constrained_columns"] == SCOPE
        assert key["referred_columns"] == SCOPE

    def test_a_profile_naming_another_scopes_upload_is_refused(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        _config, engine = postgres
        _two_scopes_with_uploads(engine)

        with pytest.raises(IntegrityError):
            _insert_profile(engine, "upl_b")

    def test_a_profile_naming_its_own_upload_is_admitted(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        _config, engine = postgres
        _two_scopes_with_uploads(engine)

        _insert_profile(engine, "upl_a")

        assert _stored(engine) == ("own_a", "ses_a", "upl_a")

    def test_deleting_the_upload_nulls_only_upload_id(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        """The #593 decision survives the wider key: the profile outlives its upload in scope."""
        _config, engine = postgres
        _two_scopes_with_uploads(engine)
        _insert_profile(engine, "upl_a")

        with engine.begin() as connection:
            connection.execute(text("delete from rra_uploads where upload_id = 'upl_a'"))

        assert _stored(engine) == ("own_a", "ses_a", None)

    def test_the_upgrade_clears_a_cross_scope_upload_id(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        """A row written under the single-column key may name another scope's upload."""
        config, engine = postgres
        command.downgrade(config, PARENT_REVISION)
        _two_scopes_with_uploads(engine)
        _insert_profile(engine, "upl_b")

        command.upgrade(config, "head")

        assert _stored(engine) == ("own_a", "ses_a", None)

    def test_downgrade_restores_the_single_column_key(
        self, postgres: tuple[Config, Engine]
    ) -> None:
        config, engine = postgres

        command.downgrade(config, PARENT_REVISION)
        keys = _keys(engine)

        assert COMPOSITE not in keys
        assert keys[LEGACY]["constrained_columns"] == ["upload_id"]
        assert keys[LEGACY]["options"].get("ondelete") == "SET NULL"
