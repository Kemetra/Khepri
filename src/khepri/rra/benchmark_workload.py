"""The datasets a benchmark run measures, built the same way every time.

**Why the datasets are generated rather than stored.** RRA-007 asks for evidence
about valid beta datasets, and a fixture checked into the repository would be one
dataset frozen at one shape, invisible to review once it is binary, and awkward
to grow towards the 50 MB boundary. Generating them means the workload is
readable as code and reproducible from a two-number declaration.

**Nothing here is drawn from entropy, a clock, or a filesystem.** Every value is
a function of the sample index and the row index, so two runs of the same
declaration produce byte-identical datasets. A benchmark whose inputs differ
between runs measures two workloads and certifies neither.

**Why the workload has a digest.** The digest is a versioned content address over
what was actually built -- the same idea as `bundle_id` and `package_digest`
elsewhere in this codebase. It exists so an approved benchmark record can *cite*
the workload it approved, and so a builder edited after approval stops matching
that citation. It is evidence of what ran; it is not authority, and computing one
here approves nothing.

**Why the row cap is derived rather than declared.** `performance` refuses a
sample one byte over the approved beta boundary, so a declaration is checked
before anything is generated: a row is bounded in length by construction, and
`MAX_DATASET_ROWS` is that bound divided into the boundary. The built dataset is
still measured and refused on its own account, because a cap that drifted from
the generator would otherwise admit an oversized dataset silently.

**No customer content can reach this module.** It has no input other than two
counts. The bytes it produces are synthetic and are never logged: what leaves a
benchmark run is a size, a duration, and an opaque sample identifier.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from khepri.rra.performance import MAX_DATASET_SIZE_BYTES
from khepri.rra.profiling import canonical_json

WORKLOAD_VERSION = "rra007.workload.v1"

# The header every generated dataset carries. The column names are the retail
# shape `mapping` recognizes; a workload the mapper cannot read would measure a
# refusal rather than a report.
HEADER = b"date,revenue,units,invoice_no,category,branch\n"

# An upper bound on one generated row, in bytes. Every field below is either
# fixed width or bounded by the widest literal in its cycle, so this is a
# ceiling rather than an average.
MAX_ROW_BYTES = 64
MAX_DATASET_ROWS = MAX_DATASET_SIZE_BYTES // MAX_ROW_BYTES

_CATEGORIES = ("Beverages", "Snacks", "Household", "Bakery")
_BRANCHES = ("Cairo", "Giza", "Alexandria")
_DAYS_IN_MONTH = 28


class WorkloadRefused(ValueError):
    """A workload declaration cannot be measured as written."""


@dataclass(frozen=True, slots=True)
class BenchmarkDataset:
    """One synthetic input, named opaquely and measured by size alone."""

    sample_id: str
    content: bytes

    def __post_init__(self) -> None:
        _require_text(self.sample_id, "sample_id")
        _require_within_boundary(len(self.content))

    @property
    def size_bytes(self) -> int:
        return len(self.content)

    @property
    def digest(self) -> str:
        """A content address for this input, which is what evidence may carry."""
        return hashlib.sha256(self.content).hexdigest()


@dataclass(frozen=True, slots=True)
class BenchmarkWorkload:
    """The declared shape of a benchmark run: how many datasets, how large.

    Both numbers come from the approved benchmark record. This module supplies
    neither a default nor a guess, because a workload nobody approved is a
    workload that certifies nothing.
    """

    sample_count: int
    rows_per_dataset: int

    def __post_init__(self) -> None:
        _require_positive(self.sample_count, "sample_count")
        _require_positive(self.rows_per_dataset, "rows_per_dataset")
        _require_declared_rows(self.rows_per_dataset)

    def datasets(self) -> tuple[BenchmarkDataset, ...]:
        """Every dataset of this workload, in a fixed order."""
        return tuple(
            _dataset(position, self.rows_per_dataset)
            for position in range(self.sample_count)
        )

    @property
    def digest(self) -> str:
        """A versioned content address over the datasets this declaration builds."""
        document = {
            "workload_version": WORKLOAD_VERSION,
            "sample_count": self.sample_count,
            "rows_per_dataset": self.rows_per_dataset,
            "datasets": [
                {
                    "sample_id": entry.sample_id,
                    "size_bytes": entry.size_bytes,
                    "content_digest": entry.digest,
                }
                for entry in self.datasets()
            ],
        }
        computed = hashlib.sha256(canonical_json(document).encode()).hexdigest()
        return f"{WORKLOAD_VERSION}:{computed}"


def _dataset(position: int, rows: int) -> BenchmarkDataset:
    body = b"".join(_row(position, index) for index in range(rows))
    return BenchmarkDataset(sample_id=f"sample_{position:04d}", content=HEADER + body)


def _row(position: int, index: int) -> bytes:
    """One transaction, derived arithmetically from where it sits."""
    seed = position * 7 + index * 13
    day = index % _DAYS_IN_MONTH + 1
    minor = seed % 100_000
    fields = (
        f"2026-01-{day:02d}",
        f"{minor // 100}.{minor % 100:02d}",
        str(index % 9 + 1),
        f"INV-{position:04d}-{index:06d}",
        _CATEGORIES[seed % len(_CATEGORIES)],
        _BRANCHES[seed % len(_BRANCHES)],
    )
    return (",".join(fields) + "\n").encode()


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise WorkloadRefused(f"{name} is required.")


def _require_positive(value: int, name: str) -> None:
    if value <= 0:
        raise WorkloadRefused(f"{name} must be positive.")


def _require_declared_rows(value: int) -> None:
    if value > MAX_DATASET_ROWS:
        raise WorkloadRefused("Declared rows would exceed the approved beta boundary.")


def _require_within_boundary(size_bytes: int) -> None:
    if size_bytes > MAX_DATASET_SIZE_BYTES:
        raise WorkloadRefused("Dataset size exceeds the approved beta boundary.")


__all__ = [
    "HEADER",
    "MAX_DATASET_ROWS",
    "MAX_ROW_BYTES",
    "WORKLOAD_VERSION",
    "BenchmarkDataset",
    "BenchmarkWorkload",
    "WorkloadRefused",
]
