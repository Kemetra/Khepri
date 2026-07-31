"""One environment, defined once, so that two of them cannot drift apart.

**Why one class and not two.** `KHEPRI-DEC-007` requires the benchmark environment to be "a second
instantiation of the same CDK application ... not a second definition to keep in sync". Two classes
could diverge, and divergence silently voids the benchmark's meaning: a duration measured on
hardware sized unlike beta is not evidence about beta, so the ten-minute objective would be met
somewhere nobody ships. One class makes that impossible rather than merely discouraged.

**Why the props are so few.** `KHEPRI-DEC-007` enumerates what the two environments may differ in,
and the list is closed: name, network isolation, service desired count, deletion protection, and
the absence of customer content. Sizing is not on it. So sizing arrives as one resolved
`InfrastructureSizing` that both instantiations share, and the only per-environment inputs are the
identifier the scope already carries and the desired count.

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
    """Everything one environment needs that another may legitimately differ in.

    `desired_count` is `None` for the beta environment: `KHEPRI-DEC-007` reserves the beta count
    and its autoscaling policy to the beta-authorization artifact, and inventing one here would
    answer a question that decision deliberately left open.
    """

    sizing: InfrastructureSizing
    image_digest: str
    desired_count: int | None


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
