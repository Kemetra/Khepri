# `[DEC-BOUNDARY]` (DRAFT): Seshat-BI analytical dependency and ownership boundary

**Draft for owner review. Not a governed artifact. No identifier is allocated.**

`[DEC-BOUNDARY]` is a **planning placeholder**, not an identifier. Should the owner direct that
this be drafted as a governed decision, its identifier is derived from
`governance/registries/decisions.yaml` **at that moment**, and any intervening decision
displaces it. Nothing is reserved. The survey of what the registry currently holds is in
[`identifier-survey.md`](identifier-survey.md).

Target on promotion: `governance/decisions/<derived-id>-seshat-analytical-boundary.md`, state
`proposed`, no approval evidence. Registry shape in §Registry below.

Follows the template at `governance/templates/decision.md`.

---

## Context

The owner supplied a master roadmap on 2026-08-05 directing that Khepri and `Kemetra/Seshat-BI`
become one analytics platform: Khepri the commercial product, Seshat the governed analytical
engine, with a one-way dependency `Khepri → Seshat headless analytical API`.

No Khepri artifact governs any relationship with `Kemetra/Seshat-BI`. The repository is named
in exactly one place — `KHEPRI-DEC-012`, which is `proposed` — and is named there to explain
why its dbt and Dagster adapters stay where they are. This decision creates the missing
boundary.

### The mirrored artifact on the other side exists

Two independent governance systems need two artifacts, each approved under its own rules, each
citing the other **by commit SHA and never by the other's approval**. Seshat's half merged as
`Kemetra/Seshat-BI@3875aca` (PR #579) — `docs/architecture/{headless-analysis-engine,
khepri-consumer-boundary, analysis-evidence-contracts}.md` — and cites this repository at
`Kemetra/Khepri@db98f4b`.

That artifact is **not evidence for this one.** It is a draft in its own repository, ratified by
nobody, and Constitution III forbids treating a reference as authority. What it does establish is
that the boundary described here is described the same way on both sides, and that a reviewer can
check the reciprocity rather than take it on trust.

### What Seshat-BI actually contains, at `157ef43`

Verified by inspection, not assumed from the roadmap. `157ef43` is the commit actually inspected
and is deliberately not restated as a later SHA. Every path cited below is **unchanged through
`3875aca`**, confirmed by diff, so the findings are current as well as attributable.

**It has** a governed statistical evidence engine (`src/seshat/statistical/`) with a closed
catalog of eight methods, all version `1.0`: `describe`, `compare_groups`, `proportion`,
`correlate`, `regress`, `detect_anomalies`, `detect_change_points`, `forecast`. Outcomes are
categorical — `computed`, `withheld`, `refused`, `unavailable`, `failed`. Evidence records
`authority: derived-evidence-only`, `review_state: pending`, and `readiness_effect: none;
named-human approval required`. No method accepts arbitrary Python, formulas, SQL, model names,
or dynamically loaded callables. `statistical/__init__.py` exposes a contract surface with
`ENGINE_VERSION = "1.0"` and keeps every numerical dependency unloaded on import.

**It does not have** a single deterministic retail metric. No revenue, no gross margin, no
growth decomposition, no concentration curve, no basket analysis. Those exist in Khepri, in
`facts.py` and `analysis/`, under approved specifications RRA-004 and RRA-008.

**It is bound to a repository root.** `run_analysis(repo_root: Path, spec, provider)`
(`runtime.py:399`) and `evaluate_policy(repo_root, spec)` (`policy.py:284`), which reads
readiness status, metric contracts, and PII evidence off the working set. Only two modules
import `statistical` — `cli/commands/analyze.py` and `statistical/registry.py` — so the
coupling is narrow, but it is real and it is the thing a headless boundary must remove.

**It is not distributable.** Not on any package index (`KHEPRI-DEC-012:74`). It pins
`dbt-core==1.12.0` against Khepri's `jinja2>=3.1,<4` and declares `requires-python >=3.13`
against Khepri's `>=3.13,<3.14`.

**It already contains a port of Khepri's renderers.**
`src/seshat/report/{html,pdf,excel,charts,chromium,layout,model}.py` carry headers reading
"PORTED from `Khepri/src/khepri/rra/rendering/…` at commit `7a1e3fd`", from a design approved
by the owner on 2026-08-03 whose decision 2 was "**Port** Khepri's `rra/rendering` into Seshat
with provenance headers," explicitly rejecting a shared package.

### The contradiction this decision must settle

The roadmap says (§5.2) Seshat does not own the customer report's visual composition, and (§4.2,
§5.2) that Seshat owns deterministic retail calculations. **Current state is the exact
inverse**: Seshat owns a renderer and no retail method; Khepri owns every retail method and its
own renderer.

Neither repository erred. Both governance systems were correct within their own frame, and
neither had a boundary artifact to consult. The port predates the roadmap by two days.

## Decision

### 1. Analytical ownership for the first commercial release

**Deterministic retail calculations remain authoritatively Khepri's.** RRA-004 and RRA-008 are
unchanged. Khepri does not transfer, deprecate, or dual-run any governed metric under this
decision.

**Statistical inference Khepri does not have is Seshat's**, and Khepri does not implement it.
Khepri will not add a hypothesis test, a regression, a change-point detector, or an anomaly
model to `src/khepri/`.

Roadmap §5.1 — "Khepri must not independently recalculate figures already owned by the Seshat
analytical engine after migration is complete" — is adopted as a **forward constraint**, not a
present one. It binds when a metric moves. No metric moves under this decision.

**Condition for any future transfer.** A deterministic retail metric moves to Seshat only when
all of the following hold, in a separately approved decision:

1. a parity fixture exists that both implementations pass, to the digit;
2. Seshat's implementation preserves the `Decimal` contract — `KHEPRI-DEC-008` forbids binary
   floating point as an authoritative financial fact;
3. reason-code and precision parity are tested, not asserted;
4. Khepri can roll back to its own path without a customer-visible change;
5. the duplicate-ownership window is bounded and named in the decision that opens it.

### 2. Permitted dependency shape — and no dependency is declared yet

**This draft proposes: define the boundary now, defer the integration.** The direction was given
by the owner in a working session on 2026-08-05 and **is not recorded anywhere in this
repository** — no issue comment, approval package, registry entry, or approval reference. It is a
planning input, not an approval, and this draft carries no authority until a named authority
approves it with traceable evidence. As proposed, the decision
settles what a dependency may look like. It declares none, and no Khepri code consumes Seshat
evidence under it.

The permitted future shape is **a versioned analytical contract package** carrying schemas,
fixtures, and validators — and nothing else. No numerical library, no CLI, no workspace root,
no adapter, no readiness state machine.

```text
Khepri  ->  kemetra analysis contracts  <-  Seshat-BI
```

This is not `Khepri → Seshat-BI`. It creates no co-installation, and every packaging conflict
`KHEPRI-DEC-012:196-201` records — the `dbt-core` pin, the `jinja2` range, the
`requires-python` mismatch, the wheel-contents rationale — is untouched, because the
distribution neither side depends on is never installed.

### 2a. No package — and the source of truth that replaces one

**This draft proposes: no package is published.** Same status as §2 — session direction, not
traceable evidence. Contracts would be exchanged as committed
files. A package would otherwise have supplied the source of truth; without one, it must be
stated, or "committed fixtures" degrades into two repositories editing lookalike files.

Five rules, all of which any future contract work must satisfy:

1. **Seshat-BI owns the canonical schemas.** They are authored and versioned in Seshat, per
   roadmap §5.2. Khepri does not author, extend, or locally amend a schema.
2. **Khepri consumes a pinned copy or a generated projection** — never a hand-maintained
   parallel definition. A copy records the Seshat commit it came from; a projection records the
   generator and its input.
3. **Schema version and content digest are recorded on both sides.** The schema version is
   independent of any package release version (roadmap §7.1). The digest is what makes a
   silent edit detectable.
4. **Cross-repository compatibility tests detect drift.** Each repository asserts that its copy
   matches the recorded digest, and fails closed when it does not. Without this, rules 1–3 are
   documentation rather than control.
5. **Fixtures demonstrate the contract; they do not define it.** A fixture is an example that
   must satisfy the schema. Adding a field to a fixture does not add it to the contract, and a
   fixture disagreeing with the schema is a fixture defect.

Rule 4 is the one that does actual work. Rules 1–3 describe an intention; rule 4 is the
mechanism that notices when the intention lapses, which is precisely what a package's version
pin would otherwise have provided.

**If a contracts-only distribution is later published**, these five rules are what it would
formalize — not replace. The package question re-opens only if and when the integration is
built.

**Prohibited, and not reopened by this decision:**

```text
Seshat-BI -> Khepri                          (any direction of import, reference, or test dependency)
Khepri -> the Seshat-BI CLI
Khepri -> a Seshat-BI checkout or workspace root
Khepri -> the Seshat-BI readiness state machine
Khepri -> the seshat-bi distribution itself
Khepri -> dbt, Dagster, or Power BI runtimes  (KHEPRI-DEC-012, on its own evidence)
```

**Distribution is a precondition, not a detail.** No contract dependency may be declared until
the package is published somewhere Khepri's `pyproject.toml` can name. Until then this section
authorizes design and fixtures, not a dependency declaration.

### 3. Forecasting is not consumed

`governance/families/RRA.md` excludes forecasting from Khepri. Seshat ships a governed
`forecast` method. **Khepri does not consume forecast evidence through this boundary**, and the
consumer fails closed on a bundle containing it.

Consuming it would import an excluded capability without amending the family that excludes it.
If forecasting is later wanted, the route is a family amendment first, then a boundary
amendment — in that order.

### 4. Renderer duplication: grandfathered, and closed

Seshat's `src/seshat/report/` and Khepri's `src/khepri/rra/rendering/` are recorded as **two
renderers serving two products**. Seshat's renders governed BI evidence for clients without a
Power BI licence; Khepri's renders the commercial customer report under RRA-006.

Neither is removed. Neither imports the other. **Neither may be ported again in either
direction** — the 2026-08-03 port is grandfathered, not a precedent.

**The reason this is tolerable, stated precisely.** Duplicated *renderers* are a maintenance
cost. Duplicated *calculators* are a correctness failure, and §17 names it as the first risk.
Both renderers already forbid themselves arithmetic in their own words — Khepri's `pdf.py`:
"It presents figures; it never produces one"; Seshat's design decision 1: "Numbers come from
one upstream bundle; renderers only transcribe."

**Therefore:** neither renderer may acquire arithmetic. That constraint is what this section
buys, and it must be tested on both sides. `Seshat/src/seshat/report/model.py` is the specific
watch point — it is a port of Khepri's `bundle.py` `CitedFigure`, and it is where a helpful
total would first appear.

### 5. Profiling and semantic mapping stay where they are

Roadmap §5.2 assigns profiling and semantic-role contracts to Seshat. Khepri's `profiling.py`
and `mapping.py` are approved under RRA-003, shipped, and tested against real retail uploads;
Seshat's serve a medallion warehouse and a Power BI readiness spine. They profile different
things for different consumers.

Both stay. Neither ports to the other. If a shared `DatasetProfile` contract later proves they
can be unified without loss, that is a separate decision with its own evidence.

### 6. Constitution III and `AGENTS.md`

Constitution III names `Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` as
immutable reference material. **That is a different repository from `Kemetra/Seshat-BI`**,
verified by remote. Article III does not govern Seshat-BI.

`AGENTS.md` states the copying rule unqualified — "Do not copy Seshat catalogs, specifications,
proposals, ledgers, governance records, or application code" — immediately after a line scoped
to Seshat-Platform. Read across both repositories, that sentence already prohibits the
2026-08-03 port in the reverse direction.

**This decision requires that `AGENTS.md` line be qualified in the same approval package**, to
read explicitly on Seshat-Platform, with Seshat-BI governed by this decision instead. Leaving
it ambiguous means either the port is a standing violation or the rule means nothing, and both
readings are available today.

`AGENTS.md` is not pinned by `document_sha256` in any approval package, so this is a plain
edit rather than a renewal. Proposed replacement for the two adjacent bullets:

> - Treat `Kemetra/Seshat-Platform@f206b7f2c021c7d4e25ba131776ca4b22db6d876` only as
>   non-authoritative reference material.
> - Do not copy **Seshat-Platform** catalogs, specifications, proposals, ledgers, governance
>   records, or application code.
> - `Kemetra/Seshat-BI` is a separate active repository, not predecessor reference material.
>   Khepri's relationship with it is governed by `[DEC-BOUNDARY]`, which permits a versioned
>   analytical contract and refuses its CLI, checkout, readiness state machine, distribution,
>   and adapter runtimes.

### 7. Fail-closed on version mismatch

Khepri pins an engine version and a contract version. On an unknown or unsupported version it
**refuses the analysis and delivers the deterministic report** — the shape
`KHEPRI-DEC-005:187` already uses for the narrative provider: "report availability never
depends on" the optional provider. Precedent, not invention.

### 8. What this decision authorizes

**Boundary only.** Per the owner's 2026-08-05 direction, the integration is deferred past
Milestones A and B.

Authorized:

- the boundary itself — §§1–7 above, as a settled record both repositories can cite;
- Seshat's counterpart ADR, under Seshat's own governance;
- participation in defining committed contract fixtures, if and when Seshat authors them.

**Not authorized, and explicitly deferred:**

- a Khepri evidence-consumer specification (a consumer specification is *not* allocated by this decision);
- any dependency declaration in `pyproject.toml`;
- any request adapter, evidence consumer, or compatibility gate in `src/`;
- any published contract package.

**It authorizes no product code, declares no dependency, moves no calculation, and changes no
existing specification.**

**Why settle a boundary for an integration that is deferred.** Because the cost of *not* having
one is already on the record: the 2026-08-03 renderer port happened in good faith, under a
correct Seshat decision, because no artifact existed for either side to consult. A boundary is
cheap now and retroactive later. Deferring the integration is a schedule choice; deferring the
boundary is how the next duplication gets built.

## Consequences

- Roadmap §5.2's analytical ownership is **partially rejected for the first release**, with the
  transfer condition in §1 recorded. Roadmap §19.10 requires the contradiction be reported
  rather than silently resolved; this is that report, in governed form.
- Roadmap §5.2's report-composition ownership is **partially rejected as already overtaken by
  an owner-approved Seshat decision**, and closed rather than reversed.
- `KHEPRI-DEC-012` is unaffected and not superseded. Its amendment (drafted separately) should
  land first, while it is still `proposed`.
- Khepri's deployment gate is untouched and remains first. `KHEPRI-DEC-005` is accepted and
  unfundable; `KHEPRI-DEC-008` is `proposed`. **Nothing in this decision can be demonstrated to
  a customer until that clears.**
- Seshat's authority model is preserved verbatim: ADR-0008's five categories,
  `authority: derived-evidence-only`, named-human approval. Roadmap §19.9 requires it; the
  headless facade must not become an approval bypass, and its adversarial test is a request
  that *claims* readiness, which must be `refused`.
- Khepri's numerical, reconciliation, privacy, bilingual, and refusal guarantees are unchanged.
  Roadmap §19.8 requires it. No RRA specification is amended.
- Distribution is answered — no package (§2a) — and the five source-of-truth rules replace what
  a package pin would have provided.
- Metric authority for consumer requests is a **precondition**, not an open question (§9).
- One follow-up obligation: the `AGENTS.md` qualification in §6, in this decision's approval
  package.

## Registry shape

**No registry entry is created by this planning pass, and no identifier is allocated.** Should
the owner direct that this be drafted as a governed decision, the entry added to
`governance/registries/decisions.yaml` would take this shape, with `<derived-id>` resolved
against the registry at that moment:

```yaml
  - id: <derived-id>
    title: Seshat-BI analytical dependency and ownership boundary
    state: proposed
    owner: AHMED-SHAABAN
    document: governance/decisions/<derived-id>-seshat-analytical-boundary.md
```

No `approved_by`, `approved_at`, or `approval_ref` — Constitution VI requires those only at
`accepted`, and Constitution II reserves the approval to a named authority.

## Session direction this draft reflects — not evidence, not approval

The four questions below were previously carried as open in the planning package. The owner gave
direction on each in a working session on 2026-08-05. **None of that direction is recorded in
this repository**, and `AGENTS.md` forbids treating it as human approval.

They are listed so a reader can see *why this draft reads the way it does*. **A reader must treat
each as an unresolved input**, and no artifact may cite this table as evidence that a question is
settled. Each becomes settled when this decision is approved with traceable evidence — or is
re-opened if the owner directs otherwise before then.

| Question | Direction this draft reflects | Where it shapes the text |
|---|---|---|
| Distribution | Committed files; no package | §2, §2a |
| Integration in the first release | Deferred past Milestones A and B; boundary drafted now | §8 |
| Renderer divergence | Two renderers, two products, closed | §4 |
| `AGENTS.md` ambiguity | Qualify to Seshat-Platform, in this package | §6 |

### 9. Metric authority is a precondition for integration, not an open question

A Khepri customer uploads a CSV. There is no Seshat source map, no approved Seshat metric
contract, no readiness stage, and no named human who approved its business meaning under
Seshat's Core Authority. Seshat's `evaluate_policy` requires metric-contract authority, grain
authority, and PII evidence.

**This decision closes the question rather than leaving it open.** A consumer request reaching
the Seshat engine must satisfy one of exactly two conditions:

1. **It carries explicit Khepri-approved metric authority through a versioned
   consumer-authority contract.** The authority is Khepri's own — an approved Khepri
   specification and the mapping confirmation recorded against that dataset — expressed in a
   versioned contract Seshat can evaluate rather than trust. The resulting evidence must
   **identify the origin of its authority on its face**, so that evidence standing on Khepri
   authority is distinguishable by inspection from evidence standing on an approved Seshat
   metric contract. Khepri Constitution II uses the same discipline for delegated approvals —
   "Human and delegated approvals remain distinguishable by inspection" — and it is the right
   precedent.
2. **Otherwise it is `refused`**, and stays refused until an approved Seshat metric contract
   exists for that data.

**There is no third option, and specifically no "contractless" or relaxed policy profile.** An
earlier draft of this package recommended one. That was wrong: a second profile that computes
without contract authority is an authority bypass with a name, and it would produce evidence
that looks like governed evidence while resting on nothing. Roadmap §19.9 requires Seshat's
named-human approval and derived-evidence boundaries not be weakened, and a relaxed profile
weakens them by construction.

**Parked, deliberately:** the mechanism. What a versioned consumer-authority contract contains,
how Seshat validates it, and how the origin marking is rendered in evidence are all questions
for the integration specification. **What is not parked is whether the precondition applies.**
It does, and no integration work may begin without it satisfied.

Because the integration is deferred (§8), this constrains nothing today. It is recorded now so
that a later slice cannot discover the problem under schedule pressure and solve it with a
relaxed profile.

## Remaining open questions

None that gate this decision. The mechanism parked in §9 is the substantive design work, and it
belongs to the integration specification that does not yet exist. It is analysed in
`Seshat-BI/docs/architecture/analysis-evidence-contracts.md` §4.
