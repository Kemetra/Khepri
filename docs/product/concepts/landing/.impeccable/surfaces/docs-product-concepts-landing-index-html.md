---
version: 1
slug: "docs-product-concepts-landing-index-html"
primary_target: "docs/product/concepts/landing/index.html"
related_targets: ["docs/product/concepts/landing/landing.css"]
---

# Public landing page — surface brief

## Scope and mode

The single public marketing page for Khepri. Visitor mode: **Persuade**. The only Khepri surface
whose visitor has no account, no organization, and no submitted data — everything else in the
product assumes all three.

**Not product code.** Lives at `docs/product/concepts/landing/` as a standalone concept. Khepri
admits product code only in slices linked to an active `governance/registry.yaml` spec;
`RCA-002:132-135` excludes any change to the RRA journey's routes, templates, or assets, and a
public marketing surface has no registry row. Nothing under `src/khepri/` is touched. Making this a
real route requires an active specification naming the surface first.

## This surface has its own visual world

**Decided by the owner, 2026-08-29.** A first version inherited the shipped app palette exactly and
was rejected on feel — it read as a plain document rather than an enterprise product. The owner
authorised a separate identity for the public marketing surface, in the "Egyptian modern" register,
and delegated the direction choice.

`docs/product/KHEPRI_DESIGN_LANGUAGE.md` still governs the **application** (`/app`, `/beta`),
including its Law 1 — containment from rules and type, never elevation. This surface is not bound by
it. Two registers, one product thesis. The rejected v1 is archived at
`docs/product/concepts/landing-v1/` and is the anti-reference: it is what "correct but ordinary"
looks like for this product.

## Audience and job

Retail operators in Egypt and the Gulf — not analysts. They arrive having heard Khepri described and
need to decide whether it is worth requesting access. They are not evaluating a metrics tool; they
are deciding whether they can defend a decision made on its output.

Arabic-reading and English-reading operators are equal populations, not a primary language plus a
translation.

**Action:** request access. There is no pricing and no self-serve sign-up, and neither appears.

## Proof the surface may use

- The mechanism itself: semantic admission before any claim, deterministic versioned facts, evidence
  reachable from the claim, refusal kept visible where the answer would have been.
- Illustrative specimen data, authored at full fidelity and labelled synthetic — currently in three
  places.

**Uninventable:** customers, testimonials, logos, benchmarks, pricing, licensing, certifications,
deployment claims, legal entity details, addresses. PRODUCT.md records each as an established
absence. The page carries none, and no section was omitted to avoid them.

## Chosen direction

**The Register Wall** — Egyptian tomb-wall registers, which were a data-graphics system before they
were art: horizontal bands, strict shared baselines, fixed reading order, scale encoding
significance rather than perspective distance. That is structurally what a governed report is.

Direction round seed key `a56e97f5`, assigned index 4 of seven grounded Egyptian-world candidates.
Raised by a declined phosphor-terminal challenger, which donated one discipline: **state prints
itself into the register as content, never as chrome.**

The reference is structural, not ornamental. Strip the story and the composition still works as
bands, fixed order, shared baselines, counted courses. There is no hieroglyph, papyrus texture, or
pyramid silhouette; the sole iconographic element is an 11px gold disc.

## The memorable moment

**The specimen performs admission on load.** In the first viewport, `q3-sales-export.csv` is stamped
ADMITTED, then its figures resolve one course at a time — each taking gold as it reconciles — and
then the last course fails to resolve and settles into the withheld treatment, its rule cutting
downward into the register where the answer would have been.

The page demonstrates its thesis before a word of copy is read. Every figure the reader has just
watched turn gold is one the product would stand behind; the one that did not is named, with its
reason.

## Unresolved decisions

1. **The trust vocabulary is provisional.** PROVEN / CAVEATED / WITHHELD are design vocabulary, not
   shipped product labels; §4.5 constraint 1 gates the customer-facing vocabulary on programme `T1`,
   which has no registry entry. The shape is durable; the words must be re-verified.
2. **Arabic copy is a design specimen**, not the product's governed copy. Real copy is authored in
   the copy modules with parity asserted at import.
3. **No route, no template, no navigation entry.** Law 5 forbids rendering capability that does not
   exist.
4. **The header's destination labels** (Product / How it works / Why Khepri / About) are marketing
   labels, unrelated to the app's reconciled destination set (Overview / Data / Analyses / Team).

## Decided, not open

- **The typeface stays at Regular.** Only the 400 weight ships; both `@font-face` rules declare it
  explicitly. The owner decided to leave it rather than acquire a face, which would require the
  licence-plus-audited-digest process. The design compensates by not leaning on weight at all —
  hierarchy comes from scale, colour role, tracking and register position. `PROVENANCE.md` holds the
  digests. This is also a live gap in the shipped `journey.css`, not something this concept
  introduced.
- **Five `side-tab` detector findings stand deliberately**, all the identical
  `border-inline-start: 4px solid var(--withheld)` — the governed refusal shape. The finish reviewer
  ruled them earned on the merits; the owner chose to leave them visible rather than add a
  file-level ignore. Note the borders were *raised* from as low as 1.09:1 to 5.28–5.86:1 so they
  clear WCAG 1.4.11 as state carriers; thinning them to satisfy the detector would have broken the
  one product law that survived the world change.
- **The bilingual pair stays side-by-side.** The finish reviewer noted Arabic therefore reads as a
  column beside English, flagged it as one line of attention rather than a headline, and accepted
  the decline: side-by-side is what makes the parity legible at a glance.

## Development artifacts, not part of the concept

`preview-mobile.html` is a local harness for viewing the page at device widths with an RTL toggle.
It is not part of the deliverable and should be deleted or gitignored before anything is handed
onward.
