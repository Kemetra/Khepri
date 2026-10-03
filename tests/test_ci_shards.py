"""SCRUM-43: the `pytest` CI job runs the suite in shards and proves the shards add up to it.

`FND-001` requires pytest on every pull request, and `FND-005` requires the browser and
concurrency guards to read the **full** suite. Sharding keeps both true only if the shards
together run every collected test exactly once. So the split is checked, not trusted:
`.github/scripts/shard.py` decides which test files a shard runs, and
`.github/scripts/merge_shards.py` refuses a set of shard reports that drops, repeats or
disagrees about a test, before the guards read the merged marker report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import merge_shards  # noqa: E402
import shard  # noqa: E402

# --- which shard runs what --------------------------------------------------------------------


@pytest.mark.parametrize("text", ["1/4", "4/4", "1/1"])
def test_a_well_formed_shard_parses(text: str) -> None:
    index, total = shard.parse(text)
    assert 1 <= index <= total


@pytest.mark.parametrize("text", ["0/4", "5/4", "4", "a/b", "2/0", ""])
def test_a_malformed_shard_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        shard.parse(text)


def test_every_file_lands_in_exactly_one_shard() -> None:
    weights = {f"tests/test_{n}.py": float(n) for n in range(1, 30)}

    plan = shard.assign(weights, total=4)

    assert set(plan) == set(weights)
    assert set(plan.values()) == {1, 2, 3, 4}


def test_the_split_balances_by_weight() -> None:
    """Greedy, heaviest first, onto the lightest shard: no shard exceeds the ideal by much."""
    weights = {f"tests/test_{n}.py": float(n) for n in range(1, 41)}

    plan = shard.assign(weights, total=4)

    loads = [sum(w for f, w in weights.items() if plan[f] == i) for i in (1, 2, 3, 4)]
    assert max(loads) - min(loads) <= max(weights.values())


def test_the_split_is_deterministic_whatever_the_input_order() -> None:
    weights = {f"tests/test_{n}.py": float(n % 7) for n in range(1, 50)}
    reordered = dict(reversed(list(weights.items())))

    assert shard.assign(weights, total=3) == shard.assign(reordered, total=3)


def test_an_unmeasured_file_is_weighted_by_its_test_count() -> None:
    counts = {"tests/test_known.py": 10, "tests/test_new.py": 4}

    weights = shard.weights_for(counts, measured={"tests/test_known.py": 30.0})

    assert weights["tests/test_known.py"] == 30.0
    assert weights["tests/test_new.py"] == 4 * shard.UNMEASURED_SECONDS_PER_TEST


def test_selection_keeps_whole_files_together() -> None:
    nodeids = [
        "tests/test_a.py::test_one",
        "tests/test_a.py::test_two",
        "tests/test_b.py::test_one",
    ]

    selected = [shard.select(nodeids, index=i, total=2, measured={}) for i in (1, 2)]

    files = [{n.split("::")[0] for n in chosen} for chosen in selected]
    assert files[0].isdisjoint(files[1])
    assert sorted(selected[0] + selected[1]) == sorted(nodeids)


# --- proving the shards add up to the suite ----------------------------------------------------

COLLECTED = ["t.py::a", "t.py::b", "u.py::c", "v.py::d"]


def _report(index: int, selected: list[str], collected: list[str] = COLLECTED) -> dict:
    return {"shard": f"{index}/2", "collected": collected, "selected": selected}


def test_two_shards_that_partition_the_suite_are_accepted() -> None:
    reports = [_report(1, ["t.py::a", "t.py::b"]), _report(2, ["u.py::c", "v.py::d"])]

    assert merge_shards.partition_errors(reports, expected=2) == []


def test_a_missing_shard_is_refused() -> None:
    errors = merge_shards.partition_errors([_report(1, ["t.py::a", "t.py::b"])], expected=2)

    assert any("expected 2 shard reports" in e for e in errors)


def test_a_dropped_test_is_refused() -> None:
    reports = [_report(1, ["t.py::a", "t.py::b"]), _report(2, ["u.py::c"])]

    errors = merge_shards.partition_errors(reports, expected=2)

    assert any("v.py::d" in e for e in errors)


def test_a_test_run_twice_is_refused() -> None:
    reports = [_report(1, ["t.py::a", "t.py::b", "u.py::c"]), _report(2, ["u.py::c", "v.py::d"])]

    errors = merge_shards.partition_errors(reports, expected=2)

    assert any("u.py::c" in e for e in errors)


def test_shards_that_collected_different_suites_are_refused() -> None:
    reports = [
        _report(1, ["t.py::a", "t.py::b"]),
        _report(2, ["u.py::c", "v.py::d"], collected=[*COLLECTED, "w.py::e"]),
    ]

    errors = merge_shards.partition_errors(reports, expected=2)

    assert any("collected different" in e for e in errors)


def test_an_empty_suite_is_refused() -> None:
    reports = [_report(1, [], collected=[]), _report(2, [], collected=[])]

    assert merge_shards.partition_errors(reports, expected=2)


def test_marker_reports_merge_into_one_full_report() -> None:
    first = {"browser": {"t.py::a": "passed"}, "concurrency": {}}
    second = {"browser": {"u.py::c": "skipped"}, "concurrency": {"v.py::d": "passed"}}

    merged = merge_shards.merge_marker_reports([first, second])

    assert merged == {
        "browser": {"t.py::a": "passed", "u.py::c": "skipped"},
        "concurrency": {"v.py::d": "passed"},
    }


def test_main_writes_the_merged_report_only_when_the_partition_holds(tmp_path: Path) -> None:
    for index, (selected, marked) in enumerate(
        ((["t.py::a", "t.py::b"], {"t.py::a": "passed"}), (["u.py::c", "v.py::d"], {})), start=1
    ):
        (tmp_path / f"shard-report-{index}.json").write_text(json.dumps(_report(index, selected)))
        (tmp_path / f"marker-report-{index}.json").write_text(
            json.dumps({"browser": marked, "concurrency": {}})
        )
    out = tmp_path / "marker-report.json"

    assert merge_shards.main([str(tmp_path), "2", str(out)]) == 0
    assert json.loads(out.read_text())["browser"] == {"t.py::a": "passed"}

    (tmp_path / "shard-report-2.json").unlink()
    out.unlink()
    assert merge_shards.main([str(tmp_path), "2", str(out)]) == 1
    assert not out.exists()
