# RRA OCI image and Chromium pin — design

Date: 2026-07-31

Authority: `KHEPRI-DEC-005` (runtime, providers, deployment boundary) and `KHEPRI-DEC-007`
(sizing, Chromium pinning), both `accepted`.

## Outcome

One reproducible OCI image runs both the web and worker services, with Chromium baked in so the
browser cannot be acquired at runtime, and with the launch flag Fargate requires actually wired.
The build records the three facts `KHEPRI-DEC-007` requires the environment descriptor to carry.

## Why the browser is baked in, not installed at start

`KHEPRI-DEC-007`: "Chromium is pinned by being **baked into the OCI image**, and the descriptor
records the image digest. That is the whole mechanism, and it is chosen because it makes the pin
transitive: the `environment_digest` already covers the image digest, the image digest covers the
browser bytes, and no run can silently acquire a different browser."

A `playwright install` at container start would defeat that: the bytes would come from the network
at run time, so two runs of the same digest could use different browsers, and a benchmark result
would not identify what produced it. The network path is also absent by construction —
`GovernedNetwork` provisions no NAT gateway and no egress route, so a runtime download cannot
succeed. Baking in is the only option that works and the only one that pins.

## The launch flag is a correctness requirement, not tuning

`KHEPRI-DEC-007` requires the worker to launch Chromium with `--disable-dev-shm-usage`: Fargate
fixes `/dev/shm` at 64 MiB and does not support `linuxParameters.sharedMemorySize`, which is an
EC2-launch-type parameter. Chromium's default shared-memory use exceeds 64 MiB while rendering a
paginated document and fails in a way that presents as a renderer crash rather than as a memory
limit.

`src/khepri/rra/rendering/chromium.py` currently calls `play.chromium.launch(headless=headless)`
with no `args`. `src/khepri/infra/compute.py` records this as an outstanding obligation of the
rendering slice, and the worker's 40 GiB ephemeral storage was sized to absorb exactly what the
flag displaces. This slice discharges that obligation: without it, the sizing already merged is
paying for a flag nobody set.

## Architecture is x86_64, and that is already settled

`src/khepri/infra/compute.py:88` sets `ecs.CpuArchitecture.X86_64`, and its docstring states the
reasoning: no approved artifact settles architecture, `KHEPRI-DEC-007` sizes tasks in CPU units and
says nothing about it, and "an ARM64 task would require the published image to match ... changing it
needs an artifact that settles it and an image built for it."

So the image is built for `linux/amd64`. The `db.m7g.large` instance being Graviton is irrelevant:
RDS runs the PostgreSQL engine on that hardware, not this container. Building ARM64 would produce an
image the merged task definitions cannot run.

## Components

```
Dockerfile              multi-stage; Playwright base, Chromium baked, non-root
.dockerignore           keeps the build context small and secret-free
scripts/build_image.py  builds, reads back the three descriptor facts, prints them as YAML
src/khepri/rra/rendering/chromium.py   add the required launch args
tests/test_rra006_chromium_launch.py   assert the flag is passed
```

### Base image

`mcr.microsoft.com/playwright/python:v1.61.0-noble` — Microsoft's official Playwright image, pinned
by tag *and* digest at build time.

Chosen over `python:3.13-slim` plus `playwright install chromium` because the system dependency set
Chromium needs on Debian is long, undocumented, and changes between Playwright releases; getting it
wrong produces the same "renderer crash" signature the `/dev/shm` flag exists to avoid. The official
image is maintained in lockstep with the Playwright version, and the Playwright version is already
pinned in `uv.lock`. The cost is a larger image, which affects Fargate pull time but not the
ten-minute per-report objective, since a pull is not inside the measured interval.

The image tag must match the locked Playwright version exactly. A mismatch between the baked browser
and the Python client is a supported-protocol error at run time, so the build asserts it rather than
trusting the tag.

### The three recorded facts

`KHEPRI-DEC-007` requires the descriptor to record the OCI image digest, the `uv.lock` digest, the
exact Python patch version, and the SHA-256 of the reviewed synthesized template. This slice
produces the first three; the fourth comes from synthesis, which needs a real digest and therefore
follows this slice.

Known today, to be re-read from the built image rather than assumed:

| Fact | Value |
|---|---|
| Playwright | `1.61.0` |
| Chromium revision | `1228` |
| Chromium browser version | `149.0.7827.55` |
| Python patch | `3.13.12` |

`build_image.py` reads all of these *out of the built image* and prints them. It never accepts them
as input, because a fact supplied by hand is not evidence about the image.

## Testing

- `launch_chromium` passes `--disable-dev-shm-usage`. Asserted against a fake Playwright so the test
  needs no browser; the argument list is the observable contract.
- The flag list is a module constant, so the test names the same constant the code uses rather than
  duplicating a string that could drift.
- `build_image.py` fails when the image's Playwright version does not match `uv.lock`.
- `build_image.py` fails rather than reporting a partial fact set if any of the three facts cannot be
  read from the image.

Docker is available in neither CI nor the authoring machine (verified 2026-07-31: no `docker`
binary). So the build script's argument handling and fact-parsing are unit-tested against captured
output, and **no image is built by this slice**. CI proves the flag is wired and the Dockerfile is
syntactically coherent; it does not prove an image exists.

This is why the slice is split. The flag wiring and the Dockerfile are complete, reviewable, and
testable now. Producing the actual digest requires a machine with Docker and is a separate,
explicitly-labelled step — recorded as an obligation rather than silently assumed done.

## Error handling

Refusal, consistent with the module: a Playwright version mismatch, an unreadable fact, or a missing
Docker daemon raises rather than emitting a partial or guessed result. No default digest exists.

## Out of scope

- The environment descriptor itself. Four of its values are synthesis outputs, and
  `KHEPRI-DEC-007` states it cannot be written before those exist.
- Pushing to ECR, and any deployment. The repository is defined by
  `GovernedImageRepository`; publishing into it is a provisioning action this slice does not take.
- Changing `CpuArchitecture`, task sizing, or any construct already merged.
- Any claim that a benchmark has been run or that the completion objective has been met.
