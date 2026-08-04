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

## D.1 The catalog is 13, not 32

Two vocabularies exist and only one is customer-facing.

| Vocabulary | Count | Source | Customer-facing? |
|---|---|---|---|
| Section reasons | 8 | `GOVERNED_SECTION_REASONS`, `bundle.py:178-192` | **Yes** — kills a whole analysis |
| Result reasons | 5 | `facts.py:80-84` | **Yes** — kills one metric, section survives |
| Bundle integrity reasons | ~21 | `GOVERNED_REASONS`, `bundle.py:363+` | **No** — no report is published at all |

The 21 integrity codes are Internal (see matrix §A.6). Earlier sessions counted
all three vocabularies together as "32 governed refusal reasons" and used that as
a product differentiator. **The customer-facing catalog is 13.** The differentiator
survives the correction — "analysis that tells you what it cannot tell you" is
true of 13 codes just as it was of 32 — but the catalog must not ship 21 internal
integrity codes to customers.

**Keep the full catalog as an internal product and specification asset.** It is
not itself the customer report.

---

## D.2 Section refusals — whole analysis unavailable

Wording below is a draft for owner review. Arabic requires owner authorship
(`RRA-005` parity).

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

## D.4 Caveats

Caveats qualify an analysis that **was** published. They are not refusals and
must not read as apologies.

| Code | Business message |
|---|---|
| `curve_points_sampled` | "The concentration curve is drawn from 100 evenly spaced points across your full product range. The figures beside it use every row." |

The full caveat vocabulary must be enumerated by the implementation slice.
`bundle.py:1324` requires **set equality** between claimed and bundle caveats, so
an unworded caveat is a reconcile failure, not a cosmetic gap.

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
