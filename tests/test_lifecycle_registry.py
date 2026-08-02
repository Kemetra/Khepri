from __future__ import annotations

from pathlib import Path

import pytest

from tests.test_cli import (
    assert_invalid,
    read_yaml,
    registry_path,
    run_validator,
    valid_repository,
    write_document,
    write_yaml,
)


def decision_registry(root: Path) -> tuple[Path, dict[str, object], list[object]]:
    path = registry_path(root, "decisions")
    data = read_yaml(path)
    decisions = data["decisions"]
    assert isinstance(decisions, list)
    return path, data, decisions


def successor(document: str, state: str = "proposed") -> dict[str, object]:
    return {
        "id": "KHEPRI-DEC-002",
        "title": "Successor decision",
        "state": state,
        "owner": "AHMED-SHAABAN",
        "document": document,
    }


def test_superseded_decision_requires_registry_linkage(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, data, decisions = decision_registry(tmp_path)
    assert isinstance(decisions[0], dict)
    decisions[0]["state"] = "superseded"
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "decisions:KHEPRI-DEC-001: superseded decision must name superseded_by",
    )


@pytest.mark.parametrize(
    ("successor_id", "message"),
    [
        ("UNKNOWN", "unknown successor 'UNKNOWN'"),
        ("FND", "successor 'FND' belongs to families, not decisions"),
        ("KHEPRI-DEC-001", "artifact cannot supersede itself"),
        (
            "KHEPRI-DEC-002",
            "successor 'KHEPRI-DEC-002' must be accepted or superseded",
        ),
    ],
)
def test_superseded_decision_rejects_invalid_registry_linkage(
    tmp_path: Path,
    successor_id: str,
    message: str,
) -> None:
    valid_repository(tmp_path)
    document = "governance/decisions/KHEPRI-DEC-002.md"
    write_document(tmp_path, document)
    path, data, decisions = decision_registry(tmp_path)
    decisions.append(successor(document))
    assert isinstance(decisions[0], dict)
    decisions[0].update(state="superseded", superseded_by=successor_id)
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(result, f"decisions:KHEPRI-DEC-001: {message}")


def test_active_decision_rejects_supersession_linkage(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, data, decisions = decision_registry(tmp_path)
    assert isinstance(decisions[0], dict)
    decisions[0]["superseded_by"] = "KHEPRI-DEC-001"
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "decisions:KHEPRI-DEC-001: superseded_by is only valid for a "
        "superseded decision",
    )


def test_historical_supersession_chain_remains_valid(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    second = "governance/decisions/KHEPRI-DEC-002.md"
    third = "governance/decisions/KHEPRI-DEC-003.md"
    write_document(tmp_path, second)
    write_document(tmp_path, third)
    path, data, decisions = decision_registry(tmp_path)
    assert isinstance(decisions[0], dict)
    decisions[0].update(state="superseded", superseded_by="KHEPRI-DEC-002")
    prior = successor(second, "superseded")
    prior.update(
        approved_by="AHMED-SHAABAN",
        approved_at="2026-07-30",
        approval_ref="https://github.com/Kemetra/Khepri/pull/2",
        superseded_by="KHEPRI-DEC-003",
    )
    current = successor(third, "accepted")
    current["id"] = "KHEPRI-DEC-003"
    current.update(
        approved_by="AHMED-SHAABAN",
        approved_at="2026-07-31",
        approval_ref="https://github.com/Kemetra/Khepri/pull/3",
    )
    decisions.extend([prior, current])
    write_yaml(path, data)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr
