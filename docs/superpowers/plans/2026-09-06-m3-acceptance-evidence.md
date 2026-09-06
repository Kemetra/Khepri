# M3 acceptance — the exit gate, measured on the deployed image

Roadmap §5 states the `M3` exit gate as one sentence:

> Active retention/workspace authority; multiple dataset versions and analyses retained; history,
> report reopen, deletion, evidence, and metric catalog work.

**This document measures that sentence and nothing else.** It creates no acceptance conditions of
its own. Unlike `M2` — whose four conditions the owner authored in `KHEPRI-DEC-031` §7 — no
governance artifact decomposes `M3`, so §5's own clauses are the condition source, cited directly.
Where a clause is ambiguous this document says which reading it measured rather than choosing
silently.

**Run on:** `main` at `c98e946`, 2026-09-06.

---

## Method

`CAL1-14`'s and `M2`'s method, used again so the runs stay comparable: driven inside
`khepri-staging-web` through the real HTTP surface against the merged `docker-compose.staging.yml`
stack.

**The stack was rebuilt before measuring, and that step is why this run means anything.** The
running image was 23 hours old — built *before* `W1-09` merged (`cf607fd`, `#390`), so it carried
none of the pin routes. A journey driven against it would have reported a failure that describes a
tree which is not `main`. After `docker compose -f docker-compose.staging.yml up -d --build`:

| Module | Container | Worktree |
|---|---|---|
| `runtime/shell_pins.py` | `2fb324539b3b3204e8b05fba2c9a23ed` | identical |
| `runtime/shell_api.py` | `85651359e44efc680b307c50718a0c45` | identical |
| `runtime/workspace_deletion.py` | `15a9dcb986f82863672c34c83583dedc` | identical |
| `runtime/retention_sweep.py` | `40ad1731b145f702f357eb31c75ac441` | identical |
| `runtime/wiring.py` | `d1b82df3b369fff13295dbcb29c2b578` | identical |

**The route table was enumerated from `khepri.runtime.web:app`** — the literal object the compose
file's uvicorn command serves — rather than from a factory called in the test process. 45 routes,
including all four `W1-09` pin routes, `data/{version_id}/delete`, and the six `RRA-011` catalog
routes. This is the check `#382`'s review introduced after a route passed every test while being
absent from the image.

**`KHEPRI-DEC-033` §5 is independently confirmed discharged.** `build_retention_sweeper` is called
from `local/wiring.py` *in the image*, not merely present in the repository, so the retention
horizons are enforced rather than intent.

**Setup used production verbs only.** `AccountService.create_account`, `OrganizationService.
create_organization`, `SessionService.create`, `OrganizationSwitcher.switch`. No workspace table was
written directly; every row the surfaces read was produced by the pipeline that a customer's own
actions drive.

**The analyses were entered the way a customer enters them:** `POST /app/{lang}/{org}/analyses`,
which resolves the session, compares the address's organization against it, opens the commercial
session, and hands the browser to the journey with the beta cookie. Calling `CommercialBridge.open`
directly would have skipped all four steps.

**Two fixed extracts**, so the published figures are comparable between runs: `CSV_A` (4 rows,
2026-01-05..07) and `CSV_B` (3 rows, 2026-02-02..04).

---

## The six §5 capabilities

| # | §5 clause | Measured as | Result |
|---|---|---|---|
| 1 | multiple dataset versions retained | Two versions created in one organization, both listed on Data, both carrying distinct `dsv_` identifiers | **PASS** |
| 2 | multiple analyses retained | Two runs completed, both listed on Analyses newest-first, distinct `run_` identifiers | **PASS** |
| 3a | history — the Analysis Passport (`W1-06`) | Passport renders period, retail day boundary, coverage, rows, and the version triple | **PASS** |
| 3b | history — the Methodology Change Notice (`W1-08`) | The diff surface is wired and correctly renders nothing; **this run cannot exercise a changed methodology** — see below | **NOT EXERCISED** |
| 4 | report reopen | All four artifact kinds hand off `303` with a scoped beta cookie | **PASS** |
| 5 | deletion, with evidence | Version deleted, absent from the surface that listed it, evidence rows written | **PASS** |
| 6 | metric catalog | Four catalog routes answer `200`, both languages, none carrying a figure | **PASS** |

**Two readings this table makes, stated rather than assumed.** *"History"* is read as covering both
provenance surfaces `W1` built — the Passport (`W1-06`) and the Change Notice (`W1-08`) — because
§5 names history separately from the retention clause before it, and `W1-08` is the only surface
that makes an analysis's history legible against another. *"Deletion, evidence"* is read as one
clause pair and measured together, because the deletion route's evidence is what the ledger rows
record; separating them would measure the same call twice.

### 1 & 2 — multiple versions and analyses

Both analyses completed end to end: `consent 204`, `upload 201`, `profile 201 (admissible)`,
`facts 201`, `report 201`, worker reaching `succeeded` with distinct `bundle_id`s. The workspace
surfaces then show both, in both languages:

| Surface | `en` | `ar` |
|---|---|---|
| Overview | `200`, 3,584 B | `200`, 3,851 B |
| Data | `200`, 3,609 B | `200`, 3,855 B |
| Analyses | `200`, 4,469 B | `200`, 4,786 B |

Data reads: *"Submitted … Admitted … Used in analysis … Kept"*, twice. Analyses reads: *"Every
analysis run for this organization, newest first"*, then two completed runs each naming what was
answered, answered-with-caveats, and refused.

### 3a — the Analysis Passport (`W1-06`)

`GET /app/{lang}/{org}/analyses/{run_id}` → `200`, 6,502 B (`en`) / 6,893 B (`ar`). It renders:

- **Period covered** `2026-01-05 – 2026-01-07`, **retail day boundary** `Africa/Cairo`
- **Coverage** `all-stores`, **rows** `4`
- **Methodology versions** `rra003.mapping.v3`, `rra004.package.v3`, `rra004.formula.v2`
- **Analysis quality** — answered / answered-with-caveats / refused, by section
- **Audit detail** — run and dataset identifiers, package digest, coverage manifest digest, upload
  digest, and all seven artifact digests

The version triple on the page equals the three constants the image pins, which is the property
`M2`'s condition 4 also checked; they bind three different ways and a page could show a stale one.

### 3b — the Methodology Change Notice (`W1-08`) — NOT EXERCISED

**This run cannot demonstrate the diff surface, and reporting it as passing would be wrong.**

Both analyses ran against the one version triple the image pins — `rra003.mapping.v3`,
`rra004.package.v3`, `rra004.formula.v2`. `methodology_change` returns `None` "when every governed
version is the same", so `analysis.html.j2`'s `{% if view.change %}` renders nothing. Verified on
both runs' live detail pages rather than reasoned from the source:

| Run | Bytes | `class="change-notice"` present | Versions shown |
|---|---|---|---|
| first | 6,485 | `false` | the same three |
| second | 6,485 | `false` | the same three |

The second run is the one that *could* carry a Notice — it has a completed predecessor — and it
does not, because there is no difference to report. **That is the surface behaving correctly, and
it is also the null case.** A run that can only produce the null case does not prove the capability:
exercising `W1-08` needs two analyses whose governed versions actually differ, which a single image
pinning one triple cannot produce. `W1-08` merged with its own tests at `267c50c` (`#377`), and
those tests are where the changed-version case is proven; this run neither confirms nor disputes
them.

Recorded as **NOT EXERCISED** rather than PASS or FAIL. If the owner reads §5's "history" as
requiring a demonstrated methodology diff, this clause is open and needs a two-version fixture; if
it is read as the Passport plus a wired diff surface, the gate is met. **That reading is the
owner's**, and it is the one place where this ledger's conclusion depends on it.

### 4 — report reopen

`POST /app/en/{org}/analyses/{run_id}/artifacts/{kind}` for each of `shell_analysis.ARTIFACT_KINDS`:

| Kind | Status | Location | Cookie |
|---|---|---|---|
| `web` | `303` | `/api/v1/beta/reports/{job}/surfaces/web/en` | set |
| `evidence` | `303` | `…/surfaces/evidence/en` | set |
| `pdf` | `303` | `…/surfaces/pdf/en` | set |
| `excel` | `303` | `…/surfaces/excel` | set |

Each hands off a scoped beta session cookie, which is what makes the surface reachable after the
analysis session has ended — the "reopen" the clause names.

### 5 — deletion with correct evidence

`POST /app/en/{org}/data/{version_id}/delete` → `303` back to Data. Measured either side of the call
rather than trusting the status:

| Property | Value |
|---|---|
| Version present on Data **before** | `true` |
| Version present on Data **after** | `false` |
| Revocation rows | `1` (run 1), `2` (run 2, cumulative) |
| Tombstone rows | `2` (run 1), `4` (run 2, cumulative) |
| Audit event rows | `25` (run 1), `32` (run 2, cumulative) |

The counts are cumulative across the database's whole lifetime, so the *increment* is the evidence:
one deletion produced one revocation and two tombstones in both runs.

### 6 — metric catalog

| Route | Status | Bytes | Carries a figure |
|---|---|---|---|
| `/catalog/quality/en` | `200` | 3,149 | no |
| `/catalog/quality/ar` | `200` | 4,095 | no |
| `/catalog/populations/sales_posted` | `200` | 41 | no |
| `/catalog/metrics/revenue/en` | `200` | 274 | no |

`quality/en` and `quality/ar` reproduce `M2`'s byte counts exactly (3,149 / 4,095), measured five
days later on a later tree. No response carries a `"value"` field, re-checking against live
responses the property `test_no_catalog_response_carries_a_figure_value` holds in process.

---

## Determinism

Two independent runs, in four separate organizations, produced **byte-identical package digests**
for the two fixed extracts:

| Extract | Package digest |
|---|---|
| `CSV_A` | `b9ea274a5e91b38a48bc55adae21719db34fcb1e4780c8815a759fa8d8307470` |
| `CSV_B` | `d3fffd17d119498c83b7667392ff2dea66fa2c0df90cefb3d001d8aa217a8e4f` |

Every rendered surface was byte-identical across runs (detail 6,502 / 6,893 B; catalog 3,149 /
4,095 / 41 / 274 B), in four separate organizations with different session identifiers.

**That is consistent with the digest being content-derived and independent of the isolation key,
but this run does not establish it** — equal digests are what a content address produces by design,
and proving independence needs a case where the key varies while everything else is held identical
by construction. The factual claim here is the reproducibility one: the same input published the
same bytes, twice.

---

## One finding, outside the M3 gate

**The Team surface raises HTTP 500 in the deployed image.**

    AttributeError: 'InvitationService' object has no attribute 'invitations_for_organization'
    shell_api.py:629 in _team_response

- `shell_api.py:152` declares `invitations_for_organization` on the shell's `_Invitations` Protocol.
- `invitation_persistence.py:436` defines it on the **store**.
- `wiring.py:497` passes `RcaInvitationService(SqlInvitationStore(...))` — the **service**, which
  defines only `issue`, `revoke`, `redeem`.
- Protocols are structural and unchecked at runtime, so the mismatch appears only when driven.

**Why no test caught it.** The team-surface tests build a hand-wired object that *has* the method;
the invitation-service tests build the real service but never reach the shell; the route-table
assertion passes because the route exists. This is the same shape as `#382`'s `deletion=` finding,
in the same module, and it is what `khepri-a-hand-wired-fixture-hides-an-unwired-deployment`
predicts.

**Age.** The call site was introduced at `1e774db` (`#274`). It is not a `W1` regression.

**Scope.** Team is `RCA-002`/`R8`'s surface (blueprint §6, recorded `SHIPPED`), and it is **not**
one of §5's six `M3` clauses — so it does not gate this acceptance. It is a live 500 on a shipped
customer surface and is recorded here rather than left to be rediscovered. Its fix is a slice under
`RCA-002`, not a change to this ledger.

---

## What this run does not establish

- **It is a local-stack run.** Exactly as with `M2`, it authorizes no external participant; the
  hosted environment (`OPS1-02`..`OPS1-03`) remains deferred by `KHEPRI-DEC-031` §4.
- **It measures §5's sentence, not a decomposed condition set.** If the owner would rather `M3`
  acceptance rest on numbered conditions in a governed decision — as `M2`'s did — this ledger
  should be re-read against them once they exist. Nothing here would change: the six clauses
  measured are §5's own words.
- **`W1-11` repeat-use telemetry stays excluded**, needing the same `KHEPRI-DEC-015` amendment as
  `R8-08` and `T1-07`. `KHEPRI-DEC-034` §2 states it is no precedent for either.

---

## Conclusion

**Six of the seven measured clauses pass on `main` at `c98e946`, against the deployed image; the
seventh is wired but not exercisable by this run.** Retention and workspace authority are active
(`KHEPRI-DEC-033`, `RCA-005`); an organization retains multiple dataset versions and completed
analyses, reads each analysis's period, coverage and governed versions on the Passport, reopens
every report surface, deletes content with revocation, tombstone and audit evidence, and reads the
metric catalog — deterministically, in both languages.

**The one clause left open is `W1-08`'s Methodology Change Notice (3b).** The surface is wired and
correctly renders nothing when no version differs, which is all a single image pinning one triple
can produce. Whether §5's "history" requires a *demonstrated* diff or is satisfied by the Passport
plus a wired diff surface is the owner's reading, and it is the only question standing between this
ledger and an unqualified `M3` acceptance.
