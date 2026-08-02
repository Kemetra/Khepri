"""KHEPRI-BMK-001's dataset population, as KHEPRI-DEC-006 fixes it.

Every number asserted here is quoted from that decision rather than chosen. A test
that agreed with the generator instead of the decision would certify nothing.
"""

from __future__ import annotations

import hashlib

import pytest

from khepri.rra.benchmark_population import (
    BENCHMARK_ID,
    CORE_COLUMNS,
    EXTENDED_COLUMNS,
    FORMAT_CSV,
    FORMAT_XLSX,
    PROFILE_CORE,
    PROFILE_EXTENDED,
    SIZE_BANDS,
    PopulationRefused,
    band_named,
    build_population,
    columns_for,
    upper_edge_sample_ids,
)
from khepri.rra.mapping import (
    SEMANTIC_CATEGORY,
    SEMANTIC_CHANNEL,
    SEMANTIC_COST,
    SEMANTIC_DISCOUNT,
    SEMANTIC_PRODUCT,
    SEMANTIC_RETURNS,
    SEMANTIC_REVENUE,
    SEMANTIC_RULES,
    SEMANTIC_STORE,
    SEMANTIC_TRANSACTION_DATE,
    SEMANTIC_TRANSACTION_ID,
    SEMANTIC_UNITS,
)
from khepri.rra.performance import MAX_DATASET_SIZE_BYTES
from khepri.rra.telemetry import DATASET_SIZE_BANDS

MASTER_SEED = "khepri-bmk-001-master-seed"


def test_bands_match_the_decision_table() -> None:
    actual = [
        (band.name, band.lower_bytes, band.upper_bytes, band.dataset_count)
        for band in SIZE_BANDS
    ]
    assert actual == [
        ("le_1_mib", 1, 1_048_576, 4),
        ("le_10_mib", 1_048_577, 10_485_760, 8),
        ("le_25_mib", 10_485_761, 26_214_400, 12),
        ("le_50_mib", 26_214_401, 52_428_800, 16),
    ]


def test_band_names_are_the_governed_telemetry_vocabulary() -> None:
    assert {band.name for band in SIZE_BANDS} == set(DATASET_SIZE_BANDS)


def test_bands_are_contiguous_and_stop_at_the_beta_boundary() -> None:
    for lower, upper in zip(SIZE_BANDS, SIZE_BANDS[1:], strict=False):
        assert upper.lower_bytes == lower.upper_bytes + 1
    assert SIZE_BANDS[-1].upper_bytes == MAX_DATASET_SIZE_BYTES


def test_population_is_exactly_forty_samples() -> None:
    assert sum(band.dataset_count for band in SIZE_BANDS) == 40
    assert len(build_population(MASTER_SEED)) == 40


def test_sample_ids_are_sequential_and_unique() -> None:
    population = build_population(MASTER_SEED)
    expected = [f"{BENCHMARK_ID}-{position:02d}" for position in range(1, 41)]
    assert [sample.sample_id for sample in population] == expected
    assert len({sample.sample_id for sample in population}) == 40


def test_each_band_divides_equally_into_four_combinations() -> None:
    population = build_population(MASTER_SEED)
    for band in SIZE_BANDS:
        in_band = [sample for sample in population if sample.band_name == band.name]
        assert len(in_band) == band.dataset_count
        combinations = [(sample.input_format, sample.column_profile) for sample in in_band]
        for combination in (
            (FORMAT_CSV, PROFILE_CORE),
            (FORMAT_CSV, PROFILE_EXTENDED),
            (FORMAT_XLSX, PROFILE_CORE),
            (FORMAT_XLSX, PROFILE_EXTENDED),
        ):
            assert combinations.count(combination) == band.dataset_count // 4


def test_every_band_has_one_csv_sample_anchored_to_its_upper_edge() -> None:
    population = build_population(MASTER_SEED)
    anchors = upper_edge_sample_ids()
    assert len(anchors) == len(SIZE_BANDS)
    by_id = {sample.sample_id: sample for sample in population}
    anchored_bands = set()
    for sample_id in anchors:
        sample = by_id[sample_id]
        assert sample.input_format == FORMAT_CSV
        anchored_bands.add(sample.band_name)
    assert anchored_bands == {band.name for band in SIZE_BANDS}


def test_seed_is_the_first_eight_bytes_of_the_documented_digest() -> None:
    for sample in build_population(MASTER_SEED):
        digest = hashlib.sha256(f"{MASTER_SEED}:{sample.sample_id}".encode()).digest()
        assert sample.seed == int.from_bytes(digest[:8], "big")


def test_generation_is_deterministic_for_one_master_seed() -> None:
    assert build_population(MASTER_SEED) == build_population(MASTER_SEED)


def test_a_different_master_seed_changes_seeds_but_not_structure() -> None:
    first = build_population(MASTER_SEED)
    second = build_population("a-different-master-seed")
    assert [sample.seed for sample in first] != [sample.seed for sample in second]
    assert [sample.sample_id for sample in first] == [sample.sample_id for sample in second]
    assert [sample.band_name for sample in first] == [sample.band_name for sample in second]


@pytest.mark.parametrize("value", ["", "   "])
def test_a_blank_master_seed_is_refused(value: str) -> None:
    with pytest.raises(PopulationRefused):
        build_population(value)


def test_core_profile_is_the_eight_governed_columns_in_order() -> None:
    assert [column for column, _ in CORE_COLUMNS] == [
        "transaction_id",
        "transaction_date",
        "product",
        "category",
        "store",
        "channel",
        "units",
        "net_sales",
    ]
    assert [semantic for _, semantic in CORE_COLUMNS] == [
        SEMANTIC_TRANSACTION_ID,
        SEMANTIC_TRANSACTION_DATE,
        SEMANTIC_PRODUCT,
        SEMANTIC_CATEGORY,
        SEMANTIC_STORE,
        SEMANTIC_CHANNEL,
        SEMANTIC_UNITS,
        SEMANTIC_REVENUE,
    ]


def test_extended_profile_is_the_core_profile_plus_four_columns() -> None:
    assert EXTENDED_COLUMNS[: len(CORE_COLUMNS)] == CORE_COLUMNS
    assert EXTENDED_COLUMNS[len(CORE_COLUMNS) :] == (
        ("cogs", SEMANTIC_COST),
        ("discount_value", SEMANTIC_DISCOUNT),
        ("refund_value", SEMANTIC_RETURNS),
        ("customer_email", None),
    )


def test_customer_email_carries_no_governed_semantic() -> None:
    """It is present so RRA-003's personal-data path is inside the measured interval."""
    semantics = dict(EXTENDED_COLUMNS)
    assert semantics["customer_email"] is None


def test_columns_for_returns_the_governed_profiles() -> None:
    assert columns_for(PROFILE_CORE) == CORE_COLUMNS
    assert columns_for(PROFILE_EXTENDED) == EXTENDED_COLUMNS


def test_an_ungoverned_column_profile_is_refused() -> None:
    with pytest.raises(PopulationRefused):
        columns_for("everything")


def test_band_named_returns_the_governed_band() -> None:
    assert band_named("le_25_mib").dataset_count == 12


def test_an_ungoverned_band_name_is_refused() -> None:
    with pytest.raises(PopulationRefused):
        band_named("le_100_mib")


def test_every_governed_column_semantic_is_one_the_mapper_knows() -> None:
    """A profile the mapper cannot read would measure a refusal rather than a report."""
    known = {rule.semantic for rule in SEMANTIC_RULES}
    for column, semantic in EXTENDED_COLUMNS:
        if semantic is not None:
            assert semantic in known, column
