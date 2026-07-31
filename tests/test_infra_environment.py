from __future__ import annotations

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template

from khepri.infra.environment import REGION, EnvironmentProps, RraEnvironmentStack
from khepri.infra.sizing_source import load_sizing

IMAGE_DIGEST = "sha256:" + "ab" * 32


def _stack(name: str, *, desired_count: int | None) -> RraEnvironmentStack:
    return RraEnvironmentStack(
        App(),
        name,
        EnvironmentProps(
            sizing=load_sizing(),
            image_digest=IMAGE_DIGEST,
            desired_count=desired_count,
        ),
    )


@pytest.fixture(scope="module")
def benchmark() -> Template:
    return Template.from_stack(_stack("Benchmark", desired_count=1))


class TestItComposesEveryGovernedResource:
    def test_the_isolated_network_is_present(self, benchmark: Template) -> None:
        benchmark.resource_count_is("AWS::EC2::VPC", 1)
        benchmark.resource_count_is("AWS::EC2::NatGateway", 0)

    def test_one_customer_managed_key_encrypts_the_environment(
        self, benchmark: Template
    ) -> None:
        """KHEPRI-DEC-005 audits infrastructure access through one KMS grant."""
        benchmark.resource_count_is("AWS::KMS::Key", 1)

    def test_the_content_bucket_and_both_queues_exist(self, benchmark: Template) -> None:
        benchmark.resource_count_is("AWS::S3::Bucket", 1)
        benchmark.resource_count_is("AWS::SQS::Queue", 2)

    def test_the_database_and_both_task_definitions_exist(
        self, benchmark: Template
    ) -> None:
        benchmark.resource_count_is("AWS::RDS::DBInstance", 1)
        benchmark.resource_count_is("AWS::ECS::TaskDefinition", 2)


class TestTheRegionIsPinned:
    def test_the_stack_names_me_central_1_rather_than_inheriting_one(self) -> None:
        """KHEPRI-DEC-007 requires the definition to fail rather than substitute a neighbour.

        A stack with no explicit env is region-agnostic and deploys wherever CDK_DEFAULT_REGION
        points, which is substitution by omission.
        """
        assert REGION == "me-central-1"
        assert _stack("Pinned", desired_count=1).region == REGION


class TestItRefusesRatherThanDefaulting:
    def test_a_tag_is_not_an_image_digest(self) -> None:
        with pytest.raises(ValueError):
            _stack_with_digest("latest")

    def test_a_malformed_digest_is_refused(self) -> None:
        with pytest.raises(ValueError):
            _stack_with_digest("sha256:abc")


def _stack_with_digest(digest: str) -> RraEnvironmentStack:
    return RraEnvironmentStack(
        App(),
        "Bad",
        EnvironmentProps(sizing=load_sizing(), image_digest=digest, desired_count=1),
    )
