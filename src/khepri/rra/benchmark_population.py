"""The population `KHEPRI-BMK-001` measures, exactly as `KHEPRI-DEC-006` fixes it.

**Nothing here is chosen.** Every count, edge, cardinality, and ordering rule below is
quoted from the approved decision. Where this module and that decision disagree, the
decision is right and this module is defective: a governed workload is defined by the
approved artifact and implemented by code, never the reverse.

**Why the population is a separate module from the bytes it describes.** Deciding *which*
forty datasets exist -- their bands, formats, profiles, identifiers, and seeds -- is pure
arithmetic over a single string, and is worth testing without generating a gigabyte to do
it. Writing the rows is a different job with different failure modes, and lives elsewhere.

**Why seeds are derived rather than stored.** The descriptor records one `master_seed`, and
each dataset's seed follows from it and from the sample identifier. Storing forty seeds
would let one drift from the rule that produced it; deriving them means the rule is the
only thing that can be wrong, and one test can check it.

**No customer content can reach this module.** Its only input is a seed string, and its
only output is a description of synthetic data that does not exist yet.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from khepri.rra.mapping import (
    SEMANTIC_CATEGORY,
    SEMANTIC_CHANNEL,
    SEMANTIC_COST,
    SEMANTIC_DISCOUNT,
    SEMANTIC_PRODUCT,
    SEMANTIC_RETURNS,
    SEMANTIC_REVENUE,
    SEMANTIC_STORE,
    SEMANTIC_TRANSACTION_DATE,
    SEMANTIC_TRANSACTION_ID,
    SEMANTIC_UNITS,
)

BENCHMARK_ID = "KHEPRI-BMK-001"

FORMAT_CSV = "csv"
FORMAT_XLSX = "xlsx"

PROFILE_CORE = "core"
PROFILE_EXTENDED = "extended"

# The core profile answers the RRA-004 core KPIs. Column order is part of the
# contract, because the descriptor's per-file digests are over exact bytes.
CORE_COLUMNS: tuple[tuple[str, str | None], ...] = (
    ("transaction_id", SEMANTIC_TRANSACTION_ID),
    ("transaction_date", SEMANTIC_TRANSACTION_DATE),
    ("product", SEMANTIC_PRODUCT),
    ("category", SEMANTIC_CATEGORY),
    ("store", SEMANTIC_STORE),
    ("channel", SEMANTIC_CHANNEL),
    ("units", SEMANTIC_UNITS),
    ("net_sales", SEMANTIC_REVENUE),
)

# The extended profile additionally answers gross profit and margin, discounts, and
# returns, so the conditional-metric and caveat paths are measured rather than skipped.
#
# `customer_email` carries no governed semantic and is present deliberately, so that
# RRA-003's personal-data detection and exclusion runs inside the measured interval
# instead of being untimed. Its values are synthetic addresses in the `example.invalid`
# reserved domain of RFC 2606: never routable, never customer-derived, never personal.
EXTENDED_COLUMNS: tuple[tuple[str, str | None], ...] = (
    *CORE_COLUMNS,
    ("cogs", SEMANTIC_COST),
    ("discount_value", SEMANTIC_DISCOUNT),
    ("refund_value", SEMANTIC_RETURNS),
    ("customer_email", None),
)

# Both read paths KHEPRI-DEC-005 selects, against both profiles. Every band count is a
# multiple of four, so assigning these round-robin divides each band equally.
COMBINATIONS: tuple[tuple[str, str], ...] = (
    (FORMAT_CSV, PROFILE_CORE),
    (FORMAT_CSV, PROFILE_EXTENDED),
    (FORMAT_XLSX, PROFILE_CORE),
    (FORMAT_XLSX, PROFILE_EXTENDED),
)


class PopulationRefused(ValueError):
    """A population cannot be described as asked."""


@dataclass(frozen=True, slots=True)
class SizeBand:
    """One governed size band, measured in stored input bytes.

    Membership is decided by stored byte size and never by row count, because the same
    rows do not produce the same bytes in CSV and XLSX.
    """

    name: str
    lower_bytes: int
    upper_bytes: int
    dataset_count: int


# The distribution weights the two largest bands because that is where the ten-minute
# objective is at risk, and retains the smallest because fixed costs -- browser start-up,
# template preload, connection establishment, six-surface rendering -- dominate small
# inputs and regress independently of dataset size.
SIZE_BANDS: tuple[SizeBand, ...] = (
    SizeBand("le_1_mib", 1, 1_048_576, 4),
    SizeBand("le_10_mib", 1_048_577, 10_485_760, 8),
    SizeBand("le_25_mib", 10_485_761, 26_214_400, 12),
    SizeBand("le_50_mib", 26_214_401, 52_428_800, 16),
)


@dataclass(frozen=True, slots=True)
class SampleSpec:
    """One dataset's identity and shape, before any byte of it exists."""

    sample_id: str
    band_name: str
    input_format: str
    column_profile: str
    seed: int


def columns_for(column_profile: str) -> tuple[tuple[str, str | None], ...]:
    """The ordered columns of a profile, refusing a profile nobody governs."""
    if column_profile == PROFILE_CORE:
        return CORE_COLUMNS
    if column_profile == PROFILE_EXTENDED:
        return EXTENDED_COLUMNS
    raise PopulationRefused(f"Unknown column profile {column_profile!r}.")


def band_named(name: str) -> SizeBand:
    """The band with this name, refusing one outside the governed vocabulary."""
    for band in SIZE_BANDS:
        if band.name == name:
            return band
    raise PopulationRefused(f"Unknown size band {name!r}.")


def upper_edge_sample_ids() -> frozenset[str]:
    """The one CSV dataset per band whose stored size must equal the band's upper edge.

    XLSX outputs are compressed containers whose exact byte size is not directly
    controllable, so the exact-edge obligation falls on CSV. The first sample of each
    band carries it, which is a CSV sample because the combination cycle starts there.
    """
    anchors: list[str] = []
    position = 1
    for band in SIZE_BANDS:
        anchors.append(_sample_id(position))
        position += band.dataset_count
    return frozenset(anchors)


def build_population(master_seed: str) -> tuple[SampleSpec, ...]:
    """The forty samples in descriptor order, derived from one seed string."""
    _require_seed(master_seed)
    samples: list[SampleSpec] = []
    for band in SIZE_BANDS:
        for offset in range(band.dataset_count):
            samples.append(_sample(band, offset, len(samples) + 1, master_seed))
    return tuple(samples)


def _sample(band: SizeBand, offset: int, position: int, master_seed: str) -> SampleSpec:
    input_format, column_profile = COMBINATIONS[offset % len(COMBINATIONS)]
    sample_id = _sample_id(position)
    return SampleSpec(
        sample_id=sample_id,
        band_name=band.name,
        input_format=input_format,
        column_profile=column_profile,
        seed=derive_seed(master_seed, sample_id),
    )


def _sample_id(position: int) -> str:
    return f"{BENCHMARK_ID}-{position:02d}"


def derive_seed(master_seed: str, sample_id: str) -> int:
    """The first eight bytes, big-endian, of `SHA-256("<master_seed>:<sample_id>")`."""
    digest = hashlib.sha256(f"{master_seed}:{sample_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _require_seed(master_seed: str) -> None:
    if not master_seed.strip():
        raise PopulationRefused("master_seed is required.")


__all__ = [
    "BENCHMARK_ID",
    "COMBINATIONS",
    "CORE_COLUMNS",
    "EXTENDED_COLUMNS",
    "FORMAT_CSV",
    "FORMAT_XLSX",
    "PROFILE_CORE",
    "PROFILE_EXTENDED",
    "SIZE_BANDS",
    "PopulationRefused",
    "SampleSpec",
    "SizeBand",
    "band_named",
    "build_population",
    "columns_for",
    "derive_seed",
    "upper_edge_sample_ids",
]
