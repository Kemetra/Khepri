"""The authoritative store, and the two features it deliberately does not enable.

**What is settled elsewhere.** `KHEPRI-DEC-005` selects RDS for PostgreSQL 17, Multi-AZ, with
encrypted storage and backups, TLS connections, and a KMS customer-managed key.
`KHEPRI-DEC-007` sizes it. Neither is re-decided here, and no size appears in this file: the
instance class, allocation, and backup horizon arrive as a `DatabaseSize` that
`sizing.resolve_sizing` already refused to invent.

**The major version is pinned and the minor version is not.** `KHEPRI-DEC-005` pins PostgreSQL
17. `KHEPRI-DEC-007` states that the minor version is a fact the environment descriptor records at
provisioning rather than a number a decision invents, and requires automatic minor upgrade to be
off so an upgrade cannot change the engine underneath an approved `environment_digest`. So the
engine is declared as major 17 with automatic minor upgrade disabled, and nothing here names a
minor.

**Performance Insights is not enabled, on purpose.** It captures SQL text, and SQL text from this
application contains literal values drawn from customer retail data. Enabling it would put
customer content into a telemetry store that `RRA-007` and `KHEPRI-DEC-005` both require to be
content-free. The same reasoning excludes exporting the PostgreSQL error and query logs to
CloudWatch: those logs carry statement text on error. Neither omission is an oversight, and both
are asserted by tests so that a later "add observability" change has to argue with them.

**TLS is required by parameter, not by convention.** `rds.force_ssl` is set to 1 so the server
refuses a plaintext connection, which is what makes the `KHEPRI-DEC-005` TLS requirement a
property of the database rather than of every client that happens to be configured correctly.

**The instance is not publicly accessible and lives in the isolated subnets.** There is no NAT
gateway and no route to the internet in those subnets, so the database is unreachable from outside
the VPC by construction as well as by flag.
"""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_kms as kms
from aws_cdk import aws_rds as rds
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from khepri.infra.sizing import DatabaseSize

# KHEPRI-DEC-005 pins the major version. KHEPRI-DEC-007 leaves the minor to the descriptor, so
# the engine is declared by major version alone and RDS resolves the minor at provisioning.
POSTGRES_MAJOR_VERSION = "17"

# The database user the application connects as. It is not a secret, and the password it is
# paired with is generated into Secrets Manager rather than written anywhere.
DATABASE_USERNAME = "khepri"

DATABASE_NAME = "khepri"

# Setting this to "1" makes the server refuse a non-TLS connection.
FORCE_SSL_PARAMETER = "rds.force_ssl"


@dataclass(frozen=True, slots=True)
class DatabaseProps:
    """Everything the store needs from the rest of the environment."""

    vpc: ec2.IVpc
    key: kms.IKey
    sizing: DatabaseSize


class GovernedDatabase(Construct):
    """One environment's Multi-AZ PostgreSQL instance and its generated credential."""

    def __init__(self, scope: Construct, construct_id: str, props: DatabaseProps) -> None:
        super().__init__(scope, construct_id)
        self.parameter_group = _tls_only_parameter_group(self)
        self.instance = _postgres_instance(self, props, self.parameter_group)

    @property
    def secret(self) -> secretsmanager.ISecret | None:
        """The generated credential, held in Secrets Manager and encrypted with the same key."""
        return self.instance.secret


def _tls_only_parameter_group(scope: Construct) -> rds.ParameterGroup:
    return rds.ParameterGroup(
        scope,
        "ParameterGroup",
        engine=_engine(),
        parameters={FORCE_SSL_PARAMETER: "1"},
    )


def _engine() -> rds.IInstanceEngine:
    return rds.DatabaseInstanceEngine.postgres(
        version=rds.PostgresEngineVersion.of(POSTGRES_MAJOR_VERSION, POSTGRES_MAJOR_VERSION)
    )


def _postgres_instance(
    scope: Construct, props: DatabaseProps, parameter_group: rds.ParameterGroup
) -> rds.DatabaseInstance:
    return rds.DatabaseInstance(
        scope,
        "Instance",
        engine=_engine(),
        instance_type=_instance_type(props.sizing.instance_class),
        vpc=props.vpc,
        vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
        multi_az=True,
        publicly_accessible=False,
        storage_encrypted=True,
        storage_encryption_key=props.key,
        storage_type=rds.StorageType.GP3,
        allocated_storage=props.sizing.allocated_storage_gib,
        backup_retention=Duration.days(props.sizing.backup_retention_days),
        auto_minor_version_upgrade=False,
        deletion_protection=True,
        parameter_group=parameter_group,
        credentials=_generated_credentials(props.key),
        database_name=DATABASE_NAME,
        removal_policy=RemovalPolicy.RETAIN,
    )


def _instance_type(instance_class: str) -> ec2.InstanceType:
    """Turn an RDS instance class into the EC2 type CDK expects.

    RDS names classes with a `db.` prefix and CDK wants the class without it, which is the reason
    `sizing` validates that prefix rather than accepting any string.
    """
    return ec2.InstanceType(instance_class.removeprefix("db."))


def _generated_credentials(key: kms.IKey) -> rds.Credentials:
    """A password nobody chose, stored where KHEPRI-DEC-005 requires runtime secrets to live."""
    return rds.Credentials.from_generated_secret(DATABASE_USERNAME, encryption_key=key)


__all__ = [
    "DATABASE_NAME",
    "DATABASE_USERNAME",
    "FORCE_SSL_PARAMETER",
    "POSTGRES_MAJOR_VERSION",
    "DatabaseProps",
    "GovernedDatabase",
]
