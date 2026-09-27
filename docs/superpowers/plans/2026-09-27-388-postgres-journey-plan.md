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
     trees key onto each other), and emptying is refused unless the database name contains
     `test`. CI's is `khepri_test`.
   - The interleaving instruments:
     - `LockPause` holds the first request just after its `FOR UPDATE` returns and records its
       backend pid;
     - `PausedCall` holds a request before one collaborator call;
     - `overlap_on_lock` proves, via `pg_blocking_pids`, that the second request waits on a lock
       held by **that** pid, before the first is released.
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

| `#388` case | Test | Held first | Second, shown waiting on the first's lock |
|---|---|---|---|
| Two overlapping deletions of one version | `test_two_overlapping_deletions_end_the_version_once` | deletion A, version lock | deletion B (route) |
| A handoff simultaneous with a deletion | `test_a_handoff_during_the_ending_does_not_hand_over_ended_content` | deletion, version lock | handoff (takes no lock; must refuse) |
| | `test_a_late_handoff_does_not_hand_over_ended_content` + control `test_a_held_handoff_with_no_deletion_hands_over_the_artifact` | handoff, before `bridge.resume` | deletion completes (no lock claim) |
| **Two concurrent runs against one version** | `TestTwoRunsOverOneVersion::test_a_run_started_while_its_version_is_deleted_is_refused` | deletion, version lock | a second run's `start_run` in `perform` (`add_analysis_run`'s version lock) |
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
checks that the observed failure *is* the filed one (`IntegrityError` for `#606`, the tombstone
guard's `ValueError` for `#610`) before raising `DefectStillPresent`.

- **`#605`.** A handoff that read before the deletion still answers `303` with a non-empty cookie
  after it. The report API refuses with `No report artifact is available for this session.`, so
  no content leaks, but the handoff breaks `FR-127`'s uniform denial.
- **`#606`.** `record_completion`'s re-check under the lock reads the run from the session's
  identity map. A losing second settlement passes it and is stopped only by the provenance
  primary key.
- **`#610`.** The same stale re-check with no backstop: a settlement that waited on a failing
  run's lock **overwrites the failed run as `completed`**. This is durable. The failure door
  against the cascade reaches the update the same way and faults on the tombstone guard.

`#388` stays open until these are fixed. `FR-127`'s concurrent class is not fully evidenced while
any pin stands.

## Mutation

Each lock statement in `rca/workspace/locks.py` was mutated in turn, and the source restored
byte-for-byte after each.

| Mutant | Red | Why red / survivors |
|---|---|---|
| `version_for_update` `with_for_update()` → none | 6 | The overlapping-deletions test fails **at pause arrival** (`HarnessError`), not at the proof, because the statement no longer carries `FOR UPDATE`. The `#606` pin **fails rather than xfails**. |
| `version_for_update` → `skip_locked=True` | 4 | Pause is reached, and **the lock-wait proof itself fails**. This is the evidence the proof can fail. `test_a_run_started_while_its_version_is_deleted_is_refused` survives: the second request still waited on the deletion's backend. The cause was not isolated (likely the insert's foreign-key check). |
| `version_for_update` → `nowait=True` | 5 | The second request raises instead of waiting. |
| `run_for_update` → none | 3 | The failing-run tests. `run_for_update` is load-bearing on `fail_run`'s door, the only lock there. |
| `run_for_update` → `skip_locked=True` | 3 | Same tests. |
| `live_runs_for_update` → none | 3 | The failing-run-vs-cascade tests. |

On the settlement doors, `run_for_update` still survives, because `record_completion` locks the
version first. **That survival means nothing while `#606` stands**: the re-check under the run
lock reads stale state, so no test can show the run lock deciding anything there. Re-run this
mutant after `#606` is fixed.

## Status

- [x] Plan and RED tests (`xfail(strict=True, raises=TypeError)`: `journey()` takes no engine)
- [x] Implementation: markers removed; `#605` and `#606` filed and pinned as strict `xfail`s
- [x] Revision: `#388`'s two-runs case driven (two doors); `#610` filed; harness/defect failures
  separated; handoff positive control; test-database guard; blocker-filtered lock proof
