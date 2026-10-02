"""Both compose stacks build MinIO from its pinned source tag (#631).

Open-source MinIO is archived. Its Docker Hub repositories return 404 and dl.min.io
returns 410, so a pinned upstream image starts nothing on a clean machine. Upstream
still publishes the release tags, so `ops/minio/minio-from-source.Dockerfile` builds
the same releases from source. Each is pinned to its full commit SHA, and the build
refuses a checkout at any other commit.

Compose and the Dockerfile share one source. Each compose image tag must name the
release that the Dockerfile clones, so neither can move without the other.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = REPOSITORY_ROOT / "ops" / "minio" / "minio-from-source.Dockerfile"
COMPOSE_FILES = ("docker-compose.local.yml", "docker-compose.staging.yml")
WITHDRAWN = ("minio/minio", "minio/mc")

# The commit each tag dereferences to (`git ls-remote ... refs/tags/<tag>^{}`), not
# the annotated tag object, which a checkout's HEAD never equals.
SERVER_COMMIT = "07c3a429bfed433e49018cb0f78a52145d4bedeb"
CLIENT_COMMIT = "7394ce0dd2a80935aded936b09fa12cbb3cb8096"

# (compose file, service, Dockerfile target, the ARG naming its release tag)
BUILT_SERVICES = (
    ("docker-compose.local.yml", "minio", "server", "MINIO_TAG"),
    ("docker-compose.staging.yml", "minio", "server", "MINIO_TAG"),
    ("docker-compose.staging.yml", "minio-init", "client", "MC_TAG"),
)


def _services(name: str) -> dict:
    return yaml.safe_load((REPOSITORY_ROOT / name).read_text(encoding="utf-8"))["services"]


def _dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def _arguments() -> dict[str, str]:
    return dict(re.findall(r"^ARG (\w+)=(\S+)$", _dockerfile(), re.MULTILINE))


def _probe(service: dict) -> str:
    test = service.get("healthcheck", {}).get("test", [])
    return " ".join(test) if isinstance(test, list) else test


@pytest.mark.parametrize("name", COMPOSE_FILES)
def test_no_service_pulls_a_withdrawn_minio_image(name: str) -> None:
    images = [service.get("image", "") for service in _services(name).values()]

    assert images, "a compose file with no images would vacuously pass"
    assert not [image for image in images if image.startswith(WITHDRAWN)]


@pytest.mark.parametrize(("name", "service", "target", "release"), BUILT_SERVICES)
def test_each_minio_service_builds_the_release_the_dockerfile_clones(
    name: str, service: str, target: str, release: str
) -> None:
    definition = _services(name)[service]
    build = definition["build"]

    assert (REPOSITORY_ROOT / build["context"] / build["dockerfile"]) == DOCKERFILE
    assert build["target"] == target
    assert definition["image"].rpartition(":")[2] == _arguments()[release]


def test_each_release_is_pinned_to_its_full_commit_and_checked() -> None:
    arguments = _arguments()
    dockerfile = _dockerfile()

    assert arguments["MINIO_COMMIT"] == SERVER_COMMIT
    assert arguments["MC_COMMIT"] == CLIENT_COMMIT
    for commit in ("MINIO_COMMIT", "MC_COMMIT"):
        assert f'test "$(git rev-parse HEAD)" = "${{{commit}}}"' in dockerfile


def test_every_base_image_is_pinned_by_digest() -> None:
    bases = re.findall(r"^FROM (\S+)", _dockerfile(), re.MULTILINE)

    assert bases, "a Dockerfile with no base image would vacuously pass"
    for base in bases:
        assert re.search(r":[\w.-]+@sha256:[0-9a-f]{64}$", base), f"{base} floats"


def test_no_healthcheck_needs_mc() -> None:
    probes = {
        (name, service): _probe(definition)
        for name in COMPOSE_FILES
        for service, definition in _services(name).items()
    }

    assert not [key for key, probe in probes.items() if re.search(r"\bmc\b", probe)]
    local = probes[("docker-compose.local.yml", "minio")]
    assert "curl -fsS http://127.0.0.1:9000/minio/health/live" in local
