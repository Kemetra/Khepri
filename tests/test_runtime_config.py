from __future__ import annotations

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
        "KHEPRI_AWS_REGION": "me-central-1",
        "KHEPRI_BUCKET": "khepri-beta-content",
        "KHEPRI_KMS_KEY_ARN": (
            "arn:aws:kms:me-central-1:123456789012:"
            "key/12345678-1234-1234-1234-123456789abc"
        ),
        "KHEPRI_EXPECTED_BUCKET_OWNER": "123456789012",
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

    assert settings.region == "me-central-1"
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
        "KHEPRI_AWS_REGION",
        "KHEPRI_BUCKET",
        "KHEPRI_KMS_KEY_ARN",
        "KHEPRI_EXPECTED_BUCKET_OWNER",
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
        ("KHEPRI_AWS_REGION", "eu-west-1"),
        ("KHEPRI_BUCKET", " "),
        (
            "KHEPRI_KMS_KEY_ARN",
            "arn:aws:kms:eu-west-1:123456789012:"
            "key/12345678-1234-1234-1234-123456789abc",
        ),
        ("KHEPRI_EXPECTED_BUCKET_OWNER", "123"),
        ("KHEPRI_QUEUE_URL", " "),
        ("KHEPRI_DLQ_URL", " "),
    ],
)
def test_invalid_or_cross_region_coordinates_are_refused(name: str, value: str) -> None:
    with pytest.raises(RuntimeConfigurationError, match=name):
        RuntimeSettings.from_environment(environment(**{name: value}))


def test_source_and_dead_letter_queue_must_be_distinct() -> None:
    source = environment()["KHEPRI_QUEUE_URL"]

    with pytest.raises(RuntimeConfigurationError, match="KHEPRI_DLQ_URL"):
        RuntimeSettings.from_environment(environment(KHEPRI_DLQ_URL=source))
