"""The network, which reaches the internet in exactly one direction.

**Why there is no NAT gateway.** `KHEPRI-DEC-005` puts application tasks, PostgreSQL, and
internal endpoints in private subnets, and the only public entry point it authorizes is an
Application Load Balancer terminating HTTPS for the web service. Nothing in the approved
architecture requires a task to originate a connection to the internet: the OpenAI adapter is the
one component that would, and that decision keeps it disabled until an executed data-processing
agreement and a verified Zero Data Retention configuration exist. So the private subnets are
isolated rather than egress-capable, and the services reach AWS through interface and gateway
endpoints inside the VPC.

That is the fail-closed arrangement, not the frugal one. With no route to the internet, a
dependency that tried to phone home, a browser that tried to fetch a remote asset, or an adapter
enabled before its gates were verified fails instead of succeeding quietly. Enabling narrative
generation later therefore requires adding egress deliberately, which is a governed change rather
than a configuration one.

**Two availability zones, because that is what the accepted decision requires.** `KHEPRI-DEC-005`
requires Multi-AZ PostgreSQL, which needs at least two. No approved artifact settles a wider
spread, and inventing three would be a sizing choice nobody made, so this is the minimum that
satisfies the requirement rather than a preference.

**Flow logs record no customer content.** They carry addresses, ports, byte counts, and accept or
reject decisions -- never a filename, label, figure, or narrative sentence. They are here because
`KHEPRI-DEC-005` requires infrastructure access to be auditable without recording customer
content, and they are one of the few controls that can show an unexpected connection was refused.
"""

from __future__ import annotations

from aws_cdk import RemovalPolicy
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_logs as logs
from constructs import Construct

# Multi-AZ PostgreSQL requires two availability zones. No approved artifact settles more.
AVAILABILITY_ZONES = 2

# The private subnets hold the services and the database and are deliberately unroutable to the
# internet. The public subnets exist only for the load balancer KHEPRI-DEC-005 authorizes.
PUBLIC_SUBNET_NAME = "Public"
PRIVATE_SUBNET_NAME = "Private"

# Every AWS service the services must reach without leaving the VPC. S3 is a gateway endpoint
# because it is the content store and a gateway endpoint keeps that traffic off any ENI.
INTERFACE_ENDPOINTS: tuple[tuple[str, ec2.InterfaceVpcEndpointAwsService], ...] = (
    ("EcrApi", ec2.InterfaceVpcEndpointAwsService.ECR),
    ("EcrDocker", ec2.InterfaceVpcEndpointAwsService.ECR_DOCKER),
    ("SecretsManager", ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER),
    ("CloudWatchLogs", ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS),
    ("Kms", ec2.InterfaceVpcEndpointAwsService.KMS),
    ("Sqs", ec2.InterfaceVpcEndpointAwsService.SQS),
)

FLOW_LOG_RETENTION = logs.RetentionDays.ONE_MONTH


class GovernedNetwork(Construct):
    """One environment's VPC: public subnets for the load balancer, isolated ones for everything."""

    def __init__(self, scope: Construct, construct_id: str) -> None:
        super().__init__(scope, construct_id)
        self.vpc = _isolated_vpc(self)
        self.endpoint_security_group = _endpoint_security_group(self, self.vpc)
        _add_endpoints(self.vpc, self.endpoint_security_group)


def _isolated_vpc(scope: Construct) -> ec2.Vpc:
    return ec2.Vpc(
        scope,
        "Vpc",
        max_azs=AVAILABILITY_ZONES,
        nat_gateways=0,
        restrict_default_security_group=True,
        subnet_configuration=[
            ec2.SubnetConfiguration(
                name=PUBLIC_SUBNET_NAME, subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24
            ),
            ec2.SubnetConfiguration(
                name=PRIVATE_SUBNET_NAME,
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                cidr_mask=22,
            ),
        ],
        flow_logs={"All": _flow_log_options(scope)},
    )


def _flow_log_options(scope: Construct) -> ec2.FlowLogOptions:
    """Accepted and rejected connections, with no customer content in either."""
    group = logs.LogGroup(
        scope,
        "FlowLogs",
        retention=FLOW_LOG_RETENTION,
        removal_policy=RemovalPolicy.RETAIN,
    )
    return ec2.FlowLogOptions(
        destination=ec2.FlowLogDestination.to_cloud_watch_logs(group),
        traffic_type=ec2.FlowLogTrafficType.ALL,
    )


def _endpoint_security_group(scope: Construct, vpc: ec2.IVpc) -> ec2.SecurityGroup:
    """HTTPS from inside this VPC only, and from nothing else."""
    group = ec2.SecurityGroup(
        scope,
        "EndpointSecurityGroup",
        vpc=vpc,
        allow_all_outbound=False,
        description="HTTPS to AWS interface endpoints from within the VPC",
    )
    group.add_ingress_rule(
        peer=ec2.Peer.ipv4(vpc.vpc_cidr_block),
        connection=ec2.Port.tcp(443),
        description="HTTPS from within the VPC",
    )
    return group


def _add_endpoints(vpc: ec2.Vpc, security_group: ec2.SecurityGroup) -> None:
    """Every route out of the isolated subnets, and there is no other one."""
    vpc.add_gateway_endpoint("S3", service=ec2.GatewayVpcEndpointAwsService.S3)
    for name, service in INTERFACE_ENDPOINTS:
        vpc.add_interface_endpoint(
            name,
            service=service,
            security_groups=[security_group],
            subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED),
        )


__all__ = [
    "AVAILABILITY_ZONES",
    "FLOW_LOG_RETENTION",
    "INTERFACE_ENDPOINTS",
    "PRIVATE_SUBNET_NAME",
    "PUBLIC_SUBNET_NAME",
    "GovernedNetwork",
]
