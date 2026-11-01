# KH-24: maintained S3 storage evaluated against Khepri's existing contract (#631)

**Authority:** Jira `KH-24`, and GitHub issue #631, which stays open. This is an evidence record
and a recommendation. It makes no storage disposition: the owner decides that. **Scope:** this
file and `2026-10-26-kh-24-captures/`. It changes no dependency, compose file, CI workflow,
runtime code, test, or registry entry. Every store ran in a disposable local container with
synthetic fixtures. No candidate was imported into the repository.

**Status:** evidence recorded 2026-10-25, 21:30–21:52 UTC, which was 2026-10-26 local time.
Docker 29.8.2 and boto3/botocore 1.43.111, from this branch's `uv.lock`.

## Recommendation

**SeaweedFS is the only candidate that passed the contract. Garage is rejected.**

- **SeaweedFS 4.50** passed every contract probe, unmodified. That includes conditional creation
  under 16 racing writers for 10 rounds.
- **Garage v2.5.0** fails the contract at the wire:
  - it ignores `If-None-Match: *`, accepts the second create with HTTP 200, and overwrites the
    object;
  - it returns `x-amz-version-id` on every `PutObject`;
  - its multipart listing has no `NextUploadIdMarker`.

  Its first refusal is a correctness defect for content-addressed writes, not a configuration
  gap.

**Retiring MinIO is not urgent, so I recommend a separate slice for it.** The baseline is local
and staging only, and both are bound to loopback. Adopting SeaweedFS is therefore a
maintenance-risk reduction for those two stacks, not a production readiness claim.

- **Make the switch its own owner-approved slice.** That slice changes the compose files, CI
  and the `test_minio_from_source.py` guard.
- **Fix the multipart baseline defect first, in a separate follow-up.** The current MinIO
  baseline fails one contract obligation that SeaweedFS meets (§Baseline defect).
- **Settle the deletion-residue reading before any hosted use** (§Owner items). It applies to
  MinIO and SeaweedFS alike.

Nothing here claims that any store is production-ready.

## The contract that was tested

These requirements come from `src/khepri/rra/storage.py` (`S3EncryptedObjectStore`) and
`KHEPRI-DEC-028`. The store has no provider branch. It needs:

- `put`, `get`, `delete`, `list`, and multipart abort;
- `IfNoneMatch="*"` for content-addressed creation;
- unversioned delete semantics.

`_write_is_unversioned` also requires each `PutObject` response to echo `ChecksumSHA256` and
carry no `VersionId`. Encryption is the application's own, using the envelope from
`khepri.rra.envelope`. No server-side encryption header is read.

Every probe drives the unmodified production class, built by
`khepri.local.storage.build_local_object_store`. Raw boto3 calls only observe error codes and
versioning, or tamper with an object.

## Pinned versions

| Store | Image | Digest | Build identity | License |
|---|---|---|---|---|
| SeaweedFS | `chrislusf/seaweedfs:4.50` | `sha256:c2658820e763294a9e9de7b36c81e59b879e3459148351aee4e31a126ca64860` | `weed version`: `30GB 4.50 ec8f97935 linux amd64` | Apache-2.0 (`gh api repos/seaweedfs/seaweedfs`) |
| Garage | `dxflrs/garage:v2.5.0` | `sha256:677e5b758e4425a325b811c425c026bf35a4bf42f7ddbaa773de3f4fd779a5a5` | `garage v2.5.0`, released 2026-10-24 | AGPL-3.0 |
| MinIO (baseline) | `khepri-minio:RELEASE.2025-09-07T16-13-09Z`, built from `ops/minio/minio-from-source.Dockerfile` | image ID `sha256:968f9fb53caaed5819746600eee1dfacad9e6c746964a32be30e0cd274143611` | `commit-id=07c3a429bfed433e49018cb0f78a52145d4bedeb` | AGPL-3.0, archived upstream |

Notes on the pins:

- SeaweedFS 4.51 was the latest GitHub release, but Docker Hub had no plain `4.51` image tag
  when I pulled. Only variants such as `4.51_large_disk_foundationdb` existed, so 4.50 was used.
- SeaweedFS publishes cosign `.sig` tags. They were **not** verified.
- Garage v2.5.0 was one day old.

## Commands

```bash
# Config: captures/scripts/seaweedfs-s3.json.txt and captures/scripts/garage.toml.txt
docker run -d --name kh24-seaweedfs -p 127.0.0.1:24333:8333 -v kh24-seaweed-data:/data \
  -v <cfg>/s3.json:/etc/s3.json:ro chrislusf/seaweedfs:4.50 \
  server -dir=/data -s3 -s3.port=8333 -s3.config=/etc/s3.json
docker run -d --name kh24-garage -p 127.0.0.1:24900:3900 -v kh24-garage-meta:/var/lib/garage/meta \
  -v kh24-garage-data:/var/lib/garage/data -v <cfg>/garage.toml:/etc/garage.toml:ro dxflrs/garage:v2.5.0
docker exec kh24-garage /garage layout assign -z dc1 -c 1G <node-id>
docker exec kh24-garage /garage layout apply --version 1
docker exec kh24-garage /garage key import --yes <GK-id> <secret>   # generated per run, not recorded
docker exec kh24-garage /garage key allow --create-bucket <GK-id>
docker run -d --name kh24-minio -p 127.0.0.1:24901:9000 -e MINIO_ROOT_USER=test \
  -e MINIO_ROOT_PASSWORD=testtest -v kh24-minio-data:/data khepri-minio:RELEASE.2025-09-07T16-13-09Z server /data

# Per store; the variables are the ones LocalSettings already reads.
PYTHONPATH=src KHEPRI_LOCAL_BUCKET=kh24-eval KHEPRI_LOCAL_S3_ENDPOINT=<endpoint> \
  [KHEPRI_LOCAL_REGION=garage KHEPRI_LOCAL_ACCESS_KEY=... KHEPRI_LOCAL_SECRET_KEY=...] \
  uv run python kh24_probe.py contract          # captures/logs/*-contract.txt
uv run python kh24_raw.py                       # captures/logs/raw-wire-behaviour.txt
KH24_MUTANT=drop-ifnonematch|ignore-overwrite uv run python kh24_probe.py contract   # mutants
uv run python kh24_probe.py restart-write s.json; docker restart kh24-<store>; uv run python kh24_probe.py restart-read s.json
uv run pytest -q tests/test_local_storage.py    # the existing stack-gated tests, per store
```

The scripts are committed as `captures/scripts/*.py.txt`, so they are not collected, linted, or
scored as source.

## Results

Key to the result marks:

- **pass**: the probe passed.
- **REFUSED**: the store contradicts the contract.
- **not reached**: an earlier refusal stopped the probe.
- **untested**: no run covered the case.

| Contract case | SeaweedFS 4.50 | Garage v2.5.0 | MinIO baseline |
|---|---|---|---|
| Bucket created through `ensure_local_bucket`, unversioned | pass (`Status=None`) | pass | pass |
| `PutObject` echoes `ChecksumSHA256`, and has no `VersionId` | pass | **REFUSED**: `x-amz-version-id` on every put | pass |
| put → get round trip; the stored bytes are ciphertext | pass | not reached (store refuses the write) | pass |
| `If-None-Match: *` on an existing key | pass: `PreconditionFailed` 412, body unchanged | **REFUSED**: HTTP 200, body overwritten | pass: 412 |
| Duplicate write proven equivalent (`put_or_verify`) | pass | not reached | pass |
| 16 racing writers, same content, ×10 rounds: exactly one creates | pass | not reached | pass |
| 16 racing writers, distinct content, ×10 rounds: one winner, 15 conflicts, stored bytes are the winner's | pass | not reached | pass |
| Missing key maps to `NoSuchKey` 404 | pass | pass | pass |
| Tampered ciphertext is refused on `get` | pass | not reached | pass |
| `list_objects_v2` pagination (23 objects, `MaxKeys=5`) and `delete_prefix` | pass (6 list calls, 0 left) | not reached | pass |
| Multipart listing by prefix, pagination (`MaxUploads=2`), abort and cleanup | pass (5 listed, 0 left, 4 list calls) | **REFUSED**: `NextUploadIdMarker` missing | **REFUSED**: a directory prefix lists 0 uploads (§Baseline defect) |
| Delete leaves no object or version (`HEAD` 404, `ListObjectVersions` empty) | pass | not reached; `ListObjectVersions` is `NotImplemented` | pass |
| Wrong secret refused (SigV4) | pass: `SignatureDoesNotMatch` 403 | pass: `AccessDenied` 403 | pass: 403 |
| Object survives a container restart | pass | not run | pass |
| `tests/test_local_storage.py` (existing, stack-gated) | 6 passed | 4 failed, 2 passed | 6 passed |
| Physical ciphertext residue after delete | present until `volume.vacuum` | not run | present in `.minio.sys/tmp/.trash` for at least about 4 min |

The probe summaries are `13 ok / 0 failed` (SeaweedFS), `3 ok / 10 failed` (Garage) and
`12 ok / 1 failed` (MinIO). The logs are under `captures/logs/`.

**The probes can fail.** Mutants against SeaweedFS (`captures/logs/seaweedfs-mutants.txt`):

- `drop-ifnonematch` strips the condition from the store's writes. It turns
  `duplicate-proven-equivalent` and both race probes red, with all 16 writers reporting
  `created`.
- `ignore-overwrite` drops unconditional raw writes. It turns `tamper-detected` red.

The real stores supply the remaining mutants:

- Garage reddens the checksum/`VersionId` and `If-None-Match` probes.
- MinIO reddens the multipart probe.

### Untested

- **TLS.**
  - SeaweedFS documents `-s3.cert.file` and `-s3.key.file`. They were not exercised.
  - Garage has no native TLS listener and expects a reverse proxy.
  - Staging's TLS posture was proven for MinIO only, by #645.
- **Upgrade and recovery.** Only a restart was tested, not a version upgrade or a restore.
- **Multiple processes.** `If-None-Match` atomicity was tested on a single `weed server`
  process: one master, one volume server, one filer, one S3 gateway. A multi-filer or
  multi-gateway deployment is untested.
- **Least privilege.** The SeaweedFS identity was granted `Admin`, and narrower action sets were
  not tested.
- **Expiry.** Lifecycle and incomplete-multipart rules on the provider side were not tested.
  Staging's `minio-init` configures these today.

## Baseline defect: MinIO multipart cleanup cannot fail

`DeletionService` calls `abort_multipart_uploads(object_prefix(scope))` with
`owners/<owner>/sessions/<session>/`. That is a directory prefix with a trailing slash
(`src/khepri/rra/deletion.py:226`, `src/khepri/rra/sessions.py:283`).

On this MinIO, `ListMultipartUploads` with that kind of prefix returns **0** uploads, while the
exact key returns them (`raw-wire-behaviour.txt`: prefix `raw/mpu/` → 0, `raw/mpu/0` → 1, no
prefix → 10). The store's abort loop therefore aborts nothing. Its confirmation re-list then
passes vacuously.

Nothing in `src/` creates multipart uploads; every write is a single `put_object`. So the
exposure is limited to uploads created by something else. Still, the only store verified so far
does not meet this obligation, and its guard cannot fail. SeaweedFS lists, paginates and aborts
by prefix correctly. **This should be recorded as a separate follow-up and is not fixed here.**

## Operations, maintenance and licensing

- **Footprint, idle:**

  | Store | Memory | Image |
  |---|---|---|
  | SeaweedFS | 154 MiB | 735 MB |
  | Garage | 14 MiB | 97 MB |
  | MinIO | 126 MiB | 286 MB |

  The existing `test_local_storage.py` took 14.4 s on SeaweedFS and 1.2 s on MinIO, so expect
  slower stack-gated runs.
- **SeaweedFS security maintenance:**
  - `SECURITY.md` supports the latest release only.
  - Releases arrive almost daily: 4.49, 4.50 and 4.51 shipped within three days. A pin will
    therefore fall behind fast, and keeping it current is a recurring cost. There is no LTS line.
  - Its advisory database lists 25 advisories, 9 critical. Several are in components Khepri
    would not run, such as SFTP, the Lance gateway, and the S3 gateway's gRPC identity API
    (GHSA-5fx4-c9qp-36jc, unauthenticated). `weed server` opens master, volume, filer and gRPC
    ports beyond S3, so **any adoption must publish only the S3 port**, as this run did.
  - Its startup banner advertises a separate commercial Enterprise Edition, and the edition
    boundary needs review.
- **Build provenance:**
  - SeaweedFS and Garage were pulled as upstream images pinned by digest. Neither was built from
    source, and no signature was verified.
  - MinIO is built from a pinned commit, but on an archived project and an EOL Go 1.24 toolchain.
- **Licences needing review, with no conclusion drawn here:**
  - SeaweedFS core is Apache-2.0.
  - Garage and MinIO are AGPL-3.0.

  Khepri runs these as separate network services and does not link them.
- **Operational cost assumption:** local and staging only, at no cost beyond the developer's
  machine. Hosted object storage stays `KHEPRI-DEC-028`'s Spaces direction. This evaluation does
  not move it.

## A reversible migration approach, for the future slice and not done here

1. The store has no provider branch, so the switch changes only the endpoint and credentials.
   Swap the compose `minio` services for SeaweedFS with only the S3 port published, then port
   `minio-init` to the AWS CLI or `weed shell` for bucket policy and lifecycle.
2. Replace `tests/test_minio_from_source.py` with a pin and port guard for the new image, and run
   `kh24_probe.py` and the stack-gated tests against it in both stacks, including staging TLS.
3. Data: local and staging hold synthetic data only, so a volume reset is enough. Where content
   must survive, use `aws s3 sync` between endpoints. The envelope is store-independent.
4. Rollback: keep `ops/minio/minio-from-source.Dockerfile` buildable until the new stack has run
   green in both compose files. Reverting is then a compose revert.

## Owner items, raised and not decided here

1. **The maintenance disposition for #631:** adopt SeaweedFS for local and staging in a separate
   slice (recommended), or keep source-built MinIO and accept that it gets no security updates.
2. **Deletion residue and RRA-002.** RRA-002 requires "immediate idempotent deletion and
   automatic seven-day expiry". On both MinIO and SeaweedFS, a successful delete removes the
   object logically, but the ciphertext stays on disk:
   - MinIO keeps it in its trash directory. When MinIO purges it was not measured.
   - SeaweedFS keeps it in the volume file until a vacuum runs. The default garbage threshold
     (0.3) means a low-churn volume may never be vacuumed unless one is scheduled.

   The bytes are application-encrypted. Whether this residue is acceptable, or must be bounded
   by a scheduled vacuum or by provider policy, is a reading for the owner. It is not a
   SeaweedFS-only negative.
3. **The MinIO multipart baseline defect** above, as its own follow-up.
