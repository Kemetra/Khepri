# G2-01 — Inventory of retained data classes and their purposes

**Roadmap task `G2-01`**, the input to `G2-02` (owner choices), `G2-03` (`[DEC-RETENTION]`) and
`G3-01` (`[RCA-WORKSPACE]`), both drafted in `docs/platform/proposed-governance/`. **Measured on
`main` at `457f276`, 2026-09-03**, from code — every row cites where the class is defined and what
ends it. Where `KHEPRI-DEC-015` states a horizon and the code does not enforce it, the row says so.

**Two findings come first, because the retention decision has to be made knowing them.**

---

## Findings

### F-1 — No retention horizon is enforced on the deployed path

Every retention sweeper in the repository — `AccountRetentionSweeper`, `MembershipEventSweeper`,
`SessionRetentionSweeper`, `InvitationRetentionSweeper`, `RetentionPasses` — has exactly one caller,
`khepri.local.cli:74`'s manual `sweep` subcommand, and `pyproject.toml:78` excludes `src/khepri/local`
from the wheel. `src/khepri/rca/invitation_retention.py:40` records it in code as
`INVITATION_HORIZON_IS_UNENFORCED = True`, and its comment at `:28-39` says the gap is shared by every
sweeper. There is no scheduler. The `rra_beta_sessions.content_expires_at` clock, the
`rra_uploads.expires_at` and `rra_report_artifacts.expires_at` clocks, and the `rra_report_deliveries`
expiry (which even has an index, `ix_delivery_expiry`, with no reader) all run and nothing acts on
them. The one sweep that *does* run on the deployed path is the worker's **lease** recovery
(`runtime/worker.py:78-91`), which is job recovery, not retention.

**Consequence for `G2`:** the seven-day rule `RRA-001`/`RRA-002` state is, in the shipped image, a
rule about the cookie and about what the API refuses to serve — not about what the store holds.
Every horizon `[DEC-RETENTION]` fixes needs `W1-07`'s sweep *and a caller on the deployed path* before
it is true. **This is also an M2 fact**: the "automatic seven-day expiry" `RRA-002` requires is
unenforced today.

### F-2 — Deletion deletes objects; two Postgres documents holding customer-derived content are never deleted and never expire

`DELETE /api/v1/beta/content` (`rra/api.py:415-445`) runs `DeletionService.delete_session_content`,
which aborts multipart uploads and deletes the object-store prefix
`owners/{owner_id}/sessions/{session_id}/` (`deletion.py:219-223`, `:257`), records evidence, and marks
`rra_beta_sessions.content_deleted_at`. **It deletes no Postgres row**, and every RRA foreign key is
`ondelete="RESTRICT"`. Two tables carry customer-derived content in plaintext JSON with **no expiry
column and no deleter**:

- `rra_dataset_profiles.document` (`persistence.py:146-181`): per column, `safe_label` is the
  customer's sanitized, truncated column header (`profiling.py:709-723`) and `minimum`/`maximum` are
  actual customer values, suppressed only when the personal-data heuristic fires
  (`profiling.py:339-341`).
- `rra_fact_packages.document` (`persistence.py:184-234`): derived figures plus customer-derived
  category labels via `safe_value_label` (`facts.py:2015-2018`), redacted only when `is_personal_value`
  matches.

The suppression is a heuristic gate, not a structural one: a commercially sensitive non-personal value
— a product name, a supplier, a branch — is retained in plaintext with no end. **`RRA-002` requires
deletion "across input, temporary materializations, facts, narrative, exports, and orphaned objects";
facts are not deleted.** The catalog routes rebuild a bundle from this retained package
(`KHEPRI-DEC-032`), which is why it is retained at all; that reading did not consider that the
package outlives the session's deletion.

**Consequence for `G2`:** the retention matrix must give the fact package and the profile an explicit
row — the draft does — and the M2 defect stands regardless of M3: a session's derived content should
end when its content does. Filed here for the owner as an `RRA-002` reading, not fixed by this task.

---

## Inventory

Two scopes coexist. **RRA rows** are keyed by the opaque `owner_id` plus a `session_id` and belong to
the one-time beta journey. **RCA rows** are keyed by `account_id` or `organization_id`, and
`rca_isolation_scopes` (`rca/persistence.py:352`) is the single join from an organization to its
opaque RRA `owner_id` (`RCA-001` `FR-031`–`FR-035`). A workspace row under `[DEC-RETENTION]` would be
an RRA-shaped row keyed by organization scope rather than session.

Migrations `0001`–`0020` (head `20260822_0020`) create exactly the 22 tables below; ORM and
migrations reconcile with no orphan either way.

### Postgres — RRA analysis pipeline

| Table | Defined | Holds | Content class | Ends when | Ended by | At-rest encryption |
|---|---|---|---|---|---|---|
| `rra_invitations` | `rra/persistence.py:44` | beta invitation salt + digest | secret digest | `expires_at` `:50` | **nothing** — no sweeper for beta invitations (the RCA one has one) | digest |
| `rra_beta_sessions` | `:58` | identifiers, consent version and instant, `content_expires_at` `:81`, `content_deleted_at` `:89` | identifiers | expiry clock | **nothing sweeps**; deletion marks `content_deleted_at` | n/a |
| `rra_uploads` | `:92` | object key, plaintext and ciphertext SHA-256, size, media type | **pointer to raw retail file** | `expires_at` `:136` | object deleted by `deletion.py:219-223`; row remains | AES-256-GCM envelope `:108`, `:141-143` |
| `rra_dataset_profiles` | `:146` | `document` JSON: column headers (sanitized), min/max values, admission outcome | **customer-derived content** (F-2) | **never** | **nothing** | none |
| `rra_fact_packages` | `:184` | `document` JSON: facts, series, comparisons, refusals, versions, category labels | **derived figures + customer-derived labels** (F-2) | **never** | **nothing** | none |
| `rra_deletion_jobs` | `:237` | state, attempts, retry | operational | never | nothing — evidence | n/a |
| `rra_deletion_evidence` | `:281` | `location_digest`, `content_digest`, outcome, attempt | **deletion evidence**, content-free | never | nothing — permanent by design | digests |
| `rra_report_jobs` | `job_persistence.py:49` | state, lease, attempts, idempotency digest | operational | never | nothing | n/a |
| `rra_report_job_attempts` | `:132` | attempt history | operational | never | nothing | n/a |
| `rra_report_deliveries` | `delivery_persistence.py:73` | identifiers, `narrative_state`, `expires_at` | identifiers | `expires_at` (indexed) | **no reader of the index** | n/a |
| `rra_report_delivery_surfaces` | `:113` | per-surface digest evidence | content-free | never | nothing | digest |
| `rra_report_artifacts` | `artifact_persistence.py:46` | object key, digests, fixed filename constant (`:56-69`) | **pointer to rendered report** | `expires_at` `:119` | object deleted by prefix; row remains | AES-256-GCM `:76-91` |
| `rra_operational_events` | `telemetry_persistence.py:26` | enumerated stage, transition, integers, **banded** size (`:66-68`) | operational, content-free | never | nothing | n/a |

### Postgres — RCA commercial identity (lifecycle stated by `KHEPRI-DEC-015` §2)

| Table | Defined | Holds | Content class | `DEC-015` horizon | Ended by | Enforced today |
|---|---|---|---|---|---|---|
| `rca_accounts` | `rca/persistence.py:66` | email `:79`, scrypt verifier `:87-91`, `disabled_at` | **PII** | 24 months after disablement → tombstone | `AccountRetentionSweeper` (`lifecycle.py:193-223`; tombstone at `accounts.py:208`: email and verifier → NULL, row kept) | **no** (F-1) |
| `rca_organizations` | `:94` | customer-supplied name | commercial identifier | while the organization exists; no deletion (§6) | nothing | — |
| `rca_memberships` | `:102` | account, organization, role | identifiers | as membership; attribution dropped by design `:134-136` | revocation | — |
| `rca_membership_events` | `:139` | opaque ids, role transition; no FK by design `:140-154` | audit, content-free | 12 months | `MembershipEventSweeper` (`lifecycle.py:259-268`) | **no** (F-1) |
| `rca_sessions` | `:172` | PK is the token hash `:176-183`; `expires_at`, `revoked_at` | hashed bearer | until expiry or revocation | `SessionRetentionSweeper`, 30 days (`session_retention.py:36,78`) | **no** (F-1); revocation itself is immediate |
| `rca_external_identities` | `:208` | provider + subject → account; no email, no token `:216-219` | identifiers | as account | nothing | — |
| `rca_invitations` | `:260` | canonical target email `:333`, bearer verifier `:337-341`, `expires_at` `:342` | **PII + secret digest** | until accepted, expired or revoked | `InvitationRetentionSweeper` (`invitation_retention.py:85-99`) | **no** (F-1, recorded in code at `:40`) |
| `rca_isolation_scopes` | `:352` | `organization_id → owner_id` | the RCA↔RRA join | organization lifetime (`FR-035`) | nothing | — |
| `rca_recovery_security_events` | `recovery_security_persistence.py:19` | hashed event key, account, instant | audit, content-free | 12 months | `RetentionPasses` | **no** (F-1) |

### Object store — one S3-compatible bucket (`storage.py:103-117`; name injected, not in `src/`)

| Key namespace | Written by | Holds | Encryption | Ended by |
|---|---|---|---|---|
| `owners/{owner_id}/sessions/{session_id}/inputs/{upload_id}` | `intake.py:212-214` | **raw retail CSV/XLSX** | AES-256-GCM envelope, per-object data key wrapped by a master key (`envelope.py:111-138`); envelope carries no filename, label or plaintext digest (`:30-32`) | `delete_prefix` on the session prefix (`storage.py:213-233`), which verifies emptiness after |
| `owners/{owner_id}/sessions/{session_id}/…` artifacts | `artifact_persistence.py`, `report_artifacts.py` | rendered web, evidence, PDF, Excel | same | same |

Isolation is structural in the key: `owner_id` and `session_id` are path segments, so one prefix
delete ends exactly one session's objects. **A workspace changes the second segment** — from a
session to a dataset version or run under the organization's `owner_id` — and nothing about the first.

### Cookies

| Cookie | Defined | Value | Attributes | Lifetime |
|---|---|---|---|---|
| `khepri_beta_session` | `rra/session_cookie.py:27` | raw beta `session_id` | Secure, HttpOnly, SameSite=Strict, path `/api/v1/beta` (`api.py:438-444`) | `content_expires_at` |
| `khepri_session` | `rca/session_cookie.py:33` | session token; only its hash is stored | Secure, HttpOnly, SameSite=Strict, path `/` (`:65-69`) | `max_age` from the session horizon (`:76-85`) |

### Telemetry and logs

`rra_operational_events` is the only telemetry sink; CHECK constraints admit enumerated stages and
transitions, integers, and a banded dataset size (`le_1_mib` … `le_50_mib`). No filename, column name
or value can enter it. Sweep reports are counts only (`invitation_retention.py:43-51`). No product
analytics exists; `W1-11` and `R8-08` both wait on a `KHEPRI-DEC-015` §3 amendment.

### Not retained

- **Journey state** — recomputed per request from existing rows (`journey/state.py:100-132`); no
  table, no cookie; the snapshot is booleans and enums.
- **`ReportBundle`** — never stored; reconstructed from the fact package (`KHEPRI-DEC-032`).
- **Benchmark rows** — synthetic, seeded (`benchmark_rows.py:117-236`).
- **Local workbooks** — `./.local-workbooks` under `khepri.local`, excluded from the wheel.

---

## Purposes, by roadmap class

The roadmap names nine classes. Each maps to the rows above:

| Roadmap class | Rows | Purpose today | Purpose in a workspace |
|---|---|---|---|
| Upload | `rra_uploads` + `inputs/` object | admission and profiling of one file | same, per dataset version; ends at sealing + grace (`[DEC-RETENTION]` OD-1) |
| Normalized events | materialized inside derivation; not separately retained | fact derivation | same; if ever materialized, it is the upload in another shape and ends with it |
| Mappings | inside `rra_dataset_profiles.document` | admission provenance | the source profile for *Remember My Data*; re-attested, never skipped |
| Manifests | coverage manifest inside the profile | completeness attestation | provenance of the dataset version |
| Facts | `rra_fact_packages.document` | the analysis; catalog reads | the analysis run; reopening a report reconstructs from it |
| Reports | `rra_report_artifacts` + objects; `rra_report_deliveries`, `_surfaces` | the deliverable | retained artifacts bound to a run by digest |
| Evidence | the evidence surface artifact; `rra_report_delivery_surfaces` digests | proof | same, plus `W1-06` provenance record |
| Telemetry | `rra_operational_events` | operational health, content-free | unchanged; product telemetry not authorized |
| Deletion evidence | `rra_deletion_jobs`, `rra_deletion_evidence` | prove content ended | same, bounded by OD-2 instead of permanent |

## What could not be determined from `src/`

- The bucket name (injected; `infra/data_resources.py` for deployment).
- The envelope master key's provisioning and rotation path (`envelope.py:6` says "the secret store").
- Whether `rra_report_deliveries.expires_at`'s index is dead or awaits an unbuilt sweep.
- Any horizon for `rca_organizations.name`; `KHEPRI-DEC-015` §2 keeps the organization record for its
  lifetime and excludes deletion, so the name has no end today.

## Method

One read-only exploration over `src/khepri/{rra,rca,runtime,infra}`, `migrations/`, and
`pyproject.toml`, followed by a second independent check of the two findings: `deletion.py` deletes
only object keys (`:257`); `rra/persistence.py` declares `expires_at` on invitations, sessions and
uploads only (`:50`, `:81`, `:136`); `grep -rn '\.sweep()' src/` outside `khepri/local` returns zero
callers; `pyproject.toml:78` excludes `khepri/local`.
