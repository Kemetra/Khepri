"""Build the RRA image and read back the facts the environment descriptor must record.

`KHEPRI-DEC-007` requires the descriptor to carry the OCI image digest, the `uv.lock` digest, the
exact Python patch version, and the SHA-256 of the reviewed synthesized template. This script
produces the first three. The fourth comes from synthesis, which needs a real image digest and so
follows this step.

**Every fact is read out of the built image, never accepted as an argument.** A digest or version
supplied by hand is a claim about an image rather than evidence about it, and the whole point of
recording them is that the descriptor's `environment_digest` covers what actually ran. The one
exception is the `uv.lock` digest, which is computed from the file in this checkout -- the same file
the image was built from, asserted by `--frozen` in the Dockerfile.

Docker is required. If it is absent this script refuses rather than emitting a partial fact set,
because a descriptor with three of four fields is not a descriptor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCKFILE = REPO_ROOT / "uv.lock"
DEFAULT_TAG = "khepri-rra:local"


class BuildRefused(RuntimeError):
    """Raised rather than emitting a partial or guessed fact set."""


def _docker() -> str:
    binary = shutil.which("docker")
    if binary is None:
        raise BuildRefused(
            "docker is not on PATH. This script records facts about a built image and cannot "
            "invent them; run it on a machine with a Docker daemon."
        )
    return binary


def _run(args: list[str], *, capture: bool = True) -> str:
    completed = subprocess.run(
        args,
        check=False,
        text=True,
        capture_output=capture,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise BuildRefused(f"{' '.join(args[:3])} failed: {detail[:400]}")
    return (completed.stdout or "").strip()


def build(tag: str) -> None:
    docker = _docker()
    _run(
        [
            docker,
            "build",
            "--platform",
            "linux/amd64",
            "--tag",
            tag,
            str(REPO_ROOT),
        ],
        capture=False,
    )


def _inspect(tag: str) -> dict[str, object]:
    docker = _docker()
    raw = _run([docker, "image", "inspect", tag])
    parsed = json.loads(raw)
    if not isinstance(parsed, list) or not parsed:
        raise BuildRefused(f"docker image inspect returned no record for {tag}.")
    entry = parsed[0]
    if not isinstance(entry, dict):
        raise BuildRefused("docker image inspect returned an unexpected shape.")
    return entry


def image_digest(tag: str) -> str:
    """The repo digest if the image has been pushed, else the local image ID.

    These are different things and the descriptor must not confuse them: a repo digest names bytes
    in a registry, an image ID names a local config blob. Both are reported, labelled, so whoever
    writes the descriptor records the one `KHEPRI-DEC-007` means -- the pushed digest.
    """
    entry = _inspect(tag)
    repo_digests = entry.get("RepoDigests") or []
    if isinstance(repo_digests, list) and repo_digests:
        first = str(repo_digests[0])
        if "@" in first:
            return first.split("@", 1)[1]
    return str(entry.get("Id", ""))


def _in_image(tag: str, code: str) -> str:
    docker = _docker()
    return _run([docker, "run", "--rm", "--platform", "linux/amd64", tag, "python", "-c", code])


def python_patch_version(tag: str) -> str:
    return _in_image(tag, "import sys; print('.'.join(map(str, sys.version_info[:3])))")


def playwright_version(tag: str) -> str:
    return _in_image(
        tag, "import importlib.metadata as m; print(m.version('playwright'))"
    )


def chromium_facts(tag: str) -> tuple[str, str]:
    """The Chromium revision and browser version Playwright pins in this image."""
    raw = _in_image(
        tag,
        "import json,pathlib,playwright;"
        "p=pathlib.Path(playwright.__file__).parent/'driver'/'package'/'browsers.json';"
        "d=json.loads(p.read_text());"
        "b=next(x for x in d['browsers'] if x['name']=='chromium');"
        "print(b['revision'], b.get('browserVersion',''))",
    )
    parts = raw.split()
    if len(parts) != 2:
        raise BuildRefused(f"could not read Chromium revision and version from the image: {raw!r}")
    return parts[0], parts[1]


def lockfile_digest() -> str:
    if not LOCKFILE.is_file():
        raise BuildRefused(f"{LOCKFILE} is missing; the uv.lock digest cannot be computed.")
    return "sha256:" + hashlib.sha256(LOCKFILE.read_bytes()).hexdigest()


def collect(tag: str) -> dict[str, str]:
    facts = {
        "oci_image_digest": image_digest(tag),
        "uv_lock_sha256": lockfile_digest(),
        "python_patch_version": python_patch_version(tag),
        "playwright_version": playwright_version(tag),
    }
    revision, browser_version = chromium_facts(tag)
    facts["chromium_revision"] = revision
    facts["chromium_browser_version"] = browser_version

    missing = sorted(key for key, value in facts.items() if not value)
    if missing:
        raise BuildRefused(
            "refusing to report a partial fact set; unreadable: " + ", ".join(missing)
        )
    return facts


def render(facts: dict[str, str]) -> str:
    lines = [
        "# Facts read out of the built image. Paste into the environment descriptor.",
        "# The synthesized-template SHA-256 is NOT here: it comes from cdk synth, which needs",
        "# the image digest above and therefore runs after this step.",
    ]
    lines += [f"{key}: {value!r}" for key, value in facts.items()]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default=DEFAULT_TAG, help=f"image tag (default {DEFAULT_TAG})")
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="inspect an already-built image instead of building it",
    )
    args = parser.parse_args(argv)

    try:
        if not args.skip_build:
            build(args.tag)
        print(render(collect(args.tag)))
    except BuildRefused as error:
        print(f"REFUSED: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
