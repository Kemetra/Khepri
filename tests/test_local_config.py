"""Local settings resolve from the environment, and default when it is silent.

Defaults are correct here and refused in `khepri.infra.sizing`, which is worth
holding in a test: a governed size guessed by code is indistinguishable from an
approved one once deployed, and a local endpoint URL is covered by no digest at
all.
"""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
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
    RuntimeSettings,
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

        The form is `-` and not `:-` on purpose: `:-` also substitutes for an empty
        value, while `os.environ.get` treats empty as a present value, so `:-` would
        configure the server with the default while the client sent `""`. This
        asserts the exact operator, because the two differ only in that case.
        """
        environment = _compose()["services"]["minio"]["environment"]

        assert environment["MINIO_ROOT_USER"] == (
            "${KHEPRI_LOCAL_ACCESS_KEY-" + DEFAULT_ACCESS_KEY + "}"
        )
        assert environment["MINIO_ROOT_PASSWORD"] == (
            "${KHEPRI_LOCAL_SECRET_KEY-" + DEFAULT_SECRET_KEY + "}"
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

    def test_no_project_env_file_can_split_the_two_runtimes(self) -> None:
        """Compose interpolates from `.env`; `LocalSettings` reads `os.environ`.

        A credential written to a project `.env` therefore configures MinIO and
        never reaches a client started with `uv run`, which is the same divergence
        the substitution closes, arriving through a different door. Reproduced:
        with a `.env` present, `docker compose config` resolved the file's value
        while the settings still returned the default.

        The repository must have no committed `.env`, and `.gitignore` must keep
        it that way -- a committed one would split every developer's stack at once,
        and the failure surfaces as a 403 that reads like a network fault.
        """
        assert not (REPOSITORY_ROOT / ".env").exists(), (
            "a committed .env would configure MinIO without reaching uv run clients"
        )
        ignored = (REPOSITORY_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert any(line.strip() == ".env" for line in ignored.splitlines()), (
            ".gitignore must exclude .env so one cannot be committed"
        )

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
        """Both hops are TLS and both chains are verified.

        The secret names `postgres`, which is not loopback, so `_database_url` builds a
        `verify-full` URL and refuses to boot without `PGSSLROOTCERT` (`#434` §4). The
        object-store hop is verified by botocore through `AWS_CA_BUNDLE`.
        """
        services = _staging()["services"]
        environment = services["web"]["environment"]

        assert environment[STORAGE_ENDPOINT_VARIABLE].startswith("https://")
        assert environment["AWS_CA_BUNDLE"], "botocore must be told to trust the local CA"
        assert "ssl=on" in services["postgres"]["command"]
        settings = RuntimeSettings.from_environment(
            {**environment, "KHEPRI_STORAGE_MASTER_KEY": base64.b64encode(b"k" * 32).decode()}
        )
        assert settings.database_url.query["sslmode"] == "verify-full"

    def test_migrations_and_the_runtime_verify_postgres_against_one_mounted_ca(self) -> None:
        """Compose and config share one source (`#434` §4).

        `migrations/env.py` reads `KHEPRI_DATABASE_URL` raw, so the migrate URL is a
        second, hand-written statement of the database TLS mode. It names the same CA
        file the runtime receives through `PGSSLROOTCERT`, and every service that reads
        that path has it mounted.
        """
        services = _staging()["services"]
        ca = services["web"]["environment"]["PGSSLROOTCERT"]
        url = services["migrate"]["environment"]["KHEPRI_DATABASE_URL"]

        assert services["worker"]["environment"]["PGSSLROOTCERT"] == ca
        assert url.endswith(f"?sslmode=verify-full&sslrootcert={ca}"), url
        for role in ("web", "worker", "migrate"):
            mounted = {volume.rsplit(":", 2)[1] for volume in services[role]["volumes"]}
            assert ca in mounted, f"{role} does not mount {ca}"

    def test_the_postgres_leaf_is_issued_by_the_local_ca_for_its_service_name(self) -> None:
        """`verify-full` checks the chain and the host name, so a self-signed leaf with only
        a CN fails. It is issued by the CA the runtime trusts, for `DNS:postgres`, and lives
        at new paths so an existing checkout's self-signed pair is reissued, not kept."""
        script = (REPOSITORY_ROOT / "ops" / "staging" / "generate-certs.sh").read_text("utf-8")
        dockerfile = (REPOSITORY_ROOT / "ops" / "staging" / "postgres-tls.Dockerfile").read_text(
            "utf-8"
        )

        assert "subjectAltName=DNS:postgres" in script
        assert "-out postgres/server.crt" in script and "-CA ca.crt" in script
        required = re.search(r"for required in(.*?)\ndo", script, re.DOTALL)
        assert required is not None and "postgres/server.crt" in required.group(1).split()
        assert "COPY certs/postgres/server.crt" in dockerfile
        assert "COPY certs/postgres/server.key" in dockerfile

    @pytest.mark.skipif(
        not (shutil.which("sh") and shutil.which("openssl")), reason="needs sh and openssl"
    )
    def test_the_generated_postgres_leaf_verifies_against_the_ca_for_postgres(
        self, tmp_path: Path
    ) -> None:
        """What the script *produces*, not what it says: a leaf self-signed with the right SAN
        would pass every string check above and still be refused by `verify-full`. A legacy
        self-signed `server.crt` is seeded so the reissue path is the one exercised."""
        shutil.copy(REPOSITORY_ROOT / "ops" / "staging" / "generate-certs.sh", tmp_path)
        certs = tmp_path / "certs"
        certs.mkdir()
        (certs / "server.crt").write_text("legacy self-signed leaf")
        # Git Bash would otherwise rewrite `-subj "/CN=..."` into a Windows path.
        environment = {**os.environ, "MSYS_NO_PATHCONV": "1"}

        def run(*command: str) -> str:
            done = subprocess.run(
                command, cwd=tmp_path, env=environment, capture_output=True, text=True
            )
            assert done.returncode == 0, done.stderr
            return done.stdout

        assert "[OK] certificates generated" in run("sh", "generate-certs.sh")
        leaf = "certs/postgres/server.crt"
        assert run("openssl", "verify", "-CAfile", "certs/ca.crt", leaf).strip().endswith("OK")
        san = run("openssl", "x509", "-in", leaf, "-noout", "-ext", "subjectAltName")
        assert san.split(":", 1)[1].split() == ["DNS:postgres"], san
        assert not (certs / "server.crt").exists(), "the legacy leaf would be mistaken for current"

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
