# #535: rewrite stored `v1` report artifacts as envelope `v2`

This is the report-artifact half of the `v1` migration that the `KHEPRI-DEC-028` amendment (#613)
requires. The owner split the migration on 2026-09-28 (#535). Uploads are out of this slice. Their
ciphertext digest is recorded as an identity in `DatasetVersion.upload_ciphertext_digest`, which
`RCA-005` `FR-112` fixes. The owner chose to give versions a stable upload identity first, and that
needs an `RCA-005` amendment before any code.

## Authority

- `KHEPRI-DEC-028` §envelope clause, amended in #613: "Format `v1` ... stays readable until a
  migration slice rewrites every `v1` object as `v2` and verifies that none remains." This slice is
  that migration, for report artifacts.
- `RRA-002` (active): stored content is encrypted at rest in isolated object namespaces. This
  slice re-encrypts content that already exists. It adds no data, no field, no column and no use.
- Owner decisions on #535: 2026-09-27 (a)–(c), and 2026-09-28 (the split).

**What this slice does not do.**
- It does not remove `1` from `READABLE_ENVELOPE_VERSIONS`. Under the 2026-09-27 ruling (b), that
  follows only once both halves have run in every environment holding data and have verified that
  no `v1` rows remain.
- It does not touch uploads.
- It does not relax `_EXISTING_OBJECT_VERSIONS`.

## Why artifacts can be rewritten and uploads cannot

A re-seal produces a new ciphertext, and so a new ciphertext digest. Only uploads carry that digest
into another record. An artifact's workspace binding (`ArtifactBindingRow.artifact_digest`) is the
**plaintext** `sha256_hex` (`workspace_recording.py`: `artifact_digest=stored.sha256_hex`).
Nothing outside `rra_report_artifacts` reads an artifact's `ciphertext_sha256_hex`.

## Protocol, one artifact row per transaction

1. **Lock the session, then the row.** `session_scope_for_update_statement` is the lock that
   `SqlDeletionRepository.begin` takes before it sets `deletion_requested_at`. Holding it across
   the rewrite means a deletion cannot begin mid-rewrite, and a deletion that already began is
   seen. The session is locked before the row, the same order publication uses, so the two cannot
   deadlock.
2. **Skip a session whose deletion was requested or completed.** Its content is on the way out,
   and rewriting it would race the deletion's object removal. The row stays `v1` until the
   deletion completes and removes it. It is counted as `deferred`, not migrated.
3. **Refuse a key outside the row's own namespace**, using `object_in_scope`, the reader rule from
   #609. Counted as `refused`. Nothing is written.
4. **`S3EncryptedObjectStore.reseal`** fetches the object and branches on the version it carries:
   - **`v1`:** open it under the row's two digests, re-seal the plaintext as `v2` bound to the
     same key, and overwrite in place. The write is unconditional, since `put` always sends
     `IfNoneMatch`. No other writer targets a key that already has a committed row: publication
     proves an existing object and never overwrites one, and a new row never attaches to a `v1`
     object.
   - **`v2` (adoption):** a previous run wrote the object and crashed before its row committed.
     The object is proved by GCM under this key's AAD and by the row's plaintext digest, then
     recorded without being rewritten.
   - **Anything else:** refused.
5. **Update the row** to `v2` with the new ciphertext digest, and commit.

**Crash windows, all of which fail closed.**
- Between the overwrite and the commit, the row still names `v1` and the old digest. A read of
  that one artifact is refused (`ArtifactUnavailable`) until the next run adopts the object.
- A store write that is not confirmed raises, and the object is **not** deleted. `put`'s delete-on-
  failure is right for a new object and wrong here, because an overwrite has no other copy. S3
  writes are atomic, so the key holds either the old envelope or the new one, and the next run
  handles both.

## Entry point

`khepri-envelope-migrate` → `khepri.runtime.envelope_migration:main`. It lives in the wheel for the
reason `pyproject.toml` gives for `khepri-retention-sweep`. It builds through `build_stack` and
prints one content-free JSON line with these counts: `resealed`, `adopted`, `deferred`, `refused`,
`failed`, `artifacts_remaining`, and `uploads_not_migrated`. The last is informational, so an
operator can see the half this slice does not cover. The command **exits non-zero while any `v1`
artifact row remains or any row failed**, so "completed and verified" is the exit status, not a
reading of the output.

Nothing schedules it, as with the retention sweep. Running it is an operational act.

## Tests: `tests/test_i535_artifact_envelope_migration.py`

The store is the real `S3EncryptedObjectStore` over a dict-backed client, and the rows come from a
real publication. `v1` objects are forged from the `v1` layout (no AAD), the way
`test_i535_envelope_aad` pins the format.

Store:
- `reseal` rewrites a `v1` object as `v2` bound to its key. The plaintext is unchanged, and the
  object refuses to open under another key.
- `reseal` adopts an existing `v2` object without writing.
- `reseal` refuses, and writes nothing, when a `v1` object does not match the row's plaintext
  digest.
- `reseal` refuses a row that does not record `v1`.
- `reseal` refuses to adopt a `v2` object sealed for another key.
- An overwrite the store does not confirm raises and deletes nothing.

Migration:
- Every `v1` row of a publication becomes `v2`, each recorded digest matches the stored body, and
  the publisher's verified read returns the original bytes. Counts are exact, and none remain.
- A second run changes nothing and writes nothing.
- Adoption after a crash between the overwrite and the commit.
- A session whose deletion was requested is deferred and left untouched.
- A key outside its session is refused and left untouched.
- One failing object does not stop the others.
- `v2` rows are not selected.

Entry point: the counts line, exit `1` while `v1` artifacts remain, exit `0` when none remain, and
`uploads_not_migrated` counted. `test_w107b_wheel_entry_point` gains the new script, so it is
resolved against the built wheel.

PostgreSQL (`concurrency` marker, 10 repeats):
- A deletion that begins while a rewrite holds the session lock waits for it.
- A deletion that began first makes the rewrite defer.

**Mutation check after GREEN**, with each mutant restored by diff:
- the session lock replaced by a plain `SELECT`;
- the deletion check removed;
- the scope check removed;
- adoption without the plaintext digest;
- `reseal` skipping the write;
- the row update dropping the new digest;
- `remaining` counted from the wrong version;
- the exit status ignoring `remaining`.
