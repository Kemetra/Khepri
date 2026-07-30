from __future__ import annotations

import pytest
from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from khepri.infra.network import (
    AVAILABILITY_ZONES,
    INTERFACE_ENDPOINTS,
    GovernedNetwork,
)


@pytest.fixture(scope="module")
def template() -> Template:
    stack = Stack(App(), "NetworkStack")
    GovernedNetwork(stack, "Network")
    return Template.from_stack(stack)


class TestNoInternetEgress:
    def test_no_nat_gateway_is_created(self, template: Template) -> None:
        """KHEPRI-DEC-005 authorizes one public entry point and no outbound path."""
        template.resource_count_is("AWS::EC2::NatGateway", 0)

    def test_no_egress_only_gateway_is_created(self, template: Template) -> None:
        template.resource_count_is("AWS::EC2::EgressOnlyInternetGateway", 0)

    def test_the_private_subnets_have_no_default_route(self, template: Template) -> None:
        """A private route table with a 0.0.0.0/0 entry would be an egress path."""
        routes = template.find_resources("AWS::EC2::Route")
        default_routes = [
            route
            for route in routes.values()
            if route["Properties"].get("DestinationCidrBlock") == "0.0.0.0/0"
        ]

        assert len(default_routes) == AVAILABILITY_ZONES
        for route in default_routes:
            assert "GatewayId" in route["Properties"]
            assert "NatGatewayId" not in route["Properties"]

    def test_an_internet_gateway_exists_only_for_the_public_subnets(
        self, template: Template
    ) -> None:
        template.resource_count_is("AWS::EC2::InternetGateway", 1)


class TestSubnets:
    def test_two_availability_zones_are_used(self, template: Template) -> None:
        """Multi-AZ PostgreSQL needs two; no approved artifact settles a wider spread."""
        assert AVAILABILITY_ZONES == 2
        template.resource_count_is("AWS::EC2::Subnet", AVAILABILITY_ZONES * 2)

    def test_the_private_subnets_do_not_assign_public_addresses(
        self, template: Template
    ) -> None:
        subnets = template.find_resources("AWS::EC2::Subnet")
        private = [
            subnet
            for subnet in subnets.values()
            if not subnet["Properties"].get("MapPublicIpOnLaunch", False)
        ]

        assert len(private) == AVAILABILITY_ZONES

    def test_the_default_security_group_is_restricted(self, template: Template) -> None:
        template.resource_count_is("Custom::VpcRestrictDefaultSG", 1)


class TestEndpoints:
    def test_s3_is_reached_through_a_gateway_endpoint(self, template: Template) -> None:
        endpoints = template.find_resources("AWS::EC2::VPCEndpoint")
        gateway = [
            endpoint
            for endpoint in endpoints.values()
            if endpoint["Properties"].get("VpcEndpointType") == "Gateway"
        ]

        assert len(gateway) == 1

    def test_every_declared_interface_endpoint_is_created(self, template: Template) -> None:
        endpoints = template.find_resources("AWS::EC2::VPCEndpoint")
        interfaces = [
            endpoint
            for endpoint in endpoints.values()
            if endpoint["Properties"].get("VpcEndpointType") == "Interface"
        ]

        assert len(interfaces) == len(INTERFACE_ENDPOINTS)

    def test_the_endpoint_security_group_admits_only_the_vpc(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::EC2::SecurityGroup",
            {
                "SecurityGroupIngress": Match.array_with(
                    [
                        Match.object_like(
                            {"FromPort": 443, "ToPort": 443, "IpProtocol": "tcp"}
                        )
                    ]
                )
            },
        )

    def test_the_endpoint_security_group_does_not_allow_all_outbound(
        self, template: Template
    ) -> None:
        groups = template.find_resources(
            "AWS::EC2::SecurityGroup",
            {
                "Properties": {
                    "GroupDescription": Match.string_like_regexp(
                        ".*interface endpoints.*"
                    )
                }
            },
        )

        assert len(groups) == 1
        properties = next(iter(groups.values()))["Properties"]
        egress = properties.get("SecurityGroupEgress", [])
        assert all(rule.get("CidrIp") != "0.0.0.0/0" for rule in egress)


class TestFlowLogs:
    def test_flow_logs_capture_accepted_and_rejected_traffic(self, template: Template) -> None:
        template.has_resource_properties("AWS::EC2::FlowLog", {"TrafficType": "ALL"})

    def test_flow_logs_go_to_a_retained_log_group(self, template: Template) -> None:
        template.has_resource("AWS::Logs::LogGroup", {"DeletionPolicy": "Retain"})


def test_two_environments_share_no_vpc() -> None:
    app = App()
    beta = Stack(app, "BetaNetwork")
    benchmark = Stack(app, "BenchmarkNetwork")
    GovernedNetwork(beta, "Network")
    GovernedNetwork(benchmark, "Network")

    for stack in (beta, benchmark):
        Template.from_stack(stack).resource_count_is("AWS::EC2::VPC", 1)
