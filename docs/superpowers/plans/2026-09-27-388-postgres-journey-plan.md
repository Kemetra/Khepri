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
     `KHEPRI_TEST_DATABASE_URL`, with the `public` schema emptied before and after. Two metadata
     trees key onto each other, so neither `drop_all` can clear them alone.
   - The interleaving instruments:
     - `LockPause` holds the first request just after its `FOR UPDATE` returns (engine
       `after_cursor_execute`);
     - `PausedCall` holds a request before it calls one collaborator;
     - `blocked_on_a_lock` polls `pg_stat_activity` for a backend waiting on a lock.
3. `tests/test_w110_concurrent_postgres.py`, marked `concurrency` and gated like
   `test_concurrency_postgres.py`. `require_concurrency_tests.py` fails CI if any of these skip.

## Cases

| `#388` case | Test | Forced interleaving | Lock proof |
|---|---|---|---|
| Two overlapping deletions | `test_two_overlapping_deletions_end_the_version_once` | 1st held on the version lock; 2nd POSTed | 2nd waits in `pg_stat_activity` |
| Handoff vs deletion (ending in flight) | `test_a_handoff_during_the_ending_does_not_hand_over_ended_content` | deletion held on the version lock; handoff runs | n/a: the handoff takes no lock |
| Handoff vs deletion (handoff read first) | `test_a_late_handoff_does_not_hand_over_ended_content` | handoff held before `bridge.resume`; deletion completes | n/a |
| Two concurrent completions of one run | `test_two_settlements_of_one_run_complete_it_once` | worker settlement held on the version lock; reconcile sweep started | sweep waits in `pg_stat_activity` |

The deletion case asserts:
- byte-identical `303`s;
- one version tombstone and one run tombstone;
- one `completed` and one `already_deleted` event;
- one content-deletion job.

The settlement case asserts:
- the first settlement's `completed_at`;
- each surface bound once;
- one `completed` event.

## Findings recorded, not fixed

- **`#605`.** A handoff that read before the deletion still answers `303` with a cookie after
  it. No content is handed over (the report API refuses, asserted), but `FR-127`'s uniform
  denial fails at the handoff. `test_a_late_handoff_issues_no_cookie_for_an_ended_session` is
  `xfail(strict=True, raises=AssertionError)`.
- **`#606`.** `record_completion`'s re-check under the lock reads the run from the session's
  identity map. The losing settlement passes it and is stopped only by the provenance primary key
  (`IntegrityError`). `test_the_losing_settlement_is_refused_not_faulted` is
  `xfail(strict=True, raises=AssertionError)`.

`#388` stays open until both are fixed. `FR-127`'s concurrent class is evidenced for deletion
overlap, an in-flight ending, and lock-holding. It is not fully evidenced while either `xfail`
stands.

## Mutation

Each lock statement in `rca/workspace/locks.py` had its `with_for_update()` removed in turn:

| Mutant | Result | Why |
|---|---|---|
| `version_for_update` | overlapping deletions, in-flight handoff and settlements go red | the lock-wait proof fails; the in-flight handoff fails because its pause point no longer exists |
| `run_for_update` | survives | both production doors lock the version first, which serialises them before the run lock matters |
| `live_runs_for_update` | survives | same reason |

The surviving two are redundant on the paths driven here. That is recorded, not hidden.

## Status

- [x] Plan and RED tests (`xfail(strict=True, raises=TypeError)`: `journey()` takes no engine)
- [x] Implementation: markers removed; `#605` and `#606` filed and pinned as strict `xfail`s
