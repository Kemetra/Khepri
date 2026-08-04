# Refusal presentation

**Status:** draft for owner approval. Docs only.

How a refusal reaches a customer. The governed reason code is the *mechanism*;
this document defines the *message*.

---

## D.0 The five-part contract

A customer-facing refusal states, in this order:

1. **What business analysis was unavailable** — named as a business capability,
   not a section id.
2. **Why the supplied data could not support it** — the actual cause, in the
   customer's terms.
3. **Whether the rest of the report remains valid** — explicitly, every time.
4. **Which missing field or evidence caused it** — named as a column a customer
   would recognise in their own export.
5. **How to make it available** — a concrete next action.

The raw governed reason code appears **only** in the audit evidence layer.

Part 3 is the part most easily dropped and the most valuable. A refusal that does
not say "the rest of this report is unaffected" invites the reader to distrust
the whole document.

---

## D.1 The catalog is 11 distinct codes, in 13 contexts — not 32

Three vocabularies exist and only two are customer-facing.

| Vocabulary | Count | Source | Customer-facing? |
|---|---|---|---|
| Section reasons | 8 | `GOVERNED_SECTION_REASONS`, `bundle.py:178-192` | **Yes** — kills a whole analysis |
| Result reasons | 5 | `facts.py:80-84` | **Yes** — kills one metric, section survives |
| Bundle integrity reasons | 20 | `GOVERNED_REASONS`, `bundle.py:365-386` | **No** — no report is published at all |

**8 + 5 = 13 messages, but only 11 distinct codes.** Two codes appear in *both*
customer-facing vocabularies:

- `required_input_unavailable`
- `incomplete_transaction_identifiers`

Each needs **two** messages, because the same code means different things at the
two levels: at section level the whole analysis is gone; at result level one metric
is gone and the section stands. §D.2 and §D.3 already word them separately.

> **Two corrections recorded rather than quietly fixed.**
>
> Earlier sessions summed all three vocabularies to "32 governed refusal reasons"
> and used it as a product differentiator. An earlier draft of *this document*
> corrected that to "13" — and reproduced the same double-counting error, summing
> two overlapping vocabularies. The honest statement is **11 distinct codes
> yielding 13 code-in-context messages**.
>
> The differentiator survives both corrections. "Analysis that tells you what it
> cannot tell you" is true of 11 codes just as it was of 32. What must not happen
> is shipping 20 internal integrity codes to customers, or quoting a catalog size
> that cannot be reproduced from the source.

**Keep the full catalog as an internal product and specification asset.** It is
not itself the customer report.

---

## D.2 Section refusals — whole analysis unavailable

Wording below is a draft for owner review. **The Arabic in §D.2a needs owner
authorship rather than proofreading** — `RRA-005` requires genuine parity, and
refusal prose is the hardest place to achieve it, because the English is written
to sound like a helpful shopkeeper rather than a system. A literal translation
will sound like a system.

### `prior_window_absent` — comparison, growth

> **Comparison with an earlier period — not available**
> Your file covers a single period, so there is no earlier period inside it to
> compare against. Everything else in this review is unaffected and describes the
> period you supplied. To add comparison, export a file that also covers the
> period you want to compare with — the same months a year earlier, or the months
> immediately before.

### `required_input_unavailable` — comparison, growth, basket

> **[Analysis name] — not available**
> The figures this analysis needs are not present in the file. The rest of the
> review is unaffected. Include [named column] in your export and this becomes
> available.

Cause-specific column naming is required — this code is reused by three families
and a generic message would be uninformative in all three.

### `aggregate_unavailable` — concentration

> **Sales concentration — not available**
> The totals this analysis is built from could not be produced from the supplied
> rows. The rest of the review is unaffected.

### `distinct_set_uncomputable` — concentration

> **Sales concentration — not available**
> Concentration compares each product or branch against all the others, and the
> file does not identify them distinctly enough to separate one from another. The
> rest of the review is unaffected. Export with a consistent product or branch
> name in every row and this becomes available.

### `units_absent` — growth

> **Growth drivers — not available**
> Splitting growth into price and volume needs a quantity for each sale, and the
> file has none. Revenue figures are unaffected — the review still shows how much
> revenue changed, but not how much of that change came from price rather than
> from volume. Include the quantity sold in your export and this becomes
> available.

### `decomposition_not_additive` — growth

> **Growth drivers — withheld**
> Price and volume effects were calculated, but they do not add up to the total
> revenue change. Rather than present a split that does not reconcile, it is
> withheld. Revenue figures are unaffected and remain correct. This usually means
> quantities and revenue in the file are measured over different sets of rows.

This is the sharpest refusal in the catalog and worth its own note: Khepri
computed an answer and **declined to publish it** because it failed an internal
consistency test. That is the differentiator made visible.

### `transaction_identifier_absent` — basket

> **Basket size — not available**
> Your file has no receipt or invoice number, so there is no way to tell which
> rows belong to the same sale. Counting rows instead would overstate basket size
> wherever one sale spans several lines. The rest of the review is unaffected.
> Export with the receipt number included and this becomes available.

### `incomplete_transaction_identifiers` — basket

> **Basket size — not available**
> Some rows carry a receipt number and some do not. Basket size calculated from
> the rows that have one would describe part of your sales and be presented as if
> it described all of them. The rest of the review is unaffected. Export with a
> receipt number on every row and this becomes available.

---

## D.2a Arabic draft — section refusals

Western numerals throughout (§B.4a). Each entry keeps the five-part contract:
what, why, rest-still-valid, which field, how to fix.

### `prior_window_absent`

> **المقارنة بفترة سابقة — غير متاحة**
> يغطي ملفك فترة واحدة، فلا توجد داخله فترة أسبق للمقارنة بها. وما عدا ذلك في هذا
> التقرير غير متأثر، وهو يوصف الفترة التي قدّمتها. ولإتاحة المقارنة، صدِّر ملفاً
> يغطي أيضاً الفترة التي تريد المقارنة بها — الأشهر نفسها من العام السابق، أو
> الأشهر التي تسبقها مباشرة.

### `required_input_unavailable`

> **[اسم التحليل] — غير متاح**
> الأرقام التي يحتاجها هذا التحليل غير موجودة في الملف. وما عدا ذلك في التقرير غير
> متأثر. أضِف [اسم العمود] إلى ملف التصدير ليصبح هذا التحليل متاحاً.

### `aggregate_unavailable`

> **تركّز المبيعات — غير متاح**
> الإجماليات التي يُبنى عليها هذا التحليل لم يتسنَّ إنتاجها من الصفوف المقدَّمة. وما
> عدا ذلك في التقرير غير متأثر.

### `distinct_set_uncomputable`

> **تركّز المبيعات — غير متاح**
> يقارن تحليل التركّز كل منتج أو فرع بالبقية، والملف لا يحدّد هويتها بدرجة تكفي
> للتمييز بينها. وما عدا ذلك في التقرير غير متأثر. صدِّر الملف باسم منتج أو فرع
> ثابت في كل صف ليصبح هذا التحليل متاحاً.

### `units_absent`

> **محرّكات النمو — غير متاحة**
> يحتاج تقسيم النمو إلى سعر وكمية إلى كمية مبيعة لكل عملية، وهي غير موجودة في
> الملف. أرقام الإيرادات غير متأثرة — يبيّن التقرير مقدار تغيّر الإيرادات، لكن لا
> يبيّن ما جاء منه من السعر وما جاء من الكمية. أضِف الكمية المبيعة إلى ملف التصدير
> ليصبح هذا التحليل متاحاً.

### `decomposition_not_additive`

> **محرّكات النمو — محجوبة**
> حُسب أثر السعر وأثر الكمية، لكن مجموعهما لا يساوي إجمالي تغيّر الإيرادات. وبدلاً
> من عرض تقسيم لا يتوازن، حُجب. أرقام الإيرادات غير متأثرة وتبقى صحيحة. وغالباً ما
> يعني ذلك أن الكميات والإيرادات في الملف مقيسة على مجموعتين مختلفتين من الصفوف.

### `transaction_identifier_absent`

> **حجم سلة الشراء — غير متاح**
> لا يحتوي ملفك على رقم فاتورة أو إيصال، فلا توجد طريقة لمعرفة أي الصفوف تنتمي إلى
> البيع نفسه. وعدّ الصفوف بدلاً من ذلك سيضخّم حجم السلة في كل بيع يمتد على عدة
> أسطر. وما عدا ذلك في التقرير غير متأثر. صدِّر الملف مع رقم الإيصال ليصبح هذا
> التحليل متاحاً.

### `incomplete_transaction_identifiers`

> **حجم سلة الشراء — غير متاح**
> بعض الصفوف تحمل رقم إيصال وبعضها لا يحمله. وحجم السلة المحسوب من الصفوف التي
> تحمله يوصف جزءاً من مبيعاتك ويُعرض كأنه يوصفها كلها. وما عدا ذلك في التقرير غير
> متأثر. صدِّر الملف مع رقم إيصال في كل صف ليصبح هذا التحليل متاحاً.

---

## D.3 Result refusals — one metric unavailable, analysis survives

These are the part 3 case in its most useful form: the section stands.

| Code | Business message |
|---|---|
| `required_input_unavailable` | "[Metric] is not shown — the file does not contain [column]. The other figures in this section are unaffected." |
| `zero_denominator` | "[Metric] cannot be calculated for this period because the figure it divides by is zero. The other figures in this section are unaffected." |
| `reconciliation_failed` | "[Metric] was calculated but did not reconcile against its own inputs, so it is withheld rather than shown. The other figures in this section are unaffected." |
| `incomplete_transaction_identifiers` | "[Metric] is not shown — receipt numbers are missing from some rows, so this would describe only part of your sales. The other figures in this section are unaffected." |
| `ambiguous_mapping` | "[Metric] is not shown — more than one column in the file could be the [field] and it is not clear which. Rename or remove the duplicate and this becomes available." |

`dimension_absent` is referenced in `bundle.py`'s comments as a result-level
reason belonging to the fact package. It is **not currently defined** in
`facts.py`. The basket slice that introduces attach rate adds it. Its message:

> "Attach rate is not shown — the file has no product or category column to
> measure attachment against. Items per sale is unaffected."

---

## D.4 Caveats — all twelve, complete

Caveats qualify an analysis that **was** published. They are not refusals and
must not read as apologies.

`_reconcile_language` (`bundle.py:1324-1325`) requires **set equality** between
claimed and bundle caveats, so an unworded caveat is a reconcile failure rather
than a cosmetic gap. An earlier draft of this document worded one code and
deferred the rest to "the implementation slice" — which contradicted its own
finding. All twelve are enumerated below.

The vocabulary: nine in `facts.py:86-94`, two in `bundle.py:148,163`, one in
`analysis/growth.py:84`.

| Code | Source | Business message |
|---|---|---|
| `currency_not_declared` | `facts.py:86` | "Your file does not state which currency the amounts are in. The figures are shown as supplied and have not been converted." |
| `duplicate_rows_present` | `facts.py:87` | "Some rows in your file are exact duplicates of each other. They have been counted as supplied — if they are genuine repeat sales this is correct, and if they are an export error the totals are overstated." |
| `negative_revenue_present` | `facts.py:88` | "Some rows carry a negative sale amount. These are included as supplied, which is correct if they are refunds recorded in the sales file." |
| `returns_not_netted` | `facts.py:89` | "Returns are reported separately and have not been subtracted from revenue. Revenue here is gross of returns." |
| `null_measure_inputs` | `facts.py:90` | "Some rows have no amount recorded. They are excluded from the totals rather than counted as zero." |
| `rows_without_time_field_excluded` | `facts.py:91` | "Some rows carry no date. They are excluded from anything measured by period, so month-by-month figures cover slightly fewer rows than the totals." |
| `comparison_buckets_truncated` | `facts.py:92` | "Your file covers more periods than this comparison shows. The comparison uses the most recent complete periods." |
| `personal_values_redacted` | `facts.py:93` | "Values that appeared to identify individual people were removed before analysis. No figure in this report depends on them." |
| `derived_metrics_use_matched_rows` | `facts.py:94` | "Figures that combine two measures — such as average price — use only the rows where both measures are present. They may therefore cover fewer rows than either measure alone." |
| `chart_not_drawn` | `bundle.py:148` | "No chart is shown for this section. The figures beside it are complete." |
| `curve_points_sampled` | `bundle.py:163` | "The concentration curve is drawn from 100 evenly spaced points across your full product range. The figures beside it use every row." |
| `growth_interaction_assigned_to_price` | `analysis/growth.py:84` | "Where price and quantity both changed, the combined part of the change is counted with the price effect. This is a stated convention, applied the same way every time, so the two effects still add exactly to the total." |

> **Arabic for all twelve is required and is not drafted here.** §D.2a drafts the
> eight section refusals; these twelve need the same treatment and the same owner
> authorship. Western numerals throughout (§B.4a).

**Completeness must be enforced at import, not reviewed.** `wording.py:120-122`
already establishes the pattern — a key-set assertion that raises at import when a
table and its vocabulary disagree. The caveat table needs the same guard against
the union of the three source modules, because the failure mode without it is
`REASON_SURFACE_FAILED` at render time on a customer's report.

---

## D.5 Placement

| Surface | Where refusals appear |
|---|---|
| HTML | §7 "What this review does not cover" — one card per refusal. Raw codes on the Technical Evidence page. |
| PDF | §7 in the business body. Raw codes in Appendix B. |
| Excel | "Data Limitations" worksheet (sheet 7). Raw codes on Audit Trail (sheet 9). |

Refusals are **never** collapsed into a footnote and never rendered as a bare
code on any customer surface.

---

## D.6 Tone rules

- Address the reader as the owner of the data: "your file", not "the input".
- Name the fix as an export action, because that is what the customer controls.
- Never use "error", "invalid", "failed", or "rejected". The data is not wrong;
  it does not contain a particular field.
- Never apologise. State the boundary and the remedy.
- Never blame the customer. "Your file has no receipt number" is a fact;
  "you did not include a receipt number" is an accusation.
- State part 3 in every single refusal, without exception.
