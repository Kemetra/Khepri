# Local staging stack

**Status: operator reference, not a governed artifact.** It selects no provider and
authorizes nothing. Nothing here is benchmark, residency, recovery, or approval evidence,
and none of it authorizes spend.

Source of truth: `docker-compose.staging.yml` and `ops/staging/generate-certs.sh`. Where
this document and those files disagree, the files are correct.

## What it is

The production image, end to end, on one machine: web, worker, and migrations running from
the built artifact against TLS-enabled backing services. Its sibling
`docker-compose.local.yml` runs the app from source instead — see
[`local-development.md`](local-development.md).

**"Staging" here means a local stack that exercises the artifact.** It is not a
provisioned environment. `KHEPRI-DEC-027` reserves the concrete product selections,
sizing, RTO/RPO, and the envelope-master-key secret source as unresolved stop-gates before
provisioning. MinIO substitutes for Spaces locally without choosing it, and the CPU and
memory limits below are local comfort values, not governed sizing — the sizing rules live
in `KHEPRI-DEC-008`, and `governance/benchmarks/KHEPRI-BMK-001-sizing.yaml` is to be
re-issued against the selected target. (The compose file's comment attributes sizing to
`KHEPRI-DEC-007`, which the registry records as `retired`, superseded by DEC-008.)

## Bring it up

```sh
sh ops/staging/generate-certs.sh
docker compose -f docker-compose.staging.yml up -d --build
```

- web: `http://127.0.0.1:8000`
- MinIO console: `https://127.0.0.1:29001`

The certificate script must run first. `ops/staging/certs/` is gitignored, so on a clean
checkout it does not exist — the script *is* the documented first command, and it creates
the directory itself rather than assuming one.

## TLS is not optional here — it is what makes the stack work

`khepri.runtime.config` builds every database URL with `sslmode=require` and offers no
override, so a plaintext PostgreSQL is **unreachable by this image**. There is no
non-TLS path to fall back on.

The certificates are local, self-signed, and written by `ops/staging/generate-certs.sh`:

| Consumer | Trust model | Why |
|---|---|---|
| PostgreSQL | Self-signed, trusted implicitly | `sslmode=require` encrypts without verifying a chain |
| MinIO | Leaf issued by a local CA | botocore verifies it, via `AWS_CA_BUNDLE` |

`AWS_CA_BUNDLE` is read natively by botocore, so the local CA is trusted without modifying
the image's trust store — which the image could not do anyway, as it runs as `pwuser`.

The script is idempotent and checks for **every** file the stack mounts
(`ca.crt`, `ca.key`, `server.crt`, `server.key`, `minio/public.crt`, `minio/private.key`,
`minio/ca.crt`), not a representative subset: an interrupted earlier run can leave
`minio/public.crt` written but `minio/ca.crt` not yet copied, and checking a subset would
report success while the stack failed later with a TLS error pointing nowhere near the
missing file.

It also `chmod 600`s the keys, because PostgreSQL refuses to start if its key is group- or
world-readable, and reads it as uid 999 inside the container.

Nothing in `ops/staging/certs/` is a secret, and none of it may be reused anywhere. The
directory is gitignored: a committed private key is a committed private key regardless of
what it protects, and this material is meant to be regenerated per machine.

## Services

| Service | Image | Role |
|---|---|---|
| `postgres` | `khepri-staging-postgres:17.11-tls` (built from `ops/staging/postgres-tls.Dockerfile`) | TLS-enabled database |
| `minio` | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | S3-compatible store over HTTPS |
| `minio-init` | `minio/mc:RELEASE.2025-08-13T08-35-41Z` | one-shot bucket creation |
| `migrate` | `khepri-runtime:staging` | `alembic upgrade head`, `restart: "no"` |
| `web` | `khepri-runtime:staging` | `uvicorn khepri.runtime.web:app`, port 8000 |
| `worker` | `khepri-runtime:staging` | `python -m khepri.runtime.worker` |

`web` and `worker` both wait on `migrate` completing successfully and on `minio-init`, so
the schema and bucket exist before either starts.

## Scale the worker by replicas, never by threads

In-task concurrency is exactly 1: `ClaimWorkerLoop` claims and settles one job at a time.
A second process inside one container would not be a second worker but a second claimant
racing the same rows.

```sh
docker compose -f docker-compose.staging.yml up -d --scale worker=2
```

This is why `worker` alone has **no** `container_name` — a fixed name makes `--scale`
fail outright, because Compose can only give one container that name. Every other service
keeps its name, because exactly one of each is correct.

Resource limits reflect what each does: `web` gets 1 CPU / 1g; `worker` gets 2 CPUs / 4g,
because Chromium renders the reports and is memory-hungry rather than CPU-hungry.

## No broker, no KMS, no separate browser

`KHEPRI-DEC-008` replaced the message broker with a PostgreSQL claim query, moved
encryption into the application, and pins Chromium inside the image via Playwright so the
pin is transitive. Redis, Kafka, RabbitMQ, SQS, LocalStack, KMS, and a Chromium container
would all be machinery for capabilities that no longer exist.

Chromium is launched with `--disable-dev-shm-usage`. `KHEPRI-DEC-008` notes that
`KHEPRI-DEC-007` originally required this because AWS Fargate fixes `/dev/shm` at 64 MiB —
a provider-specific rationale that no longer applies, though the flag is retained.

## Clerk is absent deliberately

`_clerk_settings` reads its variables through `_optional`, so their absence is valid and
the stack runs on invitation sessions. **Supplying them empty would fail `_required`.**
Add real values only to test real Clerk authentication.

## Environment worth knowing

`KHEPRI_DATABASE_SECRET` is one Secrets Manager-shaped JSON document, which is what
`_database_secret` parses — not a URL. The runtime never joins the password into a string.

`KHEPRI_STORAGE_MASTER_KEY` is 32 zero bytes, base64. It is deliberately fixed and
deliberately not a secret: a generated key would make objects written by one container
unreadable by the next. **The real secret source is a `KHEPRI-DEC-027` stop-gate.**

`migrate` overrides with `KHEPRI_DATABASE_URL`, which `migrations/env.py` prefers over
`alembic.ini` — whose pinned URL points at the *local* stack.

## Windows: Docker-in-WSL SIGTERM

Same trap as the local stack. A container started from a one-shot `wsl -- bash -lc ...`
receives SIGTERM when that WSL session ends. Keep a long-lived WSL process open, or start
the stack from a shell that stays open.

## Teardown

```sh
docker compose -f docker-compose.staging.yml down
```

Volumes `khepri-staging-pgdata` and `khepri-staging-miniodata` survive; add `-v` to
discard them. Because each compose file sets its own project `name:`, tearing this stack
down leaves the local stack running.
