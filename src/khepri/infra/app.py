"""The CDK application: one definition, instantiated twice.

`KHEPRI-DEC-007` authorizes a beta environment and a dedicated benchmark environment, and requires
the second to be "a second instantiation of the same CDK application in the same region ... with an
environment identifier as the only naming input". That is literally what this module is: two
constructions of `RraEnvironmentStack` against one resolved sizing object.

Service desired count is not set here: no ECS service is synthesized by `RraEnvironmentStack` yet,
only task definitions, so there is nothing for a desired-count value to govern. `KHEPRI-DEC-006`'s
sequential submission and `KHEPRI-DEC-007`'s "exactly 1 task" for the benchmark are enforced by the
slice that adds the service, not declared here.

The image digest is a required argument. Nothing in this module knows a default, because the digest
is produced by a build and recorded in the environment descriptor, and a template synthesized
around an unapproved image is exactly what pinning by digest exists to prevent.

Both stacks are constructed from the SAME `EnvironmentProps` instance, not two separately built
ones with matching field lists. `EnvironmentProps` is a frozen dataclass, so sharing it is safe, and
sharing it is the point: identical sizing between beta and benchmark is then guaranteed by
construction, not by a reviewer noticing that two hand-repeated field lists still agree.
"""

from __future__ import annotations

from aws_cdk import App

from khepri.infra.environment import EnvironmentProps, RraEnvironmentStack
from khepri.infra.sizing_source import load_sizing

BETA_STACK_NAME = "RraBeta"
BENCHMARK_STACK_NAME = "RraBenchmark"


def build_app(image_digest: str) -> App:
    """Construct both environments from one sizing declaration and one stack class."""
    app = App()
    props = EnvironmentProps(sizing=load_sizing(), image_digest=image_digest)
    RraEnvironmentStack(app, BETA_STACK_NAME, props)
    RraEnvironmentStack(app, BENCHMARK_STACK_NAME, props)
    return app


__all__ = ["BENCHMARK_STACK_NAME", "BETA_STACK_NAME", "build_app"]
