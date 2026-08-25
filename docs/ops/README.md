# Khepri operations documentation

**Status: operator reference, not a governed artifact.** Nothing here approves anything,
records no approval, creates no authority, allocates no identifier, and authorizes no
provisioning, deployment, or spend. `governance/registry.yaml` is authoritative for
artifact identity, state, and supersession; no document in this directory is an input to
`uv run khepri-gov validate`, which validates the registry and the artifacts it names.

Where a source-file comment cites a decision the registry records as `retired`, these
documents name the active decision and say so rather than repeating the stale citation —
`AGENTS.md` is explicit that prose cannot override the registry.

Every command and value below is traceable to a line in this repository. Where a
procedure does not exist yet, this package says so instead of inventing one.

## What can actually be run today

| Surface | Status | Document |
|---|---|---|
| Local development stack | Works. Two backing services, app from source. | [`local-development.md`](local-development.md) |
| Local staging stack | Works. The built image end to end, TLS on. | [`staging-stack.md`](staging-stack.md) |
| Image build + fact collection | Works. Requires a Docker daemon. | [`image-build.md`](image-build.md) |
| Database migrations | Works. Alembic, one head. | [`migrations.md`](migrations.md) |
| **Provisioned deployment** | **Not authorized.** See below. | — |

## There is no deployment runbook, deliberately

`KHEPRI-DEC-027` is `active` and names **DigitalOcean FRA1** as the target *direction*.
It states in its own header that it "does not authorize provisioning, deployment, beta
launch, or spend," and §4 repeats it. §3 lists the stop-gates that remain open before
provisioning:

- concrete DigitalOcean product selections and exact versions;
- acceptance and mitigation of provider-managed PostgreSQL minor upgrades;
- the envelope-master-key secret source;
- the egress/VPC posture, and whether any dependency requires IP allowlisting;
- owner-approved RTO and RPO targets;
- worker/web/database sizing derived from the governed benchmark rules;
- any remaining OPS1 operational defect that would make an environment unsafe or
  non-recoverable.

`OPS1-02` remains blocked until the target-selection/environment descriptor required by
`KHEPRI-DEC-008` is complete and approved.

**On `cdk.json`.** The repository contains an AWS CDK entry point (`cdk.json`, which
synthesizes `khepri.infra.app`; `aws-cdk-lib>=2.262,<3` is the sole member of the `infra`
dependency group in `pyproject.toml`, deliberately kept out of the runtime image). Per
`KHEPRI-DEC-027` §Consequences, AWS `eu-central-1` is "a fallback candidate, not an
active target." The CDK app in the tree therefore does **not** describe the currently
selected direction, and neither provider has an authorized deployment procedure. Do not
read `cdk.json` as one.

## Emergency procedures

The Clerk private-beta hard stop is documented once, at
[`../platform/CLERK_PRIVATE_BETA_HARD_STOP.md`](../platform/CLERK_PRIVATE_BETA_HARD_STOP.md),
and is invoked with the `khepri-clerk-hard-stop` console script declared in
`pyproject.toml`. It is deliberately not restated here — a second copy of an emergency
procedure is worse than none, because the two drift.

## Two stacks, and why they coexist

`docker-compose.local.yml` and `docker-compose.staging.yml` are siblings, not
alternatives. The local file stands up backing services for an app run from source with
`uv`; the staging file runs the built image itself — web, worker, migrations — against
TLS-enabled backing services, so what it exercises is the artifact rather than a source
tree.

Each file sets its own Compose `name:` (`khepri-local`, `khepri-staging`). This is
load-bearing: Compose otherwise derives a project name from the directory, both files
claim the same project, and starting one stack tears down and recreates the other's
containers. Their published ports are disjoint for the same reason — the two stacks are
meant to run at once.

## Windows: the Docker-in-WSL SIGTERM trap

Both compose files carry the same warning. A container started from a one-shot
`wsl -- bash -lc ...` receives SIGTERM when that WSL session ends, because WSL stops the
distribution once its last process exits. Keep a long-lived WSL process open, or start
the stack from a shell that stays open.

## Before handing work off

`AGENTS.md` requires three gates. They are not optional, and local tooling does not
reproduce CodeScene's thresholds:

```sh
uv run khepri-gov validate
uv run ruff check .
uv run pytest
```

CodeScene Code Health Review is a required server-side PR gate: every new file must
score 10.00 and no tracked hotspot may decline.
