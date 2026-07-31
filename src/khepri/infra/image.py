"""The one image both services run, and the registry that refuses to let it change.

**Why immutable tags, and what they do not achieve.** `KHEPRI-DEC-007` pins Chromium transitively:
the browser is baked into the image, the environment descriptor records the image digest, and
`environment_digest` covers that record. Immutability protects one step of that: a tag already in
use cannot be silently repointed by a later push, so a build cannot overwrite the artifact a
descriptor was written against.

It is not a substitute for the digest, and this module does not pretend otherwise. Immutability
refuses an *overwrite*; `ecr:BatchDeleteImage` followed by a fresh push of the same tag is not an
overwrite, so any tag remains rewritable by a principal holding delete. That is why `compute.py`
references the image by digest and refuses to synthesize without one: the pin lives in the task
definition, and this repository only makes the pin harder to disturb. It also means the publishing
role should not hold `ecr:BatchDeleteImage` on this repository, which is a policy this construct
does not write.

**Why scan on push.** `KHEPRI-DEC-005` requires the pinned OCI image to be scanned before it is
published. Scanning at push is the only point where that happens without a human remembering to.

**Untagged images expire.** An untagged image is one a later push displaced. It cannot be the
image any descriptor cites, because a descriptor cites a digest that is still tagged, and keeping
it costs storage while adding a second artifact nobody can identify.

**Nothing here builds or publishes.** This is the registry, not the build. `KHEPRI-DEC-005`
assigns building, scanning, and publishing to GitHub Actions, and this construct only defines
where the result lands and under which controls.
"""

from __future__ import annotations

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_kms as kms
from constructs import Construct

# An untagged image is one a newer push displaced. Long enough to investigate, short enough that
# unidentifiable layers do not accumulate.
UNTAGGED_IMAGE_RETENTION_DAYS = 7


class GovernedImageRepository(Construct):
    """One environment's ECR repository, encrypted with the environment's own key."""

    def __init__(self, scope: Construct, construct_id: str, key: kms.IKey) -> None:
        super().__init__(scope, construct_id)
        self.repository = _repository(self, key)


def _repository(scope: Construct, key: kms.IKey) -> ecr.Repository:
    return ecr.Repository(
        scope,
        "Repository",
        image_tag_mutability=ecr.TagMutability.IMMUTABLE,
        image_scan_on_push=True,
        encryption=ecr.RepositoryEncryption.KMS,
        encryption_key=key,
        empty_on_delete=False,
        removal_policy=RemovalPolicy.RETAIN,
        lifecycle_rules=[
            ecr.LifecycleRule(
                rule_priority=1,
                description="Expire images no tag points at",
                tag_status=ecr.TagStatus.UNTAGGED,
                max_image_age=Duration.days(UNTAGGED_IMAGE_RETENTION_DAYS),
            )
        ],
    )


__all__ = [
    "UNTAGGED_IMAGE_RETENTION_DAYS",
    "GovernedImageRepository",
]
