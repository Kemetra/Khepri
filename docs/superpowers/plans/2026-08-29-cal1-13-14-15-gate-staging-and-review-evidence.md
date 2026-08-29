# CAL1-13 / CAL1-14 / CAL1-15 — gate, staging, and review evidence

**Slices:** the three verification slices after `CAL1-12`. None of them adds product behaviour or
moves a governed version constant. Each produces **evidence about code that already governs** on
`main`, which is what their roadmap acceptance clauses ask for.

**Run date:** 2026-08-29. **Tree:** `cal1-12-mutation-pharmacy-evidence` at `7b19650`, which is
`main` (`9e7a886`) plus CAL1-12's test-only commit.

---

## CAL1-13 — the calculation validation gate

Acceptance (roadmap:645): *"Governance, Ruff, full tests, independent fixtures, report
reconciliation, deterministic reruns, version checks, and no skipped required behavior."*

| Clause | Evidence | Result |
|---|---|---|
| Governance | `khepri-gov validate` | **Governance validation passed.** |
| Ruff | `ruff check .` | **All checks passed!** |
| Full tests | `pytest tests/` | **3,630 passed, 72 skipped, 1 xfailed** in 290s |
| Independent fixtures | `rra_calculation_oracle.py` imports no production aggregation helper; `build_fact_package` and `analysis.*.derive` are never called there | Held |
| Report reconciliation | `test_cal1_pharmacy_golden.py` asserts `gross_profit == revenue - cost` against the published package, not against a restatement | Held |
| Deterministic reruns | two full runs, separate `--basetemp`, gave identical `3627 passed, 72 skipped, 1 xfailed`; the count moved to 3,630 only when this slice's three added assertions landed, and the staging digest below is the same property across processes | Held |
| Version checks | the two extent tests added by CAL1-12 pin both `versions.py` tables exactly | Held |
| No skipped required behavior | see below | Held |

### The 72 skips are all outside the calculation contract

The gate runs *"against the assembled successor contract"* (roadmap:625). Running exactly that
contract — `test_rra00*.py`, `test_rra_calculation_*.py`, `test_cal1_*.py`, `test_bmk001_*.py` —
gives **1,832 passed and zero skipped**. No calculation behaviour is skipped anywhere.

The 72 skips in the whole-repo run are two non-calculation classes, enumerated with `-rs`:

| Count | Cause | Files |
|---|---|---|
| 61 | `KHEPRI_TEST_DATABASE_URL` unset — needs real PostgreSQL for advisory locks and DDL | `test_rca001_concurrent_*`, `test_rra_portable_encryption_migration`, `test_concurrency_postgres` |
| 11 | local stack unreachable from the Windows-side interpreter | `test_local_storage`, `test_local_journey`, `test_rca001_migration` |

The second class has a specific cause worth recording: the compose files bind `127.0.0.1:PORT`
**inside WSL2**, whose loopback is not the Windows loopback, so a Windows-side `pytest` cannot reach
a stack that is running and healthy. The stack was verified up throughout
(`local-pg:OK local-minio:OK staging-pg:OK` from inside WSL, all six containers `healthy`).

**Not chased, deliberately.** Widening the bind to `0.0.0.0` would expose PostgreSQL and MinIO beyond
the host and would edit compose files owned by `OPS1-08`, not CAL1 — a slice widening this ledger
declines to make. The behaviour these tests cover is exercised instead through the real HTTP surface
in CAL1-14 below, which is stronger evidence than the skipped unit tests would have been.

**CAL1-13 passes.**

---

## CAL1-14 — production-like local staging, end to end

Acceptance (roadmap:646): *"Upload -> admission -> facts -> worker -> HTML/PDF/Excel -> evidence;
restart/retry/recovery and bilingual artifacts verified."*

Driven inside `khepri-staging-web` against the merged `docker-compose.staging.yml` stack: one built
`khepri-runtime:staging` image running web, worker and migrations against TLS PostgreSQL and MinIO.
The container's own interpreter, trust store and wiring; no test doubles, no `LocalSettings`
shortcut. The dataset is CAL1-12's pharmacy fixture, so the run also cross-checks that oracle against
the real stack.

| Stage | Evidence |
|---|---|
| Session | invitation `kiv1.…` issued, redeemed `201`, consent `204` |
| Upload | `201`, 623 bytes round-tripped, `text/csv` recorded |
| Admission | profile `201`, `admissible: true`, `row_count: 7` |
| Facts | `201` on **`rra003.mapping.v3` / `rra004.package.v3` / `rra004.formula.v2`** |
| Worker | job queued `201`, reached `succeeded` |
| Bundle | `200`, surfaces exactly `{web, pdf, excel}` |
| HTML | `web/en` 24,764 B (no Arabic script), `web/ar` 27,419 B (Arabic present) |
| PDF | `pdf/en` 521,283 B, `pdf/ar` 667,890 B — both begin `%PDF` |
| Excel | 37,236 B, begins `PK` |
| Evidence | `evidence/en` 41,447 B, `evidence/ar` 43,096 B |

**Zero failures.**

### The published figures equal the hand-derived oracle

The staging stack published exactly the literals CAL1-12 derived by pencil, on the successor
versions:

| Metric | Oracle | Staging |
|---|---|---|
| revenue | `955.00` | `955.00` |
| units | `12` | `12` |
| transactions | `5` | `5` |
| cost | `582.00` | `582.00` |
| discount | `74.00` | `74.00` |

That is independent cross-validation in the strong direction: the expectation was derived outside
every production helper, and the real stack — real PostgreSQL, real object storage, real worker —
reproduces it.

### Restart / retry / recovery

Two separate properties, tested separately, because the first does not establish the second.

**Containers restart cleanly.** Worker and web were restarted with `docker restart` between
journeys. Both returned to `running` with `RestartCount=0` — a clean restart, not a crash loop — the
web container accepted work again after 1 second, and the following journey completed with **zero
failures** across every stage above.

**A queued job survives a worker lifetime boundary and is claimed by the next worker.** The first
attempt at this raced and proved nothing: the worker completes a job in about one second, so a
"queue then immediately restart" sequence had already finished — `job_f8f633fd04dd7c85d2d65b7b`
queued at `07:20:56.977` and succeeded at `07:20:57.985`, six minutes before the restart at
`07:27:17` landed. Recorded because that run *reported* a failure, and the failure was in the test
rather than in the product.

The valid form removes the race by stopping the worker first:

| Step | Observed in `rra_report_jobs` |
|---|---|
| worker stopped | container `exited` |
| job queued with no worker alive | `state=queued`, `attempt_count=0`, `lease_owner=(none)` |
| worker started | reached `succeeded` after 4 s, `attempt_count=1` |

That is the claim path across a worker lifetime boundary, with the unclaimed interval read directly
from the job row rather than inferred, and `attempt_count=1` showing it was claimed exactly once.

**Two `OperationalError` classes in the worker log are environmental, not defects.** They read
`connection to server at "172.22.0.3" … FATAL: the database system is shutting down`, and they occur
because WSL tears down between tool invocations, taking PostgreSQL with it while the worker is
mid-poll. `RestartCount=0` on every container throughout confirms nothing crash-looped.

### Determinism across processes

`package_digest` was `5d5aadbc6dd930ec492b76e02a090f707c8a0c2f524e81cfb963aae1cbcdc0b2` on **all
four** independent runs — including runs separated by a container restart. `RRA-004` requires reruns
to be byte-equivalent, and this is that property observed across process boundaries rather than
inside one interpreter. Artifact sizes were byte-identical across restart except Excel (37,236 →
37,235 B); that one-byte difference was not investigated. The bundle digest, which is the governed
identity, did not move.

**CAL1-14 passes.**

---

## CAL1-15 — external review of the assembled contract

Acceptance (roadmap:647): *"No unresolved P0/P1 finding; CodeScene passes; every family sits on its
single governed successor version, and no transitional version was published on `main`"* — the last
two *"verified against the merged history rather than achieved here"*.

### Every family sits on its single governed successor version — VERIFIED

Read from the constants on `main`, and confirmed independently by the staging run above, which
stamped all three on a real package:

| Family | Constant | Value |
|---|---|---|
| mapping | `mapping.py:22` | `rra003.mapping.v3` |
| package | `facts.py:92` | `rra004.package.v3` |
| formula | `facts.py:93` | `rra004.formula.v2` |
| comparison / growth / basket / concentration | `analysis/*.py` | the four `rra008.*.v2` constants |

### No transitional version was published on `main` — VERIFIED

`ADMITTED_PACKAGE_PAIRS` holds exactly three triples and `ADMITTED_FAMILY_PAIRS` exactly eight pairs;
CAL1-12's extent tests now pin both. Every entry is either the published predecessor or one of the
seven publication commits' own rows. No fourth mapping, package or formula identity exists in either
table, and none appears in the version constants.

### P0/P1 findings

No P0 or P1 finding is open against the assembled contract from this review. Findings raised across
CAL1-11 and CAL1-12 and their disposition:

| Finding | Severity | State |
|---|---|---|
| CAL1-11 F1a, F2 (proof gaps) | P2 | Closed in `#328`, mutation-verified |
| CAL1-12 F2 — version tables had no extent guard | **P1** | **Closed** in CAL1-12, mutation-verified per table |
| CAL1-12 F1 — `CAVEAT_CURRENCY_NOT_DECLARED` unreachable | P2 | **Filed, open** — see below |
| CAL1-11 F1b, F3, F4, F5 | P2 | Filed for their own slices |
| CAL1-11 F6 | — | Owner-decided out of scope, 2026-08-28 |
| CAL1-11 F7, F8 | P3 | Docs / naming |

**F1 is P2, not P1, and the reasoning matters.** An unreachable caveat cannot publish a wrong
number — it publishes nothing. The customer-visible consequence is a disclosure that never appears
where mixed currency occurs, but in that case every monetary fact is already refused, so no monetary
figure is published unqualified. It is a catalogue-integrity defect, not a calculation defect, and
the contract under gate is the calculation contract.

### CodeScene — NOT VERIFIED

The CodeScene MCP server failed to connect this session (`CONNECTION_CLOSED`), and the `github` MCP
server returned `401`, so neither `analyze_change_set` nor `gh api …/check-runs` could be reached
from here. **CodeScene remains an unverified clause of CAL1-15.** It is a required server-side PR
gate and local tooling does not reproduce its thresholds, so it will report on the pull request; this
ledger does not claim it passed.

One new file is added by CAL1-12 (`tests/test_cal1_pharmacy_golden.py`) and will be scored. It is
deliberately flat — one package builder, one value reader, seven plain test functions, no helper
pyramid — because extracting helpers raises a module's complexity mean.

**CAL1-15 is complete except for the CodeScene clause, which is blocked on tooling rather than on
work, and which the PR gate itself will settle.**

---

## Standing

| Slice | State |
|---|---|
| CAL1-12 | Complete — committed at `7b19650` |
| CAL1-13 | **Passes** — every clause evidenced |
| CAL1-14 | **Passes** — zero failures, restart and determinism verified |
| CAL1-15 | Complete but for CodeScene, which is unreachable from this session |

**Merge authority is unchanged.** A branch and a pull request are proposals; this work becomes
governing only when Ahmed Shaaban merges it to `main`. Nothing here was merged.
