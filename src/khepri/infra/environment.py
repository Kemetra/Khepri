"""One environment, defined once, so that two of them cannot drift apart.

**Why one class and not two.** `KHEPRI-DEC-007` requires the benchmark environment to be "a second
instantiation of the same CDK application ... not a second definition to keep in sync". Two classes
could diverge, and divergence silently voids the benchmark's meaning: a duration measured on
hardware sized unlike beta is not evidence about beta, so the ten-minute objective would be met
somewhere nobody ships. One class makes that impossible rather than merely discouraged.

**Why the props are so few.** The only per-environment input today is the identifier the scope
already carries. `KHEPRI-DEC-007` also permits the two environments to differ in service desired
count and deletion protection, but neither is expressible yet: no ECS service is synthesized here,
and `database.py` fixes deletion protection. Each arrives with the slice that can enforce it,
because a prop the stack accepts and discards would invite the belief that setting it has an
effect.

**Why the region is explicit.** A stack built without `env` is region-agnostic and deploys wherever
the ambient profile points. `KHEPRI-DEC-007` requires this definition to fail rather than
substitute a neighbouring region or service, so the region is named here and never inherited.

**Why the image digest is a prop and not a size.** `KHEPRI-DEC-007` lists the OCI image digest among
the facts the *environment descriptor* records from the build, beside the `uv.lock` digest and the
Python patch version. It is not a sizing value, so it does not live in the sizing declaration. It
is required here, with no default, because `PinnedImage` already refuses a tag: a task definition
naming a tag runs whatever the tag points at, not what anyone approved.
"""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import Environment, Stack
from constructs import Construct

from khepri.infra.compute import (
    ComputeProps,
    EnvironmentResources,
    GovernedCompute,
    PinnedImage,
)
from khepri.infra.data_resources import GovernedDataResources
from khepri.infra.database import DatabaseProps, GovernedDatabase
from khepri.infra.image import GovernedImageRepository
from khepri.infra.network import GovernedNetwork
from khepri.infra.sizing import InfrastructureSizing

REGION = "me-central-1"


@dataclass(frozen=True, slots=True)
class EnvironmentProps:
    """Everything one environment needs that another may legitimately differ in."""

    sizing: InfrastructureSizing
    image_digest: str


class RraEnvironmentStack(Stack):
    """One RRA environment: network, data, store, registry, and compute."""

    def __init__(self, scope: Construct, construct_id: str, props: EnvironmentProps) -> None:
        super().__init__(scope, construct_id, env=Environment(region=REGION))
        self.network = GovernedNetwork(self, "Network")
        self.data = GovernedDataResources(self, "Data", props.sizing.queue)
        self.database = GovernedDatabase(self, "Database", self._database_props(props))
        self.image = GovernedImageRepository(self, "Image", self.data.key)
        self.compute = GovernedCompute(self, "Compute", self._compute_props(props))

    def _database_props(self, props: EnvironmentProps) -> DatabaseProps:
        return DatabaseProps(
            vpc=self.network.vpc, key=self.data.key, sizing=props.sizing.database
        )

    def _compute_props(self, props: EnvironmentProps) -> ComputeProps:
        return ComputeProps(
            resources=EnvironmentResources(
                network=self.network, data=self.data, database=self.database
            ),
            image=PinnedImage(
                repository=self.image.repository, digest=props.image_digest
            ),
            sizing=props.sizing.services,
        )
