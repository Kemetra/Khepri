# SCRUM-35 — Who may run the upload repair and the envelope migration under row-level security?

**OWNER DECISION REQUIRED.** This document classifies four operations, finds one blocked, and
recommends how to unblock it. It amends no specification. The amendment it recommends is the
owner's to choose, and it governs only once merged (Constitution II).

**Owner decision, 2026-10-03.** The owner chose **variant B** ("option b", in the Claude Code
session; recorded on #535). The amendment that records it is #652 (`RRA-017` `FR-273`). It governs
only once the owner merges it.

**Snapshot.** `main` at `93f242a7` (#650 merged). Every line reference and claim below is about that
tree. Re-verify them before acting on this document after later merges.

**Sources.** `RCA-005` §Upload identity (`FR-255`–`FR-263`, #644). `RRA-017` `FR-238`, `FR-270`–`FR-272`,
§Exclusions and Open item 7 (#646). #211's cross-amendment finding of 2026-10-02.
`khepri.runtime.upload_identity_repair` (#650). `khepri.rra.envelope_migration` and
`khepri.runtime.envelope_migration` (#620).

---

## Summary

| Operation | Disposition | Authority |
|---|---|---|
| 1. Schema migration (`20261003_0037`, and any later data migration) | **Authorized** | `RRA-017` `FR-270`, migration-owner row |
| 2. The `FR-262` upload-identity repair, after deployment | **Authorized; no gap** | `RCA-005` `FR-262`; `RRA-017` `FR-270`, application row |
| 3. Finding `v1` candidates and counting the `v1` rows left, across every scope, for both halves | **Blocked** | No role may do it under the policies (below) |
| 4. Re-sealing one row, once it is known | **Implementation authorized; deployment gated** | `RCA-005` `FR-263`; `RRA-002`; `KHEPRI-DEC-028` |

Only operation 3 blocks anything. Today it blocks the **report-artifact half**: as `main()`
composes it (the application role), `khepri-envelope-migrate` refuses in any database at or past
`20261002_0036`. It will block the **upload half** (`FR-263`)
the same way. The smallest unblocker is one recipient added to `RRA-017` `FR-271`, with no new grant
and no new policy (variant B below).

---

## 1. Schema migration: authorized

- **Who runs it.** The migration owner (`FR-270`): it owns the tables and runs DDL, it may hold
  `BYPASSRLS`, and no runtime composition holds it. `FR-270` also says "data migrations … must
  cross the policies."
- **What `20261003_0037` enforces about that.**
  - It refuses a runner subject to row security on `rra_uploads`. Such a runner would backfill
    against an empty read.
  - It refuses while `khepri_app`, `khepri_worker` or `khepri_sweep` is connected.
- **No gap.**

## 2. The `FR-262` repair: authorized, and not cross-scope

#211 recorded on 2026-10-02 that "`FR-262`'s `upload_id` repair reads across scopes", and that
`FR-272`'s refusal would not cover a separate command. **That premise does not hold for the design
#650 shipped.**

- **`rra_uploads` is read per scope.** `repair_scope` opens one transaction per scope through
  `scoped_begin`, so `FR-233`'s setting is in place. The application role's `rra_owner_scope`
  policy then admits exactly that scope's uploads. `FR-238` binds reads "run without the unit's
  scope set", and this read is not one.
- **The scopes come from an RCA table.** The list is read from `rca_workspace_dataset_versions`,
  which carries no policy (Open item 1). A policy cannot empty that read.
- **The write is the one `FR-262` admits.** It is a Core `UPDATE` of `upload_id` from null. The ORM
  guard refuses every other write (`FR-256`).
- **No new role, policy or grant.** The application row of `FR-270` covers it: "read and write
  covered tables … with a scope set."

**One dependency to carry forward.** If Open item 1 ever puts RCA tables under a policy, the scope
list becomes a read `FR-238` binds. It would then need the same treatment `FR-238` gives
`PipelineRecorder._workspace_of`.

**Who runs it, and when.**
- **During the upgrade:** nobody needs to. `0037` refuses to start while a runtime role is
  connected, and `EXCLUSIVE`-locks both tables while it runs.
- **After the upgrade:** a null `upload_id` on a live upload can only come from an old build still
  writing. `FR-263`(b)'s deployment gate is what rules that out.
- **Inside the re-seal:** `FR-263`(c) runs the repair under each upload's session lock.

So the repair needs no standalone caller. Its only required caller is the re-seal slice (see the
handoff, item 1).

## 3. Cross-scope candidates and counts: blocked

**What the operation is.** Both halves share one shape:
1. List every `v1` row across all scopes. In code today this is `_candidates`, with
   `WHERE envelope_version = 1`.
2. Re-seal each row in its own transaction, with that row's scope set and its session locked.
3. Count the `v1` rows left (`_legacy_count`). A count of zero in both tables is `KHEPRI-DEC-028`'s
   condition for retiring `v1`.

Steps 1 and 3 read across scopes. Step 2 does not.

**Why no role may run steps 1 and 3 today.** Every clause names the gap:

| Role | Why it cannot | Clause |
|---|---|---|
| application, worker | They hold no cross-scope policy. Under the policies an unscoped read returns nothing, and an empty count reads as "verified". | `FR-270`; `FR-238`; `FR-272`: "it **refuses to run** … whenever its connection is subject to the RRA policies" |
| sweep | It reads only `FR-271`'s columns, and its engine goes to "these four components and no others". | `FR-270`, sweep row; `FR-271` |
| migration owner | No runtime composition may hold it, and it has no object-store credentials. Step 2 needs both the database and the store. | `FR-270`, migration-owner row; Open item 7, option 2 |
| any role | Cross-scope reads by `khepri-envelope-migrate` are excluded outright. | §Exclusions: "any cross-scope read by `khepri-envelope-migrate` (Open item 7)" |

**Why Open item 7's third option ("run before the policies are enabled") cannot serve the upload
half.** `FR-263` opens the re-seal only once `20261003_0037` is at head. `0037` follows
`20261002_0036`, which enables the policies. So the upload re-seal can never run in a database
without policies. The option can still serve the artifact half, but only in an environment not yet
upgraded past `0035`.

### The minimum unblocker: two variants of Open item 7, option 1

Option 1 is "a further sweep-style component holding a permissive `SELECT` policy on the `v1`
columns of the two tables only, with each reseal run scoped to the row's `owner_id`." The tree
admits a narrower form of it.

**Variant A, as Open item 7 words it.**
- **What changes:** a sweep-only permissive `SELECT` policy on `rra_report_artifacts`, plus column
  grants:
  - `rra_report_artifacts`: `job_id`, `artifact_kind`, `owner_id`, `session_id`,
    `envelope_version`;
  - `rra_uploads`: `envelope_version`, added to the sweep's existing grant.
- **What the sweep then does:** lists `v1` rows directly.
- **New reach for a leaked sweep credential:** every artifact's `envelope_version` and identifying
  keys, and every upload's `envelope_version`.

**Variant B, sessions first. Recommended.**
- **What changes:** no new grant and no new policy. One new recipient joins `FR-271`'s list, an
  envelope-candidate lister.
- **What the lister does:** it reads `rra_beta_sessions (session_id, owner_id)` on the sweep engine.
  The sweep already reads that table with `USING (true)` (`20261002_0036`, `SWEEP_COLUMNS`).
- **Per session:** on the scoped engine, with that `owner_id` set, it reads and counts the `v1` rows
  of that session's artifacts and upload.
- **Why it is complete:** both tables reference the session with a composite, `RESTRICT` foreign key
  onto `rra_beta_sessions (owner_id, session_id)`. These are `fk_report_artifact_session_scope` and
  `fk_upload_session_scope`. So every `v1` row belongs to a session the lister returns.
- **Why each read is trustworthy:** each runs with its scope set, which is the exact shape `FR-271`
  already uses for expiry (listing on the sweep engine, work on the scoped engine).
- **New reach for a leaked sweep credential:** none. It already reads that session list.

**What either variant also changes in `RRA-017`.**
- **`FR-272`:** instead of refusing whenever its connection is under the policies, the command
  refuses unless its lister runs as the sweep role. The scoped work and counts run as the
  application role. A lister handed the wrong engine would list nothing, and the rule stays
  fail-closed against exactly that.
- **§Exclusions:** the line on cross-scope reads by `khepri-envelope-migrate` narrows to the
  variant's reads.
- **Verification 7:** the expected recipient set gains the lister.
- **Verification 18:** gains the variant's case.
- **Numbering:** starts at `FR-273`, the first number free after `FR-272`.

**Recommendation: variant B.** It unblocks both halves with no change to any role's reach. That is
also what this ticket's exclusions ask for ("no widening of runtime grants"). The cost is one scoped
transaction per session.

### The all-scope count `v1` retirement needs: existing authority, either way

`KHEPRI-DEC-028` retires `v1` once both halves have verified that none remains.

Whichever variant the owner picks, the retirement slice can ship its own Alembic revision, run by the
migration owner, that aborts while any `rra_report_artifacts` or `rra_uploads` row has
`envelope_version = 1`. `FR-270` already lets data migrations cross the policies. That revision is
the trustworthy all-scope backstop: the code that stops reading `v1` cannot reach a database that
still holds a `v1` row. It needs no amendment.

## 4. Re-sealing one row: implementation authorized, deployment gated

- **Implementation.** `FR-263` lets the upload re-seal slice open once `FR-255`–`FR-262` are merged
  (done, #650) and `0037` is at head in every environment that slice will run against.
  - It rewrites `rra_uploads` rows and their objects under `RRA-002` and `KHEPRI-DEC-028`.
  - Per row it runs as the application role with the scope set and the session locked, which
    `FR-270`'s application row admits.
  - It inherits operation 3's blocker for its candidate list and its final count.
- **Deployment.** `FR-263`(b) requires a deployment gate recorded per environment before the slice
  runs there. It is "recorded … as a deployment fact, not assumed from the revision being at head."

## Handoff to the upload re-seal slice

1. **The repair must run inside the upload's lock.** `repair_scope` opens its own transaction.
   `FR-263`(c) runs the repair and the null-version check *inside* the transaction that holds the
   session lock. The slice needs an in-transaction entry point to the same statement, such as a
   public form of `_repair_in(database, owner_id)`.
2. **Rewrite in place.** Keep the same row, `upload_id` and `object_key` (`FR-263`(a)). Never delete
   and re-insert an upload row: `fk_rca_workspace_version_upload` would clear the version's
   `upload_id` (`FR-256`).
3. **Crash ordering mirrors the artifact half.** A crash after the object write and before the row
   commit leaves a `v2` object under a `v1` row. That upload is unreadable until the next run adopts
   it (`ResealingStore.reseal` reports `rewritten=False`).
4. **Safe restart.** Each upload is its own transaction, so a rerun picks up from where the last one
   stopped:
   - a crash mid-run loses nothing;
   - an upload refused under `FR-263`(c) stays `v1` and is counted;
   - the run reports success only when both counts are zero.
5. **Forward-only.** Once any upload is re-sealed, `0037`'s downgrade aborts. There is no rollback
   below `0037` after the first re-seal. Recovery is forward: rerun the command.
6. **The deployment gate has no recording mechanism.** Nothing in the repository records an
   `FR-263`(b) gate per environment. Defining that record, and having the command refuse without
   it, is the slice's first deliverable.
7. **Implementation authority is not deployment authority.** Merging the slice authorizes the code.
   Running it in an environment needs that environment's gate record. Retiring `v1` needs both
   halves at zero, then the retirement revision.

## Environment inventory, at this snapshot

| Environment | Holds data? | Can hold `v1` rows? | Notes |
|---|---|---|---|
| CI | Ephemeral, rebuilt per run | No persisted rows | — |
| Hosted (OPS1) | Not provisioned | — | Once provisioned, it starts at head, where every write is `v2`. It still needs the gate record and a zero count. |
| Local compose (`docker-compose.local.yml`) | The owner's volume | **Unknown** | Not inspected. |
| Staging compose (`docker-compose.staging.yml`) | The owner's volume | **Unknown** | Not inspected. |

**How to count, per local volume, without changing anything.** As the migration owner (`khepri`):

```sql
SELECT 'artifacts', count(*) FROM rra_report_artifacts WHERE envelope_version = 1
UNION ALL
SELECT 'uploads', count(*) FROM rra_uploads WHERE envelope_version = 1;
```

The table owner crosses the policies through `BYPASSRLS`, so this count is trustworthy.

- **Zero in a volume:** there is nothing to migrate there.
- **Non-zero:** the owner chooses between migrating once the unblocker lands, and resetting the
  local data. Resetting is a decision about the owner's own test data, not a technical step.

## Owner decision

**Question.** How should `RRA-017` Open item 7 be resolved?

**Recommendation.** Variant B: add one recipient to `FR-271` and rewrite `FR-272` to refuse unless
the lister runs as the sweep role. No new grant, no new policy.

**The alternatives.**
- **Variant A:** a new sweep policy and grants on `rra_report_artifacts`, and `envelope_version` on
  `rra_uploads`.
- **Leave Open item 7 open:** the artifact half stays refused in every environment past `0035`, and
  the upload re-seal cannot run anywhere.

Once the owner chooses, the amendment is one bounded PR to `RRA-017`, numbered from `FR-273`. Its
implementation then lands with the upload re-seal slice or before it.
