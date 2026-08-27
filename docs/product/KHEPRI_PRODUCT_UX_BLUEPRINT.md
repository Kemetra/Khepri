# Khepri Product UX Blueprint

**Baseline:** `df9f1d1` (`origin/main`), 2026-08-26.
**Proposed reconciliation:** `ed57967` (`origin/main`), 2026-08-27, on branch
`docs/ux-blueprint-reconcile` — adds §5.1 Integrated Customer Experience Map; **proposes** resolving
the `W1-05` navigation conflict (§8, formerly CONFLICT-BLOCKED) via a companion roadmap amendment;
adds M2 data-intake/processing/Fix & Continue direction (§6) and M3 repeat-use direction (§7.3/§7.4);
adds Mobile/Branded Report/Secure Share/Ready Notification (§16) and guided-exploration/Ask
Khepri/Try Sample Analysis pointers (§22). **Per `governance/CONSTITUTION.md` Article II, this remains
a proposal until the owner merges it to `main`** — the `W1-05` reconciliation and every `LOCKED`
marker this PR introduces are effective only on merge; verify against `git log` on `main` before
treating them as governing. Sections not touched by this reconciliation were not re-verified against
`ed57967` and still read at `df9f1d1`.

## 1. Purpose and authority

This is Khepri's single current **product UX reference**. It records how the customer understands the
product, the information architecture, page responsibilities, journeys, trust and evidence
presentation, responsive and bilingual expectations, milestone evolution, and what is locked versus
provisional.

**It grants no implementation authority.**

```
Active governance / specifications / decisions
        ↓
Master Product Roadmap
        ↓
KHEPRI_PRODUCT_UX_BLUEPRINT.md   ← this document
        ↓
Implementation plans / visual execution
```

If this blueprint conflicts with active authority, **authority wins** and the blueprint must be
reconciled before implementation. A decision recorded here is product direction, not permission:
`governance/CONSTITUTION.md` Article IV still admits product code only in small, independently
verifiable slices linked to an active specification, and this document is not one.

### Status vocabulary

Every substantial decision below carries one of these:

| Status | Meaning |
|---|---|
| **LOCKED** | Owner-approved product direction; safe to carry forward in later shaping. |
| **PROVISIONAL / CONTRACT-BLOCKED** | Direction exists; exact behavior depends on a contract that is not yet active. |
| **AUTHORITY-BLOCKED** | Desired UX is known; implementation requires governance authority that does not exist. |
| **IMPLEMENTATION-BLOCKED** | Contract or authority may exist; the supporting capability is not built. |
| **SHIPPED** | Verified in the current implementation at the baseline SHA. |

A well-drawn wireframe is not "ready to build". Readiness is a property of contracts and authority,
never of design completeness.

### Sources reconciled

`AGENTS.md`; `governance/CONSTITUTION.md`; `governance/registry.yaml`; the Master Product Roadmap;
active `RCA`/`RRA` specifications governing customer surfaces; the merged M2 UX critique
(`docs/superpowers/specs/2026-08-25-m2-ux-design-critique.md`); the `R6-01` authorization matrix
design note (`docs/superpowers/specs/2026-08-15-r6-01-authorization-matrix-design.md`), read as
**implementation evidence only** — `governance/registry.yaml` admits `family`, `specification`, and
`decision`, so a design note carries no authority; and the M3 Workspace UX Shape report, read as
**design input, not repository authority**.

`docs/ui/design_handoff_khepri/` (the dark "Nocturne" handoff) is **not** visual or UX authority
where it conflicts with the shipped product.

---

## 2. Product UX principles

Khepri is not a generic BI dashboard. It is a governed retail decision product where:

- semantic admission happens before any claim is made;
- facts are deterministic and versioned;
- evidence is reachable from the claim it supports;
- unsupported conclusions are explicitly refused rather than approximated;
- Arabic and English are equal product surfaces;
- **the interface never invents capability the system does not possess.**

Primary characteristic: **calm, enterprise, evidence-first.**

Avoid: generic SaaS feature walls; fake dashboards; dead "Coming Soon" navigation; a large sidebar by
default; cards nested inside cards; decorative gradients; badge soup; decoration with no product
function.

---

## 3. Customer mental model

A retail operator, not an analyst. They think in **submissions and answers**:

> "I sent you last quarter's sales file. You told me what it said. Where is that, and is it still
> there?"

**LOCKED — the customer-visible scope is the Organization.** "Workspace" is an internal domain
concept and does not appear as a redundant primary customer noun. It remains useful in architecture
and contracts.

```
KHEPRI
└── Organization
    ├── Overview
    ├── Data
    ├── Analyses
    └── Team
```

| The customer wonders | The product must answer |
|---|---|
| Did my file arrive, and could you use it? | admission outcome on the data entry |
| What did you conclude? | the analysis and its report |
| Can I trust all of it? | which results were supported, and where they were not |
| Is it still available? | retention state, in absolute time |
| What do I do now? | one obvious next action |

---

## 4. Milestone evolution

The experience evolves; it is not one final UI delivered late.

### M2 — design-partner analysis experience (current)

```
Organization chooser → Commercial shell → Start analysis → Focused RRA journey → Report / evidence / artifacts
```

**The shell and the journey are separate product modes, by design.** The shell carries organization
and commercial context; the journey is focused task mode for completing one analysis. This separation
is intentional and is **not** an architectural defect to be corrected.

### M3 — durable history

Adds product memory. It answers what data was submitted, what analyses exist, what happened to them,
which report belongs to which analysis, whether content is still retained, and what to do next.

**M3 is not the executive dashboard.**

### M4 — decision workspace — FUTURE SHAPING REQUIRED

Direction only: an executive overview, period comparison, branches, products and categories, basket,
concentration, explicit limitations and refusals, contextual evidence, and governed exploration where
authorized. **No M4 page-level UX is specified here.**

**"What Changed?" as the entry narrative — direction only, `D1` gated.** Where M4 shapes the decision
workspace, the proposed direction leads with the decision story rather than a wall of charts:
*What Changed? → Executive Summary → major movements → important findings → items needing attention →
deeper KPIs/charts/breakdowns.* This is `D1-03`'s headline-KPIs-and-change-summary wording, read as an
information hierarchy rather than a flat module list; it does not add a task and does not pull the
decision workspace into M3. **This is not a directive to turn M3 Overview into an analytics
dashboard** — §7.1 excludes KPI cards, charts, and business metrics from Overview by name, and that
exclusion is unchanged by this direction.

---

## 5. Global information architecture

```
KHEPRI │ {Organization} │ {Language}          ← persistent frame

M2   Organization chooser
     └── Commercial shell ── Team                        [SHIPPED]
          └── Start analysis → RRA journey → report · evidence · artifacts

M3   Organization
     ├── Overview
     ├── Data          البيانات
     │    └── Data detail        → analyses that used it
     ├── Analyses      the durable history spine
     │    └── Analysis detail    → report · evidence · PDF · Excel
     └── Team
```

---

## 5.1 Integrated Customer Experience Map

**This is the canonical end-to-end journey.** It exists so a designer, product owner, Claude Code, or
Codex can see the whole customer path in one place without reconstructing it from every section below.
It duplicates no detailed prose — each phase links to the section that defines it, and each phase
names the milestone(s) that own it. Where a phase's capability is not yet authorized, that is stated
here in the same breath as the phase, not left implicit.

**Primary M2 path — the current, shipped one-time journey shape, no M3 dependency:**

```text
Try*
  → Enter organization → Start (new) → Upload → Pre-check → Confirm
  → Analyze → Result (report · evidence · artifacts)

*"Try" is entering an organization the customer already has invited access to
 (Commercial shell, SHIPPED). A pre-authentication sample is a separate,
 AUTHORITY-BLOCKED capability — see §21 and §22.
```

**M2 direction, not yet in the current journey — does not gate the primary path above:**

```text
Confirm → Impact Preview → Analyze        (data CONTRACT-BLOCKED on T1; the journey step itself is
                                            AUTHORITY-BLOCKED — RRA-010 excludes new journey phases,
                                            and no such step exists in the shipped journey today)
```

**M3 branches — optional, do not gate the M2 path above:**

```text
Enter organization → Start → Resume       (Draft Safety, W1-04 saved-setup resume)
Upload → Recognize → Pre-check            (Remember My Data, W1-01 profile, for a repeat source)
Result → Analysis detail                  (M3's durable home for the same result — §7.4)
```

**From the Result, in any milestone that has shipped its own authority:**

```text
Result ─┬─ Evidence / Why              (§10, contextual, M2 SHIPPED)
        ├─ Fix when possible           (§6 Fix & Continue, AUTHORITY-BLOCKED)
        ├─ Run Again / Compare         (§7.3 Run Again M3 CONTRACT-BLOCKED ·
        │                               G4/C1 Compare M4 BLOCKED)
        ├─ Export / Share              (§7.4 Analysis detail M3 ·
        │                               §16 Secure Share, future AUTHORITY-BLOCKED)
        ├─ Return next period          (§7.3 Run New Period, M3 CONTRACT-BLOCKED)
        └─ What Changed                (M4 enrichment of the same result, not a
                                         replacement for it — FUTURE SHAPING REQUIRED)
             ├─ Explore                 (X1-02, optional inside M4 or post-M4)
             └─ Guided questions        (X1-04, post-M4 only — not in the
                                          roadmap's M4-eligible X1-01..03)
                  ├─ Save Answer        (X1-05 Saved Answers, post-M4)
                  └─ Ask Khepri later   (G9/AI1, PROPOSED, later)
```

**All phases, primary path and branches together** — "Milestone" names which milestone owns the
phase, not a required stop on the way to the next row:

| Phase | Section | Milestone | Status |
|---|---|---|---|
| Try / Enter organization | §6 | M2 | Commercial shell SHIPPED; pre-auth sample AUTHORITY-BLOCKED |
| Start (new) | §6 | M2 | Current path, no Resume/Recognize dependency |
| Resume (branch) | §6, §7.3 | M3 | Draft Safety is `W1-04` saved-setup resume; CONTRACT-BLOCKED on active `G3`; optional, does not gate Start |
| Upload | §6 | M2 | Current one-time path, LOCKED shape |
| Recognize (branch) | §6 | M3 | Remember My Data is `W1-01`'s profile contract; CONTRACT-BLOCKED on active `G3`; optional, does not gate Pre-check |
| Pre-check → Confirm | §6 | M2 | LOCKED shape |
| Impact Preview → Analyze | §6 | M2 | Impact Preview data CONTRACT-BLOCKED (`T1`), journey step AUTHORITY-BLOCKED (`RRA-010` excludes new journey phases); processing states SHIPPED pattern |
| Result: report / evidence / artifacts | §6, §7.4, §16 | M2 / M3 | M2 journey result SHIPPED; M3 Analysis detail CONTRACT-BLOCKED |
| Evidence / Why | §10 | M2 | Contextual only, LOCKED; already reachable from the SHIPPED M2 result |
| Fix when possible | §6 | M2 | AUTHORITY-BLOCKED — needs an active RRA specification, not `R8-10` |
| What Changed (M4 enrichment) | §4, §22 | M4 | FUTURE SHAPING REQUIRED — adds to the M2/M3 result, does not gate it |
| Explore | §22 | M4 optional / post-M4 | `X1-02` may ship inside M4 per roadmap `X1`; PROPOSED |
| Run Again / Compare | §7.3, `G4/C1` | M3 / M4 | Run Again CONTRACT-BLOCKED; Compare BLOCKED (no `G4` authority) |
| Export / Share | §7.4, §16 | M3 / future | Export Center resolved into Analysis detail; Secure Share AUTHORITY-BLOCKED |
| Return next period | §7.3 | M3 | Run New Period CONTRACT-BLOCKED |
| Guided questions | §22 | post-M4 | `X1-04` is outside the roadmap's M4-eligible `X1-01`–`X1-03`; PROPOSED |
| Save Answer | §22 | post-M4 | `X1-05` Saved Answers, PROPOSED — reopenable decision artifact, distinct from Run Again |
| Ask Khepri | §22 | later | `G9/AI1`, PROPOSED, boundary unchanged |

**Reading this map correctly:** every arrow is a customer-visible transition, not an implementation
guarantee. A phase marked CONTRACT-BLOCKED or AUTHORITY-BLOCKED is real product direction with no
current authority to build it — see §18/§21 for the exact dependency. This map does not itself unblock
anything; it exists so those dependencies are visible in one place.

---

## 6. M2 experience

### Commercial shell — SHIPPED

A compact persistent frame: the KHEPRI wordmark as home, the active organization context where
authority permits, Team, and a language control **where a valid same-surface target exists**.

**`FR-049` principle — LOCKED.** Navigation grows only when real surfaces ship. Nothing is
preannounced: no reports history, metrics, settings, watchlists, ask-Khepri, integrations, or
billing. **No "Coming Soon".**

The language control is offered only where the frame can name a destination for it. Two surfaces opt
out deliberately — a `POST`-result page with no address of its own, and the shared unavailable
surface, which may not name what the reader was asking about. Parity holds because both languages
render the surface and neither offers the control.

### Journey — SHIPPED

Focused task mode. **Workspace navigation is not added inside it.**

### Data intake and understanding — progressive, not one opaque step

**LOCKED product direction.** Uploading is not one action; semantic understanding is proven, not
assumed. The journey progressively establishes:

```text
Upload → recognize source → understand data (pre-check) → confirm mapping
  → show analysis impact → analyze
```

The interface must not imply the system understood the data's meaning before governed admission
(`RRA-003`) proves it. Each stage names what Khepri has confirmed so far, not what it eventually
concludes.

**This is the full end-state direction, not the current M2 minimum.** `recognize source` is the M3,
`W1-01`-owned Remember My Data capability (below) and is CONTRACT-BLOCKED on active `G3`. The current
M2 journey runs the remaining stages as one-time *Upload → Map (pre-check/confirm) → Analyze* without
recognition — a first-time source path only, since M2 does not persist a reusable profile across
sessions.

- **Data Pre-check — LOCKED shape, CONTRACT-BLOCKED content.** Before analysis, the customer sees what
  Khepri understood, what is missing, what coverage is known, what needs the customer's confirmation,
  and which analyses look supportable. It does not compute or promise an unsupported business result.
- **Analysis Impact Preview — CONTRACT-BLOCKED on its data, AUTHORITY-BLOCKED as a journey step.**
  Before the analysis step runs, show capability availability drawn from the `T1` availability
  vocabulary — for example *Revenue: Available*, *Margin: Unavailable — cost basis not established*,
  *Basket: Partial*. **This is availability, not a confidence score; it must not invent certainty.**
  The underlying contract is `T1-04`'s, gated on active `T1` authority. **Rendering it as a new
  pre-analysis step inside the `/beta` journey needs its own RRA authority** — active `RRA-010` governs
  only presentation changes to the existing journey and excludes any new workflow state or phase, and
  no Impact Preview step exists today for a presentation change to modify.

**M3, not M2 — belong to the durable-workspace program, not the current one-time journey:**

- **Recognize source / Remember My Data — PROVISIONAL, M3 product direction.** For a repeat submission
  from a source the organization has used before, Khepri should be able to offer an approved
  source/mapping profile for review rather than a blank mapping step: first run is *Upload → Map →
  Confirm → Analyze*; a later run from the same source is *Upload → "We recognized this format" →
  Review → Analyze*. **A materially changed source must not silently reuse a prior mapping** — that
  would skip semantic admission rather than confirm it (Article V, fail-closed). Owned by `W1-01`'s
  reusable source/mapping profile contract, CONTRACT-BLOCKED on active `G3`. The current M2 journey is
  the one-time *Upload → Map → Confirm → Analyze* path only; recognition is not part of the M2 minimum.
- **Draft Safety — LOCKED direction, CONTRACT-BLOCKED persistence, M3.** Work in progress during
  mapping, coverage, or setup should be savable and resumable rather than lost on interruption — *Save
  setup / Resume later*. Owned by `W1-04`'s saved-setup resume operation, CONTRACT-BLOCKED on active
  `G3`. Exact persistence and retention semantics belong to `G2`/`G3`/`W1`, not to this document.

### Processing journey — real states only

**LOCKED.** The customer sees only real runtime states — for example *Validating*, *Mapping*,
*Analyzing*, *Reconciling*, *Building results*. **No fake percentages, fake ETAs, fake queue
positions, or simulated progress.** This matches the shipped indeterminate-progress treatment: a bar
that does not know its position does not report one.

### Fix & Continue — desired M2 direction, AUTHORITY-BLOCKED

**LOCKED direction, AUTHORITY-BLOCKED implementation.** Where a pre-check or refusal cause is
customer-correctable within the current session, the desired journey returns to the relevant
mapping/attestation step rather than forcing a full restart:

```text
Refuse / identify problem → explain → return to the relevant step → correct → resume
```

A refusal whose cause the customer cannot correct is not offered a false path back.

**This is not `R8-10`'s to build, and no current authority grants it.** Active `RRA-010` governs only
presentation changes to the existing journey and explicitly excludes "a new workflow state, step, or
journey phase" and any capability the runtime does not already serve. Today the review step *displays*
the confirmed mapping without letting the customer edit it, and `Restart` deletes the session outright
rather than preserving progress — so an editable return-and-resume path is a new workflow capability,
not a presentation fix, and needs an active RRA specification naming it before any implementation task
exists. Resuming a **saved, closed** session is a separate, already-scoped capability: Draft Safety
(above) and `W1-04`'s resume operation, gated on active `G3`.

### Authority gap — organization identity in the journey

**LOCKED product direction + AUTHORITY-BLOCKED implementation.**

The desired future UX makes the organization identity clear while the customer is in `/beta`. Current
authority deliberately prevents commercial organization identity from reaching the RRA journey —
`open_commercial_session` takes an opaque owner identifier so that no account id, organization id,
name, slug, or email reaches it, and the isolation holds *by absence rather than by inspection*.

**This is not shipped and must not be described as shipped.** Closing it requires authority that
permits organization identity to cross that boundary, which no current artifact grants.

---

## 7. M3 experience

### 7.1 Overview — operational orientation, not analytics

**LOCKED purpose.** Overview answers: what happened most recently, is anything processing, what data
is available, does anything need attention, is content expiring, and what is the next valid action.

One dominant action: **New analysis**, where authorized.

Content: latest analysis with its state; latest data state; retention notice; an attention section
**rendered only when non-empty**; and recent activity **only if the capability exists** (§7.5).

**Explicitly excluded** — revenue KPI cards, sales charts, branch ranking, category performance,
basket analytics, concentration analytics. Those belong to reports and M4. An always-present "no
issues" panel is decoration, not reassurance.

### 7.2 Data

Customer-facing Data explains what was submitted, when, whether it was admitted, the relevant
coverage state, which analyses used it, and its retention state.

Customer rows do **not** lead with mapping versions, formula versions, digests, or internal contract
identifiers. Those belong to contextual evidence and audit detail (§10).

Customer vocabulary: **Data**, and where more specific language helps, *data files* and *data
versions*. `DatasetVersion` is an internal domain term and does not appear on screen.

**Not designed, no authority:** raw-row browsing, generic SQL exploration, file preview.

### 7.3 Analyses — the single history spine

**LOCKED.** An analysis history item answers: when it ran, which data entry it used, its operational
state, its trust state, whether the report is available, its retention state, and the next valid
action.

Default order newest first. **No filtering system in M3** unless a real product need and contract
later justify one. **No Compare in M3.**

Per state: a completed analysis opens; a processing analysis **shows its state without promising a
durable progress page** unless a future contract provides one; a deleted analysis is a minimal
tombstone with no content action, where the retention decision permits a record to remain at all.

**Run Again / Run New Period — LOCKED direction, CONTRACT-BLOCKED.** Repeat use is a first-class
journey: where authorized, an analysis or its history entry offers running the same configuration
again or against a new period. **The prior configuration is reused only where it remains
compatible**, and the customer can see what will be reused before confirming — this is not a silent
re-run. Owned by `W1-04`; whether reuse is safe for a given configuration is the same fail-closed
compatibility question `RRA-003`/`RRA-004` govern for the underlying facts, not a new UX-only rule.

### 7.4 Analysis detail and artifacts

**LOCKED — no separate Reports index in M3.** Analysis detail is where deliverables are discovered.
Where available: open report, evidence, download PDF, download Excel. A second list of the same
objects would create two places a retention state can disagree. **This is also where "Export Center"
in the owner's customer-journey outline resolves**: export/download actions for a given analysis'
report, evidence, and Excel artifact live here, as an affordance within Analysis detail — not as a
sixth primary navigation destination or a second discoverable index (see §8, proposed-reconciled
pending merge).

**The governed report bundle's PDF is not on-demand and must not become so.** Active `RRA-006`
requires web, PDF, and Excel to publish together as one reconciled bundle, and `ReportPublication`
rejects any set naming fewer than every required surface — `RRA-006`'s own words are "treat partial
export failure as an incomplete bundle." On-demand generation is desired direction only for a
possible *future* `D1-08` export/snapshot mechanism distinct from this governed bundle, and any such
mechanism would need its own reconciliation with `RRA-006` before it could apply to the same
artifact. Analysis detail exposes the governed bundle's PDF as already generated, not generated on
request.

**Analysis Passport — LOCKED direction, CONTRACT-BLOCKED.** A compact identity/provenance summary for
the analysis, drawn from `W1-06`'s immutable provenance record: reporting/data period,
organization/data reference, branch/scope coverage, event/row scale where appropriate, coverage
state, run timestamp, and analysis/methodology version context. **Digests and machine identifiers
stay behind contextual audit detail** (§10), never leading the passport itself.

**Methodology Change Notice — LOCKED direction, CONTRACT-BLOCKED.** When a prior and later analysis
differ because governed mapping or formula/family versions changed, the customer is told —
conceptually, *"Analysis methodology changed since the previous run."* — with the specific change
reachable, not buried. **This must not imply numeric comparability where the versions are
incompatible.** This is `W1-08`'s existing version/availability-diff capability, presented to the
customer; it is not a second version subsystem. **A semantic-view version notice is out of `W1-08`'s
M3 scope** — `SV1` view definitions do not exist until after `C1`, which itself starts only after
M3/`W1`; extending the same principle to view versions is a later `SV1`/`D1` concern.

### 7.5 Activity

**LOCKED.** A standalone Activity destination is **not required for M3 launch**. Where the capability
exists, show concise recent activity and retention context on Overview. Where it is absent, **Overview
remains complete without it** — M3 navigation does not depend on Activity shipping.

A dedicated Activity surface requires later evidence that the volume and value of events justify its
own destination. An events tab without that evidence becomes an admin log.

---

## 8. Navigation model

**LOCKED — primary M3 customer navigation:**

| English | Arabic |
|---|---|
| Overview | الرئيسية |
| Data | البيانات |
| Analyses | التحليلات |
| Team | الفريق |

Inside Data, more specific language may be used: *data files* / ملفات البيانات, *data versions* /
إصدارات البيانات.

| Not primary | Why |
|---|---|
| **Reports** | Analyses is the history spine; artifacts are reached from the analysis that produced them. Does not constrain a future scheduled/recurring Executive Report surface. |
| **Activity** | Contextual on Overview (§7.5). |
| **Metrics** | Contextual in M3. A dedicated destination requires a later contract and a demonstrated customer need. |
| **Workspace** | Not a customer noun (§3). |

### PROPOSED RECONCILIATION — formerly CONFLICT-BLOCKED against `W1-05`

`KHEPRI_MASTER_PRODUCT_ROADMAP.md` `W1-05` previously required *"Workspace Overview, Datasets,
Analyses, **Reports**, **Metrics**, and **Activity** surfaces"*, which contradicted the four rows
above. **This reconciliation proposes the four-surface direction and amends `W1-05` to match it on
this branch**: scoped to Overview, Data, Analyses, and Team, with Reports discovered from Analysis
detail, Metrics and Activity contextual, and "Workspace" retained only as the internal domain term.

**Per `governance/CONSTITUTION.md` Article II, a branch or pull request is a proposal; it becomes
approved and governing only when the sole owner merges it to `main`.** The four rows above are
therefore the **proposed** product direction on this branch, not yet `LOCKED` — they become `LOCKED`
(§20 items 1, 2, 4, 19, 20) effective on merge, and this section's status must be re-read against
`git log` at that point, not asserted here ahead of it. Until merge, a slice planner reading this
document should treat the documentary conflict as *proposed to be resolved*, not resolved.

**This does not make the surfaces implementation-ready even after merge.** Neither `W1` nor this
blueprint is registered authority — `governance/registry.yaml` holds only `FND`, `RRA`, `RCA` — so
§18's `CONTRACT-BLOCKED` rows and §19's slice-readiness column are unchanged by this reconciliation.
Active `G2`/`G3` authority is still required before any M3 navigation slice may be implemented.
Resolving the conflict removes a contradiction between two roadmap-level documents; it grants no
authority, merged or not.

Each destination enters the navigation **in the slice that implements it**, never ahead of it
(`FR-049`). The navigation also needs a parity-paired label key of its own; it currently borrows the
Team title, which is already imprecise for one item and wrong for four.

---

## 9. Operational state versus trust state

**LOCKED principle — two distinct dimensions, never fused into one ambiguous badge.**

- **Operational state** answers *"what is happening to this analysis?"*
- **Trust state** answers *"what could Khepri safely support?"*

Both are real, and their combination is real: an analysis can finish successfully while some results
could not be supported. A single compound badge — "Completed with caveats and partial refusal" —
misstates that. The shape instead is a state plus a governed summary:

```
Completed
Quality: [governed summary]
```

**PROVISIONAL — the exact customer trust labels and counting grammar are not locked.** The words
*verified*, *caveated*, *refused*, *unavailable* are used here as **conceptual design vocabulary**.
The aggregate states a customer actually sees depend on the T1 / analysis-quality-summary contract,
which is not active. Do not treat those four words as the shipped vocabulary.

**LOCKED — no fixed result count is a UX invariant.** The quality summary derives its totals from the
**current governed result set**. The UX must not assume a fixed number of sections or metrics; today's
report structure is an implementation fact, not a durable product principle.

**LOCKED — machine vocabulary never reaches a customer.** Internal state and reason identifiers are
translated into operator language, following the existing precedent that renders internal column
semantics as customer-readable labels.

### Failure and reason copy

**LOCKED — copy is reason-driven, and must not overclaim a cause.**

Do not assume an exhausted-retry condition means "we could not read your file", and do not assume a
deleted-content condition means "deleted at your request" — neither the actor nor the cause is proven
by the state alone. Default to neutral, supportable wording:

> "We couldn't complete this analysis."
> "Content is no longer available."

Specialize **only** where the governed reason proves the specific cause. Where a reason does prove
one, prefer the specific wording — several governed reasons describe what the customer's own file
lacked, and each of those maps to an action the customer can take.

**LOCKED — a failure state carries a next action where one validly exists.** A row that names a
failure and offers nothing is worse than the shipped journey, which pairs failures with instructions.

---

## 10. Refusal and evidence UX

**LOCKED — a refusal is a governed result, not a system failure.** Therefore:

- it does not default to red or error styling;
- it remains visible **where the answer would otherwise appear**, rather than being omitted;
- its reason and evidence are reachable;
- reason wording explains the capability that was unavailable;
- results that remain independently answerable stay visible.

**Avoid `role="alert"` for a stable governed refusal.** An alert announces a problem; a refusal is an
outcome. The shipped precedent for the right visual treatment is a neutral state chip — a hairline
border and muted ink — carrying the rule that the state reads as text, not as colour alone.

**LOCKED — evidence is contextual.** It is reached from the claim, result, or report it supports.
There is **no generic primary "Evidence" destination.**

Evidence detail may expose definition, population, source semantics, coverage, comparison window,
reconciliation, caveats and refusal information, citation identifiers, and governed versions where
relevant. Low-level formula and version strings must not dominate primary customer pages.

---

## 11. Retention, deletion, and tombstones

### Clock cardinality — AUTHORITY-BLOCKED

**Owner product direction: one session/content retention clock for M3**, with report, evidence, and
related retained analysis content sharing one lifecycle. That preference includes not splitting
clocks per artifact — but it is a preference `G2` may overrule, not a rule this document imposes.

**This is direction, not a settled decision.** Clock cardinality for M3 belongs to `G2`: `G2-01`
inventories the retained data classes — uploads, normalized events, mappings, manifests, facts,
reports, evidence, telemetry, deletion evidence (`roadmap:722`) — and `G2-02` decides retention
defaults, deletion, organization closure, backup behavior, and export (`roadmap:723`). Until `G2-03`
activates that decision, **the retention relationship among M3 data entries, facts, reports,
evidence, and backups is undecided**, and this document must not foreclose it.

What the current implementation actually proves is narrower than an earlier draft claimed: within one
**temporary beta session**, one expiry is computed per publication and every artifact in that session
is validated to share it. That is evidence about today's single-session journey. It is **not** a
determination about durable M3 retention across dataset entries and their derived artifacts, and
citing it as one would preempt the pending data-boundary decision.

**Design consequence, safe either way.** Until `G2` decides, the UI must not promise a lifecycle it
cannot honor in either direction: it must not imply a data entry survives while its PDF disappears
independently, and it must not imply they are permanently coupled. Show each retention fact where it
is known, and state no relationship the contract has not established.

### Content versus history — LOCKED

These are separate facts and are shown separately.

```
Active → Expiring → Expired
Active → Deletion requested → Deleted
```

After expiry or deletion, **customer content is unavailable**, while a minimal safe historical record
may remain.

| | Content exists | History exists |
|---|---|---|
| Active, expiring | yes | yes |
| Expired | **no** | **conditional** — only if `G2`/`G3` permits a record to survive |
| Deletion requested | until it completes | yes |
| Deleted | **no** | **conditional** — only if `G2`/`G3` permits a tombstone |

The two conditional cells are **not** a guarantee. Whether any record survives expiry or deletion is
the retention decision itself (see the tombstone subsection below), so an implementer must read them
as "permitted only if the future decision allows it", never as "retain this".

Retention is stated in **absolute time including hour, minute, and timezone**, never as a relative
policy sentence alone. A date without a time cannot distinguish eleven hours from eleven minutes, and
the shipped report surface already carries this precision deliberately. Near the deadline a relative
form may carry emphasis: **impending data loss is the one place on these surfaces where alarm is
warranted**, and the restraint that correctly withholds red from a governed refusal should not also
withhold it from actual loss.

### Tombstones — LOCKED direction, CONTRACT-BLOCKED fields

**Deletion does not have to erase the fact that historical work occurred.** A minimal tombstone may
remain for a data entry and for an analysis.

A tombstone must **not** retain raw rows, report content, downloadable artifacts, evidence payloads,
source values, or anything future retention authority requires deletion to remove.

Where data is deleted, an analysis may retain a safe relationship such as "source data deleted"
**only if the future contract authorizes that metadata.**

**AUTHORITY-BLOCKED — both the existence of a tombstone and its fields.** Whether *any*
customer-visible historical record survives deletion is itself a retention decision, not merely a
question of which fields it carries. Active `RCA-001` excludes persistent report history and
retention changes (`RCA-001:161`), so no current authority permits retaining a record past deletion.
If the eventual `G2`/`G3` retention decision requires all such metadata to be erased, **that decision
governs and this direction yields.**

The product *preference* is that a disappearing history is worse than an honest tombstone, because a
reader who cannot find last month's analysis cannot tell deletion from a defect. That is a preference
to argue for when the retention decision is made — not a property to implement before it.

### Deletion UX — LOCKED direction, AUTHORITY-BLOCKED

**M3 deletion is owner-only.** This is product direction and is **not currently an authorized
commercial action.**

**Where the authority must come from.** `governance/registry.yaml` admits three artifact types —
`family`, `specification`, and `decision` — and holds **no design notes**. The `R6-01` matrix design
note (`docs/superpowers/specs/2026-08-15-r6-01-authorization-matrix-design.md`) is therefore
**implementation evidence, not authority**: adding a row to it cannot grant an authorization cell.

Active `RCA-001` is the registered authorization specification, and it **excludes** persistent
customer workspaces, report history, and retention changes (`RCA-001:161`). A commercial deletion
action for durable analysis history sits outside what it governs, so it is not the artifact to amend
either.

**Requirement.** The new action and its owner/member/non-member/unauthenticated cells must be carried
by the future **active `G3` specification**, or another registered successor artifact, with the
`R6-01` §3.1 table treated only as the implementation evidence that must then be extended to match.
Until that authority exists, **do not render the control.**

Implementation evidence for whoever writes that slice: §3.1 currently enumerates seven actions —
promote to owner, demote to member, revoke a membership, resolve an isolation scope, switch active
organization, issue an invitation, revoke an invitation — and **no deletion action appears in it**.
The matrix test *parses* that table rather than restating it, and a companion assertion requires every
action in it to have a matrix class, so the row and its coverage entry land in one slice. The note's
own footnote carries the shape: a new capability is *"a distinct action with its own row, not a
widening of this cell."*

What is already in place: the authorization context carries the actor's role and exposes whether the
owner column applies, so the mechanism needs no new resolver work. The gap is the governed action,
not the plumbing.

---

## 12. Roles and capability gating

Existing roles only: **owner** and **member**. No new permission-management UI.

**Every new durable-workspace cell below is product direction, not a settled permission.**
`G3-03` reserves authorization, audit, and evidence rules for **every** workspace action to the
future `G3` specification (`roadmap:727`). The existing `R6-01` permission to resolve an isolation
scope does not authorize the new `W1` list, read, or artifact-reopen actions, so those cells are
AUTHORITY-BLOCKED in exactly the way deletion is.

| Capability | owner | member | Authority |
|---|---|---|---|
| Team administration | visible where authorized | hidden | **SHIPPED** under `RCA-001`/`R6-01` |
| Start a new analysis | visible | visible | **SHIPPED** |
| See Overview, Data, Analyses | visible | visible | direction — **AUTHORITY-BLOCKED** (`G3-03`) |
| Open report, evidence, PDF, Excel | visible | visible | direction — **AUTHORITY-BLOCKED** (`G3-03`) |
| Deletion / request deletion | visible | hidden | direction — **AUTHORITY-BLOCKED** (§11) |

**LOCKED — hide actions that cannot validly complete.** Do not teach permissions with disabled
destructive buttons, and never render a control whose only outcome is an opaque authorization
refusal. An account with no membership resolves to its own surface rather than an empty organization
view.

---

## 13. Empty, loading, and error state grammar

**LOCKED.** Every empty state states three things: what this area is, why it is empty, and the next
valid action where one exists. No decorative empty-state illustrations by default. The shipped
surfaces already carry this pattern for an empty team and an empty invitation list.

| Situation | What the customer sees |
|---|---|
| No data submitted | what this area is + **New analysis** |
| Data present, no completed analysis | the entry, its admission outcome, and the analysis in progress or the action to run one |
| Analysis processing | its state; position in the run only where a contract supplies it |
| Only expired content | whatever history the retention decision permits, plus **New analysis** |
| Data not admitted | the admission and coverage outcome, and no raw values |
| No available report | named per analysis, with the reason: unsupported, expired, or deleted |
| No membership | the existing dedicated surface |
| Loading | placeholder rows at the final row height, so nothing shifts when content arrives |

---

## 14. Responsive and mobile

**LOCKED.** No page-level horizontal overflow. Wide content — tables, long rows — scrolls inside its
own container rather than moving the page.

At narrow widths the primary destinations remain text links that wrap, rather than collapsing into a
menu by default: the shipped approach prefers wrapping over a breakpoint, on the grounds that a
breakpoint encodes a guess about which element should yield first. Rows become stacked blocks; the
primary action is full width and first; artifact actions stack rather than compressing into a row of
equal buttons.

Interactive targets meet the shipped **44px minimum**, applied to the element itself rather than a
padded wrapper — a padded parent around a small anchor still leaves a small anchor. A one-line row
containing a link is therefore designed at that height from the start rather than discovering it
during implementation.

---

## 15. RTL, bilingual, and accessibility

**LOCKED — Arabic RTL and English LTR are first-class equal product surfaces.**

- `lang` and `dir` are **server-controlled**, never inferred in a template.
- **Logical CSS properties only.** The stylesheets currently contain no physical directional
  properties in code, and that is a property to preserve.
- **`dir="auto"` for customer-controlled or mixed-script values.** Organization names and file names
  must not assume LTR: a fixed LTR direction reorders an Arabic name around its own punctuation and
  digits, placing a Latin file extension at the visual left. `dir="ltr"` islands are correct only for
  values guaranteed to be Latin, such as email addresses and tokens.
- **Complete EN/AR copy parity**, enforced at import so a missing key fails the build rather than the
  visitor. Customer-facing strings live in the copy modules, never authored in JavaScript.
- Dates and numbers are locale-formatted. Arabic yields Arabic-Indic digits and Arabic month names,
  and the product commits to Arabic numeric conventions including its decimal, grouping, and percent
  marks — so a column sized for Latin digits does not fit them.
- **No literal directional glyph** for navigation affordances: a rightwards arrow does not mirror and
  points away from the reading direction in RTL.
- Truncate in character units rather than pixels, and keep the full value in the DOM so the
  accessible name is complete.

Typography and layout choices beyond the shipped design system belong to later visual craft and are
not locked here.

---

## 16. Report and artifact relationship

Longer-term product direction, preserved:

| Surface | Role |
|---|---|
| Web UI | interactive decision workspace |
| Final report | premium executive deliverable |
| Evidence | proof layer |
| Excel | structured downstream artifact |
| Mobile | executive summary, not a second analytics product |
| Ask Khepri | later — natural-language access to the same governed facts (§21, `G9/AI1`) |

**LOCKED architectural invariant.** Data flows one direction only: admission/mapping/coverage →
governed facts → semantic views where applicable → presentation surfaces. **No presentation surface
performs its own business calculation** — this restates the roadmap's "templates, controllers,
dashboards, APIs, semantic views, and AI may select and present facts; they may not recalculate them"
for every surface listed above, including the two added by this reconciliation.

All consume the same governed facts. **M3 only defines how analysis history exposes and reopens
them.**

### Mobile — executive summary, not a second analytics product

**LOCKED direction, `D1-10` gated.** Mobile prioritizes: What Changed?, key supported metrics,
findings, refusals/limitations, status, and a path to open the full analysis. It does not attempt to
reproduce dense desktop report tables on a phone. This is `D1-10`'s existing bilingual/RTL/mobile
scope, stated as a priority order rather than a new surface.

### Branded Report — future, bounded

**PROVISIONAL, AUTHORITY-BLOCKED.** Future direction: organization identity, logo, and reporting
period may appear on deliverables, under the same bounded-branding authority `A1-04` defines for
agency tenancy — not a separately invented white-label mechanism. **Branding must never remove**
Khepri provenance where required, disclosure, evidence, caveats, refusals, or audit/version
information governance requires. No branding authority is currently active.

### Secure Share — future, no current owner

**PROVISIONAL, no registered authority, no task ID.** Future capability: read-only, scoped, revocable,
expiring sharing of an analysis, report, or result without exposing the original uploaded source file,
with no cross-organization leakage and retention-aware behavior. Closest existing mechanism is
`API1-03`'s signed embed sessions, which solve a different problem. **Do not claim current authority
for this capability.**

### Ready Notification — two distinct things

**LOCKED distinction.** An in-product ready state (the analysis's operational state, §7.1/§7.3) is
different from outbound delivery (email/push/scheduled digest). Outbound delivery belongs to `S2-03`,
**once a future `G8` authority becomes active** — `G8/MON1/S2` is currently `PROPOSED`, not active, and
has no registry entry; this blueprint does not define a second notification subsystem in the meantime.

### Report accessibility baseline — SHIPPED

Recorded from the most recent report hardening, to be preserved rather than redesigned:

- horizontally scrolling report tables remain **keyboard reachable**;
- **focus is visible** — a tab stop with no visible indicator is a trap that looks like nothing
  happened;
- a **named region is a landmark and needs a meaningful, unique accessible name**; the name is the
  text its references resolve to, so distinct identifiers pointing at identical wording still name
  two regions alike;
- **not every scrollable table must become a landmark** merely to be focusable. Where nothing visible
  distinguishes sibling tables, they remain focusable and unnamed rather than several landmarks
  reading the same.

**The final report is not redesigned in this blueprint version.**

---

## 17. Visual direction

Light, calm, enterprise, evidence-first, restrained. Small radii. Borders and rules rather than heavy
shadows. Information hierarchy over decoration. State colour used semantically, separate from the
accent.

**The shipped light token set is the visual authority.** The dark Nocturne handoff is an
anti-reference for these surfaces. No high-fidelity mockups are produced here.

---

## 18. Authority and dependency matrix

| UX surface | Product decision | Required contract | Authority dependency | Current state |
|---|---|---|---|---|
| Commercial shell + Team | compact frame, no dead nav | — | active `RCA-002` | **SHIPPED** |
| Organization chooser | scope selection | — | active `RCA-002` | **SHIPPED** |
| Report / evidence surfaces | evidence as proof layer | — | active `RRA-006`, `RRA-009` | **SHIPPED** |
| Overview | operational orientation | `W1-04` authorized list/read | `G2` retention → `G3` workspace | **CONTRACT-BLOCKED** |
| Data list | submitted data, admission, retention | `W1-01` contracts, `W1-04` | `G2` → `G3` | **CONTRACT-BLOCKED** |
| Data detail | lineage + audit behind disclosure | `W1-01`, `W1-04`, `W1-06` provenance | `G2` → `G3` | **CONTRACT-BLOCKED** |
| Analyses | durable history spine | `W1-04` | `G2` → `G3` | **CONTRACT-BLOCKED** |
| Analysis detail | artifacts discovered here | `W1-04`, `W1-06`, report bundle | `G2` → `G3` | **CONTRACT-BLOCKED** |
| Quality summary | trust state, no fixed counts | `T1` metric/quality contracts | `T1` (**PROPOSED**) | **CONTRACT-BLOCKED** |
| Retention display | one clock, absolute time | `W1-07` lifecycle + deletion evidence | `G2` | **AUTHORITY-BLOCKED** |
| Tombstones | history survives content | `W1-07`; fields undefined | `G2` / `G3` | **AUTHORITY-BLOCKED** |
| Deletion action | owner-only | `W1-07` | a **registered** artifact (future active `G3`) | **AUTHORITY-BLOCKED** |
| Activity context | contextual only | `W1-09` | `G3` | **CONTRACT-BLOCKED** |
| Evidence detail | contextual entry | existing bundle + `T1-05` for metric detail | `T1` for metric detail | **partly SHIPPED**; metric detail **CONTRACT-BLOCKED** |
| Journey organization identity | make scope legible in `/beta` | — | authority permitting identity to cross the boundary | **AUTHORITY-BLOCKED** |

`W1` is blocked on active `G2`/`G3` authority; `T1` is `PROPOSED`. **Both `G2` and `G3` gate M3** —
`G2-03` activates the retention decision, and `W1-01` requires an **active `G3`** specification
(`roadmap:742`) whose `G3-03` defines authorization, audit, and evidence rules for every workspace
action (`roadmap:727`). M3 is not implementation-ready after `G2` alone. Design may proceed;
production code may not.

---

## 19. Proposed implementation slices

**Proposed only.** Prerequisite for all: active `G2`/`G3` authority and `W1-01` contracts merged.

| Slice | Purpose | Prerequisite | Owns | Forbidden scope | Readiness |
|---|---|---|---|---|---|
| **M3-U1** | Organization frame; **no destination link ships until its own surface does** | `W1-01` | the frame, route continuity, the nav mechanism | rendering a link for a surface a later slice delivers; list content; any new visual world | CONTRACT-BLOCKED |
| **M3-U2** | Operational and trust state presentation | `W1-01`; `T1` for aggregate labels | state rendering, EN/AR copy keys | fusing the axes; exposing machine words; fixed result counts | CONTRACT-BLOCKED (principle is LOCKED) |
| **M3-U3** | Analysis history and detail | `W1-04`, M3-U2 | list, detail, artifact access | Compare; filters; report redesign | CONTRACT-BLOCKED |
| **M3-U4** | Data history and detail | `W1-01`/`W1-04`, M3-U2 | list, detail, lineage | file preview; raw rows; version graph | CONTRACT-BLOCKED |
| **M3-U5** | Overview | M3-U3, M3-U4 | latest work, data state, attention | KPI cards; charts; business metrics | CONTRACT-BLOCKED |
| **M3-U6** | Retention and tombstones | `W1-07`, active `G2` (which decides clock cardinality) | retention display, tombstone rows | inventing tombstone fields; asserting any lifecycle relationship `G2` has not decided | AUTHORITY-BLOCKED |
| **M3-U7** | Deletion UX | a registered authorizing artifact (future active `G3`); `W1-07` | owner-only control | member-visible destructive controls; disabled-button education | AUTHORITY-BLOCKED |
| **M3-U8** | Responsive, RTL, state hardening | M3-U1…U7 | narrow widths, bidi, keyboard, empty and loading | new surfaces | CONTRACT-BLOCKED |

**Slice ordering is a `FR-049` constraint, not a preference.** M3-U1 delivers the frame and the navigation *mechanism*; each destination's link ships in the slice that implements its surface — Analyses with M3-U3, Data with M3-U4, Overview with M3-U5. Landing all four links in M3-U1 would render navigation with nothing behind it, which active `RCA-002` `FR-049` forbids and which §8 of this document already rules out.

---

## 20. Locked decisions register

Durable product decisions, safe to carry forward. None grants implementation authority. **Items 1, 2,
4, 19, and 20 carry a `W1-05` reconciliation note: per `governance/CONSTITUTION.md` Article II, that
reconciliation is proposed on this branch and becomes `LOCKED` only when this document's owning PR
merges to `main` — read it as PROPOSED until a `git log` on `main` confirms the merge.** The remaining
items in this register predate this reconciliation and are unaffected by it.

1. The customer-visible scope is the **Organization**. *(The "Workspace" label question is proposed-RECONCILED against `W1-05`, pending merge — see §8.)*
2. Four primary M3 destinations: **Overview, Data, Analyses, Team**. *(Proposed-RECONCILED against `W1-05`, now scoped to match pending merge — see §8.)*
3. Arabic navigation: **الرئيسية · البيانات · التحليلات · الفريق**.
4. **No separate Reports page**; artifacts are discovered from the analysis that produced them. *(Proposed-RECONCILED against `W1-05`, pending merge — see §8.)*
5. **Analyses is the single durable history spine**, newest first.
6. **Evidence is contextual** — reached from the claim it supports; no generic Evidence destination.
7. **Operational state and trust state are separate** and are never fused into one badge.
8. The quality summary derives totals from the **current governed result set**; no fixed count is a UX invariant.
9. **A refusal is a governed result, not an error** — no error styling, no `role="alert"`, and it stays visible where the answer would appear.
10. **Copy is reason-driven and must not overclaim a cause**; default to neutral supportable wording and specialize only where the governed reason proves the cause.
11. **A failure state carries a next action** where one validly exists.
12. **Machine vocabulary never reaches a customer.**
13. **One content retention clock** for M3 is product *direction*; clock cardinality is a `G2` retention decision. **AUTHORITY-BLOCKED** — see §11.
14. **Content existence and history existence are separate facts**, shown separately. Whether a history record survives expiry or deletion is a `G2`/`G3` decision — **AUTHORITY-BLOCKED**.
15. Retention is expressed in **absolute time with timezone**.
16. **History is not hidden** is a product *preference*, not a locked property: whether any record survives deletion is a retention decision. **AUTHORITY-BLOCKED** — see §11.
17. **Deletion is owner-only** as product direction, and is not rendered until a registered artifact authorizes it. **AUTHORITY-BLOCKED** — see §11.
18. **Hide controls that cannot validly complete**; never use a disabled destructive control as permission education.
19. **Activity is contextual**; M3 navigation does not depend on it shipping. *(Proposed-RECONCILED against `W1-05`, pending merge — see §8.)*
20. **Metrics is contextual** in M3. *(Proposed-RECONCILED against `W1-05`, pending merge — see §8.)*
21. **No dead navigation** — a destination appears only when its surface ships; no "Coming Soon".
22. **Overview is operational, never analytics** — no revenue, sales, branch, category, basket, or concentration content.
23. **Audit and version identifiers sit behind disclosure**, never leading a primary customer row.
24. **Arabic and English are equal surfaces**, with complete copy parity enforced at build time.
25. **`lang`/`dir` are server-controlled**; logical CSS properties only; no literal directional glyph.
26. **`dir="auto"` for customer-controlled or mixed-script values**; `dir="ltr"` only for guaranteed-Latin values.
27. **44px minimum interactive targets**, on the element rather than a wrapper.
28. **No page-level horizontal overflow**; wide content scrolls within its own container.
29. **A named region is a landmark and needs a unique, meaningful name**; focusability does not require a landmark.
30. **The shell and the journey are separate product modes by design**, not a defect.
31. **The shipped light token set is the visual authority**; the dark handoff is an anti-reference.
32. **The interface never invents capability the system does not possess.**

---

## 21. Provisional and blocked register

Unresolved. **Do not mistake any of these for a shipped contract.**

| Item | Status | Depends on |
|---|---|---|
| Exact M3 route shapes | PROVISIONAL | a specification carrying them; no route is authoritative here |
| Exact `W1` read models | CONTRACT-BLOCKED | `W1-01`, `W1-04` |
| Quality-summary aggregation contract, and the customer trust labels | CONTRACT-BLOCKED | `T1` (**PROPOSED**) |
| Exact tombstone fields | CONTRACT-BLOCKED | `G2`/`G3`, `W1-07` |
| Deletion authority | AUTHORITY-BLOCKED | a **registered** artifact (future active `G3`); the `R6-01` note is evidence, not authority |
| Workspace role cells (list, read, reopen artifacts) | AUTHORITY-BLOCKED | `G3-03` reserves authorization for every workspace action (`roadmap:727`) |
| Clock cardinality (one clock vs per-artifact) | AUTHORITY-BLOCKED | `G2-01`/`G2-02`, activated by `G2-03`; today's evidence covers one beta session only |
| Slice ordering of navigation links | LOCKED as a constraint | each link ships with its own surface (`FR-049`); see §19 |
| Whether a tombstone exists at all | AUTHORITY-BLOCKED | `G2`/`G3` retention decision; `RCA-001:161` excludes report history |
| Navigation scope: Reports / Activity / Metrics / "Workspace" | **PROPOSED-RECONCILED (pending merge), still CONTRACT-BLOCKED** | scope conflict with `W1-05` proposed-resolved on this branch (§8), effective on merge; implementation still needs active `G2`/`G3` per §18 |
| Durable progress / resume capability for a running analysis | IMPLEMENTATION-BLOCKED | `W1`; nothing persists commercial progress across a page load today |
| Exact Activity payload | CONTRACT-BLOCKED | `W1-09` |
| Journey organization identity | AUTHORITY-BLOCKED | authority permitting identity across the commercial→beta boundary |
| M4 page structure | FUTURE SHAPING REQUIRED | `SV1`, `C1`, M3 learnings |
| Executive Report System structure | FUTURE SHAPING REQUIRED | its own shaping track |
| Whether an analysis outlives its deleted data entry | PROVISIONAL | `G2`/`G3` retention contract |
| Metrics as a dedicated destination | PROVISIONAL | `T1` + demonstrated customer need |
| Remember My Data / reusable source-mapping profile | CONTRACT-BLOCKED | `W1-01` profile contract; active `G3`; must re-attest on material source change (Article V) |
| Analysis Impact Preview | CONTRACT-BLOCKED (data) / AUTHORITY-BLOCKED (journey step) | `T1-04` availability vocabulary needs active `T1`; the journey step itself needs an active RRA specification, since `RRA-010` excludes new journey phases |
| Analysis Passport fields | CONTRACT-BLOCKED | `W1-06` provenance record; active `G3` |
| Run Again / Run New Period compatibility rule | CONTRACT-BLOCKED | `W1-04`; underlying `RRA-003`/`RRA-004` compatibility contracts |
| Try Sample Analysis (pre-authentication) | AUTHORITY-BLOCKED | a new or amended RCA/RRA specification — `RCA-002` excludes public self-serve signup and any change to the beta journey's routes; active `RRA-010` is presentation-only and excludes new routes/phases; `G5-01` |
| Secure Share | AUTHORITY-BLOCKED, no task ID | a future sharing authority; `API1-03` is a related but distinct mechanism |
| Branded Report | AUTHORITY-BLOCKED | bounded-branding authority (`A1-04`'s pattern); none currently active |

---

## 22. Future shaping tracks

**M4 Executive Decision Workspace.** Executive overview, period comparison, branches, products and
categories, basket, concentration, limitations and refusals, contextual evidence, governed
exploration. Depends on `SV1`/`C1` and on what M3 teaches. **Page-level UX not specified.**

**Khepri Executive Report System.** Later shaping of the HTML report, the premium PDF, the evidence
report, and the Excel workbook — all consuming the same governed facts. Not designed in this
blueprint version, and the current report is not redesigned here.

**Journey organization identity / persistent frame authority gap.** Locked product direction, blocked
implementation (§6). Needs the authority question resolved before any design commits to it.

**Guided Exploration — `X1-01`/`X1-02`/`X1-03`/`X1-04`/`X1-05`.** The supported question catalog,
Explore actions on a KPI or chart, curated next-question suggestions, and Saved Answers, all selected
from supported governed question contracts — never LLM-inferred speculative questions. `X1-01`
through `X1-03` may ship inside M4; Saved Answers and pinning may follow immediately after. Depends on
`SV1`/`D1`.

**Ask Khepri — `G9/AI1`, later, boundary unchanged.** Natural-language questions answered only from
governed facts and semantic views, with evidence for every material claim and explicit refusal for
unsupported ones, in Arabic and English parity. **It does not calculate novel KPIs, does not retrieve
raw rows, and performs no writes or actions in the first release** — `AI1`'s existing non-goals. This
reconciliation does not pull Ask Khepri earlier than `G9/AI1`'s stated preconditions (M4 stable, `T1`
and `SV1` versioned, provider/privacy authority active).

**Try Sample Analysis.** Public pre-authentication activation belongs to `G5/ON1`, not to any M2/M3
task, and is currently AUTHORITY-BLOCKED (§21) — `RCA-002` excludes public self-serve signup and any
change to the beta journey's routes, and active `RRA-010` is presentation-only and excludes new
journey phases; a new or amended RCA/RRA specification is required, not `KHEPRI-DEC-025`, whose
account/link bootstrap prohibition does not reach a sample that creates neither. It is not folded
forward into M2 or M3 scope by this reconciliation.

---

## 23. Maintaining this document

- A decision belongs here only if it needs **no new authority** — it constrains future work rather
  than granting permission. Anything that grants permission belongs in a specification.
- When authority lands, move the affected row from §21 into §20 or into a slice, and update the
  status.
- When implementation ships, change the status to **SHIPPED** and cite the surface.
- If active authority contradicts anything here, **authority wins**: reconcile this document before
  implementing.
