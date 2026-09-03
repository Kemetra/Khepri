# F9 — what would an `RRA-010` amendment for "journey adoption" actually authorize?

**OWNER DECISION REQUIRED.** This document asks one question, recommends an answer, and does not
take it. It amends no specification. It corrects one roadmap row whose claim it falsified.

**Raised on:** `main` at `a4b0bba`, after the `U1` chain (`#350`–`#361`) merged.

---

## What was found

`#361` recorded `U1`'s next actionable task as *"drafting an `RRA-010` amendment for journey adoption
of the component layer"*, because `journey/templates/base.html.j2` loads one stylesheet and
`RRA-010`:88 excludes a new asset filename. Drafting began by asking what the amendment would let a
journey page **do**, and the tree answers: nothing.

**No journey page renders anything the component layer presents.** `RRA-012` FR-092 defines seven
components — a governed figure, a status badge, a quality summary, a refusal panel, an evidence link,
a version label, a coverage indicator — and every one presents a property of a `ReportBundle`: its
figures, its section states (`SECTION_PRESENT` / `SECTION_REFUSED`, the only two states
`COMPONENT_STATE_WORDING` words), its citations, its formula versions, its coverage identity. Read
page by page:

| `/beta` step | What it renders | Source | Rendered by |
|---|---|---|---|
| `upload` | the intake form and source contract | none | server template |
| `review` | mapping rows with `RRA-003` admission states and admission refusals | `/api/v1/beta/journey` | `review.js`, after load |
| `processing` | a job state (`preparing`, `failed`, `temporary`) | `/api/v1/beta/journey` | `processing.js`, after load |
| `report` | row count, timestamps, and seven artifact links | `/api/v1/beta/journey` | `report.js`, after load |
| `expired` | one of two terminal messages | query string | server template |

Not one governed figure, bundle section state, citation, formula version, or coverage identity
appears on any of them. The review page's states are `RRA-003`'s mapping states and its refusals are
admission refusals — a different vocabulary, already worded in `JOURNEY_COPY`, that `status_badge`
and `refusal_panel` have no governed rendering for and would fail closed on (FR-094). So an asset
wiring slice would ship a stylesheet to five pages on which none of its selectors ever matches.

**The component macros could not render there even if the data existed.** The seven macros are
Jinja, rendered server-side from a bundle at materialization time. Every journey state above is
fetched by JavaScript *after* the page is served, because the page routes render before the
session's state is known. A journey page cannot call a macro on data it does not have at render time.
Adopting the components there means either (a) rebuilding their markup in JavaScript — the *"fourth
hand-built markup block"* `RRA-012`'s Outcome exists to prevent — or (b) making the page routes read
session state at render time, which `RRA-010` excludes as *"a backend change presented as a UI
change"*.

**The only real consumer is `R8-10`, and it is already served.** `R8-10` — *"analysis quality and
evidence entry points to the journey and shell; user understands what was computed, caveated, and
refused before downloading"* — is the one roadmap task that would put bundle state on a journey page.
Since `#350`, the **web report surface opens with the quality summary** (`report.html.j2:54`, the
answered / caveated / refused counts) and links every figure to its evidence; since `#358` the
evidence surface carries a drawer beside every figure. The journey's report step links both surfaces
before the PDF and Excel downloads. A customer who opens the web report sees what was computed,
caveated, and refused before downloading anything. The entry points exist; they are the links the
report step already renders.

What `R8-10`'s journey half still lacks is presentation, not data: the seven links render as equal
cards, so nothing tells a reader that the web report is where to look first and that three of the
seven are downloads. That is a presentation change to an existing surface — reads no new data, adds
no route — and active `RRA-010` already authorizes it.

**The roadmap's `R8` row is half right.** Line 1763 says `R8-10`'s entry points are actionable
*"under existing `RRA-010` and `RCA-002` authority."* True for the journey half as links. It would be
false for a quality summary **rendered on** the journey report page, which needs the page to read
`/api/v1/beta/catalog/quality/{language}` — a new read, refused by `RRA-010`'s third bounding test
(*"reads no new data"*). That row is not corrected here because its claim, read as links, holds.

---

## The question

**Should `RRA-010` be amended to let a `/beta` page load the `RRA-012` component stylesheet and
render bundle state through the component layer?**

Three answers are possible. Each is stated with what it would cost, verified against the tree.

### A. No amendment. `U1`'s journey clause was a phantom; `R8-10`'s journey half is an `RRA-010` presentation slice. **Recommended.**

Nothing in `U1-02` through `U1-07` needs the component layer on a journey page, because no journey
page presents what the layer presents. The one task that does, `R8-10`, is met on the data side by
the web report surface and needs only a presentation slice on the report step: the web report as the
primary entry, the evidence surface beside it, the downloads labelled as downloads. That slice is
authorized today — surface identity, capability neutrality, and domain silence all hold — and needs
no amendment, no new asset, and no new read.

**Cost:** one small `RRA-010` slice. **What it forecloses:** nothing; B or C stay available if a
later program puts bundle state on a journey page.

### B. Amend `RRA-010` to admit one asset and one read, for a quality summary rendered on the report step.

Authorize: one new asset filename carrying the component rules, served through `_ASSETS`; one read of
`/catalog/quality/{language}` from `report.js`; JavaScript rendering of the quality summary's markup.
**Cost:** three `RRA-010` exclusions lifted (asset filename, allowlist change, new data read); the
component CSS must move out of `report.css` into a file both surfaces share, which is an `RRA-012`
Scope change; and the summary would then have a second rendering path, in JavaScript, beside the
Jinja macro — contradicting `RRA-012`'s reason to exist. **Not recommended:** it duplicates a summary
one click away to avoid the click.

### C. Amend `RRA-010` so the report step renders server-side from session state, through the macros.

Authorize: the `/beta/{language}/report` page route reading the journey snapshot and, when the bundle
is complete, constructing the audit context and rendering `quality_summary` through a template loader
that reaches `rendering/templates/_components.html.j2`; one asset filename for the component rules.
**Cost:** everything in B except the duplicate rendering, plus a page route that constructs a bundle
per request (the behaviour `KHEPRI-DEC-032` permitted for the catalog routes, extended to a page),
a cross-package template loader, and a new `RRA-010` dependency on `RRA-011`, `RRA-012`, and
`RRA-013`. **Not recommended now:** it is the right shape if the journey ever becomes a
server-rendered surface, and wrong to do for one summary.

---

## What this changes if A is taken

- `RRA-010` is untouched. `RRA-012`'s Scope note 1 and Implementation precondition 4 stay accurate as
  written: they say adoption *would need* an `RRA-010` slice, not that one is owed.
- `U1`'s status row reads: the program has no next actionable code task; `U1-03`, `U1-05`, `U1-06`,
  `U1-07` await authority, `U1-01` is documentation and may proceed.
- `R8-10`'s journey half becomes a bounded `RRA-010` presentation slice on the report step, plannable
  now. Its shell half stays `RCA-002`'s.

## What is corrected here regardless

The `U1` row of roadmap §16, which named the amendment as the next actionable task. It now records
this finding and points here. No other document is changed.

## What is not decided here

Whether `U1-03`, `U1-05`, `U1-06`, and `U1-07` should receive authority, and under which artifact.
Whether the shell's component layer and `RRA-012`'s should ever share tokens (`RRA-012`'s Outcome
leaves this open). Neither is this document's question.
