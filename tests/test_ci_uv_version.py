"""SCRUM-46: CI and the runtime image use one uv version.

The image copies uv from `ghcr.io/astral-sh/uv:<version>@sha256:...`; every workflow sets uv
up with `astral-sh/setup-uv` and a `version`. When they differ, CI checks and syncs `uv.lock`
with a uv the image never runs, and `uv lock --check` in `validate` answers for the wrong one.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
GITHUB = ROOT / ".github"
IMAGE_UV = re.compile(r"^COPY --from=ghcr\.io/astral-sh/uv:(\S+)@sha256:[0-9a-f]{64} ", re.M)


def _image_uv() -> str:
    matches = IMAGE_UV.findall((ROOT / "Dockerfile").read_text(encoding="utf-8"))
    assert len(matches) == 1, f"expected one digest-pinned uv COPY line in Dockerfile: {matches}"
    return matches[0]


def _yaml_files(pattern: str) -> list[Path]:
    # GitHub reads both extensions.
    return sorted([*GITHUB.glob(f"{pattern}.yml"), *GITHUB.glob(f"{pattern}.yaml")])


def _load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _step_lists() -> list[tuple[str, list[dict]]]:
    """Every step list GitHub runs: workflow jobs, then composite actions."""
    lists = []
    for path in _yaml_files("workflows/*"):
        for job_id, job in _load(path)["jobs"].items():
            lists.append((f"{path.name}:{job_id}", job.get("steps", [])))
    for path in _yaml_files("actions/**/action"):
        steps = _load(path).get("runs", {}).get("steps", [])
        lists.append((path.relative_to(GITHUB).as_posix(), steps))
    return lists


def _setup_uv_steps() -> list[tuple[str, dict]]:
    # GitHub matches the owner and repository in `uses:` without regard to case.
    return [
        (where, step)
        for where, steps in _step_lists()
        for step in steps
        if str(step.get("uses", "")).lower().startswith("astral-sh/setup-uv@")
    ]


def test_every_workflow_sets_up_the_uv_the_image_runs() -> None:
    image = _image_uv()
    steps = _setup_uv_steps()

    assert steps, "no astral-sh/setup-uv step found; the comparison would pass vacuously"
    mismatched = {where: step.get("with", {}).get("version") for where, step in steps}
    mismatched = {where: v for where, v in mismatched.items() if v != image}
    assert mismatched == {}, f"image runs uv {image}"
