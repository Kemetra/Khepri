"""The encrypted store and the report queue, with the controls that may not be optional.

**Why a construct and not a stack.** `KHEPRI-DEC-005` selects one set of data services -- a KMS
customer-managed key, one private ephemeral-content bucket, and an SQS Standard queue with a
dead-letter queue -- and `KHEPRI-DEC-007` requires the beta and benchmark environments to be two
instantiations of one definition rather than two definitions kept in sync. A construct is what
makes that literal: composing it twice cannot produce two different sets of controls, because
there is only one place the controls are written.

**None of these resources needs a size, except the queue.** Bucket and key configuration is
policy, and policy comes from an accepted decision. The queue's timings and redrive bound are
sizing, so they arrive as a `QueueSizing` that `sizing.resolve_sizing` already refused to invent.
Nothing here reads an environment variable, a context value, or a default.

**Encryption is one key, deliberately.** The bucket and both queues use the same customer-managed
key, so `KHEPRI-DEC-005` audit of infrastructure access through KMS covers uploads, generated
artifacts, and job messages under one auditable grant rather than three. `KHEPRI-DEC-007`
requires the benchmark environment never to share the beta environment's key, which holds because
the key is created inside this construct: two instantiations are two keys.

**The seven-day expiration is a backstop and is written as one.** `KHEPRI-DEC-005` states that
lifecycle expiration is not proof of timely application deletion, so the rule here exists to
bound worst-case residency, never to satisfy the `RRA-002` deletion obligation. The companion
rule aborting incomplete multipart uploads exists because an abandoned upload is content that no
indexed-object deletion would find.

**No customer content, identifier, or bucket name appears in this module.** Names are derived by
CDK from the construct path, which is why the bucket takes no explicit name: an explicit one
would be a global-namespace collision between the two environments and a value worth guessing.
"""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_sqs as sqs
from constructs import Construct

from khepri.infra.sizing import QueueSizing, QueueTimings

# KHEPRI-DEC-005 fixes the expiration rule at seven days. It is a governed number, not a tunable.
CONTENT_EXPIRATION_DAYS = 7

# An incomplete multipart upload holds uploaded parts that are not yet an object, so no
# indexed-object deletion reaches them. One day is short enough that an abandoned upload cannot
# outlive the content it belongs to.
ABORT_INCOMPLETE_UPLOAD_DAYS = 1


@dataclass(frozen=True, slots=True)
class ReportQueues:
    """The report queue and the dead-letter queue exhausted messages land in."""

    queue: sqs.Queue
    dead_letter: sqs.Queue


class GovernedDataResources(Construct):
    """One environment's encryption key, content bucket, and report queues."""

    def __init__(self, scope: Construct, construct_id: str, queue: QueueSizing) -> None:
        super().__init__(scope, construct_id)
        self.key = _customer_managed_key(self)
        self.bucket = _ephemeral_content_bucket(self, self.key)
        queues = _report_queues(self, self.key, queue)
        self.queue = queues.queue
        self.dead_letter_queue = queues.dead_letter


def _customer_managed_key(scope: Construct) -> kms.Key:
    """The single customer-managed key every resource below is encrypted with."""
    return kms.Key(
        scope,
        "ContentKey",
        enable_key_rotation=True,
        removal_policy=RemovalPolicy.RETAIN,
    )


def _ephemeral_content_bucket(scope: Construct, key: kms.Key) -> s3.Bucket:
    """The private, non-versioned bucket holding uploads and generated artifacts."""
    return s3.Bucket(
        scope,
        "ContentBucket",
        encryption=s3.BucketEncryption.KMS,
        encryption_key=key,
        bucket_key_enabled=True,
        block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
        public_read_access=False,
        versioned=False,
        enforce_ssl=True,
        object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
        lifecycle_rules=[_expiration_rule()],
        removal_policy=RemovalPolicy.RETAIN,
    )


def _expiration_rule() -> s3.LifecycleRule:
    return s3.LifecycleRule(
        id="ExpireEphemeralContent",
        enabled=True,
        expiration=Duration.days(CONTENT_EXPIRATION_DAYS),
        abort_incomplete_multipart_upload_after=Duration.days(ABORT_INCOMPLETE_UPLOAD_DAYS),
    )


def _report_queues(scope: Construct, key: kms.Key, sizing: QueueSizing) -> ReportQueues:
    """The queue pair, sized from an approved declaration and encrypted with one key."""
    dead_letter = sqs.Queue(
        scope,
        "ReportDeadLetterQueue",
        encryption=sqs.QueueEncryption.KMS,
        encryption_master_key=key,
        enforce_ssl=True,
        retention_period=Duration.seconds(sizing.timings.message_retention_seconds),
        removal_policy=RemovalPolicy.RETAIN,
    )
    queue = sqs.Queue(
        scope,
        "ReportQueue",
        encryption=sqs.QueueEncryption.KMS,
        encryption_master_key=key,
        enforce_ssl=True,
        dead_letter_queue=sqs.DeadLetterQueue(
            queue=dead_letter,
            max_receive_count=sizing.retries.max_receive_count,
        ),
        removal_policy=RemovalPolicy.RETAIN,
        **_queue_timings(sizing.timings),
    )
    return ReportQueues(queue=queue, dead_letter=dead_letter)


def _queue_timings(timings: QueueTimings) -> dict[str, Duration]:
    """Every timing the approved declaration supplies, and no timing it does not."""
    return {
        "visibility_timeout": Duration.seconds(timings.visibility_timeout_seconds),
        "retention_period": Duration.seconds(timings.message_retention_seconds),
        "receive_message_wait_time": Duration.seconds(timings.receive_wait_seconds),
    }


__all__ = [
    "ABORT_INCOMPLETE_UPLOAD_DAYS",
    "CONTENT_EXPIRATION_DAYS",
    "GovernedDataResources",
    "ReportQueues",
]
