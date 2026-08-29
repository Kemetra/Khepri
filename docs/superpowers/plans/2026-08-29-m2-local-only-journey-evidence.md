# M2 §7 — local-only completion evidence

`KHEPRI-DEC-031` §7 states four conditions for recording `M2` in its local-only form. This ledger
records what was measured for each against `main` at `46b2d56`, after `T1-04` completed at `#340`.

**This document is evidence, not a declaration.** It does not record `M2` as reached. Producing the
evidence is one act and accepting it is another; §7 is an owner judgement, and `AGENTS.md` makes the
merge of this assessment the approval.

---

## Condition 1 — catalog merged and `T1-08`'s proofs pass

> *"`RRA-011`'s catalog and evidence surfaces are merged to `main` and pass `T1-08`'s parity,
> fail-closed, and no-duplicate-truth tests."*

Measured on the merged tree at `46b2d56`, not on a branch.

| Gate | Result |
|---|---|
| `khepri-gov validate` | Governance validation passed |
| `ruff check .` | All checks passed |
| `pytest` | **3,797 passed**, 72 skipped, 1 xfailed |

`T1`'s five merges are `#334` (`a91fa63`), `#337` (`f97193d`), `#338` (`4e448ed`) and `#340`
(`46b2d56`). `T1-08`'s three properties live in `tests/test_rra011_parity.py` and ran inside that
suite.

**Condition 1 holds.**

---

## Condition 3 — nothing widened `RRA-010` or `RCA-002`

> *"The journey and shell entry points render without widening `RRA-010` or `RCA-002`."*

A static check, and the strongest available: not "the widening was reviewed" but "no journey surface
changed at all since the last staging evidence".

```
git diff --stat f320c17...46b2d56 -- src/khepri/rra/routes/ \
                                     src/khepri/rra/templates/ \
                                     src/khepri/rra/static/
```

Empty. `T1`'s four merges touched `definitions.py`, `wording.py`, `facts.py`, `bundle.py` and the
four `analysis/` families, plus the `RCA-003` legal surfaces under `runtime/`. No route, template or
static asset of the beta journey moved.

**Condition 3 holds.**

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

`AnalysisQualitySummary`'s new identity lists (`#338`) and `availability()` (`#340`) render on **no**
surface: the Impact Preview journey step is AUTHORITY-BLOCKED under `RRA-010`, which excludes new
journey phases. They are data contracts, held by their own tests, and are correctly absent from this
run.

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
| 1 — catalog merged, `T1-08` proofs pass | **Holds** — measured on `46b2d56` |
| 2 — `CAL1` complete, two `P2`s non-blocking | **Unchanged**, and cross-checked by the oracle |
| 3 — no widening of `RRA-010` / `RCA-002` | **Holds** — journey surfaces byte-unchanged |
| 4 — full journey, both languages | **Holds**, with the channel limitation stated |

Whether these four suffice to record `M2` as reached in its local-only form is the owner's call, and
merging this ledger is that decision.
