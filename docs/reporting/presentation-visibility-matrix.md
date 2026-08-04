# Presentation visibility matrix

**Status:** draft for owner approval. Docs only — no product code changes proposed here.

Every field the three surfaces currently render, classified into one of three
tiers. The classification is the whole point of this document: it is the thing an
implementation slice will be checked against.

| Tier | Meaning | Where it may appear | Delivered |
|---|---|---|---|
| **B — Business** | The customer deliverable. Plain business language. | Primary report body | **Always** |
| **A — Audit** | Customer-accessible, but separated. Machine identifiers live here. | PDF technical appendix, HTML Technical Evidence page, Excel Audit Trail / Provenance sheets | **On request** |
| **I — Internal** | Never rendered on any customer surface at all. | Logs, telemetry, attempt records | Never |

**Owner decision, 2026-08-04: the business report is the product; the audit
evidence is optional to the customer.**

Tier A content is *generated for every report, always* — skipping a surface returns
`REASON_MISSING_SURFACE` and yields an incomplete bundle (`bundle.py:1222`).

"Optional" is a **render variant of each surface**, not a filter applied at
delivery. An earlier version of this document said delivery-time filtering; that
was wrong — `delivery_persistence.py:346-350` raises `DeliveryCorrupted` on any
delivery that does not name every required surface. See the IA's §B.1, which
carries the correction and the two remaining routes.

The rule that produces the tiers: **a field is Business only if a retail owner
could act on it without knowing Khepri exists.** A field that only means
something to someone auditing Khepri is Audit. A field that only means something
to someone *operating* Khepri is Internal.

---

## A.1 Figure rows

Source: `FigureCell` (`rendering/html.py:141-163`), rendered by
`templates/report.html.j2` as a six-column table with headers
`Label / Metric / Kind / Unit / Value / Citation` (`_CHROME`, `html.py:77-134`).

| Field | Current rendering | Tier | Business treatment |
|---|---|---|---|
| `text` | `<td class="figure">` | **B** | The number. Already customer-ready — `bundle` formatted it. |
| `label` | `<th scope="row">` | **B** | Product / branch / period name. Already customer text, except governed codes — `_row_label` (`html.py:324-337`) already translates those. |
| `metric` | `<td>` raw | **A** | Replaced in B by a **business metric name** ("Revenue", "Items per sale"). The raw code moves to the appendix. |
| `unit_kind` | `<td>` raw | **A** | Folded into the B number's own formatting (currency symbol, `%`, `×`). Never its own column. |
| `kind` | `<td>` raw | **A** | Dropped from B entirely. "Is this a ratio or a total" is an audit question. |
| `figure_id` | `<td>`, plus `data-figure-id` ×2 | **A** | Removed from B, including the attributes. Retained in the appendix as the join key. |
| `citation_id` | `<td><a><code>` | **A** | Removed from B. The appendix carries the figure→fact citation table. |

**Net effect on the primary report:** the six-column identifier table becomes a
two-column business statement (name, value) — or a chart with direct labels and
no table at all, which is the preferred form for ≤ 8 rows.

> **Gap this exposes.** `_row_label` translates governed *labels* via
> `GOVERNED_FIGURE_LABELS`. There is no equivalent path for `metric` — it reaches
> the page as the raw identifier with no translation hook at all. A business
> metric name table is therefore **new**, not a fill-in of an existing one. This
> is the single largest wording gap and it is why "just fill the wording
> dictionary" was the wrong scope.

---

## A.2 Section state and refusal

Source: `_SectionView` (`html.py:433-447`); template renders a refused section as
`<p class="refused" data-reason="…"><code>{{ section.reason }}</code></p>` —
**nothing but a monospace reason code.**

| Field | Current rendering | Tier | Business treatment |
|---|---|---|---|
| `section_id` | `id=`, anchor, `<h2>` key | **B** (as heading) / **A** (as `id`) | The heading is already translated via `SECTION_HEADINGS`. The raw `section_id` survives as an HTML anchor — see the rule below — but must never be *displayed*. |
| `state` | `data-` attribute | **I** | `present` / `refused` is structural. The reader infers it from the prose. |
| `reason` | `<code>` — visible | **A** (code) + **B** (prose) | See §D. B gets a five-part customer explanation; the raw code appears only in the appendix. |

> **The rule for identifiers in attributes.** §A.1 removes `data-figure-id`
> entirely while this section keeps `section_id` as an `id=` anchor, and both are
> invisible to a reader — so the difference needs a stated rule rather than a
> case-by-case judgement.
>
> **An identifier may survive in an attribute only when the reader uses it.** An
> `id=` anchor is navigation: the table of contents links to it and the browser
> scrolls to it, so it does work for the reader. `data-figure-id` does work for
> nobody — it was a hook for tooling, and a business report is not a tooling
> surface. Same visibility, different function, so different treatment.
>
> Consequence for the leak check: it must test **visible text**, not raw markup,
> or it will flag every legitimate anchor. The verified checks in this package do
> exactly that (they strip tags before matching).

---

## A.3 Caveats

Source: `bundle.caveats`; rendered twice — section-scoped
(`caveats--section`) and report-level (`#caveats`) — both as `<li><code>{{ code }}</code></li>`.

| Field | Current rendering | Tier | Business treatment |
|---|---|---|---|
| `caveat.code` | `<code>` | **A** (code) + **B** (prose) | Becomes a "Data Limitations" entry in customer prose. |
| `caveat.section` | Selects which list | **I** | Structural routing only. |

> **Hard constraint — no opt-out.** `_reconcile_language` (`bundle.py:1324`)
> requires `frozenset(entry.caveats) == frozenset(bundle.caveats)`. That is set
> *equality*, not containment. A business report cannot show a friendly subset
> and quietly drop the rest. **Every caveat code needs customer prose**, or the
> surface fails to reconcile. This makes the wording work mandatory and complete
> rather than incremental.

---

## A.4 Narrative commentary

| Field | Current rendering | Tier | Business treatment |
|---|---|---|---|
| `passage.text` | `<p>` | **B** | Already customer prose. This is the one part of the current report that is already business-voiced. |
| `passage.cited_fact_ids` | `Cites: <code>…</code>` | **A** | Removed from B. The appendix carries passage→fact citations. |
| `narrative_state` | `data-narrative-state` | **I** | Operational. |
| `disclosure` | `<p class="disclosure">` | **B** | Governed customer text, and **immutable** — `bundle.py:1319-1323` compares it in full; shortening or re-translating it raises `disclosure_altered`. Stays in B verbatim. |

---

## A.5 Citations and provenance

| Field | Current rendering | Tier |
|---|---|---|
| `citations` (sorted citation ids) | `#citations` `<code>` list | **A** |
| `BundleIdentity.*` (all fields) | `#provenance` `<dl><code>` | **A** |
| `bundle_id` | provenance row | **A** — with a **B** short form: "Report reference 4A7C-2F91" |
| `html_surface_version`, `pdf_surface_version` | provenance row | **A** |
| formula / package version identifiers | provenance rows | **A** |

The primary report carries **one** identifier: a short human reference derived
from `bundle_id`. Everything else in the provenance table moves to the audit
layer unchanged.

---

## A.6 Internal-only — never on any customer surface

`GOVERNED_REASONS` (`bundle.py:365-386`, **20** codes) are **bundle integrity
failures**: `unknown_surface`, `missing_surface`, `duplicate_surface`,
`surface_failed`, `bundle_mismatch`, `unknown_language`, `missing_language`,
`wrong_direction`, `unknown_figure`, `figure_not_reconciled`,
`figure_coverage_differs_by_language`, `caveat_coverage_differs_by_language`,
`disclosure_altered`, `narrative_state_conflict`, `unknown_section`,
`figure_misplaced`, `section_not_presented`, `section_coverage_differs_by_language`,
`section_order_differs_by_language`, `chart_figure_not_stated`.

These are Internal for a structural reason, not a stylistic one: **when one of
them fires, no report is published.** They describe Khepri failing to build a
trustworthy artifact. A customer cannot encounter one in a delivered report, so
they belong in no customer-facing catalog — including the audit appendix.

> **Correction to earlier sessions.** These 20 were previously counted together
> with the section reasons to give a "32 governed refusal reasons" figure used as
> a product differentiator. That count is wrong for customer-facing purposes. The
> customer-facing catalog is **11 distinct codes yielding 13 code-in-context
> messages** — 8 section + 5 result, with `required_input_unavailable` and
> `incomplete_transaction_identifiers` appearing in both (see §D.1). The 20
> integrity codes are an internal correctness mechanism.

Also Internal: source module paths, stage telemetry, lease identifiers, job ids,
session ids, storage keys.

---

## A.7 Excel-specific

Source: `rendering/excel.py`.

| Current behaviour | Tier | Business treatment |
|---|---|---|
| Worksheet names built from `section_id` (`_section_sheet`, `excel.py:158`) | **A** | Business worksheets take business names (see IA). |
| `_write_report` row `(section_id, state, reason)` (`excel.py:374`) | **A** | Moves to Audit Trail. |
| Per-section repeat of `(section_id, state, reason)` (`excel.py:404`) | **A** | Removed from business sheets. |
| `_FIGURE_COLUMNS` identifier headers | **A** | Business sheets get business column names. |
| `caveat.code` rows | **A** + **B** prose | Business "Data Limitations" sheet. |
| Citations sheet | **A** | Stays, ordered last. |
| Provenance sheet | **A** | Stays, ordered last. |
| chartdata sheet | **A** | Already a mechanism sheet; belongs after the business sheets. |

---

## A.8 What this matrix does *not* change

Stated explicitly so an implementation slice does not over-reach:

- **No figure is recomputed.** `text` is still the string `bundle` produced. The
  renderers still hold no `Decimal` they could format (`html.py:1-9`).
- **No caveat, figure, or disclosure is dropped** — only relocated. Reconcile
  compares the `SurfaceContent` *claim*, never the document
  (`bundle.py:1271-1314`), so relocation is claim-neutral; **deletion is not.**
- **No new chart kind.** `GOVERNED_CHART_KINDS` stays at three.
- **PDF does not fork.** `pdf.py:193` already renders through the shared
  `build_context`, and `report.pdf.html.j2` *extends* the web template. The
  appendix is a template block plus a section move, not a second surface.
