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
WORKFLOWS = ROOT / ".github" / "workflows"
IMAGE_UV = re.compile(r"^COPY --from=ghcr\.io/astral-sh/uv:(\S+)@sha256:[0-9a-f]{64} ", re.M)


def _image_uv() -> str:
    (version,) = IMAGE_UV.findall((ROOT / "Dockerfile").read_text(encoding="utf-8"))
    return version


def _setup_uv_steps() -> list[tuple[str, dict]]:
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        for job_id, job in workflow["jobs"].items():
            for step in job.get("steps", []):
                if str(step.get("uses", "")).startswith("astral-sh/setup-uv@"):
                    found.append((f"{path.name}:{job_id}", step))
    return found


def test_every_workflow_sets_up_the_uv_the_image_runs() -> None:
    image = _image_uv()
    steps = _setup_uv_steps()

    assert steps, "no astral-sh/setup-uv step found; the comparison would pass vacuously"
    mismatched = {where: step.get("with", {}).get("version") for where, step in steps}
    mismatched = {where: v for where, v in mismatched.items() if v != image}
    assert mismatched == {}, f"image runs uv {image}"
