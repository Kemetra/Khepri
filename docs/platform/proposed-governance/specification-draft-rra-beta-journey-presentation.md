# `[RRA-PRESENTATION]` (DRAFT): Beta Journey Presentation Maintenance

**Status: DRAFT — NOT A GOVERNED ARTIFACT.** No file under `governance/` was created or modified.
**No registry entry exists. No identifier is allocated.** `[RRA-PRESENTATION]` is a planning
placeholder in the sense `docs/platform/proposed-governance/README.md` requires: *"Drafts here are
named by planning placeholder, never by a governed identifier. A file called
`KHEPRI-DEC-013-draft.md` would already be using the number it claims not to have taken."*

This document authorizes nothing. `uv run khepri-gov validate` passes unchanged, which is the
evidence that no governance was activated.

- Prepared: 2026-08-26 against `main` @ `7327695`
- **Owner rulings applied: D-1 NO, D-2 NO for this specification, D-3 mechanism B confirmed, D-4 out
  of scope. Recorded verbatim in §10 and applied throughout.** No decision point remains open.
- Family: `RRA` (see §3)
- Intended target on promotion: `governance/specifications/RRA-<assigned>.md`. **Per D-3 no
  identifier is allocated here and no registry block is pre-written**; both are settled at the
  activation step in §13 against the then-current registry. §14 records dependency *intent* only.

> **A note on the local precedent.** `specification-draft-rca-002-commercial-shell.md` named itself
> `RCA-002` while disclaiming allocation. This draft does not follow that, because the directory's
> own README forbids it and the number it would take is not this document's to take. The structural
> parts of that precedent — draft banner, placement argument, the exact registry block, the
> promotion-is-two-edits rule — are followed closely.

---

## 1. Problem statement

Khepri's private-beta journey at `/beta/{language}/{step}` is shipped, customer-facing product. It
has accumulated presentation defects that are recorded, reproduced, and in several cases already
measured — and **not one of them is implementable**, because Constitution IV admits product code
only in slices linked to an *active specification*, and no active specification governs the
presentation of that journey.

This is not a request to authorize a list of fixes. The list is the symptom. The defect in the
governance record is that **`RRA` owns a customer-facing surface for which it has published no
presentation specification**, so ordinary maintenance of a shipped surface has no admitting
authority at any size.

A specification written to permit seven known fixes would be reverse-engineered from a backlog. The
boundary below is derived from the family charter instead, and §11 shows that **three of the seven
findings remain blocked after activation** — which is the test of whether the derivation was honest.
The owner rulings in §10 narrowed the authority further rather than widening it: D-2 removed a
finding from the implementable column that an earlier draft of this document had left open.

---

## 2. Evidence from the current implementation

### 2.1 The surface exists and is served

| Artifact | Evidence |
|---|---|
| Templates | `src/khepri/rra/journey/templates/{base,upload,review,processing,report,expired}.html.j2` |
| Assets | `src/khepri/rra/journey/assets/journey.css`, and five JS files |
| Asset allowlist | `src/khepri/rra/journey/routes.py:27` serves `journey.css` by exact name |
| Steps | `base.html.j2:19-24` renders a four-step nav whose current step varies by request |
| Tests | `test_rra_journey_accessibility.py`, `test_rra_journey_browser.py`, `test_rra_journey_pages.py` all exercise `upload`, `review`, `processing`, `report` |

### 2.2 The presentation defects are recorded and verified

Re-verified at `7327695`, not inherited from the M2 critique's `b19f365` baseline:

| Defect | Evidence |
|---|---|
| `aria-current` absent from the varying four-step nav | `base.html.j2:21-24` marks the current step with a CSS class only; `grep -rn "aria-current" src/` returns **zero** occurrences |
| Two skip-link mechanisms | `journey.css:39` is `fixed` + `translateY(-180%)` with inverted colours; `shell-components.css:45` is `absolute` + offset at `min-height: 44px` |
| A governed refusal painted as a system error | `review.html.j2:7` gives `#profile-findings` the `.error-summary` class. Its `role="status"` is already correct — the semantics were fixed and the paint was not |
| Terminal state with no recovery affordance | `expired.html.j2` contains **zero** `href` attributes in either branch |
| Type tokens declared and unconsumed | `var(--text-*)` has **0** consumers in all of `src/`; nine `--text-*` tokens are declared at `shell.css:109-129` |
| Primary button diverges across the crossing | `journey.css:72` is 46px/transparent/`--accent`; `shell-components.css` is 44px/`--accent-surface`/`--accent-dark` |

### 2.3 The gap is an assignment with no receiving specification

`RCA-002` — active — excludes the journey and, in the same clause, **assigns** it:

> `governance/specifications/RCA-002.md:132-135` — *"Any change to the `RRA` beta journey, its
> routes, its templates, or its assets. The beta surface is `RRA`'s and this specification does not
> modify it."*

And `RRA` owns it at the charter level: `governance/families/RRA.md` **Owns** *"Invite-bound,
pseudonymous beta sessions and their isolated ownership boundary"* and *"consistent report
surfaces"*.

**But no active `RRA` specification governs the journey as a rendered surface.** Searched across
`governance/specifications/`: the token `journey` appears in `RRA-001:15,17,31` (consent before
upload — a domain rule) and `RRA-002:10` (a 50 MB limit), and nowhere as a presentation obligation.
Every other occurrence is in `RCA-002`, the specification that excludes it.

### 2.4 Why `RRA-006` does not already cover this

`RRA-006` is the closest candidate and does not reach. Its Outcome is *"**One report bundle** exposes
the same fact-package version and grounded narrative through accessible web, PDF, and Excel
surfaces"*, and its Verification names *"Arabic/English parity, RTL rendering, accessibility"*.

Its subject is the **report bundle and its output formats**. `RCA-002:9-12` had to disambiguate the
word precisely because of this: *"`RRA-009` uses surface to mean an output format — web, PDF, Excel —
of one report bundle."*

The journey's `upload`, `review`, and `processing` steps are not a report bundle in any output
format. They are the intake and progress surfaces that precede one. `RRA-006`'s accessibility and
RTL clauses bind the report's render targets and do not extend to journey chrome.

That `test_rra_journey_accessibility.py` happens to cover all four steps is **not** an authority
grant. A test asserting a property does not authorize changing the code that produces it.

---

## 3. Placement, and why this is a new specification rather than a successor

The mechanism is chosen from registry structure, not convenience. All three options were examined.

### Rejected — A: successor to or restatement of an existing `RRA` specification

`RRA-006` is the only plausible parent, and superseding it is both wrong and expensive:

- **Wrong subject.** A successor would carry report-bundle reconciliation, PDF and Excel fidelity,
  cross-surface citation, and partial-export retry into a document about journey chrome. Constitution
  III requires one authoritative representation per governed fact; a spec covering both would
  represent two.
- **Terminal successor cost.** `governance/registry.yaml:257-259` records `RRA-009 depends_on [RRA,
  RRA-006]`. Retiring `RRA-006` would make an active artifact depend on a retired one, which the
  README states is invalid, so the supersession would require re-pointing `RRA-009` in the same
  atomic registry change — N+1 edits for no scope gain.

### Rejected — C: another governed mechanism already established

There is none available. The approval-package mechanism is retired: `KHEPRI-DEC-004`
(*atomic approval packages*) is `state: retired`, superseded by `KHEPRI-DEC-017`
(*Minimal Single-Owner Governance*), which replaced the ledger with the Git record. There is no
`governance/approvals/` directory on `main`. The directory README's "digest hazard" warning
describes the retired era and does not apply.

The only governed route from proposal to authority is the README's Workflow: *"Edit the governed
document and registry entry together"*, merged by the owner.

### Selected — B: a new narrow `RRA` presentation specification

`governance/README.md`: *"A specification depends on exactly one family."* `RRA` specifications are
siblings under one family, not a chain, and `RRA-009 depends_on [RRA, RRA-006]` is the precedent for
a specification that **adds** scope alongside an existing one while depending on it. This document
proposes exactly that shape: a sibling that inherits `RRA-006`'s parity and accessibility posture and
governs the surface `RRA-006` does not.

---

## 4. The proposed governed boundary

The authority proposed is **maintenance of the presentation of surfaces that already exist**. It is
bounded by three tests, all of which a candidate change must pass:

1. **Surface identity.** The change alters how an existing journey surface is *presented*. It does
   not add a surface, a step, a state, or a route.
2. **Capability neutrality.** After the change, the set of things a customer can *do* is identical.
   Every action, destination, and outcome already existed.
3. **Domain silence.** The change reads no new data, computes nothing, persists nothing, and sends
   nothing new anywhere.

A change failing any of the three is outside this authority however small it looks.

### 4.1 Scope — exactly which artifacts

**Included:**

| Path | Bound |
|---|---|
| `src/khepri/rra/journey/templates/` | All templates, for presentation markup and ARIA state only |
| `src/khepri/rra/journey/assets/journey.css` | The journey stylesheet |
| `src/khepri/rra/journey/assets/*.js` | Presentation behavior only — focus, ARIA state, progressive disclosure |
| Presentation-only copy keys in `src/khepri/rra/journey/copy.py` | Only keys naming a control, a state, or an affordance |
| `tests/test_rra_journey_{accessibility,browser,pages}.py` | Extending assertions; and see §9 |

**Excluded by path, and the reason is ownership rather than directory:**

`src/khepri/rra/journey/assets/shell.css` and `shell-components.css` sit in the journey's asset
directory and are **the shell's**. `tests/test_m2_persistent_frame.py:677-687` fixes this precisely:
*"It is a journey asset by path only: `shell.html.j2` is the sole template that links it, and the
exclusion is about the beta surface rather than about a directory."* That test asserts
`shell-components.css` never reaches a `/beta` page. **This specification does not govern either
file.** Ownership follows the linking template, not the folder.

### 4.2 Permitted presentation changes

Proposed as `RRA` house-style requirement bullets (`Outcome` → `Requirements` → `Exclusions` →
`Verification`, matching `RRA-006`):

- Correct accessibility defects on an existing journey surface: programmatic state for a visible
  state the surface already conveys, accessible names, landmark and heading structure, focus
  visibility, and keyboard reachability of content already reachable by pointer.
- Correct responsive defects at supported viewports without introducing a new breakpoint policy:
  no page-level horizontal overflow, and wide content scrolling inside its own container.
- Correct bilingual and right-to-left presentation defects, preserving `RRA-006`'s parity
  obligation: logical properties only, explicit direction for a script run whose direction is not
  the page's, and locale-formatted values.
- Present a semantic state the system already computes with a treatment that matches its meaning —
  specifically, a governed refusal MUST NOT be presented with the treatment reserved for a
  transport or system error. The refusal's own text, reason, and evidence are unchanged.
- Consume design token values **declared within this specification's own governed scope** in place
  of equivalent literals, where the token and the literal are the same value or the journey's own
  token declaration documents the collapse. This authorizes reading a value from a name; it does not
  authorize choosing a value.

  **Per D-2, a slice under this specification MUST NOT depend on, read from, or require a value
  defined in a shell-owned asset.** A journey rule may not resolve a custom property whose sole
  declaration is in `shell.css` or `shell-components.css`; such a rule would be invalid on a `/beta`
  page in any case, because §4.1's ownership rule and
  `test_m2_persistent_frame.py:677-687` establish that no shell stylesheet is loaded there. Where a
  value must exist for the journey to consume it, that value is declared in the journey's own
  stylesheet — which is where the *authority* to declare it also sits.
- Correct focus and navigation semantics: one skip-link mechanism, correct tab order, and visible
  focus on every tab stop including scroll containers. **Consolidating two journey-internal
  mechanisms is in scope; adopting a shell-owned mechanism as the target is not (D-2).** Where the
  journey and the shell each hold a mechanism, this specification authorizes the journey to settle on
  **one of its own**, restated in its own files, and does not authorize borrowing the shell's.
- Add a recovery affordance to a terminal journey state **only where the destination is an existing
  `/beta`-local address that existing runtime authority already serves** (D-1). A destination outside
  `/beta` — including any address under the commercial prefix — is not authorized here, and is
  guarded by an existing test (§6).

### 4.3 Explicit exclusions

This specification would authorize **none** of the following, and a slice claiming it does is
outside its specification within the meaning of Constitution IV:

- A new workflow state, step, or journey phase.
- A new route, address, or asset filename; a change to the asset allowlist.
- Any new business capability, or any change to what a customer can do.
- Any calculation, re-derivation, re-rounding, or re-formatting of an authoritative figure.
- Any new data collection, field, telemetry event, or persistence.
- **Organization identity, name, slug, or any `/app` context inside `/beta`, and any link or
  navigation into the commercial prefix (D-1).** See §6.
- Any commercial workspace behavior, membership, role, or invitation semantics.
- **Any dependency on a presentation value or asset owned by a surface outside this
  specification's governed scope (D-2).** Naming a custom property, class, or file whose authority
  sits with the shell is outside this specification even when the resulting pixels would match.
  Consistency across the crossing is a real goal and is not this authority's to deliver.
- New report semantics, report content, citation behavior, or refusal *content*. Presentation of an
  existing refusal is in scope; what a refusal says is `RRA-009`'s.
- **The report colophon wording and any other governed report copy (D-4).**
  `src/khepri/rra/rendering/html.py` is the report renderer, and its bilingual catalogue is
  `RRA-009`'s. A defect there is fixed under `RRA-009`, not here.
- Any retention, expiry, or deletion behavior, or any presentation implying a retention guarantee
  the system does not make.
- Public signup, durable history, sharing, comments, or export of anything not already exported.
- Arbitrary remapping, semantic re-interpretation, or any change to admissibility.
- Any API surface change, request or response shape, or status code.
- Any backend, domain, service, or persistence change presented as a UI change. **A template that
  begins reading a value the view model did not previously supply is a domain change.**

---

## 5. Invariants the specification would preserve

Stated as obligations, so a reviewer can reject a slice against them.

### 5.1 Privacy, isolation, and security

- `RRA` session isolation and the opaque-owner boundary are unchanged. `RRA-001` binds every
  operation to an opaque identifier; presentation gains no identifier.
- Operational telemetry remains content-free. No presentation change emits customer content.
- Deletion and expiry guarantees are unchanged, including cross-session indistinguishability: the
  collapsed terminal causes MUST remain indistinguishable by copy, status code, page identity, or
  navigation state. A recovery affordance added under §4.2 MUST therefore be identical in wording,
  destination, and presence across every collapsed cause — the property
  `tests/test_m2_persistent_frame.py:548-560` already asserts for the shell's own exit.
- The content security policy is not weakened. `default-src 'none'` holds; no inline style or
  inline script is introduced.
- No customer content, filename, or raw value enters markup that did not carry it.

### 5.2 Bilingual, RTL, and accessibility

- Arabic and English remain equal surfaces with equivalent state, actions, and error text.
- Copy parity stays enforced at import, so a missing key fails the build rather than the visitor.
  Customer-facing strings stay in the copy modules and are never authored in JavaScript.
- **Zero physical directional CSS properties.** Verified across all five stylesheets at `7327695`;
  this is a property to preserve, not a preference.
- Interactive targets meet the 44px minimum on the element itself, in both languages at every
  supported viewport — the floor `RCA-002` `FR-056` cites as *"the minimum target size the existing
  journey tests already enforce"*.
- `prefers-reduced-motion` continues to guard animation and to fill rather than freeze a progress
  track.

### 5.3 Runtime

- Server-rendered FastAPI + Jinja2 with bundled CSS and minimal bundled JavaScript. **No SPA, no
  Node frontend, no client framework, no build step.**
- No external fonts, CDNs, analytics, or runtime assets. Typefaces stay package data verified
  against the SHA-256 manifest.
- No new dependency.

---

## 6. The shell ↔ journey boundary — RULED: the boundary holds (D-1)

**Owner ruling D-1 is NO.** Commercial organization identity does not cross into `/beta`. This is
now a settled boundary this specification preserves, not a question it defers — and the exclusion is
load-bearing rather than cautious.

The repository keeps that boundary on purpose, and by construction rather than by care:

- `governance/families/RRA.md` **Excludes** *"organizations"* and *"persistent customer
  workspaces"*, assigning them to `RCA`.
- `tests/test_m2_persistent_frame.py:652-675` `TestTheBetaJourneyIsUntouched` asserts that **no
  journey page contains a link into the commercial prefix**, in both languages across all five
  steps, with the stated reason that *"a beta-only deployment declares no `/app` route, so such a
  link is also a 404."*
- `test_m2_persistent_frame.py:20-24`: *"`open_commercial_session` takes an opaque `owner_id`… so
  that no `account_id`, `organization_id`, name, slug, or email reaches this function"* — the
  boundary holds *"by absence rather than by inspection"*. The same note records: *"The product
  decision to show the organization in the journey is made; the authority is not."*

Frame continuity across the crossing is therefore **outside this specification**, by ruling and not
merely by omission. Per D-1 it *remains* outside: it is a family-boundary question about whether
`RCA` identity may cross into an `RRA` surface, and the answer for now is no.

Consequences, stated plainly:

- **Activating this specification does not make the shell ↔ journey frame continuity seam
  implementable.** It stays blocked, and no future slice under this authority may close it.
- **`TestTheBetaJourneyIsUntouched` is preserved.** Both of its assertions survive intact and are
  listed as unchangeable in §9. Its `/app`-link assertion is the mechanical enforcement of D-1.
- **A terminal-state recovery affordance is still permitted, because its destination can be
  `/beta`-local.** `expired.html.j2` has no `href` at all today; giving it one that points within
  `/beta` neither names an organization nor links into the commercial prefix, so it does not touch
  the boundary D-1 protects. This is the one place where reading D-1 as "no recovery affordance"
  would over-apply the ruling: the ruling is about *identity and the crossing*, and it says
  explicitly that recovery "may only use an already-authorized `/beta`-local destination."

If the seam is to be closed later, the honest route is the one the shell already has available:
**make the organization legible on the `/app` side, before the crossing.** That is `RCA-002`
territory and needs no `RRA` change at all.

---

## 7. Relationship to active `RRA` and `RCA` authority

| Artifact | State | Relationship |
|---|---|---|
| `RRA` (family) | active | Parent. Owns the beta session and its surfaces. This specification adds no capability to the family. |
| `RRA-001` | active | Untouched. Session binding, consent-before-upload, identifier opacity are domain rules; presentation gains no identifier. |
| `RRA-006` | active | **Depended on.** Its parity, RTL, and accessibility posture is inherited and narrowed to the journey's non-report surfaces. Its report-bundle scope is untouched. |
| `RRA-009` | active | Untouched and explicitly deferred to. Refusal *content* — the five required parts, the bilingual catalogue — stays `RRA-009`'s. Only the *treatment* of an already-correct refusal is in scope. **Per D-4 the report colophon wording is `RRA-009`'s and is excluded here.** Not named as a `depends_on` (§14): this specification defers to it rather than building on it. |
| `RRA-007` | active | Untouched. Telemetry stays content-free; no presentation change emits an event. |
| `RCA-002` | active | **Complementary.** Its exclusion at `:132-135` assigns the journey to `RRA`; this specification is the receiving authority that assignment presumes. Nothing here modifies a shell surface. |
| `KHEPRI-DEC-017` | active | The governing process: document plus registry entry, merged by the owner. |

---

## 8. Test obligations

A slice under this specification would be required to:

- Extend the existing journey accessibility and browser tests rather than replace them, asserting
  the new invariant in **both languages** and at **every supported viewport** already parametrized.
- Assert the presence of the programmatic state, not merely its absence of error — an `aria-current`
  slice asserts the attribute on the current step *and* its absence on the others.
- Assert refusal-versus-error distinction as a *rendered* property, not a class name, so the
  assertion survives a rename.
- Re-assert the zero-physical-directional-property invariant over any stylesheet it edits.
- Measure, not assume, any change that could alter layout at 390px — the browser test's own
  `scrollWidth <= innerWidth` assertion is the contract.

---

## 9. Which existing guards a future slice may legitimately change, and what replaces them

Per the standing rule: **no guard is weakened without a replacement invariant.**

| Guard | May a slice change it? | Reasoning and replacement |
|---|---|---|
| `TestTheBetaJourneyIsUntouched::test_no_journey_page_links_into_the_commercial_shell` | **No — D-1.** | The mechanical enforcement of the ruling. Preserved by name in the ruling text. A recovery affordance added under §4.2 must satisfy it, which a `/beta`-local destination does. |
| `TestTheBetaJourneyIsUntouched::test_the_shell_stylesheet_does_not_reach_the_journey` | **No — D-1 and D-2.** | Asserts the ownership-not-directory rule §4.1 depends on, and is now also the mechanical reason a shell-owned value cannot be consumed: the sheet declaring it is never loaded on `/beta`. Strengthened by being cited, not relaxed. |
| `test_rra_journey_accessibility.py::test_css_carries_focus_touch_narrow_and_reduced_motion_rules` | **Yes, by extension only.** | It greps the stylesheet for rules. A slice consolidating the skip link or consuming tokens may need to update *what string* it looks for. **Replacement invariant:** assert the *computed* property on a rendered page rather than the presence of a literal in CSS text — a stronger assertion than the one it replaces, and it cannot pass on a stylesheet the page does not load. |
| `test_rra_journey_browser.py` 44px and `scrollWidth` assertions | **No — extend only.** | These are the floor `RCA-002` `FR-056` cites. A slice adds cases; it never relaxes a bound. |
| `test_r801_shell_tokens.py::test_the_orphan_value_count_does_not_grow` | **No.** | Subset check on hex literals below `:root`; a token-consumption slice reduces the set, which it already permits. Note this test reads `shell.css` and `journey.css` and is not itself governed here. **Replacement invariant a token slice must add:** an assertion that every custom property a journey rule resolves is declared in a stylesheet the journey actually loads. That is the D-2 boundary made mechanical, and it is a stronger check than a value-parity assertion between two files — it would fail a rule borrowing a shell-owned name, which is exactly what D-2 forbids and what no current test detects. |
| `test_m2_persistent_frame.py` recovery-exit indistinguishability | **No.** | A journey recovery affordance must satisfy the same property (§5.1), so this test becomes a *model* for the journey-side assertion rather than something to change. |

---

## 10. Owner rulings — recorded and applied

The four decision points this draft raised were ruled on by the owner on 2026-08-26. **All four are
closed**, and the ruling text below is applied throughout this document rather than left as an open
question. No decision point remains outstanding.

**D-1 — May `RCA` identity cross into an `RRA` surface? — NO.**

> Commercial organization identity must not cross into the `RRA` `/beta` surface.
> `TestTheBetaJourneyIsUntouched` and the existing isolation boundary are preserved. Expired-state
> recovery may only use an already-authorized `/beta`-local destination. Shell ↔ journey frame
> continuity remains outside this specification.

Applied in §4.2 (recovery affordance restricted to a `/beta`-local destination), §4.3 (identity
crossing excluded), §6 (the boundary and its enforcing tests), §9 (both boundary guards
unchangeable), and §11 (findings 4 and 7).

**D-2 — Does presentation authority include consuming a value declared in a file outside its
governed scope? — NO, for this specification.**

> The journey presentation authority must not create a dependency on presentation values or assets
> owned by a surface outside its governed scope. Primary-button consolidation stays blocked unless
> it can be performed entirely within the authorized journey presentation boundary without
> modifying or depending on shell-owned assets.

Applied in §4.2 (token consumption narrowed to values already declared **for the journey's own
surface**), §4.3 (a new exclusion), and §11 (finding 6, and the caveat on finding 5).

This ruling makes the authority self-contained: a slice under it can be reviewed against the
journey's own files alone, with no reader needing to consult a shell-owned artifact to know whether
the slice is admissible.

**D-3 — Mechanism confirmed: B, a new narrow `RRA` beta-journey presentation specification.**

> Do not allocate an identifier in the proposal. Record the intended dependency relationship, but
> final identifier and registry dependency wiring occur only during an explicit activation step
> after validation against the then-current registry.

Applied in §3 (mechanism), §13 (activation sequence), and §14, which now records the dependency
*intent* rather than a registry block to be copied. No identifier is taken anywhere in this
document.

**D-4 — Report colophon wording: OUT OF SCOPE.**

> Report colophon wording remains owned by `RRA-009` and must not be absorbed into this
> presentation specification.

Applied in §4.3 (explicit exclusion), §7 (`RRA-009` relationship), and §11. The wording at
`src/khepri/rra/rendering/html.py:145` — *"Full calculation evidence and data lineage are available
on request"*, for evidence published at a URL — is a real defect and is **not** this
specification's to fix. It requires a slice under `RRA-009`.

---

## 11. Finding-by-finding mapping, after the owner rulings

**Four of the seven become implementable; three stay blocked.** With D-1 through D-4 ruled, there is
no longer a "requires separate owner decision" column — every finding now resolves to implementable
or blocked, and what blocks each one is named.

This table is the honesty check on §4's derivation: an authority that unblocked all seven would be
evidence it had been written backwards from the backlog.

| # | Finding | Verdict if activated | Why |
|---|---|---|---|
| 1 | `aria-current` on the varying four-step nav | **IMPLEMENTABLE** | Programmatic state for a state the surface already conveys visually. `base.html.j2:21-24` already computes the current step, so no view-model change is needed — which keeps it inside §4's domain-silence test. |
| 2 | Duplicate skip-link mechanisms | **IMPLEMENTABLE**, narrowed by D-2 | The journey may settle on **one of its own** mechanisms, restated in its own files. It may **not** adopt the shell's as the target. The §9 replacement invariant ships in the same slice. |
| 3 | `#profile-findings` painted with error styling | **IMPLEMENTABLE** | Presentation of an existing governed state; `role="status"` is already correct, so only the treatment changes. Refusal *content* stays `RRA-009`'s. |
| 4 | `expired` recovery affordance | **IMPLEMENTABLE, `/beta`-local only** (D-1) | `expired.html.j2` has no `href` today. A destination inside `/beta` that runtime already serves neither names an organization nor links into the commercial prefix, so D-1 permits it explicitly. It must satisfy §5.1 indistinguishability: identical wording, destination, and presence across every collapsed cause. An `/app` destination stays forbidden. |
| 5 | Type-token consumption in `journey.css` | **IMPLEMENTABLE**, and D-2 settles its shape | The stylesheets never co-load, so the values must be declared in the journey's own `:root` — which D-2 now makes the *required* form rather than a workaround, since a rule resolving a shell-declared name is forbidden and would be invalid anyway. Needs the §9 invariant. Already built and measured on `origin/design/u1-journey-type-tokens`. |
| 6 | Primary-button inconsistency | **BLOCKED** (D-2) | The target treatment is defined in `shell.css`/`shell-components.css`, which §4.1 excludes as shell-owned. Adopting it would create exactly the cross-scope dependency D-2 forbids. **Not blocked forever:** if the journey settles on a treatment defined entirely in its own files, that is in scope — it simply would not be "consolidation onto the shell's". Cross-surface visual consistency needs a shared token authority owned by neither surface, which no artifact currently provides. |
| 7 | Shell ↔ journey frame continuity | **BLOCKED** (D-1) | §6. Outside this specification by ruling. The available route is to make the organization legible on the `/app` side before the crossing — `RCA-002` territory, needing no `RRA` change. |

Also mapped, from `KHEPRI_DESIGN_LANGUAGE.md`'s live findings:

| Finding | Verdict | Why |
|---|---|---|
| Report "available on request" for a published URL | **BLOCKED** (D-4) | `RRA-009`'s bilingual copy catalogue. Requires a slice under `RRA-009`. |
| Report ↔ app token namespaces | **BLOCKED** | Blueprint §16 — the report is not redesigned. Also a cross-scope dependency of the kind D-2 forbids. |
| Navigation label set | **BLOCKED** | Unreconciled `W1-05` conflict; neither side of it is a registered artifact. |

---

## 12. What becomes implementable — and the ordering constraint

If activated as drafted and ruled: **findings 1, 2, 3, 4 (`/beta`-local), and 5.**

Each is its own independently verifiable slice. **Findings 2 and 5 both edit `journey.css`, so they
are ordered rather than parallel**, and finding 5's own note in `KHEPRI_DESIGN_LANGUAGE.md` §2.8.1
records why it is not a mechanical substitution. Finding 4 touches `expired.html.j2` and its copy
keys; findings 1 and 3 touch `base.html.j2` and `review.html.j2` respectively, so those three are
independent of each other and of the stylesheet pair.

**Blocked after activation: findings 6 and 7**, plus the three report and navigation findings in §11.

Nothing in this proposal makes M3 implementable. `W1`, `T1`, `G2`, `G3`, and `U1` have **zero
entries** in `governance/registry.yaml`; this specification neither registers them nor stands in
for them.

---

## 13. Migration and activation path

Nothing here is activated. D-1 through D-4 are ruled (§10), so the remaining steps are mechanical —
but per **D-3 the identifier and the dependency wiring are decided at activation time, against the
registry as it then stands**, not pre-baked here.

1. **Re-read `governance/registry.yaml` at activation time.** Determine the next `RRA` identifier
   from the entries then present, and confirm every artifact the entry will name is still `active`.
   This is not a formality: an active artifact may not depend on a retired one, and the validator
   fails closed on an unknown `depends_on` — so a dependency list written today could be wrong by
   the time it lands.
2. Move this document to `governance/specifications/RRA-<assigned>.md`, dropping the draft framing —
   the banner, §3's rejected options, §10's ruling record, this section, and §15 — as the `RCA-002`
   promotion did, since those argue *for* the specification rather than state it. The rulings
   themselves survive as the specification's own Requirements and Exclusions, where they are already
   applied; §10 is the audit trail, not the authority.
3. Add the registry entry in the **same commit** as the document. `governance/README.md`: adding a
   document without its registry entry does not make it governed.
4. Run `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`.
5. Owner merges to `main`. That merge is the approval record — `KHEPRI-DEC-017`, and Constitution II.

No digest recomputation is required: the approval-package mechanism is retired (§3).

---

## 14. Intended dependency relationship — wired at activation, not here

**Per D-3 this section records intent, not a block to copy.** No identifier is allocated and no
`depends_on` list is fixed. The entry's final shape is determined in activation step 1 against the
then-current registry.

**Shape intended:** `type: specification`, `state: active`, `document:
governance/specifications/RRA-<assigned>.md`.

**Dependency intent:**

| Artifact | Why it is intended as a dependency |
|---|---|
| `RRA` | Required. `governance/README.md`: *"A specification depends on exactly one family."* This is that family, and it already owns the surface. |
| `RRA-006` | Intended. §4.2's bilingual, RTL, and accessibility obligations narrow `RRA-006`'s posture to a different surface, and `depends_on` is the only dependency automation can see. `RRA-009 depends_on [RRA, RRA-006]` is the sibling precedent. |

**Deliberately not intended as dependencies**, so the omissions are on the record rather than
accidental:

- `RRA-009` — this specification defers to it (§7) and excludes its copy catalogue (D-4), but
  defers rather than builds on it. A dependency would assert a coupling that does not exist.
- `RCA-002` — a specification under `RRA` may not depend on one under `RCA`; the README fixes a
  specification to exactly one family, and the two are complementary rather than dependent.

**Verification required at activation:** confirm `RRA` and `RRA-006` are both still `active` in the
registry as it then stands. If either has been retired or superseded, the dependency intent above is
re-derived against its successor before the entry is written — an active artifact may not depend on a
retired one, and the validator fails closed on an unknown identifier.

---

## 15. What this draft is not

- **Not authority.** No registry entry, no allocated identifier, no activation. Owner rulings on
  scope are recorded (§10); a ruling on scope is not a grant of authority, and only the merge of a
  document-plus-registry-entry pair makes this governing.
- **Not a licence for the seven findings.** Three remain blocked after activation (§11), two of them
  by the owner's own narrowing rulings.
- Not a widening of `RRA`. The family already owns the surface; this proposes the missing
  specification for it.
- Not a change to `RCA-002`, whose exclusion is the reason this is needed and stays exactly as
  written.
- **Not a weakening of any existing guard.** `TestTheBetaJourneyIsUntouched` keeps both assertions
  (§9), and D-1 and D-2 are the reason.
- Not a resolution of navigation scope, an M3 surface, or a report redesign.
