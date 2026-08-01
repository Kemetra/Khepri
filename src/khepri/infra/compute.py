"""The two task definitions, and the permissions each one is deliberately denied.

**One image, two roles.** `KHEPRI-DEC-005` runs separate web and bounded-worker services from one
image. Running one image does not mean carrying one permission set: the web service accepts
uploads and enqueues jobs, the worker consumes jobs and produces bundles, and neither needs the
other's access. So each task definition gets its own task role, and the grants below are the whole
of what each can do.

The asymmetry is the point and is asserted by tests:

- The **web** role may send to the report queue and may not receive from it. A web task that could
  consume a job would process a report outside the bounded worker `KHEPRI-DEC-005` requires, with
  none of the concurrency, lease, or heartbeat behaviour that makes duplicate delivery safe.
- The **worker** role may receive from the report queue and may not send to it. Retry and
  dead-lettering are decided by PostgreSQL attempt bounds and SQS redrive, never by a worker
  re-enqueueing its own work; a worker that could send could construct a job nothing authorized.

Both may read and write the content bucket, because both halves of the pipeline touch stored
content. Neither task role may read the database credential: the execution role fetches it at task
start and injects it, so the running code holds the value without holding a path back to the
secret.

The bucket grant already carries the key actions a KMS-encrypted bucket needs, so no separate
`grant_encrypt_decrypt` is made. A second grant would restate what the first one said.

**The image is pinned by digest, not by tag.** A tag is resolved at every task placement, so a
task definition naming one runs whatever the tag points at then rather than what was approved.
`PinnedImage` refuses a value that is not a full lowercase `sha256:` digest, on the same principle
as `sizing.resolve_sizing`: an identity nobody supplied is not one to invent.

**Sizing is injected, never chosen.** Task CPU, memory, and ephemeral storage arrive as a
`ServiceSizing` that `sizing.resolve_sizing` already refused to invent. No number in this module
comes from `KHEPRI-DEC-007`, which is still proposed.

**The CPU architecture is CDK's default made explicit.** No approved artifact settles it.
`KHEPRI-DEC-007` sizes tasks in CPU units and says nothing about architecture, and an ARM64 task
would require the published image to match. Writing `X86_64` here records what would otherwise be
an invisible default; changing it needs an artifact that settles it and an image built for it.

**Chromium's launch flag is not set here, and cannot be.** `KHEPRI-DEC-007` requires
`--disable-dev-shm-usage` because Fargate fixes `/dev/shm` at 64 MiB and does not support
`sharedMemorySize`. The ephemeral storage this module requests is sized to absorb what that flag
displaces, but the flag itself belongs to `khepri.rra.rendering.chromium.launch_chromium`, which
currently passes no `args`. Wiring it is an obligation of the rendering slice, recorded here
because this is where the reason for the storage figure lives.

**Log groups are not customer-content stores.** `RRA-007` and `KHEPRI-DEC-005` require logs to
carry opaque identifiers, stage names, durations, and sizes only. They are left under the default
CloudWatch encryption at rest rather than the environment key: a customer-managed key on a log
group requires granting the CloudWatch Logs service principal use of that key, which widens the
key policy to protect data that is content-free by contract.
"""

from __future__ import annotations

from dataclasses import dataclass

from aws_cdk import Aws, RemovalPolicy
from aws_cdk import aws_ecr as ecr
from aws_cdk import aws_ecs as ecs
from aws_cdk import aws_logs as logs
from aws_cdk import aws_secretsmanager as secretsmanager
from constructs import Construct

from khepri.infra.data_resources import GovernedDataResources
from khepri.infra.database import GovernedDatabase
from khepri.infra.network import GovernedNetwork
from khepri.infra.sizing import MIN_EPHEMERAL_STORAGE_GIB, ServiceSizing, TaskSize
from khepri.runtime.config import (
    BUCKET_OWNER_VARIABLE,
    BUCKET_VARIABLE,
    DEAD_LETTER_QUEUE_URL_VARIABLE,
    KMS_KEY_ARN_VARIABLE,
    QUEUE_URL_VARIABLE,
    REGION,
    REGION_VARIABLE,
)

WEB_CONTAINER_NAME = "web"
WORKER_CONTAINER_NAME = "worker"
WEB_PORT = 8080

WEB_COMMAND = (
    "uvicorn",
    "khepri.runtime.web:app",
    "--host",
    "0.0.0.0",
    "--port",
    str(WEB_PORT),
    "--no-access-log",
)
WORKER_COMMAND = ("python", "-m", "khepri.runtime.worker")

LOG_RETENTION = logs.RetentionDays.ONE_MONTH

# The environment variable the database credential is injected under. The value is resolved from
# Secrets Manager at task start and never appears in a task definition or a log.
DATABASE_SECRET_VARIABLE = "KHEPRI_DATABASE_SECRET"

# Playwright's own variables. The browser is baked into the image at this path, and the skip flag
# means a task that cannot find it fails rather than downloading an unrecorded build.
BROWSERS_PATH_VARIABLE = "PLAYWRIGHT_BROWSERS_PATH"
BROWSERS_PATH = "/opt/pw-browsers"
SKIP_BROWSER_DOWNLOAD_VARIABLE = "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"

DIGEST_PREFIX = "sha256:"
DIGEST_LENGTH = 64

RUNTIME_PLATFORM = ecs.RuntimePlatform(
    cpu_architecture=ecs.CpuArchitecture.X86_64,
    operating_system_family=ecs.OperatingSystemFamily.LINUX,
)


@dataclass(frozen=True, slots=True)
class EnvironmentResources:
    """The network the cluster joins and the stateful resources the roles are granted against.

    The network is carried rather than looked up because `ecs.Cluster` creates a VPC of its own
    when it is not given one. A second VPC would put the tasks somewhere with no route to the
    database, no interface endpoints, and its own default egress — the opposite of what
    `network.py` exists to guarantee.
    """

    network: GovernedNetwork
    data: GovernedDataResources
    database: GovernedDatabase


@dataclass(frozen=True, slots=True)
class PinnedImage:
    """A repository and the exact digest to run from it, which are useless apart.

    The two travel together because a repository reference alone does not identify an image. A
    task definition that names a tag resolves it at every task placement, so the image a task runs
    is whatever the tag points at then -- not what anyone approved. ECR tag immutability does not
    close that: it refuses to *overwrite* a tag, and `ecr:BatchDeleteImage` followed by a fresh
    push of the same tag is not an overwrite. A digest cannot be re-pointed at all.
    """

    repository: ecr.IRepository
    digest: str

    def __post_init__(self) -> None:
        _require_digest(self.digest)


@dataclass(frozen=True, slots=True)
class ComputeProps:
    """Everything the task definitions need from the rest of the environment."""

    resources: EnvironmentResources
    image: PinnedImage
    sizing: ServiceSizing


@dataclass(frozen=True, slots=True)
class ContainerSpec:
    """What every container shares: which image to run, where logs go, which secret to read."""

    image: PinnedImage
    log_group: logs.LogGroup
    runtime: RuntimeSpec


@dataclass(frozen=True, slots=True)
class RuntimeSpec:
    """The secret and non-secret coordinates a process needs at start."""

    database_secret: secretsmanager.ISecret
    environment: dict[str, str]


@dataclass(frozen=True, slots=True)
class LaunchSpec:
    """One role's exact process command and optional listening port."""

    name: str
    command: tuple[str, ...]
    port: int | None = None


class GovernedCompute(Construct):
    """One environment's ECS cluster and its two task definitions."""

    def __init__(self, scope: Construct, construct_id: str, props: ComputeProps) -> None:
        super().__init__(scope, construct_id)
        self.cluster = _cluster(self, props.resources.network)
        self.web_task = _web_task(self, props)
        self.worker_task = _worker_task(self, props)


def _cluster(scope: Construct, network: GovernedNetwork) -> ecs.Cluster:
    return ecs.Cluster(scope, "Cluster", vpc=network.vpc)


def _web_task(scope: Construct, props: ComputeProps) -> ecs.FargateTaskDefinition:
    task = _task_definition(scope, "WebTask", props.sizing.web)
    _add_container(
        task,
        _spec(scope, "WebLogs", props),
        LaunchSpec(name=WEB_CONTAINER_NAME, command=WEB_COMMAND, port=WEB_PORT),
    )
    _grant_shared(task, props)
    props.resources.data.queue.grant_send_messages(task.task_role)
    return task


def _worker_task(scope: Construct, props: ComputeProps) -> ecs.FargateTaskDefinition:
    task = _task_definition(scope, "WorkerTask", props.sizing.worker)
    _add_container(
        task,
        _spec(scope, "WorkerLogs", props),
        LaunchSpec(name=WORKER_CONTAINER_NAME, command=WORKER_COMMAND),
    )
    _grant_shared(task, props)
    props.resources.data.queue.grant_consume_messages(task.task_role)
    return task


def _task_definition(
    scope: Construct, construct_id: str, size: TaskSize
) -> ecs.FargateTaskDefinition:
    return ecs.FargateTaskDefinition(
        scope,
        construct_id,
        cpu=size.cpu_units,
        memory_limit_mib=size.memory_mib,
        ephemeral_storage_gib=_ephemeral_storage(size.ephemeral_storage_gib),
        runtime_platform=RUNTIME_PLATFORM,
    )


def _ephemeral_storage(declared_gib: int) -> int | None:
    """Omit the property when the declaration asks for exactly the Fargate default.

    A task definition may set 21 to 200 GiB and is refused at 20, so the platform provides no way
    to *state* its own default. `KHEPRI-DEC-007` records the web service at 20 GiB precisely
    because that is the default, made explicit so the environment digest covers it. Honouring that
    means declaring nothing here: the size is what the decision recorded, and the template says so
    by omission rather than by a number the platform would reject.
    """
    if declared_gib == MIN_EPHEMERAL_STORAGE_GIB:
        return None
    return declared_gib


def _spec(scope: Construct, log_id: str, props: ComputeProps) -> ContainerSpec:
    secret = props.resources.database.secret
    if secret is None:
        raise ValueError("The database must supply a generated credential.")
    return ContainerSpec(
        image=props.image,
        log_group=_log_group(scope, log_id),
        runtime=RuntimeSpec(
            database_secret=secret,
            environment=_runtime_environment(props.resources.data),
        ),
    )


def _runtime_environment(data: GovernedDataResources) -> dict[str, str]:
    return {
        REGION_VARIABLE: REGION,
        BUCKET_VARIABLE: data.bucket.bucket_name,
        KMS_KEY_ARN_VARIABLE: data.key.key_arn,
        BUCKET_OWNER_VARIABLE: Aws.ACCOUNT_ID,
        QUEUE_URL_VARIABLE: data.queue.queue_url,
        DEAD_LETTER_QUEUE_URL_VARIABLE: data.dead_letter_queue.queue_url,
    }


def _require_digest(value: str) -> None:
    """Refuse anything that is not a full SHA-256 image digest.

    There is no default and no fallback to a tag. A digest nobody supplied would be a tag by
    another name, and the whole point is that the template, not the registry, decides which image
    runs. This mirrors `sizing.resolve_sizing`, which refuses rather than inventing a size.
    """
    digest = value.strip()
    if not digest.startswith(DIGEST_PREFIX):
        raise ValueError("Image digest must be a sha256: digest, never a tag.")
    hexadecimal = digest.removeprefix(DIGEST_PREFIX)
    if len(hexadecimal) != DIGEST_LENGTH or not set(hexadecimal) <= set("0123456789abcdef"):
        raise ValueError("Image digest must be lowercase hexadecimal SHA-256.")


def _log_group(scope: Construct, construct_id: str) -> logs.LogGroup:
    return logs.LogGroup(
        scope,
        construct_id,
        retention=LOG_RETENTION,
        removal_policy=RemovalPolicy.RETAIN,
    )


def _add_container(
    task: ecs.FargateTaskDefinition,
    spec: ContainerSpec,
    launch: LaunchSpec,
) -> ecs.ContainerDefinition:
    container = task.add_container(
        launch.name,
        image=ecs.EcrImage(spec.image.repository, spec.image.digest),
        command=list(launch.command),
        logging=ecs.LogDrivers.aws_logs(
            stream_prefix=launch.name,
            log_group=spec.log_group,
        ),
        environment={
            BROWSERS_PATH_VARIABLE: BROWSERS_PATH,
            SKIP_BROWSER_DOWNLOAD_VARIABLE: "1",
            **spec.runtime.environment,
        },
        secrets={
            DATABASE_SECRET_VARIABLE: ecs.Secret.from_secrets_manager(
                spec.runtime.database_secret
            )
        },
    )
    if launch.port is not None:
        container.add_port_mappings(
            ecs.PortMapping(container_port=launch.port, protocol=ecs.Protocol.TCP)
        )
    return container


def _grant_shared(task: ecs.FargateTaskDefinition, props: ComputeProps) -> None:
    """What both halves of the pipeline legitimately need, and nothing beyond it."""
    data = props.resources.data
    data.bucket.grant_read_write(task.task_role)


__all__ = [
    "BROWSERS_PATH",
    "BROWSERS_PATH_VARIABLE",
    "DATABASE_SECRET_VARIABLE",
    "DIGEST_LENGTH",
    "DIGEST_PREFIX",
    "LOG_RETENTION",
    "LaunchSpec",
    "RUNTIME_PLATFORM",
    "RuntimeSpec",
    "SKIP_BROWSER_DOWNLOAD_VARIABLE",
    "WEB_CONTAINER_NAME",
    "WEB_COMMAND",
    "WEB_PORT",
    "WORKER_COMMAND",
    "WORKER_CONTAINER_NAME",
    "ComputeProps",
    "ContainerSpec",
    "PinnedImage",
    "EnvironmentResources",
    "GovernedCompute",
]
