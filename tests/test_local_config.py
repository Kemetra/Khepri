"""Local settings resolve from the environment, and default when it is silent.

Defaults are correct here and refused in `khepri.infra.sizing`, which is worth
holding in a test: a governed size guessed by code is indistinguishable from an
approved one once deployed, and a local endpoint URL is covered by no digest at
all.
"""

from __future__ import annotations

import json
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
from khepri.runtime.config import (
    _SECRET_FIELDS,
    BUCKET_VARIABLE,
    DATABASE_SECRET_VARIABLE,
    MASTER_KEY_VARIABLE,
    STORAGE_ENDPOINT_VARIABLE,
    STORAGE_REGION_VARIABLE,
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


def _compose(name: str = "docker-compose.local.yml") -> dict:
    return yaml.safe_load((REPOSITORY_ROOT / name).read_text(encoding="utf-8"))


def _staging() -> dict:
    return _compose("docker-compose.staging.yml")


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

    def test_the_object_store_credentials_follow_the_settings(self) -> None:
        """MinIO rejects any credential but its configured root user.

        LocalStack accepted anything, so this pair could drift silently and the
        journey still worked. It cannot now: a mismatch fails every S3 call with a
        403 that reads like a networking fault rather than a configuration one.

        Asserted as substitution rather than as literals, because the settings read
        the same two variables from the environment: hardcoding the defaults here
        would make `KHEPRI_LOCAL_ACCESS_KEY=other` move the client without moving
        the server. The `:-` fallbacks must still be the settings' own defaults, or
        an unset environment starts a server the defaults cannot reach.
        """
        environment = _compose()["services"]["minio"]["environment"]

        assert environment["MINIO_ROOT_USER"] == (
            "${KHEPRI_LOCAL_ACCESS_KEY:-" + DEFAULT_ACCESS_KEY + "}"
        )
        assert environment["MINIO_ROOT_PASSWORD"] == (
            "${KHEPRI_LOCAL_SECRET_KEY:-" + DEFAULT_SECRET_KEY + "}"
        )

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

        assert "127.0.0.1:14566:9000" in services["minio"]["ports"]
        assert "127.0.0.1:15432:5432" in services["postgres"]["ports"]
        assert DEFAULT_S3_ENDPOINT.endswith(":14566")
        assert ":15432/" in DEFAULT_DATABASE_URL

    def test_every_local_port_is_bound_to_loopback(self) -> None:
        """The same exposure the staging stack had: short syntax means all interfaces.

        These credentials are fixed and published in the file, so a developer host
        reachable from another machine would be offering its database and object
        store to the network.
        """
        services = _compose()["services"]

        published = [
            (name, mapping)
            for name, service in services.items()
            for mapping in service.get("ports", [])
        ]

        assert published, "a stack publishing nothing would vacuously pass"
        for name, mapping in published:
            assert mapping.startswith("127.0.0.1:"), (
                f"{name} publishes {mapping} on every interface"
            )


class TestStagingComposeContract:
    """The staging stack runs the built image, so its contract is the runtime's.

    `docker-compose.local.yml` is checked against `LocalSettings`; this file is
    checked against what `khepri.runtime.config` refuses to start without. Both
    are compose files and neither substitutes for the other.
    """

    def test_no_service_floats_its_image_tag(self) -> None:
        services = _staging()["services"]

        assert services, "a compose file with no services would vacuously pass"
        for name, service in services.items():
            tag = service.get("image", "").rpartition(":")[2]
            assert tag, f"{name} must pin a tag rather than defaulting to latest"
            assert tag not in {"latest", "stable", "edge"}, f"{name} floats on {tag}"

    def test_the_database_secret_is_the_json_document_the_runtime_parses(self) -> None:
        """`_database_secret` parses a Secrets Manager document, not a URL.

        Supplying a connection string here would fail at boot inside
        `RuntimeSettings.from_environment`, so the shape is asserted rather than
        assumed -- and asserted through the runtime's own field set, so adding a
        required field to the secret fails here rather than in a container.
        """
        environment = _staging()["services"]["web"]["environment"]
        document = json.loads(environment[DATABASE_SECRET_VARIABLE])

        assert set(document) >= _SECRET_FIELDS
        assert isinstance(document["port"], int), "port must not be a string"

    def test_every_runtime_variable_the_web_service_needs_is_present(self) -> None:
        """The four coordinates `_runtime_coordinates` requires, plus the secret."""
        environment = _staging()["services"]["web"]["environment"]

        for variable in (
            DATABASE_SECRET_VARIABLE,
            STORAGE_ENDPOINT_VARIABLE,
            STORAGE_REGION_VARIABLE,
            BUCKET_VARIABLE,
            MASTER_KEY_VARIABLE,
        ):
            assert environment.get(variable), f"{variable} must be set and non-empty"

    def test_the_worker_and_web_share_one_runtime_environment(self) -> None:
        """They read the same rows and the same bucket; divergence is a split brain."""
        services = _staging()["services"]

        assert services["web"]["environment"] == services["worker"]["environment"]

    def test_no_clerk_variable_is_supplied_empty(self) -> None:
        """`_clerk_settings` reads these through `_optional`.

        Absent is valid and means invitation sessions. Present-but-empty is not:
        `_required` rejects it, so an empty value turns an intentional omission
        into a boot failure.
        """
        environment = _staging()["services"]["web"]["environment"]

        clerk = {k: v for k, v in environment.items() if k.startswith("KHEPRI_CLERK")}
        assert all(clerk.values()), f"empty Clerk variables would fail boot: {clerk}"

    def test_both_storage_hops_are_encrypted(self) -> None:
        """`_database_url` pins `sslmode=require` and offers no override.

        A plaintext PostgreSQL is therefore not merely weaker here, it is
        unreachable by this image. The object-store hop is TLS for the same
        reason the deployed one will be, and botocore verifies its chain.
        """
        services = _staging()["services"]
        environment = services["web"]["environment"]

        assert environment[STORAGE_ENDPOINT_VARIABLE].startswith("https://")
        assert environment["AWS_CA_BUNDLE"], "botocore must be told to trust the local CA"
        assert "ssl=on" in services["postgres"]["command"]
        assert "sslmode=require" in services["migrate"]["environment"]["KHEPRI_DATABASE_URL"]

    def test_web_and_worker_wait_for_migrations_and_the_bucket(self) -> None:
        """Either racing the schema or the bucket fails in a way that looks flaky."""
        services = _staging()["services"]

        for role in ("web", "worker"):
            depends = services[role]["depends_on"]
            assert depends["migrate"]["condition"] == "service_completed_successfully"
            assert depends["minio-init"]["condition"] == "service_completed_successfully"

    def test_the_worker_has_no_fixed_container_name(self) -> None:
        """Its own comment says to scale by replicas, and a fixed name forbids that.

        Compose can give exactly one container a given name, so `--scale worker=2`
        fails outright. The other services keep theirs because one of each is right.
        """
        services = _staging()["services"]

        assert "container_name" not in services["worker"]
        assert "container_name" in services["web"]

    def test_the_one_shot_services_do_not_restart(self) -> None:
        """A completed one-shot that restarts never satisfies its dependents."""
        services = _staging()["services"]

        assert services["migrate"]["restart"] == "no"
        assert services["minio-init"]["restart"] == "no"

    def test_every_published_port_is_bound_to_loopback(self) -> None:
        """Compose's short syntax publishes on every interface, not just localhost.

        This stack carries fixed credentials written in the file itself, so on any
        machine reachable from another the short form would put PostgreSQL and the
        object store on the LAN. The header advertises `127.0.0.1`; this is what
        makes that true rather than aspirational.
        """
        services = _staging()["services"]

        published = [
            (name, mapping)
            for name, service in services.items()
            for mapping in service.get("ports", [])
        ]

        assert published, "a stack publishing nothing would vacuously pass"
        for name, mapping in published:
            assert mapping.startswith("127.0.0.1:"), (
                f"{name} publishes {mapping} on every interface"
            )

    def test_the_two_stacks_do_not_contend_for_ports(self) -> None:
        """Both are local, and a developer may reasonably run them at once."""

        def published(compose: dict) -> set[str]:
            """The host port, whether or not the mapping names a bind address."""
            return {
                mapping.split(":")[-2]
                for service in compose["services"].values()
                for mapping in service.get("ports", [])
            }

        assert not published(_compose()) & published(_staging())


class TestMigrationContract:
    def test_default_migrations_target_the_local_runtime_database(self) -> None:
        config = Config(REPOSITORY_ROOT / "alembic.ini")

        assert config.get_main_option("sqlalchemy.url") == DEFAULT_DATABASE_URL
