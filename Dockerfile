# The one image both RRA services run, with Chromium baked in.
#
# `KHEPRI-DEC-007` pins Chromium "by being baked into the OCI image", because that makes the pin
# transitive: the environment_digest covers the image digest, the image digest covers the browser
# bytes, and no run can silently acquire a different browser. Installing a browser at container
# start would defeat that -- and could not work anyway, since `GovernedNetwork` provisions no NAT
# gateway and no egress route, so there is nowhere to download from.
#
# The base is Microsoft's official Playwright image rather than python:slim plus
# `playwright install`. The Debian dependency set Chromium needs is long, undocumented, and moves
# between Playwright releases; getting it wrong produces the same "renderer crash" signature the
# /dev/shm flag exists to avoid. This image is maintained in lockstep with the Playwright version
# that `uv.lock` already pins, so the browser and the client cannot disagree.
#
# The tag must match the locked Playwright version exactly -- a mismatch is a supported-protocol
# error at run time, so the build asserts it below rather than trusting the tag.
#
# Architecture is amd64. `src/khepri/infra/compute.py` sets `CpuArchitecture.X86_64` and records
# why: no approved artifact settles architecture, and an ARM64 task would require a matching image.
# The Graviton database instance is irrelevant here -- RDS runs the engine, not this container.
FROM --platform=linux/amd64 mcr.microsoft.com/playwright/python:v1.61.0-noble

# Fail the build rather than produce an image whose browser and client disagree.
ARG EXPECTED_PLAYWRIGHT_VERSION=1.61.0

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/khepri/.venv \
    PATH="/opt/khepri/.venv/bin:${PATH}"

# uv is copied from its own published image so the version is pinned by digest-bearing tag rather
# than fetched by a script whose output changes over time.
COPY --from=ghcr.io/astral-sh/uv:0.10.11 /uv /usr/local/bin/uv

WORKDIR /opt/khepri

# Dependencies resolve from the lockfile alone, before any source is copied, so a source-only
# change cannot silently re-resolve them. `--frozen` refuses to update the lock: an image whose
# dependency set differs from `uv.lock` would make the recorded uv.lock digest a lie.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev

# Assert the three facts the environment descriptor will record are what this build intended.
# A mismatch here is a failed build, never a warning: `KHEPRI-DEC-007` requires the descriptor to
# record what was actually produced, and a fact asserted by hand is not evidence about an image.
RUN set -eu; \
    installed="$(python -c 'import importlib.metadata as m; print(m.version("playwright"))')"; \
    if [ "$installed" != "$EXPECTED_PLAYWRIGHT_VERSION" ]; then \
        echo "FAIL: playwright $installed does not match the base image tag $EXPECTED_PLAYWRIGHT_VERSION" >&2; \
        exit 1; \
    fi; \
    python -c "from playwright.sync_api import sync_playwright" ; \
    python -c "import khepri.rra.rendering.chromium"

# Prove the baked browser actually launches, with the flag `KHEPRI-DEC-007` requires. A browser
# that cannot start is a broken image, and finding that out at build time costs a build; finding it
# out at run time costs a report.
RUN python -c "\
from playwright.sync_api import sync_playwright; \
from khepri.rra.rendering.chromium import LAUNCH_ARGS; \
p = sync_playwright().start(); \
b = p.chromium.launch(headless=True, args=list(LAUNCH_ARGS)); \
print('chromium', b.version); \
b.close(); p.stop()"

# The Playwright base image ships a non-root `pwuser`. Nothing in this container needs to write
# outside the ephemeral storage the task definition grants, so it does not run as root.
RUN chown -R pwuser:pwuser /opt/khepri
USER pwuser

# No CMD, deliberately. One image serves both roles, and the containers in
# `src/khepri/infra/compute.py` are named `web` and `worker` but currently pass no command of their
# own. A default here would silently make this image one of those two roles, so the entry point
# arrives with the slice that gives each container its command -- the same reason no size and no
# image digest is defaulted anywhere else in this repository.
