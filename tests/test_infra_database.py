from __future__ import annotations

import pytest
from aws_cdk import App, Stack
from aws_cdk import aws_kms as kms
from aws_cdk.assertions import Match, Template

from khepri.infra.database import (
    DATABASE_NAME,
    FORCE_SSL_PARAMETER,
    POSTGRES_MAJOR_VERSION,
    DatabaseProps,
    GovernedDatabase,
)
from khepri.infra.network import GovernedNetwork
from khepri.infra.sizing import DatabaseSize

INSTANCE_CLASS = "db.m7g.large"
ALLOCATED_STORAGE_GIB = 100
BACKUP_RETENTION_DAYS = 7


def _sizing() -> DatabaseSize:
    return DatabaseSize(
        instance_class=INSTANCE_CLASS,
        allocated_storage_gib=ALLOCATED_STORAGE_GIB,
        backup_retention_days=BACKUP_RETENTION_DAYS,
    )


def _synthesize(sizing: DatabaseSize | None = None) -> Template:
    stack = Stack(App(), "DatabaseStack")
    network = GovernedNetwork(stack, "Network")
    key = kms.Key(stack, "Key")
    GovernedDatabase(
        stack,
        "Database",
        DatabaseProps(vpc=network.vpc, key=key, sizing=sizing or _sizing()),
    )
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template() -> Template:
    return _synthesize()


class TestEngine:
    def test_the_major_version_is_pinned(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::RDS::DBInstance",
            {"Engine": "postgres", "EngineVersion": POSTGRES_MAJOR_VERSION},
        )

    def test_no_minor_version_is_named(self, template: Template) -> None:
        """KHEPRI-DEC-007 makes the minor a fact the descriptor records, not one code invents."""
        instance = _properties(template, "AWS::RDS::DBInstance")

        assert instance["EngineVersion"] == "17"
        assert "." not in instance["EngineVersion"]

    def test_automatic_minor_upgrade_is_disabled(self, template: Template) -> None:
        """An upgrade must not change the engine underneath an approved environment digest."""
        template.has_resource_properties(
            "AWS::RDS::DBInstance", {"AutoMinorVersionUpgrade": False}
        )


class TestGovernedControls:
    def test_the_instance_is_multi_az(self, template: Template) -> None:
        template.has_resource_properties("AWS::RDS::DBInstance", {"MultiAZ": True})

    def test_the_instance_is_not_publicly_accessible(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::RDS::DBInstance", {"PubliclyAccessible": False}
        )

    def test_storage_is_encrypted_with_the_customer_managed_key(
        self, template: Template
    ) -> None:
        template.has_resource_properties(
            "AWS::RDS::DBInstance",
            {"StorageEncrypted": True, "KmsKeyId": Match.any_value()},
        )

    def test_deletion_protection_is_on_and_the_instance_is_retained(
        self, template: Template
    ) -> None:
        template.has_resource_properties(
            "AWS::RDS::DBInstance", {"DeletionProtection": True}
        )
        template.has_resource("AWS::RDS::DBInstance", {"DeletionPolicy": "Retain"})

    def test_plaintext_connections_are_refused_by_the_server(
        self, template: Template
    ) -> None:
        template.has_resource_properties(
            "AWS::RDS::DBParameterGroup",
            {"Parameters": {FORCE_SSL_PARAMETER: "1"}},
        )

    def test_the_instance_lives_in_a_subnet_group(self, template: Template) -> None:
        template.resource_count_is("AWS::RDS::DBSubnetGroup", 1)


class TestNoCustomerContentLeaves:
    def test_performance_insights_is_not_enabled(self, template: Template) -> None:
        """It captures SQL text, and this application's SQL text carries retail literals."""
        instance = _properties(template, "AWS::RDS::DBInstance")

        assert instance.get("EnablePerformanceInsights") in (None, False)

    def test_no_postgresql_logs_are_exported(self, template: Template) -> None:
        """PostgreSQL logs carry statement text on error, which is not content-free."""
        instance = _properties(template, "AWS::RDS::DBInstance")

        assert not instance.get("EnableCloudwatchLogsExports")


class TestCredential:
    def test_the_password_is_generated_into_secrets_manager(
        self, template: Template
    ) -> None:
        template.resource_count_is("AWS::SecretsManager::Secret", 1)

    def test_the_secret_is_encrypted_with_the_customer_managed_key(
        self, template: Template
    ) -> None:
        template.has_resource_properties(
            "AWS::SecretsManager::Secret", {"KmsKeyId": Match.any_value()}
        )

    def test_the_password_is_a_secret_reference_and_never_a_literal(
        self, template: Template
    ) -> None:
        """The template ships a resolve-at-deploy reference, so no password exists in it."""
        instance = _properties(template, "AWS::RDS::DBInstance")
        rendered = str(instance["MasterUserPassword"])

        assert "{{resolve:secretsmanager:" in rendered
        assert ":SecretString:password::}}" in rendered

    def test_the_database_name_is_declared(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::RDS::DBInstance", {"DBName": DATABASE_NAME}
        )


class TestSizingReachesTheTemplate:
    def test_the_declared_instance_class_survives_the_prefix_round_trip(
        self, template: Template
    ) -> None:
        """`ec2.InstanceType` wants the class without `db.`; CloudFormation wants it back.

        So the declaration is stripped on the way in and must reappear intact on the way out. A
        class that arrived with the prefix doubled or missing would deploy as a different size.
        """
        template.has_resource_properties(
            "AWS::RDS::DBInstance", {"DBInstanceClass": INSTANCE_CLASS}
        )
        assert INSTANCE_CLASS.startswith("db.")

    def test_the_declared_allocation_and_storage_type_are_used(
        self, template: Template
    ) -> None:
        template.has_resource_properties(
            "AWS::RDS::DBInstance",
            {"AllocatedStorage": str(ALLOCATED_STORAGE_GIB), "StorageType": "gp3"},
        )

    def test_the_declared_backup_horizon_is_used(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::RDS::DBInstance", {"BackupRetentionPeriod": BACKUP_RETENTION_DAYS}
        )

    def test_a_resized_declaration_changes_the_template(self) -> None:
        resized = _synthesize(
            DatabaseSize(
                instance_class="db.m7g.xlarge",
                allocated_storage_gib=200,
                backup_retention_days=14,
            )
        )

        resized.has_resource_properties(
            "AWS::RDS::DBInstance",
            {
                "DBInstanceClass": "db.m7g.xlarge",
                "AllocatedStorage": "200",
                "BackupRetentionPeriod": 14,
            },
        )


def _properties(template: Template, resource_type: str) -> dict[str, object]:
    resources = template.find_resources(resource_type)

    assert len(resources) == 1
    return next(iter(resources.values()))["Properties"]
