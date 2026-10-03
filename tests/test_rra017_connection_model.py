"""RRA-017 `FR-270`'s connection model: each process holds its own role's credential alone (`#595`).

Five roles, four credentials. The application, worker and sweep roles each read their own secret
variable; the migration owner's arrives only to `migrations/env.py`. These cases hold the runtime's
reading of those variables, both compose stacks, the roles script both stacks mount, and the local
defaults together, so a service handed the wrong role's secret, or the owner's, fails here before
it fails as a policy bypass or a refused login.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml
from alembic.config import Config
from sqlalchemy.engine import make_url

from khepri.local.config import LocalSettings
from khepri.runtime.config import (
    MIGRATION_DATABASE_SECRET_VARIABLE,
    RuntimeConfigurationError,
    RuntimeSettings,
    migration_database_url,
)
from khepri.runtime.db_roles import SECRET_VARIABLES, DatabaseRole
from tests.test_runtime_config import environment

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ROLES_SCRIPT = REPOSITORY_ROOT / "ops" / "local" / "khepri-runtime-roles.sql"
INITDB = "/docker-entrypoint-initdb.d/"
MIGRATION_OWNER = "khepri"
#: Which staging service connects as which role. `migrate` is the migration owner.
STAGING_ROLES = {"web": DatabaseRole.APPLICATION, "worker": DatabaseRole.WORKER}


def _compose(name: str) -> dict:
    return yaml.safe_load((REPOSITORY_ROOT / name).read_text(encoding="utf-8"))


def _secret_for(role: DatabaseRole) -> str:
    return json.dumps(
        {
            "username": role.value,
            "password": "secret",
            "engine": "postgres",
            "host": "database.internal",
            "port": 5432,
            "dbname": "khepri",
        }
    )


def _only(role: DatabaseRole) -> dict[str, str]:
    """The runtime environment, holding `role`'s database secret and no other."""
    values = {k: v for k, v in environment().items() if k not in SECRET_VARIABLES.values()}
    values[SECRET_VARIABLES[role]] = _secret_for(role)
    return values


def _database_secrets(service: dict) -> dict[str, dict]:
    return {
        name: json.loads(value)
        for name, value in service["environment"].items()
        if name.endswith("DATABASE_SECRET")
    }


# -- the runtime's reading -----------------------------------------------------------------------


def test_the_three_runtime_roles_each_have_their_own_secret_variable() -> None:
    assert set(SECRET_VARIABLES) == set(DatabaseRole)
    assert len(set(SECRET_VARIABLES.values())) == len(DatabaseRole)
    assert MIGRATION_DATABASE_SECRET_VARIABLE not in SECRET_VARIABLES.values()


@pytest.mark.parametrize("role", list(DatabaseRole), ids=lambda role: role.value)
def test_each_role_connects_with_its_own_secret(role: DatabaseRole) -> None:
    settings = RuntimeSettings.from_environment(_only(role), role=role)
    assert settings.database_url.username == role.value
    assert settings.database_role is role


@pytest.mark.parametrize("role", list(DatabaseRole), ids=lambda role: role.value)
def test_no_role_falls_back_to_another_roles_secret(role: DatabaseRole) -> None:
    for other in DatabaseRole:
        if other is not role:
            with pytest.raises(RuntimeConfigurationError):
                RuntimeSettings.from_environment(_only(other), role=role)


def test_a_root_that_names_no_role_does_not_start() -> None:
    """`FR-270`: a forgotten role is an error, not silently the application role."""
    with pytest.raises(TypeError):
        RuntimeSettings.from_environment(_only(DatabaseRole.APPLICATION))  # type: ignore[call-arg]


def test_the_migration_owner_is_read_only_from_its_own_variable() -> None:
    assert migration_database_url(_only(DatabaseRole.APPLICATION)) is None
    owner = {**environment(), MIGRATION_DATABASE_SECRET_VARIABLE: _secret_for_owner()}
    url = migration_database_url(owner)
    assert url is not None
    assert url.username == MIGRATION_OWNER


def _secret_for_owner() -> str:
    document = json.loads(_secret_for(DatabaseRole.APPLICATION))
    return json.dumps({**document, "username": MIGRATION_OWNER})


# -- the staging stack ---------------------------------------------------------------------------


@pytest.mark.parametrize("service", sorted(STAGING_ROLES))
def test_each_staging_runtime_service_holds_its_own_roles_secret_alone(service: str) -> None:
    role = STAGING_ROLES[service]
    secrets = _database_secrets(_compose("docker-compose.staging.yml")["services"][service])
    assert set(secrets) == {SECRET_VARIABLES[role]}
    assert secrets[SECRET_VARIABLES[role]]["username"] == role.value


def test_only_staging_migrate_holds_the_migration_owners_secret() -> None:
    services = _compose("docker-compose.staging.yml")["services"]
    holders = {
        name
        for name, service in services.items()
        if MIGRATION_DATABASE_SECRET_VARIABLE in service.get("environment", {})
    }
    assert holders == {"migrate"}
    secrets = _database_secrets(services["migrate"])
    assert set(secrets) == {MIGRATION_DATABASE_SECRET_VARIABLE}
    assert secrets[MIGRATION_DATABASE_SECRET_VARIABLE]["username"] == MIGRATION_OWNER
    assert "KHEPRI_DATABASE_URL" not in services["migrate"]["environment"]


# -- the roles script, both stacks, and the local defaults ---------------------------------------


@pytest.mark.parametrize("name", ["docker-compose.local.yml", "docker-compose.staging.yml"])
def test_both_stacks_create_the_runtime_roles_on_a_new_volume(name: str) -> None:
    volumes = _compose(name)["services"]["postgres"]["volumes"]
    mounts = [volume for volume in volumes if volume.startswith("./ops/local/")]
    assert len(mounts) == 1, volumes
    source, target, mode = mounts[0].split(":")
    assert REPOSITORY_ROOT / source == ROLES_SCRIPT
    assert target.startswith(INITDB) and target.endswith(".sql")
    assert mode == "ro"


def test_the_roles_script_creates_exactly_the_three_runtime_roles() -> None:
    script = ROLES_SCRIPT.read_text(encoding="utf-8")
    (listed,) = re.findall(r"ARRAY\[([^\]]*)\]", script)
    assert set(re.findall(r"'([a-z_]+)'", listed)) == {role.value for role in DatabaseRole}
    assert "PASSWORD %L', role_name, role_name" in script
    for attribute in ("NOSUPERUSER", "NOBYPASSRLS", "NOCREATEROLE", "NOCREATEDB"):
        assert attribute in script


@pytest.mark.parametrize("role", list(DatabaseRole), ids=lambda role: role.value)
def test_each_local_default_logs_in_as_its_role_with_the_scripts_password(
    role: DatabaseRole,
) -> None:
    url = make_url(LocalSettings().url_for(role))
    assert (url.username, url.password) == (role.value, role.value)


@pytest.mark.parametrize("service", sorted(STAGING_ROLES))
def test_each_staging_secret_carries_the_scripts_password(service: str) -> None:
    role = STAGING_ROLES[service]
    secret = _database_secrets(_compose("docker-compose.staging.yml")["services"][service])
    assert secret[SECRET_VARIABLES[role]]["password"] == role.value


def test_alembics_local_default_is_the_migration_owner_not_a_runtime_role() -> None:
    url = make_url(Config(REPOSITORY_ROOT / "alembic.ini").get_main_option("sqlalchemy.url"))
    assert url.username == MIGRATION_OWNER
    assert url.username not in {role.value for role in DatabaseRole}
