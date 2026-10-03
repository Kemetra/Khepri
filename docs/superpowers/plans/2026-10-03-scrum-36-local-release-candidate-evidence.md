# SCRUM-36: the local Docker journey and recovery, after row-level security and upload identity

> ## STATUS: RUN ON 2026-10-03, `main` AT `93f242a7`. ACCEPTANCE IS THE OWNER'S CALL
>
> A cold, cache-free build of the committed staging stack came up on one migration head, with
> every process on its own non-owner role and secret-free logs. Through that stack:
> - the whole commercial and design-partner journey ran and was reread after a restart;
> - two versions were compared, and one was deleted;
> - isolation held on every surface tried;
> - the worker recovered a job it had not claimed;
> - a backup restored completely;
> - the oracle's headline figures reconciled exactly.
>
> Two refusals were expected and observed:
> - the envelope migration refuses under the policies (`RRA-017` `FR-272`);
> - the upload-identity revision refuses while the app is connected (`RCA-005` `FR-262`).
>
> No product defect was found. Residual risks are listed at the end.
>
> This verifies the implemented product on one machine. It authorizes no external participant,
> paid use or hosting (`KHEPRI-DEC-031`).

## Pins

| Item | Value |
|---|---|
| `main` | `93f242a7` (#650 merged), from a detached worktree |
| Compose file | `docker-compose.staging.yml`, committed form, with no override |
| Build | `docker compose build --no-cache --pull`: exit 0, 854 s, no cached image used |
| Runtime image | `khepri-runtime:staging` `sha256:6d8d8a0e…5bda5b` |
| PostgreSQL image | `khepri-staging-postgres:17.11-tls` `sha256:c7c1fb69…9f005` |
| MinIO image | `khepri-minio:RELEASE.2025-09-07T16-13-09Z` `ac52fc87d010`, built from source (#645) |
| Migration head | `20261003_0037`, one head; `alembic current` equals it |
| Docker | 29.4.2, Compose 5.1.3, WSL2 Ubuntu |
| Master key | 32 random bytes generated for this run; kept out of the repository |
| Started / finished (UTC) | 19:53:54 / 20:22 |

The images carry no `khepri.commit` label, because `docker compose build` does not set one;
`scripts/build_image.py` does. The pins above are image IDs (observation O1).

## Method

- **Stack.** `sh ops/staging/generate-certs.sh`, then a cold build, then `docker compose up -d`.
  - Web, worker and the migration ran from the built image, with TLS to PostgreSQL and MinIO, as
    committed.
  - A long-lived WSL process held the stack, so the idle stop that ended an earlier run's stack
    did not recur.
- **Identity.** This used the approved local handoff, as the M4 run did, with production verbs
  only.
  - Inside the web container, as the application role, the operator script called
    `AccountService.create_account`, `OrganizationService.create_organization`,
    `SessionService.create` and `OrganizationSwitcher.switch`, plus
    `InvitationService.issue_invitation` for design-partner sessions.
  - The customer routes did everything else. No table was written directly.
- **Driver.** Customer HTTP routes and Playwright (Chromium) ran from Windows against
  `http://127.0.0.1:8000`.
  - Requests carry the headers a same-origin browser sends (`Origin`, `Sec-Fetch-Site`).
  - They carry the cookies a browser holds: the commercial `khepri_session` (path `/`) and,
    where the journey has issued it, `khepri_beta_session` (path `/api/v1/beta`).
  - Both header and cookie rules were themselves checked (§Security behaviour).
- **Files.**
  - `tests/rra_printed_support.retail_csv`: 160 rows (seed 21), and the same file shifted 56 days
    for a second period. A 1-row file. A 160-row file with seed 36 for recovery.
  - `tests/rra_calculation_oracle.CLEAN_ROWS`, through `to_csv` and `oracle_contract()`, for
    reconciliation.
  - The profile body is `tests.rra003_contract_fixtures.profile_payload()`, with an attested
    coverage manifest.
- **Scripts.** Every command run is in
  [`2026-10-03-scrum-36-captures/scripts/`](2026-10-03-scrum-36-captures/scripts/). They are
  stored as `.txt` so no gate executes or lints them.
- **Fixture identities.** These are synthetic organizations (`S36 A 2`, `S36 B 2`, `S36 A 3`,
  `S36 B 3`) and invitation sessions. Their tokens are not recorded here.

## Coverage

| SCRUM-36 case | How exercised | Result |
|---|---|---|
| Cold build and start, no withdrawn images | `--no-cache --pull` build of the committed compose file | **Pass.** Exit 0; all six services up; `migrate` exited 0 |
| Role-specific connections | `pg_roles`, `pg_stat_activity` | **Pass.** `khepri_app`, `khepri_worker` and `khepri_sweep` hold no superuser or `BYPASSRLS`; the worker connects as `khepri_worker`; only the migration owner `khepri` bypasses |
| One Alembic head | `alembic heads`, `alembic current` in the image | **Pass.** `20261003_0037` |
| Secret-free logs | All container logs (1,073 lines at the end) | **Pass.** Zero hits for the master key, any role name or password, `password`, a private key, the MinIO credentials, a session or upload identifier, the fixture e-mails, or a traceback |
| Identity handoff | Operator verbs, then `POST /app/en/{org}/analyses` | **Pass.** `303` to `/beta/en/upload`, with the beta cookie set |
| Upload, declarations, processing | Consent, upload, profile with manifest, facts, report request | **Pass.** Two commercial versions, both `succeeded` |
| Time to first usable report | Upload to `succeeded`, measured by the driver | 8.6 s and 7.5 s (160 rows); 3.2 s (1 row) |
| Report reader, evidence, PDF, Excel | All seven surfaces per run | **Pass.** See §Surfaces |
| Retained history and reopen | `/app/{en,ar}/{org}/overview`, `analyses`, `data`, `team`, both run passports | **Pass.** `200`; both versions and both runs listed |
| Governed two-version comparison | `POST /app/en/{org}/analyses/compare` with the two versions | **Pass.** `200`, rendered |
| Deletion | `POST /app/en/{org}/data/{version}/delete` | **Pass.** See §Deletion |
| Normal, insufficient, malformed | 160 rows; 1 row; PNG bytes as `text/csv`; header-only CSV | **Pass.** `succeeded`; `succeeded` with every surface; `400` "Upload content is invalid or unsupported." twice |
| Caveated and refused | Reports from the normal, 1-row and oracle runs | **Shown.** Every web report carries refused-results and caveat wording (EN normal: 34 "refus…", 18 "caveat…") |
| Expired | Not reached by time | **Not exercised.** Expiry needs seven days. The retention sweep ran under its real roles with nothing due (§Recovery). Expiry behaviour is covered by `test_t01_deployed_retention_passes` and `test_rra017_sweep_postgres` |
| Permission and isolation | Second organization; foreign beta session; no session | **Pass.** See §Isolation |
| Interrupted worker and recovery | Worker stopped, job queued, worker started | **Pass.** See §Recovery |
| Restart | `docker compose restart web worker` | **Pass.** History, both reports and the data page served `200` afterwards |
| Arabic and English, RTL and LTR | Every page, both languages | **Pass.** `lang`/`dir` correct; Arabic pages `rtl` |
| Narrow layout | 390 px | **Pass.** No page-level horizontal overflow on any page |
| 200% text | Root font at 200%, 390 px | **Pass for reflow.** No overflow on any page. As in SCRUM-21, this proves root-relative text only; chart text is fixed-size |
| Keyboard and focus | First 12 Tab stops per page at 1440 | **Pass.** Every stop had a visible indicator |
| Reduced motion | `prefers-reduced-motion: reduce` | **Pass.** No transition or animation over 10 ms on any page |
| Rendered PDF parity | EN and AR PDFs, PyMuPDF | **Pass.** See §PDF parity |
| Published numbers against the oracle | `CLEAN_ROWS` through the journey | **Pass.** See §Reconciliation |
| Backup and restore | `pg_dump`/`pg_restore` into a scratch database | **Pass, database only.** See §Backup |
| Safe upgrade and recovery | Revision `0037` down and up on populated data | **Pass.** See §Upgrade |
| Envelope migration | `khepri-envelope-migrate` in the image | **Refused, as required.** See §Expected refusals |
| Manual task completion, assistance points | — | **Not measured.** No human tester took part; the driver is synthetic |

**Pages checked in the browser.** Each was checked in both languages, at 1440, at 390, and at 390
with 200% text:
- report web, report evidence;
- journey upload, journey report;
- app overview, analyses, data, team.

## Surfaces

Normal run, version 1. Version 2 and the 1-row run match in status, type and disposition.

| Surface | Status | Type | Disposition | CSP | Bytes |
|---|---|---|---|---|---|
| `web/en` | 200 | `text/html; charset=utf-8` | `inline; filename="khepri-report-en.html"` | yes | 50,913 |
| `web/ar` | 200 | same | `inline; filename="khepri-report-ar.html"` | yes | 54,527 |
| `evidence/en` | 200 | same | `inline; filename="khepri-evidence-en.html"` | yes | 405,700 |
| `evidence/ar` | 200 | same | `inline; filename="khepri-evidence-ar.html"` | yes | 431,862 |
| `pdf/en` | 200 | `application/pdf` | `attachment; filename="khepri-report-en.pdf"` | — | 2,721,959 |
| `pdf/ar` | 200 | `application/pdf` | `attachment; filename="khepri-report-ar.pdf"` | — | 3,095,110 |
| `excel` | 200 | spreadsheet | `attachment; filename="khepri-report.xlsx"` | — | 59,970 |

The inline CSP is exactly `default-src 'none'; style-src 'unsafe-inline'; base-uri 'none';
form-action 'none'; frame-ancestors 'none'; sandbox allow-same-origin`.

## Reconciliation

**The governed oracle.** `tests/rra_calculation_oracle.CLEAN_ROWS` (12 rows, two stores,
January and May) was run through the staging journey with `oracle_contract()`. Every headline
literal of `CLEAN_HEADLINE` appears in the published workbook:

| Figure | Oracle | Published | Where |
|---|---|---|---|
| Revenue | 1380.00 | 1,380.00 | Executive Summary |
| Units | 37 | 37 | Executive Summary |
| Transactions | 8 | 8 | Executive Summary ("Number of sales") |
| Cost | 770.00 | 770.00 | Profitability ("Cost of goods sold") |
| Gross profit | 610.00 | 610.00 | Profitability |
| Gross margin | 0.4420 | 44.20% | Profitability |
| Discount | 0.00 | 0.00 | Discounts and Returns ("Discounts given") |

The two period totals are 630.00 and 750.00 (Sales Performance), the arithmetic the oracle states
for January and May.

**One deviation.** A manifest must attest every day it spans, and the route refused a gap: "A
coverage manifest omits a day inside its own window." So the operator attestation covered 1
January to 31 May, rather than only the oracle's two windows. Headline totals do not depend on
attested days. Comparison figures can, so this run reconciles headline figures only.

**Independent cross-check of the normal file.** Summing the 160-row CSV directly gives revenue
23,520.06, units 836 and 80 distinct invoices. The published Executive Summary shows 23,520.06, 836
and 80.

## PDF parity

| Run | EN pages | AR pages | Producer |
|---|---|---|---|
| Normal, v1 | 106 | 106 | Skia/PDF m149 |
| Normal, v2 | 106 | 106 | Skia/PDF m149 |
| 1 row | 25 | 24 | Skia/PDF m149 |

- Every decimal figure in the English PDF also appears in the Arabic one: 74 of 74 (normal), and 4
  of 4 (1 row).
- The Arabic PDF prints Arabic-Indic digits, and PyMuPDF returns its text in visual order, as
  SCRUM-21 recorded. So the comparison maps the digits and reverses each run before matching.
- The 1-row page counts (25 / 24) equal SCRUM-21's.
- This run did not repeat SCRUM-21's capture-by-capture reading of tables and charts. No renderer
  input changed since then, and the ticket excludes repeating visual review on unchanged screens.

## Isolation

The target is organization A's version-1 job. Every probe was refused, and none served HTML or a
`Content-Disposition`:

| Caller | Status, JSON |
|---|---|
| Organization B, with its own commercial and beta cookies | `404` on status, bundle, `web/en`, `pdf/en`, `excel` |
| Organization B's commercial cookie with A's beta cookie | `401` on all five (#594's guard) |
| No session | `401` on all five |
| Organization B's session on A's `/app/…/analyses`, `/data`, a passport | `404` |
| No session on the same | `404` |
| Organization B posting A's delete route | `404`; A's version survives |

## Security behaviour observed along the way

- **Cross-site guard (`rra/journey/security.py`).** The first driver pass sent no `Origin` and no
  Fetch Metadata. Every mutation carrying a cookie was refused with `403` "Cross-site mutation is
  not allowed." That is the guard working, not a fault.
- **#594 membership guard.** The beta cookie of an organization's analysis, sent without a live
  commercial session, was refused with `401` "Session is unavailable." A browser holds both cookies.
  A client that drops the commercial one loses access, as `RCA-001` `FR-030` intends.

## Deletion

Organization A deleted version `dsv_LFAD…` through `/app`:

| Check | Result |
|---|---|
| Route | `303` to `/app/en/{org}/data`. A repeat gives the same `303`, so deletion is idempotent |
| Data page | The deleted version is gone; the other remains |
| Deleted version's report | `404` "No report artifact is available for this session." |
| The other version's report | `200` |
| Comparing against the deleted version | `404` |
| `rra_uploads` for the deleted version's session | 0 rows; the kept session still holds 1 |
| Session content | `content_deleted_at` set; deletion job `complete` |
| Version record | `tombstoned`, with one tombstone |
| `upload_id` | `NULL` on the deleted version, cleared by `fk_rca_workspace_version_upload` (`RCA-005` `FR-256`); kept on the other |

## Recovery

- **Worker interrupted before claiming.**
  - The worker was stopped, and a job was queued (`job_1497…`).
  - Read twice, 5 s apart: `queued`, `attempt_count = 0`, lease owner none.
  - Then the worker started at 20:15:39.
  - In about 10 s: `succeeded`, `attempt_count = 1`. It was claimed exactly once.
  - This uses the race-free form: the unclaimed interval is read, not inferred.
- **Restart.** `docker compose restart web worker`. History, both reports and the data page served
  `200` afterwards. No container restarted on its own at any point; every `RestartCount` was 0.
- **Retention sweep.** `khepri-retention-sweep` ran in the image with the application role and
  the sweep role's credential (`RRA-017` `FR-271`). It exited 0, and every count was 0, because
  nothing was due.
- **Not exercised: a worker killed mid-job.** A lease that expires after the worker dies is
  `RRA-017` Verification 17's subject, covered by `test_rra017_recovery_postgres`.

## Upgrade

1. **With web and worker running.** `alembic downgrade 20261002_0036` was refused: "an
   application process is connected; stop web, worker and sweep before this revision runs".
   `current` stayed `20261003_0037`.
2. **With web and worker stopped.** Downgrade to `20261002_0036` succeeded, and the `upload_id`
   column was gone. Upgrade to head succeeded. Both took 10 s together, on populated data.
3. **The backfill on real rows.** The kept version got its `upload_id` back, matched by digest. The
   deleted version stayed `NULL`, because its upload is gone (`FR-262`).
4. **The grant.** The sweep's grant on the version table is `owner_id, sealed_at, upload_id`
   (`FR-271`).
5. **After restarting web and worker,** the kept report served `200`.

## Backup

- `pg_dump -Fc` of the staging database came to 291,481 bytes. It was restored into a scratch
  database on the same server, and the round trip took 2 s.
- **Restored completely:** row counts were equal in all ten tables compared. The head was the same
  (`20261003_0037`), with all 18 policies and all 12 forced-row-security tables.
- **Not measured: object storage.** MinIO was not backed up, so restoring stored files is unproved.
  A restore across machines, and hosted recovery-time and recovery-point targets, are also unproved.
  All of that is future hosted work (`OPS1`).

## Expected refusals

| Command | Result | Authority |
|---|---|---|
| `khepri-envelope-migrate`, application role, under the policies | `{"event": "envelope_migration", "refused": "row_security_active"}`, exit 2 | `RRA-017` `FR-272`. Resolution is proposed in #652 (`FR-273`) |
| `alembic downgrade` of `0037` with the app connected | `RuntimeError`, no change | `RCA-005` `FR-262`; #650 |

Both are the system refusing what it must, not failed gates.

## Observations

- **O1. Compose-built images carry no `khepri.commit` label.** `scripts/build_image.py` stamps
  one, and `docker compose build` does not, so a staging image cannot name its commit by
  inspection. Pins here use image IDs. Low; a candidate issue only if staging images are compared
  across commits.
- **O2. `/app/{lang}/{org}` with no page answers the governed `404`.** The overview is at
  `/app/{lang}/{org}/overview`, and the shell's own navigation links there. This is not a defect.
  The first browser pass used the bare address by mistake.

## Residual risks

- **The envelope migration is still blocked.** It refuses under the policies until #652
  (`RRA-017` `FR-273`) is merged and implemented. The upload re-seal (`RCA-005` `FR-263`) waits
  on the same work, and `v1` cannot be retired until both halves verify zero.
- **The storage decision is still open.** MinIO is archived upstream and runs here from source
  (#631, SCRUM-37). It receives no security updates.
- **Not measured here:**
  - expiry by elapsed time;
  - a worker killed mid-job;
  - restoring object storage;
  - human task completion, and where a person would need help.
- **One machine, one run.** No hosted environment, no concurrency load and no external
  participant was involved (`KHEPRI-DEC-031`).

## Captures

- [`report-web-ar-390-200pct.png`](2026-10-03-scrum-36-captures/report-web-ar-390-200pct.png):
  the Arabic report at 390 px with 200% text.
- [`app-ar-analyses-1440.png`](2026-10-03-scrum-36-captures/app-ar-analyses-1440.png): Arabic
  analyses history.
- [`journey-report-en-390.png`](2026-10-03-scrum-36-captures/journey-report-en-390.png): the
  journey's report step, narrow.
- [`report-evidence-en-1440.png`](2026-10-03-scrum-36-captures/report-evidence-en-1440.png): the
  evidence page.
- [`app-en-data-390-200pct.png`](2026-10-03-scrum-36-captures/app-en-data-390-200pct.png): the
  data page at 390 px with 200% text.
