# `D1-02`–`D1-10` — The bounded allocation plan for the executive decision workspace

> **For agentic workers:** this is an **allocation** plan, the `G3-04`/`SV1` tier. It allocates one
> specification's thirteen requirements to nine slices and writes no code. Each slice below opens
> its own **execution** plan at build time — the `W1-09` tier, with `- [ ]` RED/GREEN/commit steps
> and literal test code — created with `superpowers:writing-plans` when that slice starts.
> REQUIRED SUB-SKILL at execution: `superpowers:subagent-driven-development` or
> `superpowers:executing-plans`.

**Goal:** Put a decision in front of an organization member on one navigable workspace — headline
figures, the limits on them, change, and supported breakdowns — with every figure traceable to an
exact semantic view and version, and no number derived anywhere else.

**Architecture:** Read models in `src/khepri/rca/workspace/decision/` that assemble `SV1`
projections into surface-ready structures and compute nothing; surfaces in
`src/khepri/runtime/shell_api.py` and `shell_templates/` under `RCA-002`'s frame; stylesheet rules
in `src/khepri/runtime/shell_assets/`. Every figure enters through
`SemanticQueryActions.request(...)` and leaves as a `ViewOutcome`. A read model is a *selection*
boundary: it selects, orders, groups for layout and passes through.

**Tech Stack:** Python 3.13, frozen dataclasses with `slots=True`, Jinja2 templates, pytest. No new
dependency, no SQLAlchemy model, no Alembic revision, no cache.

**Authority:** active `RCA-008` (`FR-159`–`FR-171`), merged 2026-09-10 at `2734886` (`#444`).

**Scope note this plan expands:** `D1-01`'s information architecture, on `main` at `8e6dc94` —
`docs/superpowers/plans/2026-09-10-d1-01-workspace-information-architecture.md`.
Roadmap: `docs/product/KHEPRI_MASTER_PRODUCT_ROADMAP.md` §PROGRAM D1.

---

## Global Constraints

Every slice's requirements implicitly include this section. Values are copied verbatim from the
governing artifact.

- **Scope is three paths and `tests/`.** `RCA-008` §Scope admits `src/khepri/rca/workspace/`
  ("decision read models only … New modules; `RCA-005`'s existing files are untouched"),
  `src/khepri/runtime/shell_api.py` and `shell_templates/`, and
  `src/khepri/runtime/shell_assets/` ("for the D1 surfaces only and for no earlier one").
- **A surface that computes is a defect** (`FR-159`, §Invariants). A read model "may select, order,
  group for layout, and pass through; it may not sum, average, difference, rank, score, normalize,
  threshold, or compute a percentage, and it may not read raw rows."
- **Every version is a literal** (`FR-160`). The `view_version` is "a literal constant in the
  reading module, never obtained at read time from `published_versions`, `published_history`, or
  any other enumeration of what the registry currently publishes."
- **A refusal is content, not an error state** (§Invariants, `FR-164`). Governed bilingual wording
  from `RRA-014`'s vocabulary, in the page language. No surface invents refusal text, softens a
  refusal, or substitutes a nearby figure.
- **No cache, ever** (`FR-168`): no cache, pre-aggregation, materialized view, sampling, or
  persisted projection. `FR-144` bars all of them from this path.
- **Nothing is retained** (`FR-169`, §Retention): no product-analytics or repeat-use telemetry, no
  new audit event, counter, access record or content-bearing log, and no retained preference,
  layout, filter, sort or dismissal state. `KHEPRI-DEC-015` §3 stands unamended.
- **Fail closed** (§Invariants): "no fallback, no partial projection, no nearby substitution, and
  no widening to unfiltered data."
- **Both empty rules render distinguishably** (`FR-163`). `stated_no_rows` ≠ `stated_absence`.
- **Bilingual parity on every surface** (`FR-171`). A figure, caveat, refusal or availability state
  present in one language is present in the other.
- **Every new file must score 10.00** in the required server-side CodeScene Code Health Review
  (§Verification). CodeScene gates cyclomatic >9, module mean >4, args >4, and cohesion —
  extracting helpers *raises* the mean, so prefer value-object grouping over flat parameter lists.
- **Run tests with `./.venv/Scripts/python.exe -m pytest`.** Do **not** run `ruff format` (no CI
  format gate); `ruff check .` only. Ruff counts characters, not bytes.
- **Every slice runs** `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`.
- **One PR per slice**, carrying a plan-and-RED commit then an implementation commit. Use
  `git commit -F <file>` (rebase ignores `-c commit.gpgsign`). Branch every slice off `main` —
  never stack a PR on another branch.
- **`governance/**` is untouched by every slice here.** The authority is already active.
- **`RCA-008` precondition 1:** a slice "identifies itself as `D1-02` through `D1-10` and stays
  within that slice's scope." `D1-11` is excluded by §Retention and is not in this plan.

---

## 1. The ordering constraint, stated once

`G3-04` fixed W1's order with one rule and `SV1` fixed its own with another. D1's rule is this:

> **A surface can only be qualified by a limit that some surface already produces, and only
> presented once something exists to present.**

That single sentence fixes the whole order. The read path must exist before a page can call it
(`D1-02` first). A card cannot select among four statuses until availability and the outcome kinds
are both reachable (`D1-03`). Breakdowns re-use the card contract rather than restate it
(`D1-04`). The evidence drawer hangs off figures that exist (`D1-05`), and the report workspace is
a refactor of a surface those figures now populate (`D1-06`). Filters are last among the
functional slices because `FR-166` makes them a claim about *what the earlier surfaces already
sent* (`D1-07`). Presentation without recalculation needs something to present (`D1-08`),
measurement needs something to measure (`D1-09`, after `SV1-08`'s precedent), and cross-cutting
parity evidence needs every surface to exist to be crossed (`D1-10`, last).

**Build order is numeric here.** The narrative order the reader experiences is *not* the build
order and `D1-01` §3 already said so: S-6 (Exceptions, Caveats and Refusals) is **second in the
narrative and cannot be built second**, because it reads every other surface's caveats. It is
built in `D1-04` and re-asserted in `D1-10`.

The one non-obvious placement is `D1-07` at position six rather than first. A filter bar looks like
scaffolding, but `FR-166` reclassifies it: the period is a *source selector*, the workspace is
scope resolved before any read, and only `store`, `product` and `category` are view filters. Those
three are properties of the surfaces that own them, so the control surface is assembled from
decisions the earlier slices have already made — not the other way round.

---

## 2. The seam, stated once

Every figure on every surface enters through one call and leaves as one value:

```text
SemanticQueryActions.request(SemanticQueryRequest(
    actor=SemanticQueryActor(account_id),
    organization_id=...,
    view=SemanticViewRequest(view_id, view_version, metrics, dimensions, filters),
    source_ids=(run_id, ...),
)) -> ViewOutcome(kind = admitted | refused | unavailable)
```

Three properties of that seam constrain every slice below, and none of them is negotiable:

1. **`view_version` is a literal in the calling module** (`FR-160`). Not a lookup, not a default,
   not a constant resolved from the registry at import time by enumeration.
2. **Each read is independently authorized and can independently answer `unavailable`**
   (`FR-165`). A surface renders partial success rather than failing whole, and the unavailable
   outcome is **content-free** — a surface may say a part is unavailable and may never say why.
3. **An unsupported filter refuses before projection** (`FR-137`, `FR-166`). Sending a parameter a
   view's `request_filter_allowlist` does not name does not get it ignored; it gets a refusal.

`D1-01` §5 established that a single metric card is **four projections plus the catalog**. That is
the acquisition cost `D1-09` is pointed at, and it is a property of the seam rather than of any one
surface.

---

## 3. File Structure

```text
src/khepri/rca/workspace/decision/          # NEW subpackage; RCA-005's files untouched
    __init__.py
    seam.py            # D1-02  the one call, the literal versions, the outcome envelope
    overview.py        # D1-02  S-1 read model
    card.py            # D1-03  the metric card contract and its four-status selection
    breakdowns.py      # D1-04  S-3, S-4, S-5a, S-5b read models
    limits.py          # D1-04  S-6: availability, caveats, refusals
    evidence.py        # D1-05  S-9 figure half; RRA-011 catalog supplies the definition half
    controls.py        # D1-07  source selector, resolved scope, the three real view filters

src/khepri/runtime/
    shell_api.py                            # every slice: routes, under RCA-002's frame
    shell_templates/decision_*.html.j2      # D1-03..D1-08
    shell_assets/workspace.css              # D1-03, D1-08, D1-10: decision-surface rules only

tests/                                      # every slice
```

`decision/` as a subpackage rather than flat files in `workspace/` is what keeps `RCA-008`'s "new
modules; `RCA-005`'s existing files are untouched" checkable by path rather than by review.

---

## 4. Slices

### `D1-02` — The read path and the executive overview read model

**Requirements:** `FR-159`, `FR-160`, `FR-163`, `FR-165`, `FR-168`.

Builds `seam.py` and `overview.py`. The seam module holds the eight `view_version` literals and the
single call shape; `overview.py` is S-1 — the ten core metrics for one run from
`ExecutiveOverviewView`, output fields in published order, `stated_absence` as its empty rule.

**This slice settles "from SV1 only" by construction.** `FR-159` governs figures, not pages, so
`overview.py` may take structure from elsewhere and figures from nowhere else. `D1-01`'s first
finding is closed here and not re-litigated downstream.

**No route.** This is the read model and its tests only; `D1-03` is the first slice with a surface.
Splitting them is what lets the arithmetic ban be asserted against a module with no template noise
in it.

**Acceptance:** the static no-arithmetic and no-raw-row check over `decision/` (the check itself,
plus its first subject); versions are literals, asserted by grepping the module and by resolving
each against the registry; an unavailable read yields a content-free outcome; both empty rules are
distinguishable in the read model's own output, before any renderer sees them.

---

### `D1-03` — Headline KPIs, the metric card, and the change summary that is not yet reachable

**Requirements:** `FR-161`, `FR-162`, `FR-164`, `FR-170`, plus `FR-171` for this surface.

Builds `card.py` and the first decision surface. The card exposes `RCA-008` `FR-162`'s eleven
lines, and its four-status selection comes from three inputs `D1-01` §5 already mapped:
`ViewOutcome.kind` gives *refused* and *unavailable*; `MetricAvailabilityView` gives
`available`/`partial`/`unavailable`; *caveated* is an admitted projection with non-empty `caveats`.
**Selection among four presentation states is presentation; counting or scoring them crosses
`FR-159`.**

> **The roadmap row for `D1-03` is "headline KPIs **and change summary**", and the change summary
> is S-2 — the Period Comparison surface whose source `FR-170` holds open.** This slice therefore
> ships the KPIs and, for the change summary, **an asserted absence**: the surface states that the
> comparison is unreachable and a test asserts it, on the discipline `SV1-04`, `SV1-07` and
> `SV1-08` used for exactly this shape. The assertion is removed by the slice that makes the source
> reachable — not by this one, and not by `D1-08` or `D1-10`.

**Acceptance:** every `FR-162` line is reachable from the card directly or in one action; the
four-status selection is exhaustive over its inputs and derives nothing; an incompatible comparison
renders as `ViewRefusal.wording` in the page language rather than an invented string; `FR-170`'s
unreachability assertion fails if the Period Comparison source ever becomes reachable without this
assertion being removed deliberately.

---

### `D1-04` — Breakdowns, and the limits surface that qualifies them

**Requirements:** `FR-159`, `FR-163`, `FR-165`, `FR-167`.

Builds `breakdowns.py` (S-3 Branch, S-4 Product/Category, S-5a Basket, S-5b Concentration) and
`limits.py` (S-6). S-5 is **one surface reading two views**, and `FR-165` makes those reads
independent: Basket may be admitted while Concentration is unavailable, and the surface renders
that rather than failing whole.

**`FR-167` is this slice's hard edge and `D1-01`'s F-4 is why.** `MetricAvailabilityView` publishes
no series metric, so **no per-store, per-product or per-category figure may carry a four-state
availability**, and none may be synthesized from the core metric it aggregates. A breakdown figure
is qualified only by its own projection's caveats and population qualifiers and by the outcome that
fetched it. A slice that reaches for the core metric's availability to fill the gap has invented a
figure's status.

**`stated_no_rows` versus `stated_absence` earns its own tests here**, because S-3 and S-4 are the
two surfaces whose empty rule is `stated_no_rows` while every other surface's is `stated_absence`.
A store filter naming a store with no sales is not a refused measure.

**Acceptance:** each breakdown reads only its own view at its literal version; S-5's two reads
succeed and fail independently; a breakdown figure carries no four-state availability, asserted
negatively; the two empty rules render differently on the same surface.

---

### `D1-05` — Metric detail and the evidence drawer

**Requirements:** `FR-159`, `FR-161`, `FR-162` (evidence action), `FR-164`.

Builds `evidence.py` and wires the drawer. **The drawer is two halves from two authorities**: the
*definition* half — label, formula, bilingual wording — is `RRA-011`'s catalog, which `T1-05`
shipped; the *figure* half is `ReportEvidenceView`. `FR-159` admits the first because it is
structure, not a figure.

**No D1 surface may present evidence absence as a view refusal.** `D1-01` §4 established that every
view's `required_evidence` is `()` at v1 and that this is not an oversight to correct in D1:
`FR-141` makes a required-but-absent evidence code a refusal cause, and the v1 registry requires
none. Absences arrive as `ViewProjection.evidence_absences` — data on an admitted projection.

**Acceptance:** the drawer is reachable from every figure on S-1, S-3, S-4 and S-5 and is never a
page of its own (`FR-161`); definitions come from the catalog and figures from the view; an
evidence absence renders as data, not as a refusal.

---

### `D1-06` — The navigable report workspace

**Requirements:** `FR-159`, `FR-161`, `FR-165`.

Refactors the existing report page into a navigable workspace reading the `RRA-006` report bundle
and `RCA-005` analysis detail. **S-8 is a surface `D1-06` refactors rather than builds**, and S-7
(Recent Analyses and Comparisons) reads `RCA-005` workspace records and pins.

**Neither is an `SV1` read, and S-7 could not be one at any view version** — no published
projection ranges over runs; `ScopedSourceReader.get_analysis_run` reads one run by id. `FR-159`
admits both because the rule governs figures.

**The `RCA-005` boundary is the risk in this slice.** `RCA-008` §Scope permits *new modules* under
`src/khepri/rca/workspace/` and §Exclusions bars edits to `RCA-005` source paths, while
§Not-in-scope names "workspace persistence and the comparison request/result routes." A refactor
that needs to change `persistence.py`, `pins.py` or `store.py` is mis-sliced and needs the owner,
not a workaround.

**Acceptance:** the workspace reads records and bundles for structure and derives no figure; a
record read that is unavailable degrades that region only; no file under `RCA-005`'s paths is
modified, asserted by path.

---

### `D1-07` — Visible controls, modelled as what they actually are

**Requirements:** `FR-166`, plus `FR-164` for the refusal path.

Builds `controls.py` and the control surface. **`D1-01`'s F-2 is the whole of this slice**: no
published view names `period` in `request_filter_allowlist` and five name no request filter at all.

| Control | What it actually is |
|---|---|
| Period | A **source selector** — choosing a completed run, i.e. a `source_id` |
| Workspace | The organization scope, resolved by `resolve_scope` **before any read** |
| `store`, `product`, `category` | The only real view filters, on the three views that admit them |

**A filter bar that passes a period into `ExecutiveOverviewView` gets a refusal, not an unfiltered
overview**, because `FR-137` refuses an unsupported filter *before* projection rather than dropping
it. That is the failure this slice exists to make structurally impossible.

`FR-166` also requires every effective filter be visible **in the request and the result** — the
`EffectiveRequest` on the outcome, not a copy the surface keeps. And `FR-169` bars retaining any of
it: no remembered filter, sort, or layout state, per viewer or otherwise.

**Acceptance:** no surface sends a parameter a view's allowlist does not name, asserted per view;
a period is carried as a `source_id` and never as a filter; the effective filters shown come from
the outcome; nothing is persisted between requests.

---

### `D1-08` — Presentation without recalculation

**Requirements:** `FR-159`, `FR-168`, plus §Retention.

Print and stable presentation for the decision surfaces, in `shell_assets/` and the templates.

**This slice is narrower than its roadmap row and the narrowing is `RCA-008`'s, not a judgment
call.** The row reads "print/export/snapshot behavior without recalculation." Of those three:

- **Print** is in scope — stylesheet rules for the decision surfaces, which §Scope claims for D1.
- **A stored snapshot is excluded.** §Retention: the surfaces "retain nothing of their own," and
  §Exclusions bars "no persistence schema change, migration, or new stored column." A snapshot that
  survives the request is a stored projection, which `FR-168` also bars.
- **Export needs the owner.** §Exclusions bars "no cross-organization access, sharing, or export."
  Whether the modifier reaches all three nouns or only the first is not resolvable from the
  document, and a slice may not resolve it by choosing the reading that lets it ship. **Raise it;
  do not decide it.**

"Without recalculation" is satisfied structurally rather than by discipline: `FR-159` already
means there is no calculation to repeat. A print view re-renders the same outcome.

**Acceptance:** print rules apply only to decision surfaces; no stored snapshot, no new column, no
cache; the printed figures are the rendered figures, asserted by comparing against the same
outcome.

---

### `D1-09` — Latency behavior, pointed at acquisition

**Requirements:** `FR-168`, and `RCA-008` §Verification's measurement discipline.

**`SV1-08`'s ledger §3a already fixed this slice's target and it is not projection.** The composed
request measures 4003 µs p50 end to end, of which projection is 11.6 µs — about one part in 345.
Optimizing projection would move nothing.

**And `FR-168` removes the usual instruments.** No cache, pre-aggregation, materialized view,
sampling, or persisted projection; "performance work is a change to a governed artifact and not a
surface decision." What is left is legitimate and is where the cost actually is:

- **The number of reads per surface.** `D1-01` §5: a single card is four projections plus the
  catalog. A surface of ten cards that issues forty reads multiplies *acquisition*.
- **Coalescing reads within one request** — issuing one read whose result serves several cards
  instead of one read per card. This is not caching: nothing survives the request, and nothing is
  reused across requests. A slice that keeps a result *between* requests has built a cache and
  crossed `FR-168` whatever it is called.

**Acceptance:** a measured baseline per surface in the `SV1-08` ledger's shape; read counts asserted
per surface so a later slice cannot quietly multiply them; nothing retained between requests,
asserted rather than reviewed.

---

### `D1-10` — Cross-cutting parity and refusal-state evidence

**Requirements:** `FR-171`, and a re-assertion of `FR-163`, `FR-164`, `FR-165`, `FR-167`, `FR-170`
across every surface at once.

**This slice is materially narrower than its roadmap row, and the gap is an owner item rather than
a scheduling detail.** The row reads "Arabic/English parity, RTL, accessibility, mobile, visual
regression, and refusal-state tests." `RCA-008` §Exclusions authorizes "no chart grammar,
navigation, accessibility-evidence, or visual-regression programme beyond the tests its Verification
names, **which remain `U1-03`, `U1-05`, `U1-06` and `U1-07`'s and need their own authority**."

| Roadmap item | Authorized here? |
|---|---|
| Arabic/English parity over figures, caveats, refusals, availability | **Yes** — `FR-171`, named in §Verification |
| Refusal-state tests | **Yes** — §Verification names them |
| Cross-organization isolation on every surface | **Yes** — §Verification names it |
| RTL, mobile | **Partly** — as parity evidence, not as a layout programme |
| Accessibility-evidence programme, visual regression | **No** — `U1-05`/`U1-06`/`U1-07`, own authority needed |

So `D1-10` closes D1's own evidence and **does not close the roadmap row**. The remainder is `U1`'s,
and `U1` is itself blocked on the owner's `RRA-010` journey-adoption reading.

**Acceptance:** parity over figures, caveats, refusals and availability states in both languages;
cross-organization isolation on every surface; every refusal state reachable and correctly worded;
the `FR-170` unreachability assertion still standing.

---

## 5. What this plan does not do

- **It does not bind the Period Comparison source.** `RCA-008` §The open question and precondition
  2: the binding is a composition-root change in a file `RCA-007` §Scope already governs, and two
  active specifications over one file is the ambiguity this repository fails closed on. **A
  successor composition artifact is the precondition**, and it is owner-authored. No slice here may
  reach for it.
- **It does not schedule `D1-11`.** `RCA-008` §Retention: `KHEPRI-DEC-015` §3's prohibition on
  repeat-use telemetry "is not amended here and `D1-11` stays unauthorized."
- **It does not authorize `U1`'s programme.** Precondition 3 makes `U1`'s chart grammar,
  navigation, accessibility and visual-regression tasks *not preconditions* for D1 — which is what
  unblocks these nine slices while `U1` waits on `RRA-010`. It equally means they are not
  authorized here.
- **It does not resolve the export reading in `D1-08`.** Stated as an owner item, not decided.
- **It writes no code and no test.** Each slice opens its own execution plan.

---

## 6. Sequencing summary

| Slice | Builds | Blocked by | Ships a surface? |
|---|---|---|---|
| `D1-02` | seam + S-1 read model | — | No |
| `D1-03` | metric card, headline KPIs, S-2 asserted absent | `D1-02` | Yes |
| `D1-04` | S-3, S-4, S-5a, S-5b, S-6 | `D1-03` | Yes |
| `D1-05` | S-9 evidence drawer | `D1-04` | Yes |
| `D1-06` | S-7, S-8 report workspace | `D1-05` | Yes |
| `D1-07` | source selector and the three real filters | `D1-04` | Yes |
| `D1-08` | print and stable presentation | `D1-03`…`D1-07` | Yes |
| `D1-09` | acquisition baseline and read-count bounds | `D1-08` | No |
| `D1-10` | parity, isolation, refusal-state evidence | all above | No |

**Three things the owner decides, none of which this plan may take:**

1. **The successor composition artifact for Period Comparison.** Without it, `D1-03` ships an
   asserted absence and **D1 does not satisfy M4's "compare governed periods."**
2. **The export reading in `D1-08` §Exclusions** — whether "cross-organization" reaches "export."
3. **`U1`'s authority**, which `D1-10` cannot substitute for, and which waits on `RRA-010`.
