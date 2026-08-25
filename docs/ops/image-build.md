# Image build and fact collection

**Status: operator reference, not a governed artifact.** Running this script authorizes no
provisioning, deployment, or spend, and its output is not an approved environment
descriptor — it is raw material for one.

Source of truth: `scripts/build_image.py` and `Dockerfile`.

## What it does

Builds the RRA image and then **reads back** the facts an environment descriptor must
record: the OCI image digest, the `uv.lock` digest, the exact Python patch version, and
the SHA-256 of the reviewed synthesized template. This script produces the first three.

**On the decision this cites.** The script's docstring attributes the requirement to
`KHEPRI-DEC-007`, which `governance/registry.yaml` records as `retired`, superseded by
`KHEPRI-DEC-008`. The active requirement is `KHEPRI-DEC-008`, whose "Target selection is a
separate, pre-deployment artifact" section fixes the required content of that artifact —
provider and region, residency justification, the concrete product and exact version per
capability, object-store semantics against `RRA-002`, recorded RTO and RPO, and sizing
values. DEC-008 describes recording the value as "the discipline `KHEPRI-DEC-007`
established," i.e. as precedent rather than as live authority. Cite DEC-008, and read the
docstring's DEC-007 reference as stale prose the registry has superseded.

## Run it

```sh
uv run python scripts/build_image.py
```

| Flag | Effect |
|---|---|
| `--tag TAG` | image tag; default `khepri-rra:local` |
| `--skip-build` | inspect an already-built image instead of building it |

Docker is required. If it is absent the script **refuses** rather than emitting a partial
fact set, because a descriptor with three of four fields is not a descriptor. Refusals
print `REFUSED: ...` to stderr and exit 1.

The build is pinned to `--platform linux/amd64`.

## What it reports

```
oci_image_digest
uv_lock_sha256
python_patch_version
playwright_version
chromium_revision
chromium_browser_version
```

If any value comes back empty, the script refuses instead of reporting a partial set.

## Every fact is read out of the image, never accepted as an argument

This is the design rule, and the reason there is no `--digest` flag. A digest or version
supplied by hand is a *claim about* an image rather than *evidence about* it, and the whole
point of recording them is that the descriptor's `environment_digest` covers what actually
ran.

The one exception is `uv_lock_sha256`, computed from `uv.lock` in the checkout — the same
file the image was built from, asserted by `--frozen` in the `Dockerfile`.

## Repo digest versus image ID — do not conflate them

`image_digest()` returns the **repo digest** if the image has been pushed, and otherwise
falls back to the local **image ID**. These are different things:

- a repo digest names bytes in a registry;
- an image ID names a local config blob.

The descriptor means the **pushed** digest — `KHEPRI-DEC-008` requires the OCI image to be
published to a registry the descriptor records. Both values are reported and labelled so
whoever writes the descriptor records the right one. An unpushed local build yields an
image ID, which is **not** descriptor-grade evidence.

## The fourth fact comes later

The synthesized-template SHA-256 is not produced here. It comes from CDK synthesis, which
needs a real image digest and therefore runs after this step — the script's own output says
so.

Note that synthesis runs the AWS CDK app in `cdk.json`. Per `KHEPRI-DEC-027`, AWS
`eu-central-1` is a fallback candidate and not the active target, so treat that step as
governance-blocked rather than routine; see [`README.md`](README.md).
