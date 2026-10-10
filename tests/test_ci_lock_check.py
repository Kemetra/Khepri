"""SCRUM-45: CI fails when `uv.lock` is stale against `pyproject.toml`.

Every job installs with `uv sync --frozen`, which installs the lock as written and never
compares it with the manifest. `uv lock --check` does: it exits non-zero when resolving
`pyproject.toml` would change `uv.lock`. It runs in `validate` because that job's check is
required on `main`, so a stale lock blocks the merge instead of only reporting.

That a stale lock really turns the step red needs the package index, so it is shown in CI and
not here; offline, uv cannot tell a stale lock from a package it has not cached.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GOVERNANCE = ROOT / ".github" / "workflows" / "governance.yml"


def _validate_job() -> dict:
    workflow = yaml.safe_load(GOVERNANCE.read_text(encoding="utf-8"))
    return workflow["jobs"]["validate"]


def test_the_required_validate_job_checks_the_lock_against_the_manifest() -> None:
    job = _validate_job()
    runs = [step.get("run") for step in job["steps"]]

    assert job["name"] == "validate"
    assert "uv lock --check" in runs
