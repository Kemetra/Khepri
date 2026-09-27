# #388: a PostgreSQL-backed `journey()` for `FR-127`'s concurrent case class

Test infrastructure under `RCA-005` `FR-127` (`W1-10`). The owner decision on `#388` (2026-09-24)
settles the shape: add a minimal PostgreSQL-backed `journey()`, prove the concurrent lifecycle
cases over the real route and composition path, and do not prove concurrency through SQLite. No
product code changes in this slice.

## Shape

1. `tests/w104_support.world(engine=None)` and `tests/w104b_support.journey(engine=None)`. With no
   argument they build today's SQLite `StaticPool` engine (`sqlite_engine()`), so no W1 module
   changes. `#388`'s own observation is the RED: `journey(engine)` is not a signature they accept.
2. `tests/w110_postgres_support.py`:
   - `postgres_journey()` builds the same composition over a pooled engine on
     `KHEPRI_TEST_DATABASE_URL`. The `public` schema is emptied before and after (two metadata
     trees key onto each other), and emptying is refused unless `test` is a whole `_`-separated token
     of the database name. CI's is `khepri_test`.
   - The interleaving instruments:
     - `LockPause` holds the first request just after its `FOR UPDATE` returns and records its
       backend pid;
     - `PausedCall` holds a request before one collaborator call;
     - `overlap_on_lock` proves, via `pg_blocking_pids`, that the second request waits on a lock
       held by **that** pid, in a `FOR UPDATE` on the named table, before the first is released.
   - Three failure kinds, kept apart so a pinning `xfail` absorbs only its defect:
     - `HarnessError(RuntimeError)`: a pause never reached, a request never finished, a
       non-test database;
     - a plain `AssertionError`: a property, including the lock-wait proof;
     - `DefectStillPresent(AssertionError)`: the only exception a pinning `xfail(raises=...)`
       names.
3. `tests/test_w110_concurrent_postgres.py` covers deletions and handoffs.
   `tests/test_w110_concurrent_runs_postgres.py` covers runs. Both are marked `concurrency`, so
   `require_concurrency_tests.py` fails CI on a skip.

## `#388`'s three cases, and what drives each

"Waiting" means that `pg_blocking_pids` names the held backend, **and** that the waiting backend's
`pg_stat_activity.query` is a `FOR UPDATE` on the named table. A foreign key's `FOR KEY SHARE` wait
on an insert therefore cannot satisfy the proof (the trap `test_w102_workspace_lock_contention.py`
records).

| `#388` case | Test | Held first | Second, shown waiting on the first's lock |
|---|---|---|---|
| Two overlapping deletions of one version | `test_two_overlapping_deletions_end_the_version_once` | deletion A, version lock | deletion B (route) |
| A handoff simultaneous with a deletion | `test_a_handoff_during_the_ending_does_not_hand_over_ended_content` | deletion, version lock | handoff (takes no lock; must refuse) |
| | `test_a_late_handoff_does_not_hand_over_ended_content` + control `test_a_held_handoff_with_no_deletion_hands_over_the_artifact` | handoff, before `bridge.resume` | deletion completes (no lock claim) |
| **Two concurrent runs against one version** | `TestTwoRunsOverOneVersion::test_two_runs_started_over_one_version_serialise_on_its_lock` | `start_run`, version lock | a second `start_run`; both land as live runs |
| | `TestTwoRunsOverOneVersion::test_a_run_started_while_its_version_is_deleted_is_refused` | deletion, version lock | `start_run` (`add_analysis_run`): must end in `WorkspaceRefused`, with no `active` run row under the version, read raw |
| | `TestTwoRunsOverOneVersion::test_a_deletion_arriving_while_a_run_is_added_cascades_to_it` | `start_run`, version lock | deletion |
| | `TestARunFailingWhileEnded::test_a_deletion_waits_for_a_failing_run_and_records_its_failure` | `abandoned` → `fail_run` → `complete_analysis_run`, run lock | deletion's cascade (`live_runs_for_update`) |
| | `TestARunFailingWhileEnded::test_a_run_the_cascade_holds_is_not_failed_under_it` | deletion's cascade, run lock | `fail_run` |
| | `TestARunFailingWhileEnded::test_a_settlement_waits_for_a_failing_run_and_does_not_complete_it` (**xfail, `#610`**) | `fail_run`, run lock | settlement (`record_completion`) |

**Not one of `#388`'s cases, and labelled so.** `TestOneRunTwoSettlingDoors` covers one run
completed at once by the worker's settlement and the reconcile sweep. It keeps its tests
(durable state; the `#606` pin), but does not stand in for the two-runs case.

No door named by `#388` was left undriven.

## Findings recorded, not fixed

Each finding is pinned as `xfail(strict=True, raises=DefectStillPresent)`. A pinning test first
asserts that the observed failure *is* the filed one before raising `DefectStillPresent`:

| Pin | Observed failure it checks for |
|---|---|
| `#605` | `303` with a non-empty session cookie |
| `#606` | `IntegrityError` |
| `#610` | the run's state is `completed` |
| `#611` | the tombstone guard's `ValueError` |

- **`#605`.** A handoff that read before the deletion still answers `303` with a cookie after it.
  The report API refuses with `No report artifact is available for this session.`, so no content
  leaks, but the handoff breaks `FR-127`'s uniform denial.
- **`#606`.** `record_completion`'s re-check under the lock reads the run from the session's
  identity map. A losing second settlement passes it and is stopped only by the provenance
  primary key.
- **`#610`.** The same stale re-check with no backstop: a settlement that waited on a failing
  run's lock **overwrites the failed run as `completed`**. This is durable.
- **`#611`.** `complete_analysis_run` guards with `_visible_in` instead of `_live_in`. So a failure
  that waited on the deletion cascade reaches the update and faults on the tombstone guard
  instead of being refused. It was first attributed to `#610`, and it is not the same root.

Mechanism checks, on scratch copies of `src` (the worktree `src` untouched):

| Change | `#606` and `#610` pins | `#611` pin |
|---|---|---|
| `populate_existing=True` on the three lock statements | flip (strict pins fail) | still xfails |
| `complete_analysis_run` guarding with `_live_in` | — | flips |

`#388` stays open until these are fixed. `FR-127`'s concurrent class is not fully evidenced while
any pin stands.

## Mutation

Each lock statement in `rca/workspace/locks.py` was mutated in turn, and the source restored
byte-for-byte after each. Counts are for the final tests: 10 passing, 4 pinned.

| Mutant | Red | Notes |
|---|---|---|
| `version_for_update` → no `FOR UPDATE` | 7 | Mostly **at pause arrival** (`HarnessError`), not at the proof, because the statement no longer carries `FOR UPDATE`. The `#606` pin **fails rather than xfails**. |
| `version_for_update` → `skip_locked=True` | 6 | The pause is reached and **the lock-wait proof itself fails**: the evidence the proof can fail. The earlier survivor (`..._is_deleted_is_refused`) is red now that the proof names the statement. |
| `version_for_update` → `nowait=True` | 6 | The second request raises instead of waiting. |
| `run_for_update` → no `FOR UPDATE` | 4 | The failing-run tests. It is load-bearing on `fail_run`'s door, the only lock there. |
| `live_runs_for_update` → no `FOR UPDATE` | 3 | The failing-run-vs-cascade tests. |

The next mutant was applied in a scratch `src` copy. `add_analysis_run` reads its parent with a
plain `SELECT`, which is the defect `test_a_run_started_while_its_version_is_deleted_is_refused`
guards. **That test fails at the statement-filtered lock-wait proof.** Before this revision the
test passed on that mutant: the start waited on the foreign key's `FOR KEY SHARE`, and the old
assertions (a `None` accepted as refused, a read through the revocation filter) could not see the
live run it committed under a tombstoned version.

On the settlement doors, `run_for_update` still survives because `record_completion` locks the
version first. **That survival means nothing while `#606` stands**: the re-check under the run
lock reads stale state, so no test can show the run lock deciding anything there. Re-run this
mutant after `#606` is fixed.

## Status

- [x] Plan and RED tests (`xfail(strict=True, raises=TypeError)`: `journey()` takes no engine)
- [x] Implementation: markers removed; `#605` and `#606` filed and pinned as strict `xfail`s
- [x] Revision: `#388`'s two-runs case driven (two doors); `#610` filed; harness/defect failures
  separated; handoff positive control; test-database guard; blocker-filtered lock proof
- [x] Final review:
  - two `start_run`s overlapping on the version lock;
  - statement-filtered proof;
  - raw-row check and a strict refusal type for the start under deletion;
  - `#611` split out of `#610`;
  - each pin checks its observed failure first;
  - token-matched test-database guard.
