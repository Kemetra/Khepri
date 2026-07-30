"""The sizing every construct reads, and the platform limits it is checked against.

**Why this exists before any construct.** `KHEPRI-DEC-005` authorizes AWS CDK v2 as the
definition of reproducible infrastructure and selects services without sizing them. So a
synthesized template needs its sizes from somewhere, and the only two honest sources are an
approved governance record or a refusal. This module is the seam that makes the second one
happen: it holds the shape of a sizing declaration and no value of one.

**Nothing here has a default.** Every field is required, and an absent field is a refusal rather
than a fallback. A default would be a size nobody approved, silently synthesized into a template
whose digest an approved benchmark record is supposed to cite -- which is exactly the fabricated
authority `BenchmarkTampered` exists to catch, arriving one layer lower.

**What is checked is AWS, not judgement.** The bounds below are published platform constraints:
the Fargate CPU and memory pairs, the ephemeral-storage range, the SQS timing and redrive
bounds, the RDS allocation range. Encoding them turns a deploy-time rejection into a
synthesis-time refusal, which is the difference between finding out in review and finding out in
a protected environment. None of them expresses a preference, and none of them is a value from a
proposed decision.

**What is deliberately not checked.** `KHEPRI-DEC-007` is proposed, so its cross-field rules --
that the queue visibility timeout equals the PostgreSQL lease, and that the redrive count equals
the database attempt bound -- are not enforced here. Enforcing an unapproved rule would be
acting on authority nobody granted, which fails closed in the wrong direction. Adding those
checks is a follow-on obligation of that decision's approval, not a gap in this one.

**Region and availability are out of reach.** Whether an instance class or a Fargate pair is
offered in `me-central-1` for a given account is not knowable from a constraint table, and
`KHEPRI-DEC-005` already requires that verification before provisioning. An instance class is
therefore checked for shape and never for existence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Fargate accepts only these task CPU values, and for each one only a fixed set of task memory
# values. The 256 row is enumerated because it is the one row that is not an arithmetic series.
_FARGATE_MEMORY_MIB: dict[int, tuple[int, ...]] = {
    256: (512, 1024, 2048),
    512: tuple(range(1024, 4097, 1024)),
    1024: tuple(range(2048, 8193, 1024)),
    2048: tuple(range(4096, 16385, 1024)),
    4096: tuple(range(8192, 30721, 1024)),
    8192: tuple(range(16384, 61441, 4096)),
    16384: tuple(range(32768, 122881, 8192)),
}

# 20 GiB is the Fargate default and 21 GiB the smallest value a task definition may set, so the
# inclusive range covers both the default and every configurable size.
MIN_EPHEMERAL_STORAGE_GIB = 20
MAX_EPHEMERAL_STORAGE_GIB = 200

# RDS for PostgreSQL allocation bounds, and the allocation at which gp3 begins to admit
# provisioned IOPS above its baseline.
MIN_ALLOCATED_STORAGE_GIB = 20
GP3_PROVISIONING_FLOOR_GIB = 400
MAX_BACKUP_RETENTION_DAYS = 35

# SQS bounds: visibility timeout up to twelve hours, retention from one minute to fourteen days,
# long-poll wait up to twenty seconds, and redrive count up to one thousand.
MAX_VISIBILITY_TIMEOUT_SECONDS = 12 * 60 * 60
MIN_MESSAGE_RETENTION_SECONDS = 60
MAX_MESSAGE_RETENTION_SECONDS = 14 * 24 * 60 * 60
MAX_RECEIVE_WAIT_SECONDS = 20
MAX_RECEIVE_COUNT = 1000

WEB_TASK_KEYS = ("web_cpu_units", "web_memory_mib", "web_ephemeral_storage_gib")
WORKER_TASK_KEYS = ("worker_cpu_units", "worker_memory_mib", "worker_ephemeral_storage_gib")
DATABASE_KEYS = ("database_instance_class", "allocated_storage_gib", "backup_retention_days")
QUEUE_TIMING_KEYS = (
    "visibility_timeout_seconds",
    "message_retention_seconds",
    "receive_wait_seconds",
)
RETRY_KEYS = ("max_receive_count", "max_attempts")

SIZING_KEYS = (
    *WEB_TASK_KEYS,
    *WORKER_TASK_KEYS,
    *DATABASE_KEYS,
    *QUEUE_TIMING_KEYS,
    *RETRY_KEYS,
)


class SizingRefused(ValueError):
    """A sizing declaration cannot be synthesized as written."""


@dataclass(frozen=True, slots=True)
class TaskSize:
    """One Fargate task definition's compute, memory, and disk."""

    cpu_units: int
    memory_mib: int
    ephemeral_storage_gib: int

    def __post_init__(self) -> None:
        _require_fargate_pair(self.cpu_units, self.memory_mib)
        _require_range(
            self.ephemeral_storage_gib,
            MIN_EPHEMERAL_STORAGE_GIB,
            MAX_EPHEMERAL_STORAGE_GIB,
            "ephemeral_storage_gib",
        )


@dataclass(frozen=True, slots=True)
class DatabaseSize:
    """The RDS for PostgreSQL instance, its gp3 allocation, and its backup horizon.

    Storage type is not a field: `KHEPRI-DEC-005` requires encrypted storage and backups, and
    gp3 is the only type this contract expresses. An allocation at or above the gp3 provisioning
    floor is refused rather than supported, because above it a declaration must also carry
    provisioned IOPS and throughput, which no approved artifact settles.
    """

    instance_class: str
    allocated_storage_gib: int
    backup_retention_days: int

    def __post_init__(self) -> None:
        _require_instance_class(self.instance_class)
        _require_range(
            self.allocated_storage_gib,
            MIN_ALLOCATED_STORAGE_GIB,
            GP3_PROVISIONING_FLOOR_GIB - 1,
            "allocated_storage_gib",
        )
        _require_range(
            self.backup_retention_days, 1, MAX_BACKUP_RETENTION_DAYS, "backup_retention_days"
        )


@dataclass(frozen=True, slots=True)
class QueueTimings:
    """How long a message stays invisible, retained, and waited on."""

    visibility_timeout_seconds: int
    message_retention_seconds: int
    receive_wait_seconds: int

    def __post_init__(self) -> None:
        _require_range(
            self.visibility_timeout_seconds,
            1,
            MAX_VISIBILITY_TIMEOUT_SECONDS,
            "visibility_timeout_seconds",
        )
        _require_range(
            self.message_retention_seconds,
            MIN_MESSAGE_RETENTION_SECONDS,
            MAX_MESSAGE_RETENTION_SECONDS,
            "message_retention_seconds",
        )
        _require_range(
            self.receive_wait_seconds, 0, MAX_RECEIVE_WAIT_SECONDS, "receive_wait_seconds"
        )


@dataclass(frozen=True, slots=True)
class RetryBounds:
    """The two independent attempt bounds: the queue's redrive count and the database's.

    They are kept as two fields rather than one because they belong to two systems that can
    disagree. Requiring them to agree is a `KHEPRI-DEC-007` rule and is not enforced here.
    """

    max_receive_count: int
    max_attempts: int

    def __post_init__(self) -> None:
        _require_range(self.max_receive_count, 1, MAX_RECEIVE_COUNT, "max_receive_count")
        _require_positive(self.max_attempts, "max_attempts")


@dataclass(frozen=True, slots=True)
class QueueSizing:
    """Everything the report queue and its dead-letter queue are bounded by."""

    timings: QueueTimings
    retries: RetryBounds


@dataclass(frozen=True, slots=True)
class ServiceSizing:
    """The two Fargate services, sized separately because their work is not alike."""

    web: TaskSize
    worker: TaskSize


@dataclass(frozen=True, slots=True)
class InfrastructureSizing:
    """One complete sizing declaration, or no declaration at all."""

    services: ServiceSizing
    database: DatabaseSize
    queue: QueueSizing


def resolve_sizing(source: Mapping[str, str]) -> InfrastructureSizing:
    """Read a complete sizing declaration, refusing anything less.

    There is no "sized by default" answer. A missing, blank, or non-integer field is a refusal,
    because a template synthesized around a guessed size is indistinguishable from one
    synthesized around an approved size once it is deployed.
    """
    _require_declared(source)
    return InfrastructureSizing(
        services=_services(source),
        database=_database(source),
        queue=_queue(source),
    )


def _services(source: Mapping[str, str]) -> ServiceSizing:
    return ServiceSizing(web=_task(source, WEB_TASK_KEYS), worker=_task(source, WORKER_TASK_KEYS))


def _task(source: Mapping[str, str], keys: tuple[str, str, str]) -> TaskSize:
    cpu, memory, storage = keys
    return TaskSize(
        cpu_units=_integer(source, cpu),
        memory_mib=_integer(source, memory),
        ephemeral_storage_gib=_integer(source, storage),
    )


def _database(source: Mapping[str, str]) -> DatabaseSize:
    return DatabaseSize(
        instance_class=source[DATABASE_KEYS[0]].strip(),
        allocated_storage_gib=_integer(source, DATABASE_KEYS[1]),
        backup_retention_days=_integer(source, DATABASE_KEYS[2]),
    )


def _queue(source: Mapping[str, str]) -> QueueSizing:
    return QueueSizing(timings=_timings(source), retries=_retries(source))


def _timings(source: Mapping[str, str]) -> QueueTimings:
    return QueueTimings(
        visibility_timeout_seconds=_integer(source, QUEUE_TIMING_KEYS[0]),
        message_retention_seconds=_integer(source, QUEUE_TIMING_KEYS[1]),
        receive_wait_seconds=_integer(source, QUEUE_TIMING_KEYS[2]),
    )


def _retries(source: Mapping[str, str]) -> RetryBounds:
    return RetryBounds(
        max_receive_count=_integer(source, RETRY_KEYS[0]),
        max_attempts=_integer(source, RETRY_KEYS[1]),
    )


def _require_declared(source: Mapping[str, str]) -> None:
    missing = [key for key in SIZING_KEYS if not str(source.get(key, "")).strip()]
    if missing:
        raise SizingRefused(f"Sizing declaration is incomplete: {', '.join(sorted(missing))}.")


def _integer(source: Mapping[str, str], key: str) -> int:
    try:
        return int(str(source[key]).strip())
    except ValueError as error:
        raise SizingRefused(f"{key} must be an integer.") from error


def _require_fargate_pair(cpu_units: int, memory_mib: int) -> None:
    allowed = _FARGATE_MEMORY_MIB.get(cpu_units)
    if allowed is None:
        raise SizingRefused("cpu_units is not a Fargate task CPU value.")
    if memory_mib not in allowed:
        raise SizingRefused("memory_mib is not valid for this cpu_units on Fargate.")


def _require_instance_class(value: str) -> None:
    if not value.startswith("db.") or value.count(".") < 2:
        raise SizingRefused("instance_class must name an RDS instance class.")


def _require_range(value: int, low: int, high: int, name: str) -> None:
    if not low <= value <= high:
        raise SizingRefused(f"{name} must be between {low} and {high}.")


def _require_positive(value: int, name: str) -> None:
    if value <= 0:
        raise SizingRefused(f"{name} must be positive.")


__all__ = [
    "GP3_PROVISIONING_FLOOR_GIB",
    "MAX_BACKUP_RETENTION_DAYS",
    "MAX_EPHEMERAL_STORAGE_GIB",
    "MAX_MESSAGE_RETENTION_SECONDS",
    "MAX_RECEIVE_COUNT",
    "MAX_RECEIVE_WAIT_SECONDS",
    "MAX_VISIBILITY_TIMEOUT_SECONDS",
    "MIN_ALLOCATED_STORAGE_GIB",
    "MIN_EPHEMERAL_STORAGE_GIB",
    "MIN_MESSAGE_RETENTION_SECONDS",
    "SIZING_KEYS",
    "DatabaseSize",
    "InfrastructureSizing",
    "QueueSizing",
    "QueueTimings",
    "RetryBounds",
    "ServiceSizing",
    "SizingRefused",
    "TaskSize",
    "resolve_sizing",
]
