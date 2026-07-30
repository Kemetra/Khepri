from __future__ import annotations

import pytest

from khepri.rra.benchmark_workload import (
    MAX_DATASET_ROWS,
    MAX_ROW_BYTES,
    WORKLOAD_VERSION,
    BenchmarkDataset,
    BenchmarkWorkload,
)
from khepri.rra.performance import MAX_DATASET_SIZE_BYTES


def workload(*, sample_count: int = 3, rows_per_dataset: int = 8) -> BenchmarkWorkload:
    return BenchmarkWorkload(sample_count=sample_count, rows_per_dataset=rows_per_dataset)


def test_the_same_declaration_builds_byte_identical_datasets() -> None:
    # A benchmark whose datasets differ between runs measures two workloads and
    # certifies neither. Nothing here is drawn from entropy or from a clock.
    first = workload().datasets()
    second = workload().datasets()

    assert [entry.content for entry in first] == [entry.content for entry in second]


def test_the_same_declaration_reaches_the_same_workload_digest() -> None:
    assert workload().digest == workload().digest
    assert workload().digest.startswith(f"{WORKLOAD_VERSION}:")


def test_a_different_declaration_is_a_different_workload() -> None:
    # The digest is what an approved record cites, so a builder or a
    # declaration that changed after approval must be visible as a change.
    assert workload(rows_per_dataset=9).digest != workload().digest
    assert workload(sample_count=4).digest != workload().digest


def test_every_dataset_is_named_once_and_counted() -> None:
    datasets = workload(sample_count=5).datasets()

    assert len(datasets) == 5
    assert len({entry.sample_id for entry in datasets}) == 5


def test_every_built_dataset_stays_inside_the_approved_beta_boundary() -> None:
    datasets = workload(rows_per_dataset=MAX_DATASET_ROWS // 1000).datasets()

    assert max(entry.size_bytes for entry in datasets) <= MAX_DATASET_SIZE_BYTES


def test_every_generated_row_stays_within_the_bound_the_cap_assumes() -> None:
    # MAX_DATASET_ROWS is derived from MAX_ROW_BYTES. A row that outgrew that
    # bound would make the declaration cap admit a dataset over the boundary.
    dataset = workload(rows_per_dataset=64).datasets()[0]

    rows = dataset.content.splitlines()
    assert max(len(row) for row in rows) <= MAX_ROW_BYTES


@pytest.mark.parametrize(
    ("sample_count", "rows_per_dataset"),
    [
        pytest.param(0, 8, id="no_samples"),
        pytest.param(3, 0, id="no_rows"),
        pytest.param(3, -1, id="negative_rows"),
        pytest.param(3, MAX_DATASET_ROWS + 1, id="a_dataset_over_the_boundary"),
    ],
)
def test_a_declaration_that_cannot_be_measured_is_refused(
    sample_count: int,
    rows_per_dataset: int,
) -> None:
    with pytest.raises(ValueError):
        BenchmarkWorkload(sample_count=sample_count, rows_per_dataset=rows_per_dataset)


def test_a_dataset_over_the_approved_boundary_is_refused() -> None:
    with pytest.raises(ValueError, match="approved beta boundary"):
        BenchmarkDataset(sample_id="sample_0", content=b"x" * (MAX_DATASET_SIZE_BYTES + 1))
