# #631 slice: both compose stacks build MinIO from its pinned source tag

**Authority:** GitHub issue #631. The compose files belong to `OPS1-08`, which is deferred with
OPS1, and the issue asks that the fix land as its own slice. This is option 1 from the issue,
"build from source in the repository". It was chosen on the owner's instruction to fix these
issues, together with the issue's own recommendation. **Scope:** `docker-compose.local.yml`,
`docker-compose.staging.yml`, a new `ops/minio/minio-from-source.Dockerfile`, and their tests.
`khepri.rra.storage` and every storage contract are unchanged.

**Status:** bounded plan. Its RED tests land with it (`tests/test_minio_from_source.py`, strict
`xfail`). Option 3 from the issue, another S3-compatible server, is not evaluated here. It stays
open on #631 because an archived MinIO receives no security updates.

---

## Cause

Both stacks pin `minio/minio:RELEASE.2025-09-07T16-13-09Z`, and staging's `minio-init` pins
`minio/mc:RELEASE.2025-08-13T08-35-41Z`. Open-source MinIO is archived. Docker Hub returns 404
for both repositories, and dl.min.io returns 410 for every community binary. Upstream ships
source only, but the release tags are still on GitHub. A machine without those images cached
cannot start either stack. The local healthcheck also runs `mc ready local`, which depends on
the `mc` bundled in the withdrawn image.

## Change

- `ops/minio/minio-from-source.Dockerfile` has two targets, `server` and `client`. Each one
  clones its release tag with `--depth 1` and fails the build unless `git rev-parse HEAD`
  equals the full commit SHA that the tag dereferences to:
  - `minio`: `07c3a429bfed433e49018cb0f78a52145d4bedeb`;
  - `mc`: `7394ce0dd2a80935aded936b09fa12cbb3cb8096`.
- Each binary is built the way upstream's `Makefile` builds it: `CGO_ENABLED=0`,
  `-tags kqueue -trimpath`, and the ldflags from `buildscripts/gen-ldflags.go` with the release
  time. As a result, `--version` reports the release, not `DEVELOPMENT`.
- The base images are `golang:1.24.13-bookworm` and `debian:12.15-slim`, each pinned by digest.
  The runtime image adds only `curl` and `ca-certificates`. It runs as root, as the upstream
  image did. Staging's TLS pair is mounted at `/root/.minio/certs`, and `minio-init` writes
  its CA to `/root/.mc/certs/CAs`.
- `mc` is built, not replaced. `minio-init` keeps its script and the mc-specific behaviour that
  its comments record, so its behaviour stays identical.
- Both compose files use `build:` (context `ops/minio`, with a target) and a local `image:` tag.
  The tag names the release that the Dockerfile clones.
- The local healthcheck becomes `curl -fsS http://127.0.0.1:9000/minio/health/live`. Staging's
  healthcheck was already curl over TLS against the mounted CA, and it is unchanged.

## Tests (RED at `11ac802`)

`tests/test_minio_from_source.py` is a new file, which keeps the `test_local_config.py` hotspot
untouched. The tests read the parsed compose values, not the raw text, because the comments
legitimately name the withdrawn images. Each test is listed with a mutant that turns it red.

| Test | What it pins | Mutant |
|---|---|---|
| `test_no_service_pulls_a_withdrawn_minio_image` | No service image in either file starts with `minio/minio` or `minio/mc` | restore a `minio/minio:` image |
| `test_each_minio_service_builds_the_release_the_dockerfile_clones` | Each MinIO service builds the committed Dockerfile at the right target, and its image tag equals the Dockerfile's release `ARG` | change a target, or a tag |
| `test_each_release_is_pinned_to_its_full_commit_and_checked` | Both full SHAs, and the `git rev-parse HEAD` comparison for each | change a SHA, or drop a check |
| `test_every_base_image_is_pinned_by_digest` | Every `FROM` is an exact tag plus `@sha256:` | drop a digest |
| `test_no_healthcheck_needs_mc` | No probe runs `mc`, and the local one curls `/minio/health/live` | restore `mc ready local` |

## Verification (real Docker)

1. Run `docker image rm` on the two withdrawn tags first, so a passing `up` cannot be served
   from a cache.
2. Build both targets. Check that `minio --version` and `mc --version` name the release.
3. Build with a wrong commit `ARG`, and check that the build fails at the check.
4. Bring the local stack up and wait for `healthy`. Run the real-stack tests (gated by
   `tests/local_stack_support.py`) and a boto3 put/get round trip.
5. Staging: run `generate-certs.sh` with a random `KHEPRI_STORAGE_MASTER_KEY`, then
   `up -d minio minio-init`. Check that `minio-init` exits 0 with `[OK]`, then run a boto3
   put/get over TLS against the local CA.
6. Run `down` on both stacks, and keep any volume that existed before this run.

## Status 2026-10-02 -- implemented on `fix/631-minio-from-source`

The markers are removed and all eight tests pass. Nine mutants were each run against their test,
and all nine turned it red. The Docker checks ran in WSL (Docker 29.4.2):

- **Clean cache.** The two withdrawn images were already absent. `docker image rm` answered
  `No such image` for both, and `docker pull minio/minio:RELEASE.2025-09-07T16-13-09Z` was
  refused with `repository does not exist`. Nothing below could have come from a cached
  upstream image.
- **Builds.** Both targets built. `minio --version` reports
  `RELEASE.2025-09-07T16-13-09Z (commit-id=07c3a429bfed433e49018cb0f78a52145d4bedeb)`, and
  `mc --version` reports
  `RELEASE.2025-08-13T08-35-41Z (commit-id=7394ce0dd2a80935aded936b09fa12cbb3cb8096)`. Both
  run on go1.24.13.
  - A build with `MINIO_COMMIT` set to the annotated tag object's SHA cloned `07c3a42`. It then
    failed at the check, before any module was downloaded.
  - One `mc` build failed first with a transient `tls: bad record MAC` from proxy.golang.org.
    It had already passed the SHA check, and the retry built.
- **Local stack.** `up -d` brought both services to `healthy`, and the curl probe exits 0. The
  server image contains no `mc`. Run against the stack after `alembic upgrade head`, the
  stack-gated tests (`test_local_storage`, `test_local_journey`, `test_local_sweeper`,
  `test_rca001_migration`) gave `39 passed, 1 skipped`. The skip is `KHEPRI_DATABASE_URL is not
  set`, which does not depend on the stack. A boto3 round trip from `LocalSettings` also passed:
  - `put` returned 200 with no `VersionId`;
  - a second `IfNoneMatch` put was refused with `PreconditionFailed`;
  - `get` returned the bytes that were put;
  - after `delete`, `KeyCount` was 0.
- **Staging stack.** `generate-certs.sh` ran, and a random master key was supplied.
  - MinIO served `https://` and became `healthy` through the unchanged TLS probe.
  - `minio-init`, on the built `mc`, exited 0. It printed `[OK] bucket private, lifecycle
    configured`, and it exited 0 again when re-run.
  - A boto3 put/get/delete over TLS, verified against `certs/ca.crt`, passed.
  - The whole stack then ran with `--no-build`: `migrate` exited 0, and web and worker started.
    From inside `khepri-staging-web`, a round trip that used only the runtime's own environment
    (`KHEPRI_STORAGE_ENDPOINT=https://minio:9000`, `AWS_CA_BUNDLE`) passed.
  - The runtime image was the cached `khepri-runtime:staging`, which was not rebuilt from this
    branch. This change touches nothing in that image.
- Both stacks were taken down with `down -v`. Every volume removed was created by this run. None
  existed before it.
