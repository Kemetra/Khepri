from __future__ import annotations

import pytest
from aws_cdk import App
from aws_cdk.assertions import Template

from khepri.infra.compute import WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME
from khepri.infra.environment import REGION, EnvironmentProps, RraEnvironmentStack
from khepri.infra.sizing_source import load_sizing

IMAGE_DIGEST = "sha256:" + "ab" * 32


def _stack(name: str) -> RraEnvironmentStack:
    return RraEnvironmentStack(
        App(),
        name,
        EnvironmentProps(
            sizing=load_sizing(),
            image_digest=IMAGE_DIGEST,
        ),
    )


@pytest.fixture(scope="module")
def benchmark() -> Template:
    return Template.from_stack(_stack("Benchmark"))


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
        assert _stack("Pinned").region == REGION


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
        EnvironmentProps(sizing=load_sizing(), image_digest=digest),
    )


class TestTheTwoEnvironmentsAreIdenticallySized:
    """KHEPRI-DEC-007 requires every sizing value to be identical between the two.

    Comparing the synthesized templates rather than the InfrastructureSizing object is deliberate:
    the same object can still be applied differently downstream, and it is the template that gets
    deployed.
    """

    @staticmethod
    def _properties(template: Template, resource_type: str) -> list[dict]:
        return [
            resource["Properties"]
            for resource in template.find_resources(resource_type).values()
        ]

    @pytest.fixture(scope="class")
    def templates(self) -> tuple[Template, Template]:
        from khepri.infra.app import build_app

        app = build_app(IMAGE_DIGEST)
        stacks = [child for child in app.node.children if isinstance(child, RraEnvironmentStack)]
        assert len(stacks) == 2
        return tuple(Template.from_stack(stack) for stack in stacks)  # type: ignore[return-value]

    def test_both_task_definitions_agree_on_cpu_memory_and_disk(
        self, templates: tuple[Template, Template]
    ) -> None:
        """Keyed by container name so a web/worker role swap cannot pass as parity.

        A bag of (Cpu, Memory, EphemeralStorage) tuples with no container identity is blind to a
        benchmark whose web service is sized like beta's worker and vice versa: the same two
        tuples appear in both sets, so set equality holds despite the roles being swapped. Keying
        by container name makes the comparison per-role instead.
        """

        def sizes(template: Template) -> dict[str, tuple[str, str, str]]:
            result: dict[str, tuple[str, str, str]] = {}
            for properties in self._properties(template, "AWS::ECS::TaskDefinition"):
                containers = properties["ContainerDefinitions"]
                assert len(containers) == 1
                name = containers[0]["Name"]
                result[name] = (
                    properties["Cpu"],
                    properties["Memory"],
                    str(properties.get("EphemeralStorage", {}).get("SizeInGiB", "default")),
                )
            assert set(result) == {WEB_CONTAINER_NAME, WORKER_CONTAINER_NAME}
            return result

        beta, benchmark = templates
        assert sizes(beta) == sizes(benchmark)

    def test_both_databases_agree_on_class_storage_and_retention(
        self, templates: tuple[Template, Template]
    ) -> None:
        """Compared as a list, not a set, so multiplicity is part of the assertion.

        A set would collapse a second identically-sized instance into one member, and it would
        rely on the count-of-one asserted in a different test to mean anything at all. The
        environment has exactly one store; comparing sequences says so here rather than borrowing
        that guarantee from elsewhere.
        """

        def store(template: Template) -> list[tuple[object, ...]]:
            return [
                (
                    properties["DBInstanceClass"],
                    properties["AllocatedStorage"],
                    properties["StorageType"],
                    properties["BackupRetentionPeriod"],
                    properties.get("MultiAZ"),
                )
                for properties in self._properties(template, "AWS::RDS::DBInstance")
            ]

        beta, benchmark = templates
        assert len(store(beta)) == 1
        assert store(beta) == store(benchmark)

    def test_both_queue_sets_agree_on_timings_and_the_redrive_bound(
        self, templates: tuple[Template, Template]
    ) -> None:
        """Keyed by whether the queue carries a RedrivePolicy, not compared as a bag.

        A bag of (VisibilityTimeout, MessageRetentionPeriod, ReceiveMessageWaitTimeSeconds,
        maxReceiveCount) tuples has no identity beyond its own values, so the main report queue and
        its dead-letter queue could exchange settings entirely and set equality would still hold.
        `data_resources.py` constructs only the report queue with `dead_letter_queue=`, so only that
        queue's CloudFormation properties carry a `RedrivePolicy` -- the dead-letter queue never
        redrives anywhere. That makes "has a RedrivePolicy" a stable, role-defining discriminator
        rather than an incidental setting, unlike the CDK-derived logical ID.
        """

        def queues(template: Template) -> dict[str, tuple[object, object, object, str]]:
            result: dict[str, tuple[object, object, object, str]] = {}
            for properties in self._properties(template, "AWS::SQS::Queue"):
                has_redrive = "RedrivePolicy" in properties
                role = "report_queue" if has_redrive else "dead_letter_queue"
                result[role] = (
                    properties.get("VisibilityTimeout"),
                    properties.get("MessageRetentionPeriod"),
                    properties.get("ReceiveMessageWaitTimeSeconds"),
                    str(properties.get("RedrivePolicy", {}).get("maxReceiveCount", "none")),
                )
            assert set(result) == {"report_queue", "dead_letter_queue"}
            return result

        beta, benchmark = templates
        assert queues(beta) == queues(benchmark)

    def test_both_stacks_pin_the_same_region(self) -> None:
        from khepri.infra.app import build_app

        app = build_app(IMAGE_DIGEST)
        stacks = [child for child in app.node.children if isinstance(child, RraEnvironmentStack)]
        assert {stack.region for stack in stacks} == {REGION}

    def test_they_do_not_share_a_key_bucket_database_or_queue(
        self, templates: tuple[Template, Template]
    ) -> None:
        """KHEPRI-DEC-007 forbids the benchmark sharing beta's key, bucket, instance, or queues."""
        beta, benchmark = templates
        for resource_type, expected in (
            ("AWS::KMS::Key", 1),
            ("AWS::S3::Bucket", 1),
            ("AWS::RDS::DBInstance", 1),
            ("AWS::SQS::Queue", 2),
            ("AWS::ECS::TaskDefinition", 2),
        ):
            beta.resource_count_is(resource_type, expected)
            benchmark.resource_count_is(resource_type, expected)
