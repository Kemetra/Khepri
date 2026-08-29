# M2 §7 — local-only completion evidence

`KHEPRI-DEC-031` §7 states four conditions for recording `M2` in its local-only form. This ledger
records what was measured for each against `main` at `46b2d56`, after `T1-04` completed at `#340`.

**This document is evidence, not a declaration.** It does not record `M2` as reached. Producing the
evidence is one act and accepting it is another; §7 is an owner judgement, and `AGENTS.md` makes the
merge of this assessment the approval.

---

## Condition 1 — catalog merged and `T1-08`'s proofs pass — **DOES NOT HOLD**

> *"`RRA-011`'s catalog and evidence surfaces are merged to `main` and pass `T1-08`'s parity,
> fail-closed, and no-duplicate-truth tests."*

The proofs pass. The catalog is not reachable.

| Gate on `46b2d56` | Result |
|---|---|
| `khepri-gov validate` | Governance validation passed |
| `ruff check .` | All checks passed |
| `pytest` | **3,797 passed**, 72 skipped, 1 xfailed |

`T1`'s four merges are `#334` (`a91fa63`), `#337` (`f97193d`), `#338` (`4e448ed`) and `#340`
(`46b2d56`). `T1-08`'s three properties live in `tests/test_rra011_parity.py` and ran in that suite.

**But `definitions.py` has no production consumer.** Verified two ways, because attribute-access grep
alone would miss a bare from-import:

```bash
grep -rn "definitions\." src/khepri/ | grep -v src/khepri/rra/definitions.py
grep -rn "definitions import\|import definitions" src/khepri/
```

Neither returns a hit outside `infra/compute.py`, where the word means an ECS task definition.
`define_metric`, `describe_metric`, `summarize` and `availability` are called by nothing that ships.

`RRA-011`:53-54 places three read routes in scope — *"read routes exposing the registry, the summary,
and a fact's evidence, session scoped exactly as their existing siblings are."* The third is merged
and was exercised in condition 4 below. The first two have no route, because `cc042e3` withdrew the
catalog route inside `#334`.

**That withdrawal was not a governance violation**: lines 50-58 sit under `RRA-011`'s **Scope**
heading, which names the files a slice may touch, not a requirement it must satisfy. What it means is
narrower and still decisive — **`T1-05` is incomplete against its own roadmap output**, *"Build metric
detail and evidence routes"*. The evidence route exists; metric detail does not.

So a test count is the wrong evidence for this condition, and offering one here repeated a known
failure: a module's own tests passing while nothing calls it. Four merges and 3,797 passing tests do
not make a catalog a customer can reach.

**Condition 1 does not hold.** The remedy is a `T1-05` slice adding the metric-detail read route to
`report_api.py`, session-scoped like its siblings. It is deliberately not built here: this is a
docs-only ledger, and building the thing whose absence it records would be self-certifying the
condition it failed.

---

## Condition 3 — nothing widened `RRA-010` or `RCA-002`

> *"The journey and shell entry points render without widening `RRA-010` or `RCA-002`."*

**The first form of this check was invalid, and the correction changed the answer.** It ran
`git diff` over `src/khepri/rra/routes/`, `templates/` and `static/` — three paths that **do not
exist**. Git returns an empty diff and exit 0 for an absent pathspec, so the result was
indistinguishable from "nothing changed" while measuring nothing at all. Found in review on `#342`.

The governed paths are named by the specifications themselves: `RRA-010`:21-25 names
`src/khepri/rra/journey/templates/`, `journey/assets/journey.css`, `journey/assets/*.js` and the
presentation-only copy keys in `journey/copy.py`; the shell lives under `src/khepri/runtime/`.

Every path below was confirmed to exist before the diff was read.

```bash
git diff --stat f320c17...46b2d56 -- \
  src/khepri/rra/journey/templates/ \
  src/khepri/rra/journey/assets/ \
  src/khepri/rra/journey/copy.py \
  src/khepri/rra/journey/routes.py
```

Empty. **`RRA-010`'s named scope is byte-unchanged.**

The shell is not. `src/khepri/runtime/` gained 472 lines across five files:

| File | Origin |
|---|---|
| `legal_api.py`, `legal_copy.py` | `#331` (`9161b50`) |
| `legal_templates/legal.html.j2`, `legal_page.html.j2` | `#331` |
| `wiring.py` (+2) | `#331`, mounting the above |

Those are the public legal and trust pages, authorized by **active `RCA-003`** — FR-062 closes the
surface set, FR-063 requires both languages, FR-064 forbids authentication. They are a separate
authorized surface, not a widening of `RRA-010`, whose scope is the beta journey's presentation, and
not of `RCA-002`, which excludes changes to *the beta journey's* routes, templates and assets
(`RCA-002`:134).

**Condition 3 holds** — now on evidence that could have failed.

---

## Condition 4 — the full journey, end to end, in both languages

> *"The full journey passes end to end on the local stack against the merged catalog surfaces, in
> both languages."*

Driven inside `khepri-staging-web` through the real HTTP surface, against the merged
`docker-compose.staging.yml` stack — six containers, TLS PostgreSQL and MinIO, the container's own
interpreter and trust store. This is `CAL1-14`'s method.

`tests/test_local_journey.py` was **not** used. Its own docstring states *"This is a development
test, not evidence"*: it builds a `LocalSettings` stack and a `TestClient`, which is the shortcut
`CAL1-14` declined. The compose files bind `127.0.0.1` inside WSL2, so a Windows-side client cannot
reach a healthy stack; widening those binds would edit files owned by `OPS1-08`, so the journey was
driven from inside the container instead.

The runtime image carries `src/` only — no `tests/` package. The oracle and its contract fixture were
copied in at run time, so the *expectation* is external to the product and the product is unmodified.

### Stages

| Stage | Evidence |
|---|---|
| Session | invitation `kiv1.…` issued, redeemed `201`, consent `204` |
| Upload | `201`, 623 bytes, `text/csv` |
| Admission | profile `201`, `admissible: true`, `row_count: 7` |
| Facts | `201` on **`rra003.mapping.v3` / `rra004.package.v3` / `rra004.formula.v2`** |
| Worker | job `job_525689c4be49ea9b909893ee` queued `201`, reached `succeeded` |
| Bundle | `200`, surfaces exactly `{web, pdf, excel}` |
| HTML | `web/en` 25,969 B (no Arabic script), `web/ar` 28,926 B (Arabic present) |
| Evidence | `evidence/en` 42,828 B, `evidence/ar` 44,501 B |
| PDF | `pdf/en` 568,893 B, `pdf/ar` 715,957 B — both begin `%PDF` |
| Excel | 38,244 B, begins `PK` |

**Zero failures.** Two independent runs produced identical sizes for all seven surfaces.

### The published figures still equal the hand-derived oracle

`CAL1-12` derived these by pencil outside every production helper. The staging stack reproduces them
on the successor versions, after four `T1` merges touched `facts.py` and all four analysis families:

| Metric | Oracle | Staging |
|---|---|---|
| revenue | `955.00` | `955.00` |
| units | `12` | `12` |
| transactions | `5` | `5` |
| cost | `582.00` | `582.00` |
| discount | `74.00` | `74.00` |

### What this run proves that `CAL1-14` did not

`CAL1-14` already drove this journey to zero failures on the same version triple, so stage results
alone would re-prove its work rather than this milestone's. The changes since `f320c17` that reach a
rendered surface are all in `wording.py`, and they are asserted directly:

| Delta | Where verified |
|---|---|
| Arabic concentration curve names categories (`المنتجات أو الفئات`) | asserted **in `web/ar`** |
| `revenue_by_channel` / `units_by_channel` business names, both languages | asserted in the running image |
| `RRA-011` metric descriptions | asserted in the running image |

**The channel names are verified in the image rather than in a surface, and that limit is real.**
`OracleRow` carries no channel field, so this fixture emits no channel series and no name for one can
render. Asserting a string that cannot appear would be a check that measures nothing. Their rendering
behaviour is held by `tests/test_rra009_wording.py` — the import-time coverage guard and its
symmetric-removal test — which ran in condition 1's suite.

### Scope note — the catalog surface

`cc042e3` **withdrew** the `GET /api/v1/beta/catalog/{language}` route. §7.4's "merged catalog
surfaces" is therefore the rendered evidence HTML that carries governed vocabulary, not an endpoint,
and that is what the table above exercises.

`AnalysisQualitySummary`'s identity lists (`#338`) and `availability()` (`#340`) are absent from this
run for **two** reasons, and only one of them is by design. The Impact Preview journey step is
AUTHORITY-BLOCKED under `RRA-010`, so nothing may render the availability contract yet -- that is the
designed one. The other is condition 1's finding: neither has a read route or any other production
caller, so there is no surface that *could* carry them even where governance permits it.

**Condition 4 holds for what it can hold**, with the channel limitation stated above rather than
absorbed.

---

## Condition 2 — `CAL1` remains complete

> *"`CAL1` remains complete, with its two carried `P2` findings still non-blocking."*

Not re-derived here. `CAL1`'s completion is recorded in the roadmap's own standing table and its two
carried `P2` findings (`CAVEAT_CURRENCY_NOT_DECLARED` unreachable under `rra003.mapping.v3`; the
Excel container not byte-identical across regenerations) are unchanged by `T1` — no `T1` merge
touched `rendering/excel.py`'s container assembly or `RRA-003` admission.

The oracle cross-check above is positive evidence that `CAL1`'s calculation contract still holds
after four merges into `facts.py` and the analysis families.

---

## First-run environment note

`ops/staging/certs/` is gitignored and absent on a clean checkout, so the first
`docker compose -f docker-compose.staging.yml up --build` fails on `/certs/server.key`.
`ops/staging/generate-certs.sh` is the documented first command and generates the CA, the PostgreSQL
pair and the MinIO material. Recorded because the failure looks like a build defect and is not one.

---

## Standing

| Condition | Status |
|---|---|
| 1 — catalog merged, `T1-08` proofs pass | **Does not hold** — proofs pass, catalog has no consumer |
| 2 — `CAL1` complete, two `P2`s non-blocking | **Unchanged**, and cross-checked by the oracle |
| 3 — no widening of `RRA-010` / `RCA-002` | **Holds** — `RRA-010`'s named scope byte-unchanged |
| 4 — full journey, both languages | **Holds**, with the channel limitation stated |

**`M2` is not reachable on this tree.** Condition 1 fails, so three of four holding is not a partial
pass -- §7 requires all four. What remains is one slice: the `T1-05` metric-detail read route in
`report_api.py`, session-scoped like its siblings, after which condition 1 can be re-measured against
a catalog something calls.

Two of this ledger's own findings came from review rather than from the run, and both were checks
that reported success while measuring nothing -- an empty `git diff` over paths that do not exist,
and a passing test count for a module with no caller. They are recorded rather than quietly
corrected, because the failure mode is the interesting part.

Whether this assessment is accepted is the owner's call, and merging it is that decision.
