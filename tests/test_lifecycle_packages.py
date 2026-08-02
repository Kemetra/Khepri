from __future__ import annotations

from pathlib import Path

import pytest

from tests.lifecycle_support import LifecycleRepo, Transition
from tests.test_approval_packages import package_artifacts, proposed_package, rewrite_package
from tests.test_cli import assert_invalid, run_validator, valid_repository


def test_proposed_decision_can_be_rejected(tmp_path: Path) -> None:
    valid_repository(tmp_path)
    path, package = proposed_package(tmp_path)
    package_artifacts(package)[0]["to_state"] = "rejected"
    rewrite_package(path, package)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "transition",
    [
        Transition("AUX", "retired", {"retirement_reason": "Purpose ended."}),
        Transition("FND-002", "implemented"),
        Transition(
            "FND-002",
            "retired",
            {"retirement_reason": "Specification withdrawn."},
        ),
    ],
)
def test_approved_artifact_accepts_lifecycle_transition(
    tmp_path: Path,
    transition: Transition,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    fixture.propose("APP-003", transition)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("to_state", ["verified", "retired"])
def test_implemented_specification_accepts_next_transition(
    tmp_path: Path,
    to_state: str,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    path, package = fixture.propose("APP-003", Transition("FND-002", "implemented"))
    fixture.approve(path, package)
    extra = {"retirement_reason": "Specification withdrawn."}
    transition = Transition("FND-002", to_state, extra if to_state == "retired" else {})
    fixture.propose("APP-004", transition)

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


def test_verified_specification_can_retire(tmp_path: Path) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    path, package = fixture.propose("APP-003", Transition("FND-002", "implemented"))
    fixture.approve(path, package)
    path, package = fixture.propose("APP-004", Transition("FND-002", "verified"))
    fixture.approve(path, package)
    fixture.propose(
        "APP-005",
        Transition("FND-002", "retired", {"retirement_reason": "Withdrawn."}),
    )

    result = run_validator(tmp_path)

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("reverse", [False, True])
def test_successor_must_be_accepted_before_decision_supersession(
    tmp_path: Path,
    reverse: bool,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    fixture.decision_supersession(reverse)

    result = run_validator(tmp_path)

    if reverse:
        assert_invalid(
            result,
            "approval-packages:APP-003: successor KHEPRI-DEC-003 is not "
            "approved before KHEPRI-DEC-002",
        )
    else:
        assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("transition", "message"),
    [
        (
            Transition("KHEPRI-DEC-002", "superseded", {"superseded_by": "UNKNOWN"}),
            "unknown successor 'UNKNOWN'",
        ),
        (
            Transition("KHEPRI-DEC-002", "superseded", {"superseded_by": "FND"}),
            "successor 'FND' belongs to families, not decisions",
        ),
        (
            Transition(
                "KHEPRI-DEC-002",
                "superseded",
                {"superseded_by": "KHEPRI-DEC-002"},
            ),
            "artifact cannot supersede itself",
        ),
        (
            Transition("AUX", "retired", {"superseded_by": "UNKNOWN"}),
            "unknown successor 'UNKNOWN'",
        ),
        (
            Transition("AUX", "retired", {"superseded_by": "FND-001"}),
            "successor 'FND-001' belongs to specifications, not families",
        ),
        (
            Transition("AUX", "retired", {"superseded_by": "AUX"}),
            "artifact cannot supersede itself",
        ),
        (
            Transition("FND-002", "retired", {"superseded_by": "UNKNOWN"}),
            "unknown successor 'UNKNOWN'",
        ),
        (
            Transition("FND-002", "retired", {"superseded_by": "FND"}),
            "successor 'FND' belongs to families, not specifications",
        ),
        (
            Transition("FND-002", "retired", {"superseded_by": "FND-002"}),
            "artifact cannot supersede itself",
        ),
    ],
)
def test_authority_ending_transition_rejects_invalid_successor(
    tmp_path: Path,
    transition: Transition,
    message: str,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    fixture.propose("APP-003", transition)

    result = run_validator(tmp_path)

    assert_invalid(result, f"approval-packages:APP-003: {message}")


@pytest.mark.parametrize("artifact_id", ["AUX", "FND-002"])
def test_retirement_requires_successor_or_reason(
    tmp_path: Path,
    artifact_id: str,
) -> None:
    fixture = LifecycleRepo.create(tmp_path)
    fixture.propose("APP-003", Transition(artifact_id, "retired"))

    result = run_validator(tmp_path)

    assert_invalid(
        result,
        f"approval-packages:APP-003: {artifact_id} must name a successor or "
        "retirement_reason",
    )
