# `D1-05` — The evidence drawer, and the three surfaces it has to hang from

> **Execution plan** (the `W1-09` tier). Parent: the allocation plan at
> `docs/superpowers/plans/2026-09-10-d1-02-10-decision-workspace-allocation-plan.md`.
> **Authority:** active `RCA-008` — `FR-159`, `FR-161`, `FR-162`, `FR-164`, and `FR-171` for the
> parity the drawer's new wording owes.

**Deliverable:** `decision/evidence.py` (S-9's figure half), `MetricCard.evidence` filled with the
action `D1-03` named and left empty, the drawer rendered **inline on the surface carrying the
figure and nowhere else**, and the S-3/S-4/S-5 sections the drawer has to be reachable from.

---

## What `D1-03` handed forward, verbatim

> "`comparison` and `evidence` are always `None` today and are fields anyway: `FR-162` names them,
> `FR-170` explains the first, and `D1-05` fills the second. A card that omitted them would let a
> later slice add a line the contract already required, which is how a required line goes missing."

That is discharged here. `comparison` is **not**, and cannot be: `FR-170`'s source is still
unreachable and the successor composition artifact is the owner's, not this slice's.

---

## The thing this plan found before writing a line, and why it changes the slice

`D1-05`'s acceptance in the allocation plan reads: "the drawer is reachable from every figure on
**S-1, S-3, S-4 and S-5** and is never a page of its own (`FR-161`)."

**Three of those four surfaces do not exist.** `D1-04` shipped `breakdowns.py` and `limits.py` as
read models and shipped the route, and `decision.html.j2` renders S-1's cards and nothing else —
no branch table, no product table, no basket, no concentration, no limits. The sequencing table
says `D1-04` ships a surface, and `D1-04`'s own acceptance says "the two empty rules render
differently **on the same surface**"; what merged asserts both rules on `BreakdownReading`, at the
read-model level, and renders neither.

So `D1-05` cannot meet its own acceptance by building a drawer. A drawer reachable from S-1's ten
cards while three read models sit behind no surface at all is **this branch's recurring defect
exactly** — the half-closed guard, for the third time: `decisions` unwired while `deletion` and
`pins` were named; the omitted run refused while the empty one built; and now an evidence action on
the surface that exists while the three that were supposed to exist have none.

**This slice therefore renders S-3, S-4, S-5a, S-5b and S-6 as well.** That is not scope this plan
is taking; it is `D1-04`'s surface half, which `D1-05`'s acceptance depends on and which no later
slice is allocated. It is inside `RCA-008` §Scope (`shell_templates/`, `shell_api.py`) and needs no
new read model — `read_branches`, `read_products`, `read_basket_surface` and `read_limits` are
merged, tested, and called by nothing.

**If this slice has to be halved**, the split is after Step 3: `evidence.py` plus the card action
plus the drawer on S-1 is a complete, mergeable change, and the breakdown sections are the second
half. The halves are not reordered — a section rendered without a drawer would ship a figure whose
claim the reader cannot reach, which is the `FR-161` failure this slice exists to close.

---

## Seven decisions, taken from what the code says rather than assumed

**1. Which half of the drawer lives in `khepri.rca`, and which in the shell?**
The figure half only. `khepri.rca` may not import `khepri.rra`, so `evidence.py` carries governed
codes and the shell names them — `card.py` settled this and `shell_decisions.py` already imports
`metric_business_name` and `caveat_message`. The **definition** half — business name,
`describe_metric`, `define_metric(code).formula_version` — is read in `shell_decisions.py` from
`RRA-011`'s catalog, which `FR-159` admits in as many words: "Structure and navigation may come
from `RCA-005` records and the `RRA-011` catalog; figures may not."

**2. What is the join key between a card and its evidence, given the view publishes no `metric`
column?**
`ReportEvidenceView`'s `output_field_order` is `("figure", "evidence", "provenance", "absence")`
and names no metric, so its **rows** cannot be joined to a card. Its `projection.evidence` records
can: `CitedEvidence` carries `citation_id`, `metric`, `unit_kind`, `formula_version`, `precision`,
`inputs` and `provenance`. The drawer is keyed by **metric**, off the records, and the rows supply
the figure identifiers the records are cited by. Both are parts of one projection, so `FR-159` is
satisfied either way; the records are simply the part that states a metric.

**3. `provenance` and `absence` project as `None` on this view, and this slice does not fix that.**
`projection._FIELD_READERS` maps `figure` → `figure_id` and `evidence` → `citation_id` and has no
reader for the other two, so `_unstated` returns `None` for both — "a field no member of
`RenderableBundle` states — an absence, not a blank." That is `RRA-014`'s projection and
§Exclusions bars this specification from touching it. The drawer therefore reads provenance from
`CitedEvidence.provenance` and absences from `ViewProjection.evidence_absences`, and **a test
asserts the two columns are stated absences** so that the day `RRA-014` gives them readers, the
assertion fails and this module is looked at rather than silently double-sourced.

**4. `evidence_absences` is pairs, not strings, and the annotation on this side says otherwise.**
`projection._evidence_absences` returns `tuple[tuple[str, str], ...]` — `(citation_id, one of
precision | inputs | provenance)` — and the adapter hands `RRA-014`'s outcome back unchanged, so
that is what arrives. `khepri.rca.semantic_queries.ports.ViewProjection.evidence_absences` is
annotated `tuple[str, ...]`, which is narrower than what flows through it. **This slice does not
correct the annotation**: `ports.py` is `RCA-006`'s and §Exclusions bars editing it. It models the
pair correctly on its own type and asserts the real shape against the real projector, which is
where an annotation that drifted from its data becomes visible. *Raised for the owner in
§For the owner.*

**5. A drawer is a disclosure, never an address.** `FR-161`: "reachable from the surface carrying
the figure they qualify and **not deferred to a terminal page**." So the drawer is a `<details>`
beside its figure, rendered in the same response, and **this slice declares no route**. Asserted
negatively against the app's route table: the count of decision addresses is unchanged by this
slice, and `SHELL_SURFACES` gains no entry.

**6. `FR-162` requires a count, and `FR-159` bars deriving figures. Both hold.**
`card_status` deliberately uses `if not caveats` rather than `len(caveats)`, and that is about
*status selection*: a status counted would be a figure. The drawer's caveat count is not a status
and not a measurement of the customer's data — it is how many qualifications are displayed beside
one figure, which `FR-162` names outright. It is rendered, and a test asserts the status of a card
with three caveats equals the status of a card with one, so the count can never reach the
selection.

**7. What supplies "effective filters and period"?**
`ViewOutcome.effective` — `EffectiveRequest(dimensions, requested_filters, fixed_filters)`, which
`FR-137` defines as "what actually applied, requested and definition-fixed alike". Every read model
merged so far drops it. `EvidenceReading` keeps it. The **period** is not on it and must not be
invented: `FR-166` makes the period a *source selector*, so the period the drawer states is the
run the surface is addressed by — `CardsRequest.source_id`, already structure.

---

## Files

```text
src/khepri/rca/workspace/decision/evidence.py       NEW   S-9 figure half
src/khepri/rca/workspace/decision/card.py           EDIT  evidence: EvidenceAction | None
src/khepri/runtime/shell_decisions.py               EDIT  definition half, sections, drawer view
src/khepri/runtime/shell_templates/decision.html.j2 EDIT  drawer + S-3/S-4/S-5/S-6 sections
src/khepri/runtime/shell_assets/workspace.css       EDIT  drawer and table rules only
tests/test_d105_evidence_drawer.py                  NEW
```

No new `ShellServices` field is expected: `services.decisions` is one `SemanticQueryActions` and
every read in this slice goes through it. **Rule 11 still applies** — if that turns out to be
wrong, the collaborator reaches `build_shell_services` in the same commit, and
`test_the_built_image_wires_every_optional_field` fails until it does.

---

## Steps

### RED

- [ ] `tests/test_d105_evidence_drawer.py`, failing because `evidence.py` does not exist:
  - **`FR-160` — S-9 is read at its literal version**, `sv1.report_evidence.v1`, asserted against
    the registry, and `read_evidence` reads that view and no other.
  - **`FR-137` — the evidence request carries no filters.** `ReportEvidenceView`'s
    `request_filter_allowlist` is `()`, so a drawer that forwarded the surface's filters would
    refuse every figure it was opened on. Asserted through a recording port: the request's
    `filters` is empty even when the surface's is not.
  - **The join is by metric, off the records.** An entry exists for each `CitedEvidence.metric`,
    carrying its citation, unit kind, formula version, precision, inputs and provenance.
  - **`FR-140` — an absence is data, not a refusal.** A record stating `precision=None` yields an
    entry whose absences name `precision` against that citation, on an **admitted** reading, and
    the reading's status is admitted. Asserted positively and negatively: no `ViewRefusal` is
    constructed anywhere on the absence path.
  - **The view's `provenance` and `absence` columns are stated absences.** Driven against the real
    `projection.project`, so the assertion breaks if `RRA-014` ever gives them readers.
  - **`evidence_absences` arrives as `(citation, kind)` pairs**, asserted against the real
    projector rather than a hand-built projection.
  - **`FR-165` — S-9 answers unavailable independently.** The cards still render; the drawer says
    that part is unavailable and says nothing more.
  - **The dispatch rule** — a refused outcome carrying a projection is refused, and the drawer
    shows no entry from it.
  - **`FR-162` — the card exposes every line the requirement names**, through the action:
    label, value with unit, status, population, formula and contract version, effective filters,
    the period as the run, the evidence action, and the caveat count. Asserted as a set against
    the requirement's own list so a dropped line fails rather than goes unnoticed.
  - **The count cannot reach the status**: one caveat and three caveats select the same status.
  - **`FR-161`, negatively — the drawer is not an address.** The app's route table gains nothing;
    the drawer's markup is in the decision response itself; opening it needs no second request.
  - **`FR-161` over four surfaces** — every rendered figure on S-1, S-3, S-4 and S-5 carries its
    drawer, asserted by parsing the rendered page rather than by counting template lines.
  - **`FR-163` on the surface at last** — S-3's `stated_no_rows` and S-5's `stated_absence` render
    as distinguishable text on one page, which is `D1-04`'s acceptance criterion finally driven.
  - **`FR-171`** — every string this slice adds exists in both languages, and the Arabic page
    states no less than the English one: same drawer count, same entry count, same absences.
  - **Isolation** — a session whose organization disagrees with the address gets the uniform
    unavailable surface, drawer and sections included.

### GREEN

- [ ] `decision/evidence.py`: `EvidenceEntry`, `EvidenceReading`, `EvidenceRequest`,
      `read_evidence`. Keys by metric, keeps `effective`, groups absences by citation, computes
      nothing.
- [ ] `decision/card.py`: `evidence: EvidenceAction | None = None`, and `read_cards` attaching the
      entry for each card's metric. The type stops being `None` and starts being a value.
- [ ] `shell_decisions.py`: the definition half from `RRA-011`'s catalog, a `_DrawerView`, the
      S-3/S-4/S-5/S-6 section views, and the bilingual wording the drawer's new lines need in
      `DECISION_COPY`.
- [ ] `decision.html.j2`: a `<details>` drawer beside every figure, and the four sections.
- [ ] `shell_assets/workspace.css`: drawer and table rules, decision surfaces only.

### Gates

- [ ] `uv run khepri-gov validate`, `uv run ruff check .`, `uv run pytest`.
- [ ] Browser cases driven directly against the container's headless shell, because a shell surface
      changed and `-m browser` skips here.
- [ ] Every new file 10.00 in CodeScene; no tracked hotspot declines. `shell_decisions.py` is the
      risk: it gains four section views and a drawer view, and it has already paid the Excess
      Number of Function Arguments finding once. Every new helper takes a value object, and no
      conditional carries two logical operators.

---

## For the owner

**`ports.ViewProjection.evidence_absences` is annotated `tuple[str, ...]` and carries
`tuple[tuple[str, str], ...]`.** `RRA-014`'s projector builds the pairs, the adapter passes the
outcome through unchanged, and `RCA-006`'s port declares the narrower type. Nothing is broken at
runtime and nothing type-checks the difference, which is why it has survived four slices.
`D1-04`'s `BreakdownReading.evidence_absences` copied the narrow annotation and would read a pair
as a string the day anything renders it. §Exclusions bars this slice from editing either module, so
it is stated here rather than fixed: it needs `RCA-006`'s authority, or a one-line amendment.

---

## Not in this slice

- **The comparison line on the card.** `FR-170`'s source is unreachable and the successor
  composition artifact is the owner's decision (`RCA-008` §The open question).
- **The source selector and the three real filters** — `D1-07`'s, and the drawer states the
  effective filters it was given rather than offering any.
- **S-7 and S-8** — `D1-06`'s.
- **Any change to `RRA-014`'s projection**, including giving `provenance` and `absence` readers.
