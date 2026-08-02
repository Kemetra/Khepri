from __future__ import annotations

from pathlib import Path

import pytest

from tests.lifecycle_support import LifecycleRepo, Transition
from tests.test_cli import assert_invalid, read_yaml, run_validator, write_yaml


@pytest.mark.parametrize(
    "transition",
    [
        Transition(
            "KHEPRI-DEC-002",
            "superseded",
            {"superseded_by": "KHEPRI-DEC-001"},
        ),
        Transition("AUX", "retired", {"retirement_reason": "Purpose ended."}),
        Transition(
            "FND-002",
            "retired",
            {"retirement_reason": "Specification withdrawn."},
        ),
    ],
)
def test_authority_ending_transition_requires_prior_approval(
    tmp_path: Path,
    transition: Transition,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    path, package = fixture.propose("APP-003", transition)
    del fixture.entry(package)["supersedes_approval_ref"]
    fixture.rewrite(path, package)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        f"approval-packages:APP-003: lifecycle transition for "
        f"{transition.artifact_id} must supersede prior approval evidence",
    )


def test_authority_ending_transition_rejects_unapproved_evidence(
    tmp_path: Path,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    initial_path = tmp_path / "governance/approvals/APP-002.yaml"
    initial = read_yaml(initial_path)
    initial["state"] = "proposed"
    del initial["approval"]
    write_yaml(initial_path, initial)
    fixture.propose(
        "APP-003",
        Transition(
            "KHEPRI-DEC-002",
            "superseded",
            {"superseded_by": "KHEPRI-DEC-001"},
        ),
    )

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-003: superseded approval must be an approved "
        "YAML package containing KHEPRI-DEC-002",
    )


@pytest.mark.parametrize("field", ["superseded_by", "retirement_reason"])
def test_non_ending_transition_rejects_authority_ending_field(
    tmp_path: Path,
    field: str,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    value = "FND-001" if field == "superseded_by" else "Not applicable."
    fixture.propose(
        "APP-003",
        Transition("FND-002", "implemented", {field: value}),
    )

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        f"approval-packages:APP-003: {field} is only valid for an "
        "authority-ending transition",
    )


@pytest.mark.parametrize(
    ("transition", "field"),
    [
        (Transition("FND-002", "implemented"), "supersedes_approval_ref"),
        (
            Transition("FND-002", "retired", {"retirement_reason": ""}),
            "retirement_reason",
        ),
    ],
)
def test_lifecycle_transition_rejects_empty_required_value(
    tmp_path: Path,
    transition: Transition,
    field: str,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    path, package = fixture.propose("APP-003", transition)
    fixture.entry(package)[field] = ""
    fixture.rewrite(path, package)

    result = run_validator(tmp_path)

    message = (
        "lifecycle transition for FND-002 must supersede prior approval evidence"
        if field == "supersedes_approval_ref"
        else "retirement_reason must be a non-empty string"
    )
    assert_invalid(result, f"approval-packages:APP-003: {message}")


def test_supersession_preserves_prior_approval_evidence(tmp_path: Path) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    path, package = fixture.decision_supersession()
    fixture.approve(path, package)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr
    _, prior = fixture.artifact("KHEPRI-DEC-002")
    assert prior["approved_by"] == "AHMED-SHAABAN"
    assert str(prior["approved_at"]) == "2026-07-29"
    assert prior["approval_ref"] == "governance/approvals/APP-002.yaml"


def test_supersession_rejects_rewritten_prior_approval(tmp_path: Path) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    path, package = fixture.decision_supersession()
    fixture.approve(path, package)
    decisions_path = tmp_path / "governance/registries/decisions.yaml"
    data = read_yaml(decisions_path)
    decisions = data["decisions"]
    assert isinstance(decisions, list)
    prior = next(item for item in decisions if item["id"] == "KHEPRI-DEC-002")
    prior["approved_at"] = "2026-07-30"
    write_yaml(decisions_path, data)

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        "approval-packages:APP-002: KHEPRI-DEC-002 approved_at does not "
        "match package",
    )


@pytest.mark.parametrize("artifact_id", ["AUX", "FND-002"])
def test_retired_artifact_cannot_renew(tmp_path: Path, artifact_id: str) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    transition = Transition(artifact_id, "retired", {"retirement_reason": "Ended."})
    path, package = fixture.propose("APP-003", transition)
    fixture.approve(path, package)
    fixture.propose(
        "APP-004",
        Transition(artifact_id, "retired", {"retirement_reason": "Rewrite."}),
    )

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        f"approval-packages:APP-004: unsupported transition for {artifact_id}: "
        "retired -> retired",
    )
