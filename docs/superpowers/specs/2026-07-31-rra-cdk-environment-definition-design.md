# RRA CDK environment definition — design

Date: 2026-07-31

Authority: `KHEPRI-DEC-005` (runtime, providers, deployment boundary) and `KHEPRI-DEC-007`
(sizing), both `accepted` in `governance/registries/decisions.yaml` as of PR #44.

## Outcome

One AWS CDK v2 application defines both the RRA private-beta environment and the dedicated
benchmark environment, instantiated twice from a single stack class, with every sizing value
supplied from a governed declaration and none invented.

## Why one class instantiated twice

`KHEPRI-DEC-007` requires the benchmark environment to be "a second instantiation of the same CDK
application in the same region, `me-central-1`, with an environment identifier as the only naming
input. It is not a hand-built environment, and it is not a second definition to keep in sync."

Two stack classes could drift, and drift silently voids the benchmark's inferential value: a
duration measured on hardware sized unlike beta is not evidence about beta, so the ten-minute
objective would be met somewhere nobody ships. One class makes divergence structurally impossible
rather than merely discouraged.

The decision enumerates the differences that are permitted, and the list is closed: name, network
isolation, service desired count, deletion protection, and the total absence of customer content.
Those five become the stack's only environment-varying props. Any other difference is a governance
violation, not a configuration choice.

## Components

```
src/khepri/infra/
  environment.py      RraEnvironmentStack: composes the five existing constructs
  app.py              cdk.App entrypoint; instantiates the stack twice
  sizing_source.py    loads the governed YAML and hands it to resolve_sizing
governance/benchmarks/
  KHEPRI-BMK-001-sizing.yaml    KHEPRI-DEC-007's sizing table, verbatim
tests/
  test_infra_environment.py     composition, region pinning, and template parity
```

### Wiring order

Forced by the existing constructs' prop shapes; no judgment is involved.

```
GovernedNetwork          -> vpc
GovernedDataResources    -> key, bucket, queue, dead-letter queue   (takes QueueSizing)
GovernedDatabase         -> DatabaseProps{vpc, key, sizing}
GovernedImageRepository  -> repository                              (takes key)
GovernedCompute          -> ComputeProps{EnvironmentResources, PinnedImage, ServiceSizing}
```

### Sizing declaration

`resolve_sizing` already refuses a missing, blank, or non-integer field, so the only question is
where a complete declaration comes from. It comes from a checked-in YAML file holding
`KHEPRI-DEC-007`'s values verbatim.

A checked-in document is reviewable, diffable, and digest-coverable: changing a size becomes a pull
request that changes a digest, which is what `KHEPRI-DEC-007` means by "resizing a task is
therefore a governed change and never an operational adjustment." CDK context and environment
variables are excluded because `sizing.py` already refuses them by name -- "Nothing here reads an
environment variable, a context value, or a default."

Values, from `KHEPRI-DEC-007`:

| Field | Value |
|---|---|
| `web_cpu_units` | 1024 |
| `web_memory_mib` | 4096 |
| `web_ephemeral_storage_gib` | 20 |
| `worker_cpu_units` | 4096 |
| `worker_memory_mib` | 16384 |
| `worker_ephemeral_storage_gib` | 40 |
| `database_instance_class` | `db.m7g.large` |
| `allocated_storage_gib` | 100 |
| `backup_retention_days` | 7 |
| `visibility_timeout_seconds` | 300 |
| `message_retention_seconds` | 1209600 (14 days) |
| `receive_wait_seconds` | 20 |
| `max_receive_count` | 3 |
| `max_attempts` | 3 |

### The image digest is not a sizing value

`KHEPRI-DEC-007` lists the OCI image digest among the four facts the *environment descriptor*
records from the build, beside the `uv.lock` digest, the exact Python patch version, and the
SHA-256 of the reviewed synthesized template. It is not in the sizing table.

So it does not belong in the sizing YAML. Putting it there would merge two governed artifacts and
force a placeholder into a governance directory to assert a fact that is not yet true.

`RraEnvironmentStack` therefore takes `image_digest` as a required constructor prop with no
default, and `app.py` supplies it as an explicit build input. `PinnedImage.__post_init__` already
validates the shape -- a full `sha256:` digest, never a tag -- and shape validation is all it does,
which is why the existing `tests/test_infra_compute.py` constructs one from `"sha256:" + "ab" * 32`.
Synthesis is therefore possible today; it is gated on supplying a value, not on a built image
existing. This preserves the honest ordering `KHEPRI-DEC-007` describes: definition, then build,
then synthesis, then descriptor.

### Region is pinned, not inherited

`KHEPRI-DEC-007` states that if any selection is unavailable in `me-central-1`, "the CDK definition
must fail rather than substitute a neighbour."

A stack constructed without an explicit `env` is region-agnostic and deploys wherever
`CDK_DEFAULT_REGION` or the ambient profile points. That is silent substitution by omission, so
both instantiations pass `env=Environment(region="me-central-1")` explicitly. No construct in
`src/khepri/infra/` currently pins a region; this slice introduces it.

Regional *availability* of `db.m7g.large`, `gp3` at the stated baseline, and the two Fargate
combinations remains unverified and outside this slice. Pinning the region is what makes an
unavailable selection fail at deployment instead of quietly landing elsewhere.

## Testing

The load-bearing test synthesizes **both** instantiations and asserts the two CloudFormation
templates agree on every sizing property: task CPU, task memory, ephemeral storage, database
instance class, allocated storage, backup retention, queue visibility timeout, message retention,
receive wait, and the redrive `maxReceiveCount`.

Asserting parity on the `InfrastructureSizing` object would be weaker, because the same object can
still be applied differently downstream. Comparing synthesized templates is the mechanized form of
"identical by construction," and it is the test that catches future drift.

Also tested:

- Every sizing field absent, blank, or non-integer in the YAML raises `SizingRefused`.
- The YAML values equal `KHEPRI-DEC-007`'s table, so editing the decision without the declaration
  fails a test rather than passing silently.
- Both stacks pin `me-central-1`.
- The benchmark stack's service desired count is 1; the beta stack does not set one.
- The two environments do not share a KMS key, bucket, database instance, or queue -- which holds
  by construction, because each construct is created inside its own stack instance.

## Error handling

Failure is refusal, consistent with the existing module. `resolve_sizing` raises `SizingRefused` on
an incomplete declaration; `PinnedImage` raises on a tag or malformed digest; a missing or
unparseable sizing YAML raises rather than falling back to a default. No path substitutes a value.

## Out of scope

- The environment descriptor `governance/benchmarks/KHEPRI-BMK-001-environment.yaml`.
  `KHEPRI-DEC-007` states it "cannot be written before the CDK definition exists, because four of
  those values are outputs of building and synthesizing it."
- Verifying `me-central-1` availability of every selection.
- Building or pushing the OCI image, and the Chromium/Playwright pinning facts.
- Beta desired count and autoscaling, reserved to the beta-authorization artifact.
- Any deployment, and any claim that a benchmark has been run or the objective met.
