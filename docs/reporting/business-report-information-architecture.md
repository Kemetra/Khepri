# Business-report information architecture

**Status:** draft for owner approval. Docs only.

Companion to `presentation-visibility-matrix.md`, which classifies *fields*. This
document defines *structure*: what the customer-facing report is, in what order,
on each of the three surfaces — and where the audit layer attaches.

---

## B.0 The governing principle

> **Lead with the finding. The number is evidence for the finding, not the
> finding itself.**

The current report is ordered by *mechanism*: sections in bundle order, each a
table of figures, then caveats, then citations, then provenance. That is the
order in which Khepri computed things.

A business report is ordered by *decision relevance*: what happened, why, who
drove it, what it means, what is missing. That is the order in which a retail
owner reads.

Every rule below follows from that inversion.

---

## B.1 Two layers — always generated, separately delivered

| Layer | Purpose | Audience | Delivery |
|---|---|---|---|
| **Business report** | The deliverable. Findings, figures, charts, limitations. | The customer, their staff, their bank | **Always** |
| **Audit evidence** | The defensibility mechanism. Identifiers, citations, provenance. | An auditor, a sceptical CFO, a dispute | **On request** |

**Owner decision, 2026-08-04: the business report is the product; the audit
evidence is optional to the customer.**

The word "optional" is load-bearing and applies to **delivery only**. The
distinction is not stylistic — getting it the other way round breaks the build.

### Why the audit layer is always *generated*

`REQUIRED_SURFACES = (web, pdf, excel)` (`bundle.py:89`) is compared for exact
equality in six places — `bundle.py:1222`, `pipeline.py:156`, `pipeline.py:345`,
`reports.py:253`, `delivery_persistence.py:349`, `benchmark_trial.py:164`. A
bundle that produces fewer than three surfaces returns
`REASON_MISSING_SURFACE` and becomes an **incomplete bundle**
(`bundle.py:1222-1223`) — meaning no report is delivered at all, not a smaller
report.

There is a second and stronger reason. `surface_digest`
(`delivery_persistence.py:242-250`) content-addresses what each surface
*presented*. If audit content were generated conditionally, two runs of the same
input would produce different digests depending on a customer preference — and
"re-running the same input reproduces the same bundle identity" is the claim the
product is sold on. Conditional generation would make reproducibility a function
of a preference rather than of the data.

**So the audit layer is generated for every report, always, unconditionally.**

### Why it is delivered *within* the surface, not filtered out of the delivery

> **Corrected 2026-08-04 after external review.** An earlier version of this
> section claimed the audit layer could be withheld by a *delivery-time filter*,
> citing `delivery_persistence.py:239` and its `if surface in found` guard as
> evidence that "the delivery layer already tolerates reading a subset."
> **That reading was wrong, and the claim it supported was false.**

Line 239 is a *corruption detector feeding a rejector*, not a tolerance for
subsets. Its consumer rejects any partial delivery outright:

```python
named = tuple(entry.surface for entry in surfaces)
if named != REQUIRED_SURFACES:
    raise DeliveryCorrupted("Stored delivery does not name every required surface.")
```
> `delivery_persistence.py:346-350`

Two further equality gates sit on the same path — `pipeline.py:156` ("A delivered
report names every required surface") and `pipeline.py:345` ("A delivery carries
every required surface exactly once"). So there are **seven** equality checks, not
six, and the seventh is the one the filter story depended on being permissive.

### The corrected mechanism: within-surface suppression

All three surfaces are generated, stored, and read **whole**. The audit content is
a *region inside each surface*, and optionality is a **render variant** — which
region the customer's copy includes — decided before the surface is stored, not a
subset selected at download.

| Surface | Business variant | With-evidence variant |
|---|---|---|
| HTML | Report page; colophon points to evidence | Report page + Technical Evidence page |
| PDF | Business body, appendix block empty | Business body + appendix after a page break |
| Excel | Business worksheets; audit sheets absent | Business worksheets + Audit Trail + Provenance |

Both variants are complete `web`/`pdf`/`excel` surfaces. `REQUIRED_SURFACES` is
satisfied in both cases, every equality gate passes, and no delivery contract
changes.

**The open question this leaves, and it is the owner's call.** Two variants of one
report means either (i) the customer chooses before generation, so one variant is
produced and stored — which makes `surface_digest` a function of the choice as well
as the data, weakening but not breaking reproducibility, since the digest still
pins exactly what was shown; or (ii) both variants are produced, which needs a
place to put the second one — a fourth non-required deliverable outside
`REQUIRED_SURFACES`, and *that* is a delivery-contract change.

**Recommended: (i).** It changes no contract, and the reproducibility claim that
matters commercially is "this report re-runs to this identity," which (i)
preserves. Route (ii) is the right answer only if a customer must be able to
request the evidence *after* receiving the report without re-running it — worth
asking a prospect, not worth assuming.

**Either way, the audit layer is generated with every report.** Skipping a surface
returns `REASON_MISSING_SURFACE` and yields an incomplete bundle
(`bundle.py:1222`). That part of the original argument stands.

### What the customer sees

| Surface | Default delivery | On request |
|---|---|---|
| **HTML** | Business report page | "Technical evidence" — a separate page, linked from the colophon |
| **PDF** | Business PDF, no appendix | Appendix PDF (or the combined file) |
| **Excel** | Business worksheets 1–7 | Full workbook including sheets 8–10 |

The business report names its reference and points to the evidence, once, in the
colophon — and carries no identifier anywhere else:

> **Report reference 4A7C-2F91 · version 2**
> Full calculation evidence and data lineage available on request.

That pointer is deliberate. It keeps the defensibility claim visible to the
reader — a report that never mentions its own evidence cannot be forwarded to an
auditor by someone who does not know the evidence exists — while putting no
figure id, digest, or reason code in the body.

---

## B.2 HTML

```
Business report  (report.html)
├── Header
│   ├── Report title + client name + period covered
│   └── Governed disclosure                    ← verbatim, immutable
├── 1. Summary
│   ├── Lead finding (prose, 1–3 sentences)
│   ├── Hero figure + delta
│   └── KPI row (≤ 4 stat tiles)
├── 2. Sales performance
│   ├── Finding sentence
│   ├── Chart (line — trend)
│   └── Supporting figures (business names, no identifiers)
├── 3. Period comparison
│   ├── Finding sentence
│   └── Chart (grouped bar)
├── 4. Growth drivers
│   ├── Finding sentence
│   └── Chart (grouped bar — price / volume effects)
├── 5. Concentration
│   ├── Finding sentence
│   └── Chart (line — cumulative share curve)     ← RRA-008 requires this kind
├── 6. Basket analysis
│   ├── Finding sentence
│   └── Chart (bar)
├── 7. What this review does not cover           ← §D refusals + caveats, in prose
├── Commentary                                   ← narrative passages, no cited ids
└── Colophon
    ├── "Report reference 4A7C-2F91 · version 2"
    └── "Full calculation evidence and data lineage available on request."
        (link → Technical Evidence, when the customer has requested it)

Technical Evidence  (report.evidence.html)          ← generated always, served on request
├── How to read this page
├── Figures table        ← figure_id, metric, kind, unit_kind, value, citation_id
├── Section states       ← section_id, state, raw reason code
├── Caveat codes         ← raw codes beside their customer prose
├── Citations            ← citation_id → fact
├── Commentary citations ← passage → cited_fact_ids
└── Provenance           ← full BundleIdentity, bundle_id, surface versions
```

A refused section keeps its numbered place in the business report **only if its
refusal is worth a heading**; otherwise it appears under §7. Recommended: refused
sections appear under §7 and the numbered list contracts, so a customer does not
read six headings of which three are apologies. This is a design choice the owner
should confirm — the alternative (keep the heading, put the prose under it) is
also defensible and preserves a 1:1 map to the bundle's sections.

---

## B.3 PDF

The PDF reuses the HTML structure — `pdf.py:193` already renders through the
shared `build_context`, and `report.pdf.html.j2` extends the web template. So:

```
Page 1        Cover — title, client, period, disclosure, report reference
Pages 2–n     Business report §1–§7   (same content as HTML, paginated)
              ── page break ──                    ← appendix omitted by default
Appendix A    Figures and citations                 (delivered on request)
Appendix B    Section states and reason codes       (delivered on request)
Appendix C    Provenance and versions               (delivered on request)
```

The appendix begins on a fresh page with its own running header. Because the
default delivery omits it entirely, the business PDF ends at the colophon and is
a complete document on its own — a customer who prints and forwards it is not
forwarding a truncated file.

**No forked template.** The appendix is a `{% block appendix %}` in the shared
template. This preserves the DEC-005 single-engine property: Arabic/English
parity, the disclosure, and the figure set stay correct in one place.

**Two printed artifacts, one generation pass.** The appendix block is rendered
whether or not it is delivered, because the surface content must still reconcile
(see §B.1). Which file the customer downloads is a delivery-layer choice:

| Requested | Delivered |
|---|---|
| Business report (default) | Pages 1–n, appendix suppressed |
| With evidence | The full document, appendix included |

---

## B.4 Excel

Worksheet order **is** the information architecture in a workbook, because it is
what a reader sees on opening. Business sheets first, in reading order; mechanism
sheets last.

| # | Worksheet | Tier | Delivered | Contents |
|---|---|---|---|---|
| 1 | Executive Summary | B | always | Lead finding, hero figures, KPI block, period covered, disclosure |
| 2 | Sales Performance | B | always | Revenue / units / sales / average sale / average price / margin by period |
| 3 | Period Comparison | B | always | Current vs prior, absolute and percentage, with per-line assessment |
| 4 | Growth Drivers | B | always | Price effect, volume effect, total change |
| 5 | Profitability | B | always | Revenue, cost, gross profit, gross margin; monthly margin trend |
| 6 | Discounts and Returns | B | always | Discounts, returns, combined leakage as a share of revenue |
| 7 | Branch Performance | B | always | Ranked contribution per branch — the concentration family, rebadged² |
| 8 | Data Limitations | B | always | Every refusal and caveat in customer prose (§D) |
| 9 | Chart Data | A | always¹ | Existing chartdata sheet — the one numeric write path (`APP-013`) |
| 10 | Audit Trail | A | on request | section_id, state, raw reason, figure_id, metric, kind, unit_kind, citation_id |
| 11 | Provenance | A | on request | Full BundleIdentity, bundle_id, surface versions |

> **Revised 2026-08-04 after external review**, which found the earlier table
> disagreed with the golden sample. The table now matches the sample. Three changes
> and the reasons for them:
>
> - **`Profitability` and `Discounts and Returns` added.** The earlier table covered
>   four metrics; the governed vocabulary is twelve. `cost`, `gross_profit`,
>   `gross_margin`, `discount` and `returns` had no worksheet to live on.
> - **`Product & Category Performance` renamed `Branch Performance`.**
>   Same sheet, same adopted decision (a) — the concentration family's ranked
>   buckets. The bucket dimension is whatever the customer's file supplies, which
>   for a retail chain is usually branch; the old name implied product only.
>   The short form is forced by the 31-character cap — see note 2.
> - **`Basket Analysis` removed as a standing sheet.** Basket is the family most
>   often refused (`transaction_identifier_absent` needs a receipt number most
>   exports lack), and a worksheet whose only content is an apology is worse than
>   its absence. When basket is *present* it takes a sheet in this position; when
>   refused it appears in Data Limitations. **This makes the business sheet set
>   dependent on which analyses survived** — a property the audit sheets do not have,
>   and worth stating because it means the workbook's tab count varies by dataset.

¹ Sheet 8 holds the chart series addresses the embedded charts read, and it must
ship with the business workbook or the native charts break. `_series_range`
(`excel.py:656-665`) addresses the chartdata sheet **by name**, so a chart whose
series points at a removed sheet renders empty. It carries no authoritative figure
and no citation (`excel.py:56-60`), so it is Audit-tier by classification but
always-delivered by necessity.

**It stays visible.** An earlier draft of this document recommended hiding it for
tab-bar tidiness. That was wrong, and `excel.py:71-75` already argues why:

> "It is a visible worksheet, not a hidden one. Hiding numbers that a decision
> permits only conditionally is the wrong direction: an auditor opening the
> workbook is owed every cell in it, and the disclosure that these are chart
> machinery is the section identifier written above each block, not their absence
> from the tab bar."

The reasoning is sound and it is an auditability property, not a style preference.
`APP-013` permits a numeric cell *conditionally* — solely as a chart series
address, on a dedicated worksheet holding no authoritative figure and no citation
identifier. A conditional permission that hides its own evidence is worse than no
permission. **Do not hide this sheet.** The block-level section identifiers written
above each series (`_write_chart_block`, `excel.py:587-593`) are the disclosure
that these cells are machinery.

Business sheets carry **business column names**. No sheet in 1–7 contains a
`figure_id`, `citation_id`, raw `metric`, `kind`, or `unit_kind` column.

**Two workbooks, one generation pass.** The default download carries sheets 1–8;
the on-request download carries all ten. Both are written from the same bundle in
the same pass, so no figure can differ between them.

² **Excel caps worksheet names at 31 characters, and this binds the suffix
decision.** Found while regenerating the golden sample: XlsxWriter raises
`InvalidWorksheetName` on a 33-character name. With ` (English)` costing 10
characters, a business sheet name has a **21-character budget**. Measured:

| Name | With suffix | |
|---|---|---|
| `Executive Summary` | 27 | ok |
| `Discounts and Returns` | **31** | at the limit, zero headroom |
| `Branch & Category Performance` | 39 | **rejected** → `Branch Performance` (28) |

The Arabic suffix ` (العربية)` is the same 10 characters, so the budget is
symmetric. Two consequences for the implementation slice:

- **The business sheet names in the table above are the long form.** Any name
  exceeding 21 characters must be shortened, and the shortened form is what a
  customer reads — so it is a wording decision, not a truncation. Never let
  XlsxWriter or Excel truncate silently.
- **A key-set assertion at import should also assert the length budget**, in the
  same style as `wording.py:120-122`. The failure without it is an exception during
  a customer's report render, and a 22-character name added later would pass every
  review and fail on the first bilingual workbook.

This is a real constraint on the adopted decision (a) that was not visible when it
was adopted. It does not overturn the decision — every required name fits within
the budget — but it does mean **option (b), two workbooks, buys 10 characters of
name budget** as well as fewer tabs. Worth remembering if a future sheet needs a
longer name.

### The table above is per language, and the real workbook is bilingual

`_write_workbook` (`excel.py:341-354`) loops `for language in LANGUAGES` and
writes every sheet twice — `_REPORT_SHEET`, `_CITATION_SHEET` and the section
sheets are all per-language dictionaries (`excel.py:147-148`). Only `Provenance`
is written once, in English (`excel.py:688`), because it holds nothing
translatable.

So the delivered workbook is roughly **15 sheets, not 10**: seven business sheets
× 2 languages, a hidden chartdata sheet × 2, an Audit Trail × 2, and one shared
Provenance sheet.

**The golden sample shows the English half only.** That is a deliberate
simplification to keep the sample readable, and it is the one place the sample
diverges from the delivered artifact. Two naming options existed:

| Option | Sheet names | Trade-off |
|---|---|---|
| **(a)** Suffix, as today | `Executive Summary (English)` / `الملخص التنفيذي (العربية)` | Consistent with the current `_REPORT_SHEET` convention; 15 tabs is a lot to scan |
| **(b)** Two workbooks | One file per language, 8 tabs each | Cleaner for the reader; doubles the delivered files and needs a delivery-layer change |

**Adopted: (a), owner-authorized 2026-08-04.** It changes no delivery contract,
and a bilingual client opening one file is the behaviour customers have already
seen. Revisit if 15 tabs tests badly with real readers — reversing it is a
delivery-layer change, not a bundle change.

Sheet 5 (Product & Category) is listed because the owner asked for it. The
current bundle's section set is
`overview / comparison / concentration / growth / basket` — there is no
product-or-category performance section. Two options existed: (a) re-present the
concentration family's ranked buckets under a business name, or (b) add a new
`RRA-008` family.

**Adopted: (a), owner-authorized 2026-08-04.** It needs no new governed analysis,
and the concentration family already ranks buckets by contribution. Sheet 5 is a
presentation of `concentration` and nothing more; the ranked-bucket figures it
shows are the same figures the concentration section states, so the two can never
disagree.

Sheet 7 is where the reconcile constraint lands: `bundle.py:1324` requires the
caveat set to match exactly, so this sheet must be complete, not curated.

---

## B.4a Conventions checked against outside practice

The structure above was designed from Khepri's own field inventory. Its *look and
voice* were not — those were assumed, so they were checked against retail
reporting practice on 2026-08-04. Four results, one of which corrected the sample.

### Confirmed

**Findings before figures, with progressive disclosure.** Retail business-review
practice puts a short executive layer first — "whether the business is on track
and where attention is needed" — then drivers, then detail. §B.0's inversion and
§B.2's section order match this. No change.

**Four KPIs at the executive level is the right ceiling.** Practice warns against
including data "simply because it's available" and recommends the few signals that
*explain* performance rather than describe it. The sample's 4-tile row is at the
limit, not below it.

**Limitations as specific, actionable exceptions.** Practice recommends alerts
that "explain why the issue matters, and point to the owner or next step" over
undifferentiated flagging. This is independently the same shape as §D's five-part
refusal contract — particularly part 5, the export action. Convergent, so §D
stands as written.

### Corrected

**Western numerals (0–9) in Arabic financial text, not Eastern (٠–٩).** Western
numerals are the safe commercial default across the Arabic-speaking world;
Eastern Arabic numerals appear in literary and formal contexts, not commercial
documents. The golden sample originally rendered the Arabic summary with
`٢٫١٪` / `٤٫٧٪` / `٧١٪` and has been corrected to `2.1%` / `4.7%` / `71%`.

**Rule for the implementation slice:** Arabic report text uses Western numerals.
This is a wording-layer rule, not a formatting one — `bundle` already produces the
figure strings and the renderers must not reformat them (`html.py:1-9`), so the
Arabic renderings must be *generated* with Western numerals in `bundle`, never
transliterated at the surface.

**RTL means mirroring the layout, not just the text.** Tables, charts, and
diagrams all mirror; bullets align right. Khepri already does this correctly —
one document per language each declaring its own `dir`, logical CSS properties
throughout (`html.py:11-17`), and `chart.set_x_axis({"reverse": True})` for the
Arabic category axis (`excel.py:645-652`). Noted as already-satisfied so the
implementation slice does not "fix" it.

### A gap worth naming, not closing here

**Comparable-store ("like-for-like") sales is the metric this buyer segment reads
first, and Khepri does not compute it.** Total revenue growth conflates a concept
getting stronger with a chain getting bigger: a retailer can post 24% total growth
while comparable sales fall 3%. Operators and lenders treat like-for-like as the
cleanest read on whether the business is actually improving.

This is **out of scope for this package** — it is a new governed analysis, not a
presentation change, and would need an `RRA-008` family. It is recorded here
because it is the most likely "why isn't this in the report?" question from a
mid-market retail buyer, and because the roadmap should carry it. Note the
dependency: it needs branch-level data across two comparable periods, which is
also what `prior_window_absent` currently refuses on. **Recommended: add to the
roadmap as a Phase 3 candidate** (multi-dataset accumulation), where the retention
change that makes two comparable periods available is already planned.

Sources: [Umbrex retail KPI dashboard playbook](https://umbrex.com/resources/retail-industry-playbooks/retail-kpi-dashboard-weekly-business-review-playbook/designing-the-retail-kpi-dashboard/) ·
[Arabic invoicing and RTL conventions](https://invovate.com/blog/invoicing-in-arabic) ·
[RetailDogma on same-store sales](https://www.retaildogma.com/same-store-sales/) ·
[Toolio comparable-store reporting guide](https://www.toolio.com/post/your-go-to-guide-for-comparable-store-sales-reporting-and-planning)

---

## B.5 Naming — business names for governed metrics

The matrix (§A.1) established there is **no existing translation path for
`metric`**. This is the table that has to exist. Illustrative, not exhaustive —
the implementation slice derives the full key set from the governed metric
vocabulary.

The governed metric vocabulary is **13 keys**: ten metrics (`facts.py:69-78`) plus
the three in `growth.GOVERNED_METRICS` (`analysis/growth.py:71-74`). The earlier
draft covered four and left the rest to reach the page as raw identifiers.

> **Corrected while verifying the assertion is implementable.** Two earlier drafts
> said "twelve metrics — ten plus two growth effects." `growth.py:74` exports
> `GOVERNED_METRICS = (METRIC_REVENUE_CHANGE, METRIC_PRICE_EFFECT,
> METRIC_VOLUME_EFFECT)` — **three**, not two. `growth_revenue_change` is a governed
> metric in its own right, not the "derived label" the table below once filed it as.
>
> **Assert against the exported tuple, never against scraped `METRIC_*` names.**
> `growth.py` also *imports* `METRIC_UNITS` from `facts`, so a module-level scan for
> the `METRIC_` prefix picks up four names and one of them is a re-export. The
> exported tuple is the vocabulary; the name prefix is a coincidence of style.

> **This table must be complete at import, and an incomplete one means no report.**
> `worded()` (`wording.py:149-151`) does `return LABEL_WORDING[language][key]` and
> raises on a missing code by deliberate design — the docstring says "a missing one
> raises rather than falling back to the code… a fallback would ship it quietly." A
> `KeyError` raised inside a renderer is caught at `bundle.py:1213-1219` as
> `REASON_SURFACE_FAILED`, which produces an **incomplete bundle**.
>
> So a missing business name is not an ugly label on a customer's report — it is the
> absence of the report. Guard the table with an import-time key-set assertion in the
> style `wording.py:120-122` already establishes:
>
> ```python
> if set(_headings) != set(ORDERED_SECTIONS):
>     raise RuntimeError(...)
> ```
>
> Assert against the union of `facts.py`'s metric constants and
> `analysis/growth.py`'s effect constants, so a metric added later cannot reach a
> renderer unworded.

| Governed metric | English business name | Arabic business name |
|---|---|---|
| `revenue` | Revenue | الإيرادات |
| `units` | Units sold | الوحدات المبيعة |
| `transactions` | Number of sales | عدد المبيعات |
| `average_order_value` | Average sale value | متوسط قيمة البيع |
| `average_selling_price` | Average selling price | متوسط سعر البيع |
| `cost` | Cost of goods sold | تكلفة المبيعات |
| `gross_profit` | Gross profit | إجمالي الربح |
| `gross_margin` | Gross margin | هامش الربح الإجمالي |
| `discount` | Discounts given | الخصومات الممنوحة |
| `returns` | Returns | المرتجعات |
| `growth_revenue_change` | Total revenue change | إجمالي تغير الإيرادات |
| `growth_price_effect` | Effect of price changes | أثر تغير الأسعار |
| `growth_volume_effect` | Effect of volume changes | أثر تغير الكميات |

Derived labels the surfaces also need — **not** part of the 13-key assertion, because
they are not governed metric codes:

| Concept | English | Arabic |
|---|---|---|
| Items per sale (basket) | Items per sale | عدد الأصناف لكل بيع |
| Attach rate (basket) | Attach rate | معدل الإضافة |
| Concentration bucket share | Share of sales | نصيب من المبيعات |
| Cumulative share | Cumulative share | النصيب التراكمي |

> **The Arabic column above is a draft and needs owner authorship, not owner
> proofreading.** `RRA-005` requires genuine bilingual parity, and a translated
> English column is not parity — it is English wearing Arabic script. Two
> specific places to check: `gross_margin` vs `gross_profit` are distinguished in
> Arabic accounting usage by more than an adjective, and "attach rate" has no
> settled Arabic retail term, so `معدل الإضافة` may need replacing with a phrase
> rather than a term.
>
> **Numerals: Western (0–9), never Eastern (٠–٩)** — see §B.4a. This is a
> `bundle`-layer rule, not a surface one.

---

## B.6 Flagged implementation dependencies

Recorded here rather than resolved, so the owner sees the risk before approving.

1. **Reconcile is claim-based, not document-based — verified.**
   `reconcile` (`bundle.py:1271-1314`) validates the `SurfaceContent` claim
   against the bundle and never parses the rendered document. Relocating a field
   from the business report to the audit layer changes no claim. **The separation
   is a pure presentation change.** No change to the reconcile contract is
   required, and none is proposed.

2. **Caveat set equality is binding.** `bundle.py:1324` — every caveat must be
   claimed. Customer prose is required for all of them; a subset fails closed.

3. **Disclosure is immutable.** `bundle.py:1319-1323` compares it in full.
   It cannot be reworded for tone.

4. **`metric` has no translation hook.** Unlike `label`
   (`GOVERNED_FIGURE_LABELS` → `_row_label`). §B.5's table is new work.

5. **Excel sheet 5 has no governed section.** See §B.4. Recommendation (a)
   avoids new governed analysis.

6. **Chart kinds stay at three.** `GOVERNED_CHART_KINDS`. The waterfall in the
   golden sample is a grouped bar, as `bundle.py:306-314` already documents.

7. **`SECTION_HEADINGS` already exists and is already business-voiced.** The
   section heading path is the one part of this that needs no new mechanism.

8. **Optionality is a render variant per surface — never a delivery filter.**
   `REQUIRED_SURFACES` is compared for exact equality in **seven** places:
   `bundle.py:1222`, `pipeline.py:156`, `pipeline.py:345`, `reports.py:253`,
   `delivery_persistence.py:349`, `benchmark_trial.py:164`, and
   `delivery_persistence.py:346-350` — the last of which raises `DeliveryCorrupted`
   on a partial delivery. All three surfaces are always produced, stored, and read
   whole. **Do not implement optionality by skipping generation, and do not
   implement it by filtering the delivery.** See §B.1.

9. **The workbook is bilingual and the sample is not.** ~17 sheets delivered
   versus 12 shown. Suffix naming adopted; see §B.4.

10. **Excel's chart-data sheet must ship with the business workbook and stay
    visible.** `_series_range` (`excel.py:656-665`) addresses it by name, so the
    native charts break without it — and `excel.py:71-75` requires it visible on
    `APP-013` grounds. An earlier draft of this document recommended hiding it; that
    was withdrawn. Hiding it would need an `APP-013` amendment, and `APP-013` pins
    `KHEPRI-DEC-005` by document digest.

11. **`worded()` raises on a missing key, so every wording table is a
    no-report-if-incomplete dependency**, not a cosmetic one. See §B.5.

12. **Excel worksheet names cap at 31 characters**, leaving 21 once the bilingual
    suffix is added. See §B.4 note 2.

13. **Test migration is the largest single work item and is unpriced here.** 19 test
    files carry ~170 references to the structure being relocated, and
    `tests/test_rra006_excel_charts.py` pins the chart-data sheet by name in eleven
    places. The tests currently assert the ledger structure is correct, so migrating
    them is a contract decision rather than a find-and-replace. See the README.
