"""Local settings resolve from the environment, and default when it is silent.

Defaults are correct here and refused in `khepri.infra.sizing`, which is worth
holding in a test: a governed size guessed by code is indistinguishable from an
approved one once deployed, and a local endpoint URL is covered by no digest at
all.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from alembic.config import Config

from khepri.local.config import (
    DEFAULT_ACCESS_KEY,
    DEFAULT_BUCKET,
    DEFAULT_DATABASE_URL,
    DEFAULT_REGION,
    DEFAULT_S3_ENDPOINT,
    DEFAULT_SECRET_KEY,
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

    def test_the_region_is_not_the_retired_aws_one(self) -> None:
        """`KHEPRI-DEC-008` leaves the store with no region requirement at all.

        The default is now any string an S3-compatible client accepts. Asserting
        it is *not* `me-central-1` keeps the retired pin from reappearing as a
        default nobody chose.
        """
        assert DEFAULT_REGION == "us-east-1"

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


def _compose() -> dict:
    return yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.local.yml").read_text(encoding="utf-8")
    )


class TestComposeContract:
    """The local stack is only useful if it matches what the code reaches for."""

    def test_no_service_floats_its_image_tag(self) -> None:
        """Every image is pinned, and the pin is exact rather than a moving name.

        This began as a LocalStack rule: `:latest` and `:stable` acquired a licence
        gate in a patch release and exited with a code whose message looked nothing
        like its cause. The service is gone and the hazard is not -- a moving tag
        can change behaviour under a developer who changed nothing -- so the rule is
        now stated over every service rather than over the one that taught it.
        """
        services = _compose()["services"]

        assert services, "a compose file with no services would vacuously pass"
        for name, service in services.items():
            _, _, tag = service["image"].rpartition(":")
            assert tag, f"{name} must pin a tag rather than defaulting to latest"
            assert tag not in {"latest", "stable", "edge"}, f"{name} floats on {tag}"

    def test_the_object_store_credentials_match_the_settings(self) -> None:
        """MinIO rejects any credential but its configured root user.

        LocalStack accepted anything, so this pair could drift silently and the
        journey still worked. It cannot now: a mismatch fails every S3 call with a
        403 that reads like a networking fault rather than a configuration one.
        """
        environment = _compose()["services"]["minio"]["environment"]

        assert environment["MINIO_ROOT_USER"] == DEFAULT_ACCESS_KEY
        assert environment["MINIO_ROOT_PASSWORD"] == DEFAULT_SECRET_KEY

    def test_the_object_store_secret_satisfies_the_minio_minimum(self) -> None:
        """MinIO refuses to start with a root password under eight characters.

        The previous default was `test`, which is four. A shorter value makes the
        container exit at boot rather than fail a call, so this is asserted on the
        setting the compose file mirrors.
        """
        assert len(DEFAULT_SECRET_KEY) >= 8

    def test_the_published_ports_are_the_ones_the_settings_name(self) -> None:
        """The endpoint and database URL defaults are only correct if these agree."""
        services = _compose()["services"]

        assert "14566:9000" in services["minio"]["ports"]
        assert "15432:5432" in services["postgres"]["ports"]
        assert DEFAULT_S3_ENDPOINT.endswith(":14566")
        assert ":15432/" in DEFAULT_DATABASE_URL


class TestMigrationContract:
    def test_default_migrations_target_the_local_runtime_database(self) -> None:
        config = Config(REPOSITORY_ROOT / "alembic.ini")

        assert config.get_main_option("sqlalchemy.url") == DEFAULT_DATABASE_URL
