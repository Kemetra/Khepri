"""Whether an approved benchmark workload exists, and refusing to invent one.

**There is no approved benchmark workload.** RRA-007 requires the completion-time
objective to be demonstrated "under an approved benchmark workload and
environment", and no accepted governance record names one. So this module reads
the identity from outside the code and reports absence as absence. It contains no
benchmark identifier, workload digest, environment digest, or approval reference,
and it never constructs one from a default: writing any of those four values into
a source file would fabricate the approval evidence
`performance.BenchmarkTampered` exists to catch.

**Why the environment.** The four identity values and the two workload numbers
belong to a governance record, and a registry this repository does not yet have a
schema for cannot supply them. The seam is therefore a plain mapping -- `os.environ`
in the gate, a hand-written dictionary in tests -- which a workflow populates from
the approved record once one exists. The names below are the *shape* of that
supply, not the values.

**Three answers, deliberately distinct.** No benchmark named at all is `None`: the
caller certified nothing, and says so. A benchmark named in part, blank, or
unreadable is `BenchmarkNotAuthorized`: Constitution V blocks on ambiguous
authority, and filling in the rest would be a guess presented as approval. A
benchmark named completely is an `ApprovedBenchmark`, which is still only a claim
about what was approved -- whether the datasets built match the digest that record
cites is decided where the run is certified.

**No value read here is echoed.** The refusal messages name the failure, never the
supplied text, because a message travels into build logs documented as
content-free.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from khepri.rra.benchmark_workload import BenchmarkWorkload
from khepri.rra.performance import BenchmarkIdentity

BENCHMARK_ID_KEY = "KHEPRI_BENCHMARK_ID"
WORKLOAD_DIGEST_KEY = "KHEPRI_BENCHMARK_WORKLOAD_DIGEST"
ENVIRONMENT_DIGEST_KEY = "KHEPRI_BENCHMARK_ENVIRONMENT_DIGEST"
APPROVAL_REF_KEY = "KHEPRI_BENCHMARK_APPROVAL_REF"
SAMPLE_COUNT_KEY = "KHEPRI_BENCHMARK_SAMPLE_COUNT"
DATASET_ROWS_KEY = "KHEPRI_BENCHMARK_DATASET_ROWS"

# Every value an approved benchmark record must supply. Named as a set so a
# partly supplied record is a detectable state rather than a defaulted one.
BENCHMARK_APPROVAL_KEYS = frozenset(
    {
        BENCHMARK_ID_KEY,
        WORKLOAD_DIGEST_KEY,
        ENVIRONMENT_DIGEST_KEY,
        APPROVAL_REF_KEY,
        SAMPLE_COUNT_KEY,
        DATASET_ROWS_KEY,
    }
)


class BenchmarkNotAuthorized(RuntimeError):
    """No approved benchmark authority could be established for this run."""


@dataclass(frozen=True, slots=True)
class ApprovedBenchmark:
    """What an approved benchmark record claims: an identity and a workload."""

    identity: BenchmarkIdentity
    workload: BenchmarkWorkload


def resolve_approved_benchmark(
    environment: Mapping[str, str],
) -> ApprovedBenchmark | None:
    """The approved benchmark this environment names, or nothing at all.

    A blank value counts as unnamed, because a workflow that reads an unset
    repository variable supplies exactly that: every name present, every value
    empty. Reading that as a partly declared benchmark would block every build
    over an authorization nobody asked for -- while a benchmark named in part,
    with some values blank and others supplied, still blocks.
    """
    named = {
        key: environment[key]
        for key in BENCHMARK_APPROVAL_KEYS
        if environment.get(key, "").strip()
    }
    if not named:
        return None
    _require_every_value(named)
    try:
        return ApprovedBenchmark(identity=_identity(named), workload=_workload(named))
    except ValueError as error:
        raise BenchmarkNotAuthorized(
            "The benchmark declaration is incomplete or malformed."
        ) from error


def _require_every_value(named: Mapping[str, str]) -> None:
    if set(named) != BENCHMARK_APPROVAL_KEYS:
        raise BenchmarkNotAuthorized("The benchmark declaration names only part of itself.")


def _identity(named: Mapping[str, str]) -> BenchmarkIdentity:
    return BenchmarkIdentity(
        benchmark_id=named[BENCHMARK_ID_KEY],
        workload_digest=named[WORKLOAD_DIGEST_KEY],
        environment_digest=named[ENVIRONMENT_DIGEST_KEY],
        approval_ref=named[APPROVAL_REF_KEY],
    )


def _workload(named: Mapping[str, str]) -> BenchmarkWorkload:
    return BenchmarkWorkload(
        sample_count=int(named[SAMPLE_COUNT_KEY]),
        rows_per_dataset=int(named[DATASET_ROWS_KEY]),
    )


__all__ = [
    "APPROVAL_REF_KEY",
    "BENCHMARK_APPROVAL_KEYS",
    "BENCHMARK_ID_KEY",
    "DATASET_ROWS_KEY",
    "ENVIRONMENT_DIGEST_KEY",
    "SAMPLE_COUNT_KEY",
    "WORKLOAD_DIGEST_KEY",
    "ApprovedBenchmark",
    "BenchmarkNotAuthorized",
    "resolve_approved_benchmark",
]
