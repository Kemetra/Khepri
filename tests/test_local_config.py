"""Local settings resolve from the environment, and default when it is silent.

Defaults are correct here and refused in `khepri.infra.sizing`, which is worth
holding in a test: a governed size guessed by code is indistinguishable from an
approved one once deployed, and a local endpoint URL is covered by no digest at
all.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from alembic.config import Config

from khepri.local.config import (
    DEFAULT_BUCKET,
    DEFAULT_DATABASE_URL,
    DEFAULT_REGION,
    DEFAULT_S3_ENDPOINT,
    LocalSettings,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class TestDefaults:
    def test_an_empty_environment_yields_the_local_defaults(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        for name in (
            "KHEPRI_LOCAL_S3_ENDPOINT",
            "KHEPRI_LOCAL_REGION",
            "KHEPRI_LOCAL_BUCKET",
            "KHEPRI_LOCAL_DATABASE_URL",
        ):
            monkeypatch.delenv(name, raising=False)

        settings = LocalSettings.from_environment()

        assert settings.s3_endpoint == DEFAULT_S3_ENDPOINT
        assert settings.region == DEFAULT_REGION
        assert settings.bucket == DEFAULT_BUCKET
        assert settings.database_url == DEFAULT_DATABASE_URL

    def test_the_region_matches_the_one_the_store_requires(self) -> None:
        """`S3EncryptedObjectStore` regex-refuses a key ARN outside me-central-1."""
        assert DEFAULT_REGION == "me-central-1"

    def test_the_endpoint_is_loopback(self) -> None:
        """A local default that reached a network would be a surprising default."""
        assert "127.0.0.1" in DEFAULT_S3_ENDPOINT


class TestOverrides:
    def test_every_field_is_overridable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("KHEPRI_LOCAL_S3_ENDPOINT", "http://127.0.0.1:9999")
        monkeypatch.setenv("KHEPRI_LOCAL_REGION", "me-central-1")
        monkeypatch.setenv("KHEPRI_LOCAL_BUCKET", "other-bucket")
        monkeypatch.setenv("KHEPRI_LOCAL_DATABASE_URL", "postgresql+psycopg://a:b@h/d")

        settings = LocalSettings.from_environment()

        assert settings.s3_endpoint == "http://127.0.0.1:9999"
        assert settings.bucket == "other-bucket"
        assert settings.database_url == "postgresql+psycopg://a:b@h/d"

    def test_settings_are_immutable(self) -> None:
        """Shared by the web app and the worker, so neither may edit the other's."""
        settings = LocalSettings()

        with pytest.raises(AttributeError):
            settings.bucket = "changed"  # type: ignore[misc]


class TestComposeContract:
    def test_localstack_uses_an_exact_patch_release(self) -> None:
        compose = yaml.safe_load(
            (REPOSITORY_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")
        )

        image = compose["services"]["localstack"]["image"]
        _, tag = image.rsplit(":", maxsplit=1)
        assert re.fullmatch(r"\d+\.\d+\.\d+", tag)


class TestMigrationContract:
    def test_default_migrations_target_the_local_runtime_database(self) -> None:
        config = Config(REPOSITORY_ROOT / "alembic.ini")

        assert config.get_main_option("sqlalchemy.url") == DEFAULT_DATABASE_URL
