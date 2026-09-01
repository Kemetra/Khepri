# M2 §7 condition 4 — the full journey, re-run on the current tree

`KHEPRI-DEC-031` §7.4 requires *"the full journey passes end to end on the local stack against the
merged catalog surfaces, in both languages."*

**Raised because `#345` records this as owed under either reading of the `RRA-011` Exclusion.**
`#342`'s condition-4 evidence was measured before `#343` merged, and `#343` changed
`report_api.py` (+743 lines), `rra/api.py`, and both wiring modules. Delivery evidence measured
against a tree that predates those changes cannot be inherited, so it is re-measured here.

**This document answers condition 4 only.** It takes no position on `#345`'s open owner question,
and condition 1 is not re-assessed here.

**Run on:** `main` at `d355d12`, 2026-09-01.

---

## Method

Driven inside `khepri-staging-web` through the real HTTP surface, against the merged
`docker-compose.staging.yml` stack. This is `CAL1-14`'s and `#342`'s method, and it is used again so
the two runs are comparable.

**The stack was rebuilt before measuring, and that step is the reason this run means anything.**
The running image was stale: `md5sum` of `report_api.py` differed between the container and the
worktree, and the image carried **none** of `#343`'s six catalog routes. A journey driven against it
would have reported a pass for a tree that is not `main`. After
`docker compose -f docker-compose.staging.yml up -d --build`:

| | Checksum |
|---|---|
| `/opt/khepri/src/khepri/rra/report_api.py` (image) | `46093d1531c851a2f3b7c2bfeab79c52` |
| `src/khepri/rra/report_api.py` (worktree at `d355d12`) | `46093d1531c851a2f3b7c2bfeab79c52` |

All six catalog routes are present in the running image, verified by enumeration rather than by
assuming the build succeeded.

The oracle and its contract fixture were copied into `/tmp/journey` at run time, so the *expectation*
is external to the product and the product is unmodified. The runtime image carries `src/` only.

**Dataset: `CLEAN_ROWS` (12 rows, 821 bytes).** `#342` used a 7-row, 623-byte set, so the published
figures below are not comparable to that ledger's line for line. Both are checked against the oracle
that derives them, which is the property that matters; a figure equal to a *different* run's figure
would prove nothing.

**Two transport details, recorded because they look like product defects and are not.** The session
cookie is issued `secure=True` and the compose network speaks plain HTTP internally, so `httpx` will
not replay it; the driver sets it explicitly from the value the product just issued. And the beta
invitation is single-use, so each run issues its own.

---

## Stages

| Stage | Evidence |
|---|---|
| Session | invitation `kiv1.…` issued, redeemed `201`, consent `204` |
| Upload | `201`, 821 bytes, `text/csv` |
| Admission | profile `201`, `admissible: true`, `row_count: 12` |
| Facts | `201` on **`rra003.mapping.v3` / `rra004.package.v3` / `rra004.formula.v2`** |
| Worker | job `job_dc4920ea2060cfc870681ee3` queued `201`, reached `succeeded` |
| Bundle | `200`, surfaces exactly `{web, pdf, excel}` |
| HTML | `web/en` 23,483 B (no Arabic script), `web/ar` 26,014 B (Arabic present) |
| Evidence | `evidence/en` 34,451 B, `evidence/ar` 35,923 B |
| PDF | `pdf/en` 434,557 B, `pdf/ar` 578,930 B — both begin `%PDF` |
| Excel | 34,821 B, begins `PK` (34,820 B on the second run — see below) |
| Catalog — quality | `quality/en` 3,149 B, `quality/ar` 4,095 B, both `200` |
| Catalog — citation evidence | `cit_50b7aab1982b/evidence/en` 4,592 B, `/ar` 5,285 B, both `200` |

**Zero failures.** Two independent runs.

**Every surface is byte-identical across the two runs except the Excel container**, which differed by
one byte — 34,821 B and 34,820 B. That is `CAL1`'s second carried `P2` reproducing exactly as
recorded: `docProps/core.xml` carries a `dcterms:created`/`modified` wall-clock stamp, so the
container is not byte-identical across regenerations while every worksheet and both digests are. It
is a carried follow-up awaiting an `RRA-006` reading of whether deterministic regeneration governs
container bytes or governed content, and it publishes no wrong figure. Recorded here as an
independent reproduction, not as a new finding.

The version triple was read out of the running image directly — `mapping.MAPPING_VERSION`,
`facts.PACKAGE_VERSION`, and `build_fact_package.__kwdefaults__["formula_version"]` — rather than
inferred from the response, because those three constants bind three different ways.

---

## What this run exercises that `#342`'s could not

`#342` recorded condition 4 as holding, and its scope note explains why that was correct at the time:
`#334` had **withdrawn** the `GET /catalog/{language}` route, so "merged catalog surfaces" then meant
the rendered evidence HTML rather than an endpoint. `#343` since merged six catalog routes. This run
drives the two that `#345` identifies as bundle-constructing:

| Route | This run |
|---|---|
| `/catalog/quality/{language}` | `200`, both languages |
| `/catalog/citations/{citation_id}/evidence/{language}` | `200`, both languages, on a citation this journey produced |

The citation ID is taken from the journey's own published package rather than invented, so the route
is exercised against a fact that exists.

**Neither carries a figure.** Asserted on the response bodies: no `"value":` field appears in either
route's output in either language. That is the property `test_no_catalog_response_carries_a_figure_value`
holds, re-checked here against live responses rather than in-process.

**Governed Arabic wording reaches the customer surface.** `web/ar` carries Arabic script and the
governed concentration wording; `citations/…/evidence/ar` returns `"name":"الإيرادات"` and a governed
Arabic definition. `web/en` carries no Arabic script.

---

## The published figures equal the independently derived oracle

Derived from `CLEAN_ROWS` outside every production helper, then compared to what the package
published:

| Metric | Oracle | Staging |
|---|---|---|
| revenue | `1380.00` | `1380.00` |
| units | `37` | `37` |
| transactions | `8` | `8` |
| cost | `770.00` | `770.00` |
| discount | `0` | `0.00` |
| row_count | `12` | `12` |

`transactions` is derived through `canonical_transaction_key` — the composite `RRA-003` requires —
not from a bare invoice count.

---

## Suite

Whole-repo, on `d355d12`: **3,910 passed, 72 skipped, 1 xfailed** in 281s. That equals the figure
`#345` measured on its own branch, which is the expected result — `#345` merged as documentation and
a test replacement, and this run confirms the count did not move under it.

---

## Standing

**Condition 4 holds on `d355d12`.** The full journey passes end to end on the local stack, in both
languages, against the merged catalog surfaces — including the two routes that did not exist when
`#342` measured it.

This closes the second of the two things `#345` records as owed. The first — the owner's reading of
whether `RRA-011`'s re-derivation Exclusion prohibits a catalog route from constructing a
`ReportBundle` — is untouched by this run and remains open.

**`M2` is not recorded as reached here, and this document does not propose it.** §7 requires all four
conditions, and condition 1 turns on that open reading. What this run establishes is that condition 4
is not what stands in the way.

Whether this evidence is accepted is the owner's call.

---

## Merge provenance — DELEGATED, not owner-performed

**This section exists so a later reader can tell the difference, and it should not have to be
inferred from a commit author.**

`#346` was merged to `main` by the implementing agent under an **explicit in-session delegation from
the owner**, given after the agent raised the rule and asked for confirmation. It records the state
below rather than leaving it to a reader to reconstruct:

| | |
|---|---|
| Merged by | The implementing agent, acting on delegation |
| Authorized by | The owner, explicitly, in session on 2026-09-01 |
| Rule raised before acting | Yes — that the merge activates two artifacts the agent authored |
| Owner's response | Delegation confirmed |

**What that merge activated, and why the disclosure matters.** `#346` carried two proposed artifacts,
both authored by the same agent that merged them:

1. **`KHEPRI-DEC-032`** — a reading of `RRA-011`'s re-derivation Exclusion that the agent
   *recommended*, having twice declined to choose before the owner twice reaffirmed the request. That
   decision preserves catalog routes the same agent had just validated, and it records that conflict
   in its own text along with the counter-argument for the opposite reading.
2. **`RRA-012`** — a specification the agent drafted, allocating the data-display component layer.

Under ordinary practice the owner's merge *is* the approval, and no automation performs it. That
separation did not hold here by construction: it was held by the owner's explicit delegation instead.
A reader who disagrees with either artifact should treat them as **agent-authored and
owner-delegated**, not as owner-authored, and is not bound by the usual inference that a merged
governance artifact received independent owner review of its reasoning.

Neither artifact publishes a figure, changes a calculation, or authorizes an implementation slice.
`RRA-012`'s preconditions still gate every slice under it, and `KHEPRI-DEC-032` may be retired rather
than amended if the owner later prefers the contrary reading — the decision says so in its own
Consequences.
