from __future__ import annotations

import pytest
from aws_cdk import App, Stack
from aws_cdk.assertions import Match, Template

from khepri.infra.data_resources import (
    ABORT_INCOMPLETE_UPLOAD_DAYS,
    CONTENT_EXPIRATION_DAYS,
    GovernedDataResources,
)
from khepri.infra.sizing import QueueSizing, QueueTimings, RetryBounds

VISIBILITY_TIMEOUT_SECONDS = 300
MESSAGE_RETENTION_SECONDS = 1209600
RECEIVE_WAIT_SECONDS = 20
MAX_RECEIVE_COUNT = 3


def _queue_sizing() -> QueueSizing:
    return QueueSizing(
        timings=QueueTimings(
            visibility_timeout_seconds=VISIBILITY_TIMEOUT_SECONDS,
            message_retention_seconds=MESSAGE_RETENTION_SECONDS,
            receive_wait_seconds=RECEIVE_WAIT_SECONDS,
        ),
        retries=RetryBounds(max_receive_count=MAX_RECEIVE_COUNT, max_attempts=MAX_RECEIVE_COUNT),
    )


def _synthesize() -> Template:
    stack = Stack(App(), "TestStack")
    GovernedDataResources(stack, "Data", _queue_sizing())
    return Template.from_stack(stack)


@pytest.fixture(scope="module")
def template() -> Template:
    return _synthesize()


class TestEncryptionKey:
    def test_exactly_one_customer_managed_key_is_created(self, template: Template) -> None:
        template.resource_count_is("AWS::KMS::Key", 1)

    def test_the_key_rotates(self, template: Template) -> None:
        template.has_resource_properties("AWS::KMS::Key", {"EnableKeyRotation": True})

    def test_the_key_survives_stack_deletion(self, template: Template) -> None:
        template.has_resource("AWS::KMS::Key", {"DeletionPolicy": "Retain"})


class TestContentBucket:
    def test_exactly_one_bucket_is_created(self, template: Template) -> None:
        template.resource_count_is("AWS::S3::Bucket", 1)

    def test_the_bucket_is_encrypted_with_the_customer_managed_key(
        self, template: Template
    ) -> None:
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "BucketEncryption": {
                    "ServerSideEncryptionConfiguration": [
                        {
                            "BucketKeyEnabled": True,
                            "ServerSideEncryptionByDefault": {
                                "SSEAlgorithm": "aws:kms",
                                "KMSMasterKeyID": Match.any_value(),
                            },
                        }
                    ]
                }
            },
        )

    def test_all_public_access_is_blocked(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "PublicAccessBlockConfiguration": {
                    "BlockPublicAcls": True,
                    "BlockPublicPolicy": True,
                    "IgnorePublicAcls": True,
                    "RestrictPublicBuckets": True,
                }
            },
        )

    def test_the_bucket_is_not_versioned(self, template: Template) -> None:
        """KHEPRI-DEC-005 requires non-versioned, because a version is content deletion misses."""
        bucket = template.find_resources("AWS::S3::Bucket")
        properties = next(iter(bucket.values()))["Properties"]

        assert "VersioningConfiguration" not in properties

    def test_the_bucket_has_no_explicit_name(self, template: Template) -> None:
        """A fixed name would collide between environments and would be worth guessing."""
        bucket = template.find_resources("AWS::S3::Bucket")
        properties = next(iter(bucket.values()))["Properties"]

        assert "BucketName" not in properties

    def test_content_expires_after_seven_days(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::S3::Bucket",
            {
                "LifecycleConfiguration": {
                    "Rules": [
                        {
                            "Status": "Enabled",
                            "ExpirationInDays": CONTENT_EXPIRATION_DAYS,
                            "AbortIncompleteMultipartUpload": {
                                "DaysAfterInitiation": ABORT_INCOMPLETE_UPLOAD_DAYS
                            },
                        }
                    ]
                }
            },
        )

    def test_the_expiration_rule_is_seven_days_and_not_a_longer_horizon(self) -> None:
        assert CONTENT_EXPIRATION_DAYS == 7

    def test_non_tls_access_is_denied(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::S3::BucketPolicy",
            {
                "PolicyDocument": {
                    "Statement": Match.array_with(
                        [
                            Match.object_like(
                                {
                                    "Effect": "Deny",
                                    "Condition": {"Bool": {"aws:SecureTransport": "false"}},
                                }
                            )
                        ]
                    )
                }
            },
        )


class TestReportQueues:
    def test_a_queue_and_a_dead_letter_queue_are_created(self, template: Template) -> None:
        template.resource_count_is("AWS::SQS::Queue", 2)

    def test_neither_queue_is_fifo(self, template: Template) -> None:
        """KHEPRI-DEC-005 selects SQS Standard; PostgreSQL makes duplicate delivery safe."""
        for queue in template.find_resources("AWS::SQS::Queue").values():
            assert "FifoQueue" not in queue["Properties"]

    def test_both_queues_are_encrypted_with_the_customer_managed_key(
        self, template: Template
    ) -> None:
        queues = template.find_resources("AWS::SQS::Queue")

        assert len(queues) == 2
        for queue in queues.values():
            assert "KmsMasterKeyId" in queue["Properties"]

    def test_the_queue_carries_the_declared_timings(self, template: Template) -> None:
        template.has_resource_properties(
            "AWS::SQS::Queue",
            {
                "VisibilityTimeout": VISIBILITY_TIMEOUT_SECONDS,
                "MessageRetentionPeriod": MESSAGE_RETENTION_SECONDS,
                "ReceiveMessageWaitTimeSeconds": RECEIVE_WAIT_SECONDS,
            },
        )

    def test_exhausted_messages_redrive_to_the_dead_letter_queue(
        self, template: Template
    ) -> None:
        template.has_resource_properties(
            "AWS::SQS::Queue",
            {
                "RedrivePolicy": {
                    "maxReceiveCount": MAX_RECEIVE_COUNT,
                    "deadLetterTargetArn": Match.any_value(),
                }
            },
        )

    def test_the_dead_letter_queue_does_not_itself_redrive(self, template: Template) -> None:
        """A dead-letter queue with its own redrive would silently discard the evidence."""
        redriving = [
            queue
            for queue in template.find_resources("AWS::SQS::Queue").values()
            if "RedrivePolicy" in queue["Properties"]
        ]

        assert len(redriving) == 1

    def test_non_tls_access_to_the_queues_is_denied(self, template: Template) -> None:
        policies = template.find_resources("AWS::SQS::QueuePolicy")

        assert len(policies) == 2


class TestTwoEnvironmentsAreTwoInstantiations:
    def test_composing_twice_shares_no_key_bucket_or_queue(self) -> None:
        """KHEPRI-DEC-007 requires the benchmark environment to share nothing with beta."""
        app = App()
        beta = Stack(app, "BetaStack")
        benchmark = Stack(app, "BenchmarkStack")
        GovernedDataResources(beta, "Data", _queue_sizing())
        GovernedDataResources(benchmark, "Data", _queue_sizing())

        for stack in (beta, benchmark):
            template = Template.from_stack(stack)
            template.resource_count_is("AWS::KMS::Key", 1)
            template.resource_count_is("AWS::S3::Bucket", 1)
            template.resource_count_is("AWS::SQS::Queue", 2)

    def test_the_same_declaration_produces_the_same_controls(self) -> None:
        first = _synthesize().to_json()
        second = _synthesize().to_json()

        assert first == second


def test_a_different_declaration_changes_the_synthesized_queue() -> None:
    """Sizing reaches the template, so a resized queue is a different template."""
    stack = Stack(App(), "ResizedStack")
    resized = QueueSizing(
        timings=QueueTimings(
            visibility_timeout_seconds=600,
            message_retention_seconds=MESSAGE_RETENTION_SECONDS,
            receive_wait_seconds=RECEIVE_WAIT_SECONDS,
        ),
        retries=RetryBounds(max_receive_count=5, max_attempts=5),
    )
    GovernedDataResources(stack, "Data", resized)
    template = Template.from_stack(stack)

    template.has_resource_properties("AWS::SQS::Queue", {"VisibilityTimeout": 600})
    template.has_resource_properties(
        "AWS::SQS::Queue", {"RedrivePolicy": {"maxReceiveCount": 5}}
    )
