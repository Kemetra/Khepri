from __future__ import annotations

import pytest

from khepri.rra.benchmark_authorization import (
    BENCHMARK_APPROVAL_KEYS,
    BenchmarkNotAuthorized,
    resolve_approved_benchmark,
)

APPROVED = {
    "KHEPRI_BENCHMARK_ID": "supplied_by_the_record",
    "KHEPRI_BENCHMARK_WORKLOAD_DIGEST": "sha256:supplied",
    "KHEPRI_BENCHMARK_ENVIRONMENT_DIGEST": "sha256:also_supplied",
    "KHEPRI_BENCHMARK_APPROVAL_REF": "supplied_approval_ref",
    "KHEPRI_BENCHMARK_SAMPLE_COUNT": "20",
    "KHEPRI_BENCHMARK_DATASET_ROWS": "8",
}


def without(key: str) -> dict[str, str]:
    return {name: value for name, value in APPROVED.items() if name != key}


def test_an_environment_naming_no_benchmark_is_not_an_approved_one() -> None:
    # No approved benchmark workload exists. Absence is reported as absence so
    # the caller can say it certified nothing, rather than guessed an identity.
    assert resolve_approved_benchmark({"PATH": "/usr/bin"}) is None


def test_an_environment_that_named_every_value_blank_names_no_benchmark() -> None:
    # This is what a workflow supplies when the repository configures none of
    # them: every name present and every value empty. It is an absence, and
    # reading it as a partly declared benchmark would fail every build over an
    # authorization nobody was asked for.
    blank = dict.fromkeys(APPROVED, "")

    assert resolve_approved_benchmark(blank) is None


def test_an_approved_record_supplies_every_value_the_gate_uses() -> None:
    approved = resolve_approved_benchmark(APPROVED)

    assert approved is not None
    assert approved.identity.benchmark_id == "supplied_by_the_record"
    assert approved.identity.approval_ref == "supplied_approval_ref"
    assert approved.workload.sample_count == 20


@pytest.mark.parametrize("missing", sorted(BENCHMARK_APPROVAL_KEYS))
def test_a_partly_named_benchmark_blocks_rather_than_defaults(missing: str) -> None:
    # Constitution V: ambiguous authority blocks. A record that named some of
    # its own terms is not a record, and inventing the rest would fabricate
    # approval evidence.
    with pytest.raises(BenchmarkNotAuthorized):
        resolve_approved_benchmark(without(missing))


@pytest.mark.parametrize(
    ("key", "value"),
    [
        pytest.param("KHEPRI_BENCHMARK_ID", "   ", id="a_blank_identifier"),
        pytest.param("KHEPRI_BENCHMARK_APPROVAL_REF", "", id="a_blank_approval_ref"),
        pytest.param("KHEPRI_BENCHMARK_SAMPLE_COUNT", "many", id="an_unreadable_count"),
        pytest.param("KHEPRI_BENCHMARK_SAMPLE_COUNT", "0", id="a_workload_of_nothing"),
        pytest.param("KHEPRI_BENCHMARK_DATASET_ROWS", "-1", id="a_dataset_of_nothing"),
    ],
)
def test_a_malformed_benchmark_declaration_blocks(key: str, value: str) -> None:
    with pytest.raises(BenchmarkNotAuthorized):
        resolve_approved_benchmark(APPROVED | {key: value})
