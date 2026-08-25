# Local development stack

**Status: operator reference, not a governed artifact.** Authorizes nothing. Nothing this
stack produces is benchmark, residency, recovery, or approval evidence.

Source of truth: `docker-compose.local.yml`. Where this document and that file disagree,
the file is correct.

## What it is

Two backing services — PostgreSQL and an S3-compatible endpoint — on a developer's
machine, so the journey can be run with the application itself started from source by
`uv`. It is named `.local` so it can never be mistaken for a provisioned environment.

**It names no cloud provider, and that is the point.** MinIO is a local development
choice and pre-empts none of the `KHEPRI-DEC-027` stop-gates. `khepri.rra.storage` has no
provider branch and must never acquire one, so what runs here differs from any target
only in endpoint and credentials.

## The journey

```sh
docker compose -f docker-compose.local.yml up -d
uv run alembic upgrade head
uv run python -m khepri.local.cli invite
uv run uvicorn khepri.local.app:app --reload
uv run python -m khepri.local.cli work
```

The last two are separate long-running processes: the web app serves, and `work` processes
due report jobs. `khepri.local.cli` also exposes `sweep`, which runs one recovery and
expiry pass.

## Services and ports

| Service | Image | Host port | Notes |
|---|---|---|---|
| `postgres` | `postgres:17.11-alpine` | `127.0.0.1:15432` → 5432 | user/password/db all `khepri` |
| `minio` | `minio/minio:RELEASE.2025-09-07T16-13-09Z` | `127.0.0.1:14566` → 9000 | S3 API |
| `minio` console | — | `127.0.0.1:19001` → 9001 | nothing reads it |

Ports are **bound to loopback explicitly**. Compose's short syntax omits the host IP and
publishes on every interface, which would put a fixed-credential database on the LAN of
whatever machine this runs on.

Neither port is arbitrary. `15432` is what `DEFAULT_DATABASE_URL` in
`khepri.local.config` points at, and it leaves a system PostgreSQL alone. `14566` is
inherited from the endpoint `DEFAULT_S3_ENDPOINT` already names — it is not a LocalStack
remnant, and changing it means editing that default and everything asserting it.

## Credentials are load-bearing

`khepri.local.config` sends `test` / `testtest`. MinIO, unlike LocalStack, rejects
anything but its configured root user, so these two values must match that module. MinIO
also requires a secret of at least eight characters, which is why the secret is not simply
`test`.

The compose file substitutes `${KHEPRI_LOCAL_ACCESS_KEY-test}` and
`${KHEPRI_LOCAL_SECRET_KEY-testtest}` so that overriding them moves client and server
together.

### Set these by exporting them, never in a project `.env`

Compose interpolates from a `.env` beside the compose file automatically, while
`LocalSettings` reads `os.environ` only. A credential written to `.env` therefore
configures MinIO and never reaches a `uv run` client — every call 403s while looking like
a network fault. There is no `.env` in this repository and `.gitignore` keeps it that way.
If one is ever added for other purposes, run compose with `--env-file /dev/null`, or
export these two alongside it.

### The `-` in the substitution is deliberate

`${VAR-default}`, not `${VAR:-default}`. The `:-` form substitutes when the variable is
unset **or empty**, while `os.environ.get(name, default)` substitutes only when it is
unset. With `KHEPRI_LOCAL_ACCESS_KEY=` exported, `:-` would have the client send `''`
while the server was configured with `test` — recreating the exact divergence the
substitution exists to remove. `-` matches Python's semantics, so an empty override
reaches both sides and MinIO refuses to start rather than surfacing later as a 403.

## Why MinIO, and no KMS

The store used to prove its policy by reading `ServerSideEncryption`, `SSEKMSKeyId`, and
`BucketKeyEnabled` off the `PutObject` response, which MinIO cannot satisfy — it rewrites
the key identifier to a form carrying neither region nor account. That is still true and
no longer matters: `KHEPRI-DEC-008` moved encryption into the application, so bytes are
already ciphertext when they leave the process, and `_write_is_unversioned` now checks
only the echoed checksum and the absence of a `VersionId`.

The required surface is put, get, delete, list, abort multipart, and `IfNoneMatch`.
LocalStack was present to supply a KMS that nothing asks for any more.

## The bucket is unversioned on purpose

`ensure_local_bucket` creates it unversioned, and MinIO does not version by default.
`RRA-002` requires deletion to actually delete rather than leave a recoverable prior
version behind, and the store rejects any response carrying a `VersionId`.

## Windows: Docker-in-WSL SIGTERM

A container started from a one-shot `wsl -- bash -lc ...` receives SIGTERM when that WSL
session ends, because WSL stops the distribution once its last process exits. Keep a
long-lived WSL process open, or start the stack from a shell that stays open.

## Teardown

```sh
docker compose -f docker-compose.local.yml down
```

Named volumes `khepri-local-pgdata` and `khepri-local-miniodata` survive that. Add `-v`
to discard the database and object store as well.
