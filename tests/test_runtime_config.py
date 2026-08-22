from __future__ import annotations

import base64
import json

import pytest

from khepri.runtime.config import RuntimeConfigurationError, RuntimeSettings

PASSWORD = "p@ss:/word"
SECRET = {
    "username": "khepri_runtime",
    "password": PASSWORD,
    "engine": "postgres",
    "host": "khepri.cluster.internal",
    "port": 5432,
    "dbname": "khepri",
}


def environment(**overrides: str) -> dict[str, str]:
    values = {
        "KHEPRI_DATABASE_SECRET": json.dumps(SECRET),
        # A non-AWS endpoint and a non-AWS region on purpose: the portable runtime
        # must accept any conforming S3-compatible target, and a fixture pinned to
        # AWS would let a reintroduced region allowlist pass unnoticed.
        "KHEPRI_STORAGE_ENDPOINT": "https://fra1.digitaloceanspaces.example",
        "KHEPRI_STORAGE_REGION": "fra1",
        "KHEPRI_BUCKET": "khepri-beta-content",
        "KHEPRI_STORAGE_MASTER_KEY": base64.b64encode(b"k" * 32).decode("ascii"),
        "KHEPRI_QUEUE_URL": (
            "https://sqs.me-central-1.amazonaws.com/123456789012/report-jobs"
        ),
        "KHEPRI_DLQ_URL": (
            "https://sqs.me-central-1.amazonaws.com/123456789012/report-jobs-dlq"
        ),
    }
    values.update(overrides)
    return values


def test_valid_settings_build_a_tls_postgresql_url_without_exposing_the_password() -> None:
    settings = RuntimeSettings.from_environment(environment())

    assert settings.storage_endpoint == "https://fra1.digitaloceanspaces.example"
    assert settings.storage_region == "fra1"
    assert settings.database_url.drivername == "postgresql+psycopg"
    assert settings.database_url.query == {"sslmode": "require"}
    assert settings.database_url.password == PASSWORD
    assert settings.database_url.render_as_string(hide_password=False) == (
        "postgresql+psycopg://khepri_runtime:p%40ss%3A%2Fword@"
        "khepri.cluster.internal:5432/khepri?sslmode=require"
    )
    assert PASSWORD not in repr(settings)
    assert PASSWORD not in str(settings.database_url)
    assert settings.clerk is None


def clerk_environment(**overrides: str) -> dict[str, str]:
    values = environment(
        KHEPRI_CLERK_MODE="private_beta",
        KHEPRI_CLERK_ISSUER="https://private-beta.clerk.accounts.example",
        KHEPRI_CLERK_JWT_KEY=(
            "-----BEGIN PUBLIC KEY-----\npublic-material\n-----END PUBLIC KEY-----"
        ),
        KHEPRI_CLERK_KEY_ID="ins_private_beta",
        KHEPRI_CLERK_AUTHORIZED_PARTIES='["https://beta.khepri.example"]',
        KHEPRI_CLERK_AUDIENCE="khepri-private-beta",
    )
    values.update(overrides)
    return values


def test_clerk_settings_pin_one_private_beta_instance_without_exposing_its_key() -> None:
    settings = RuntimeSettings.from_environment(clerk_environment())

    assert settings.clerk is not None
    assert settings.clerk.mode == "private_beta"
    assert settings.clerk.issuer == "https://private-beta.clerk.accounts.example"
    assert settings.clerk.key_id == "ins_private_beta"
    assert settings.clerk.authorized_parties == ("https://beta.khepri.example",)
    assert settings.clerk.audience == "khepri-private-beta"
    assert "public-material" not in repr(settings)


@pytest.mark.parametrize(
    "missing",
    [
        "KHEPRI_CLERK_ISSUER",
        "KHEPRI_CLERK_JWT_KEY",
        "KHEPRI_CLERK_KEY_ID",
        "KHEPRI_CLERK_AUTHORIZED_PARTIES",
    ],
)
def test_every_enabled_clerk_trust_coordinate_is_required(missing: str) -> None:
    values = clerk_environment()
    del values[missing]

    with pytest.raises(RuntimeConfigurationError, match=missing):
        RuntimeSettings.from_environment(values)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("KHEPRI_CLERK_MODE", "commercial"),
        ("KHEPRI_CLERK_ISSUER", "http://private-beta.clerk.accounts.example"),
        ("KHEPRI_CLERK_JWT_KEY", "not-a-public-key"),
        ("KHEPRI_CLERK_AUTHORIZED_PARTIES", "[]"),
        ("KHEPRI_CLERK_AUTHORIZED_PARTIES", '["https://same.example", "https://same.example"]'),
        ("KHEPRI_CLERK_AUDIENCE", " "),
    ],
)
def test_invalid_or_commercial_clerk_configuration_fails_closed(name: str, value: str) -> None:
    with pytest.raises(RuntimeConfigurationError, match=name):
        RuntimeSettings.from_environment(clerk_environment(**{name: value}))


@pytest.mark.parametrize(
    "missing",
    [
        "KHEPRI_DATABASE_SECRET",
        "KHEPRI_STORAGE_ENDPOINT",
        "KHEPRI_STORAGE_REGION",
        "KHEPRI_BUCKET",
        "KHEPRI_STORAGE_MASTER_KEY",
        "KHEPRI_QUEUE_URL",
        "KHEPRI_DLQ_URL",
    ],
)
def test_every_runtime_coordinate_is_required(missing: str) -> None:
    values = environment()
    del values[missing]

    with pytest.raises(RuntimeConfigurationError, match=missing):
        RuntimeSettings.from_environment(values)


@pytest.mark.parametrize("field", list(SECRET))
def test_every_database_secret_field_is_required(field: str) -> None:
    secret = dict(SECRET)
    del secret[field]

    with pytest.raises(RuntimeConfigurationError, match="database secret"):
        RuntimeSettings.from_environment(
            environment(KHEPRI_DATABASE_SECRET=json.dumps(secret))
        )


@pytest.mark.parametrize(
    "secret",
    [
        "not-json",
        "[]",
        json.dumps({**SECRET, "engine": "mysql"}),
        json.dumps({**SECRET, "host": " "}),
        json.dumps({**SECRET, "port": 0}),
        json.dumps({**SECRET, "port": "5432"}),
        json.dumps({**SECRET, "dbname": "other"}),
    ],
)
def test_malformed_or_non_postgresql_secrets_are_refused(secret: str) -> None:
    with pytest.raises(RuntimeConfigurationError, match="database secret"):
        RuntimeSettings.from_environment(environment(KHEPRI_DATABASE_SECRET=secret))


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("KHEPRI_STORAGE_ENDPOINT", " "),
        # Not HTTPS, so refused: the endpoint carries customer content.
        ("KHEPRI_STORAGE_ENDPOINT", "http://spaces.example"),
        ("KHEPRI_STORAGE_REGION", " "),
        ("KHEPRI_BUCKET", " "),
        ("KHEPRI_STORAGE_MASTER_KEY", " "),
        # Not base64.
        ("KHEPRI_STORAGE_MASTER_KEY", "not base64 at all!!"),
        # Valid base64, wrong length: 16 bytes is not a 256-bit key.
        ("KHEPRI_STORAGE_MASTER_KEY", "AAAAAAAAAAAAAAAAAAAAAA=="),
        ("KHEPRI_QUEUE_URL", " "),
        ("KHEPRI_DLQ_URL", " "),
    ],
)
def test_invalid_storage_coordinates_are_refused(name: str, value: str) -> None:
    with pytest.raises(RuntimeConfigurationError, match=name):
        RuntimeSettings.from_environment(environment(**{name: value}))


def test_source_and_dead_letter_queue_must_be_distinct() -> None:
    source = environment()["KHEPRI_QUEUE_URL"]

    with pytest.raises(RuntimeConfigurationError, match="KHEPRI_DLQ_URL"):
        RuntimeSettings.from_environment(environment(KHEPRI_DLQ_URL=source))


def test_any_conforming_endpoint_and_region_are_accepted() -> None:
    """No provider is recognised by name and no region is allowlisted.

    `KHEPRI-DEC-008` states the runtime as a capability contract, so the only
    question about an endpoint is whether it is an HTTPS URL. A regression that
    reintroduced `me-central-1`, an account identifier, or a provider check would
    fail one of these rows.
    """
    for endpoint, region in (
        ("https://fra1.digitaloceanspaces.example", "fra1"),
        ("https://s3.eu-central-1.amazonaws.example", "eu-central-1"),
        ("https://nbg1.your-objectstorage.example", "nbg1"),
        ("https://minio.internal.example:9000", "us-east-1"),
        ("https://s3.me-central-1.amazonaws.example", "me-central-1"),
    ):
        settings = RuntimeSettings.from_environment(
            environment(
                KHEPRI_STORAGE_ENDPOINT=endpoint,
                KHEPRI_STORAGE_REGION=region,
            )
        )
        assert settings.storage_endpoint == endpoint
        assert settings.storage_region == region


def test_no_aws_specific_coordinate_is_required() -> None:
    """The retired coordinates must not be readmitted as requirements."""
    values = environment()
    for retired in (
        "KHEPRI_AWS_REGION",
        "KHEPRI_KMS_KEY_ARN",
        "KHEPRI_EXPECTED_BUCKET_OWNER",
    ):
        assert retired not in values
    # Present but unread: supplying them changes nothing.
    settings = RuntimeSettings.from_environment(
        environment(
            KHEPRI_AWS_REGION="me-central-1",
            KHEPRI_KMS_KEY_ARN="arn:aws:kms:me-central-1:123456789012:key/x",
            KHEPRI_EXPECTED_BUCKET_OWNER="123456789012",
        )
    )
    assert settings.storage_region == "fra1"


def test_the_master_key_never_appears_in_a_repr() -> None:
    settings = RuntimeSettings.from_environment(environment())

    assert (b"k" * 32).hex() not in repr(settings)
    assert "material" not in repr(settings.master_key)
