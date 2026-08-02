# Multi-Section Report Surfaces and Charts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present the report bundle as an ordered set of governed sections — each with an accessible table and a chart — across web, PDF and Excel, with the four `RRA-008` analysis families supplying four of those sections.

**Architecture:** A section is a grouping of `CitedFigure`s by the analysis family that produced them, carried in the bundle rather than invented by a renderer. `reconcile()` gains placement checks so a surface cannot silently move a figure or a caveat between sections, and each language states its ordered sections explicitly rather than having them inferred from its figure rows. Chart geometry is computed in `Decimal` from `Bucket.value`, becomes a coordinate string at build time, and is written as markup by a Jinja macro rather than returned as an SVG string. The workbook renders native XlsxWriter charts addressing a dedicated non-authoritative numeric worksheet.

**Tech Stack:** Python 3.13, uv, Jinja2 (autoescaped), Playwright + pinned Chromium, XlsxWriter, pytest, ruff.

## Slices

Eight independently verifiable slices, each merged on its own. The four analysis families stay four
slices, per `2026-08-02-rra-comparative-analysis-design.md` and `AGENTS.md`'s rule that a slice never
widen beyond its stated boundary.

| Slice | Tasks | Gated on |
|---|---|---|
| **0a** `KHEPRI-DEC-005` amendment | 1 | — |
| **0b** `RRA-004` amendment | 2 | — |
| **1** Section model | 3, 4, 5 | — |
| **2** Period comparison | 6 | — |
| **3** Concentration | 7 | 0b to complete |
| **4** Growth decomposition | 8 | — |
| **5** Basket structure | 9 | 0b for attach rate |
| **6** Charts, web and PDF | 10, 11, 12 | 1 |
| **7** Workbook | 13 | 1, 0a |

**There are two approval gates, not one.** Task 1 amends `KHEPRI-DEC-005` for numeric workbook chart
cells. Task 2 amends `RRA-004` for two aggregates that `RRA-008` requires and the fact package does
not carry — without it, concentration and attach rate are not computable at all, not merely harder.
The two gates are independent, neither blocks slice 1, and both can be proposed in parallel.

Tasks 7 and 9 are written to be implementable **before** gate 0b clears: each emits the governed
refusal `aggregate_unavailable` and its section renders that reason. That is deliverable behaviour,
not a stub, and it means no branch waits on a human. Each is completed afterwards by a follow-on slice
that consumes the new aggregate.

## Global Constraints

- Python 3.13 and `uv`. Run everything through `uv run`.
- **Every new file must score 10.00 on CodeScene Code Health.** No tracked hotspot may decline; `src/khepri/rra/api.py` is a tracked hotspot. CI is the only authority — iterate locally with per-file `code_health_review` until findings are empty.
- Keep constructors to 2–3 parameters. Never sit exactly at a threshold.
- *Complex Conditional* counts logical operators, threshold 2: `if a and (b or c)` fails. Push multi-operator conditions into a helper's `return`.
- *Overall Code Complexity* is the **mean** CC per function, threshold 4, aim ≤ 3.5.
- Binary floating point is never an authoritative financial fact. Use `Decimal`.
- Every workbook cell is written through `write_string`. The only exception this plan introduces is the `chartdata` worksheet, and only after Task 1 records approval.
- No Jinja2 autoescape exemptions. No `|safe`, and no `Markup` either — the second is the first with a
  different spelling. SVG structure is written by template source; everything derived from data passes
  through autoescaping. A chart helper that returns markup as a string is the design this plan rejects.
- **One slice, one merge.** Do not carry a second slice's files in a branch because they are convenient
  to write together. `AGENTS.md` forbids widening a slice past its stated boundary, and the Code Health
  gate scores every new file at 10.00 with no partial credit.
- Arabic is RTL; Arabic and English carry equal facts, caveats and citations.
- Commit signing is broken locally; unsigned commits are sanctioned until the key is restored. Use `git commit --no-gpg-sign`. **The harness classifier blocks the agent from committing an approval attributed to itself — Ahmed runs those commits with a `!` line.**
- Branch protection forces serial merges. `main` is protected; work on a branch.

---

### Task 1 — Slice 0a: Delegation record and the DEC-005 amendment

**One of the plan's two approval gates.** Only Task 13's native chart path depends on it. It does not
gate the section model, any analysis family, or the web and PDF surfaces.

**Files:**
- Create: `governance/delegations/DEL-002.yaml`
- Modify: `governance/decisions/KHEPRI-DEC-005-rra-runtime-architecture.md`
- Modify: `governance/registries/decisions.yaml`
- Create: `governance/approvals/APP-013.yaml`

**Interfaces:**
- Consumes: nothing.
- Produces: authority for a numeric cell on a `chartdata` worksheet, cited by Task 13.

**Scope this conservatively.** The instruction is session-scoped and expires the day it was given. If Task 1 is not completed that same day, **stop and ask Ahmed for a fresh instruction** — do not extend, renew, or reinterpret `DEL-002`. A delegate reading its own instruction generously is exactly what Article VIII exists to prevent.

**Implementation was deferred on 2026-08-02, so the record below is already stale.** The instruction
it quotes was given in session `05cd944b-db94-4195-928a-a724c8b7d6ca` and expired that day. Treat the
YAML as a *shape to follow*, not a record to copy: when this task is picked up, the `instruction`,
`granted_at`, `session`, and `expires_at` fields must all be re-captured verbatim from a fresh
instruction given at that time, and the identifier will not be `DEL-002` if another delegation has
been recorded meanwhile. Copying the fields below forward would fabricate a delegation record, which
is the one failure `FND-003` cannot detect.

- [ ] **Step 1: Write the delegation record with the instruction verbatim**

Store the typo as typed. Session id is this session's.

```yaml
schema_version: 1
id: DEL-002
delegate: KHEPRI-AGENT
granted_by: AHMED-SHAABAN
instruction: >-
  i authroize you]
granted_at: 2026-08-02
session: 05cd944b-db94-4195-928a-a724c8b7d6ca
scope:
  kind: session
  artifacts:
    - KHEPRI-DEC-005
expires_at: 2026-08-02
revoked: false
```

- [ ] **Step 2: Add the bounded clause to KHEPRI-DEC-005**

Add beneath the existing rendering bullets, adjacent to the prohibition it narrows:

```markdown
- A workbook may carry numeric cells solely as chart series addresses, on a dedicated worksheet
  that holds no authoritative figure and no citation identifier. Such cells are excluded from the
  surface content a bundle reconciles, and the authoritative figure remains the decimal string on
  the section worksheet. This narrows the binary floating-point prohibition above; it does not
  relax it.
```

- [ ] **Step 3: Run the governance validator and confirm it still passes**

Run: `uv run khepri-gov validate`
Expected: PASS. A failure here means the registry and the documents disagree — fix before continuing.

- [ ] **Step 4: Compute the document digest for the amended decision**

Run: `uv run khepri-gov document-digest governance/decisions/KHEPRI-DEC-005-rra-runtime-architecture.md`
Record the value; it goes into `APP-013.yaml` as `document_sha256`.

- [ ] **Step 5: Write the approval package with delegate attribution**

`approved_by` is `KHEPRI-AGENT` with a `delegation_ref`. **Never** `evidence_ref`, never a human identifier — that would claim Ahmed approved it.

```yaml
schema_version: 1
id: APP-013
title: Bounded numeric chart cells in the governed workbook
state: approved
owner: AHMED-SHAABAN
scope: >-
  Amend KHEPRI-DEC-005 to permit numeric cells solely as chart series addresses, on a
  dedicated worksheet holding no authoritative figure and no citation.
exclusions:
  - Any change to governance/CONSTITUTION.md or the authorities registry
  - Any delegation record, including DEL-002 which this package cites
  - Any widening of DEL-002, whose scope and expiry this package cannot alter
  - Any relaxation of the binary floating-point prohibition beyond chart series addressing
  - Any claim that a human authority approved this package
  - Any transition or approval of KHEPRI-DEC-008
approval:
  approved_by: KHEPRI-AGENT
  approved_at: 2026-08-02
  delegation_ref: governance/delegations/DEL-002.yaml
  session: 05cd944b-db94-4195-928a-a724c8b7d6ca
```

Fill `manifest_digest`, `approved_manifest_digest`, and the `artifacts` block following `APP-012.yaml` exactly, using `uv run khepri-gov approval-digest governance/approvals/APP-013.yaml`.

- [ ] **Step 6: Run both guards**

Run: `uv run khepri-gov validate && uv run khepri-gov delegation-guard`
Expected: both PASS. The package validator sees artifact transitions; the delegation guard sees the diff. Both are required because neither sees what the other does.

- [ ] **Step 7: Hand the commit to Ahmed**

The classifier refuses to let the agent commit an approval attributed to itself, and will not be moved by a spoken approval or a settings rule. Do not hunt for a phrasing that slips past it. Write the message to a file and hand over one line:

```
! git -C C:/Users/user/Documents/GitHub/Khepri commit --no-gpg-sign -F <msgfile>
```

---

### Task 2 — Slice 0b: The RRA-004 amendment for two missing aggregates

**The plan's second approval gate, and the one nobody expected.** `RRA-008` requires two things the
fact package cannot supply, and `RRA-008` excludes itself from fixing that.

**Do not start this task by writing code.** Nothing here is implementable until the amendment records
approval evidence from the named active authority.

**What is missing, and why it is not a coding problem:**

1. **Concentration has no full set to rank.** `RRA-008` requires concentration "over the full
   admissible distinct-value set, never over the truncated display buckets," plus the cumulative share
   curve and the top-decile and top-quartile shares. `build_comparison` keeps `MAX_COMPARISON_BUCKETS
   = 20` buckets plus one aggregated `other`; `distinct_values` and `truncated_values` are **counts**.
   The omitted values and their revenues are gone. A curve over 57 values cannot be recovered from 21
   buckets, and ranking the survivors while calling the result a full-set statistic publishes a display
   artifact as a governed figure.
2. **Attach rate has no transaction membership.** `RRA-008` requires "the share of transactions
   containing a given admissible dimension value" and forbids substituting row count. `FactPackage`
   carries no transaction identifiers and `Bucket` records `rows`. A product in 40 rows may sit in 40
   transactions or in one.

**Why `RRA-008` cannot authorize the remedy.** Its exclusions name "any change to the profiling,
admissibility, or fact-package specifications this one builds on," and `RRA-004`'s stable contract
makes `FactPackage` "immutable after publication and the only numerical source" for every surface.
Adding a required aggregate amends `RRA-004`.

**Files:**
- Create: `governance/delegations/DEL-00N.yaml` (identifier assigned at the time; see Task 1's warning)
- Modify: `governance/specifications/RRA-004.md`
- Modify: `governance/registries/specifications.yaml`
- Create: `governance/approvals/APP-01N.yaml`

**Interfaces:**
- Consumes: nothing.
- Produces: authority for `ConcentrationCurve` and `TransactionMembership` in the fact package, and for
  `PACKAGE_VERSION = "rra004.package.v2"`. Cited by the follow-on slices that complete Tasks 7 and 9.

- [ ] **Step 1: Capture a fresh instruction**

Same discipline as Task 1, and for the same reason: the instruction must be re-captured verbatim at the
time this is picked up. Do not reuse Task 1's `DEL-002` record, and do not extend one delegation to
cover both amendments — `DEL-002`'s `scope.artifacts` names `KHEPRI-DEC-005` only, and reading it to
cover `RRA-004` is exactly the generous self-reading Article VIII forbids.

- [ ] **Step 2: Add the two aggregates to RRA-004's requirements**

Add beneath the existing dimension-comparison bullet:

```markdown
- Retain, for each admissible comparison dimension, the ranked revenue share curve over the full
  distinct-value set before display truncation, together with the distinct-value count and the count
  ranked. The curve carries shares only and no value labels.
- Retain, for each admissible comparison dimension, the count of distinct transactions per published
  bucket and the full-set distinct transaction total, when a transaction identifier is mapped.
```

Both are phrased as retention rather than new computation, because that is what they are: the values
exist during construction and are discarded at truncation.

- [ ] **Step 3: Record the package version bump in the same amendment**

`RRA-004`'s contract already requires it — "a new input, mapping, formula, or correction creates a new
version." The amendment must say that the added aggregates move the package to `rra004.package.v2`, so
the version change carries approval rather than arriving as an implementation detail.

- [ ] **Step 4: Validate, digest, and write the approval package**

Follow Task 1's Steps 3–6 exactly — `uv run khepri-gov validate`, `document-digest`, an approval
package with `approved_by: KHEPRI-AGENT` and a `delegation_ref` (**never** `evidence_ref`, never a
human identifier), then `validate && delegation-guard`.

`exclusions` must name, at minimum: any change to `RRA-008`'s own exclusions; any widening beyond the
two retained aggregates; any new mapping semantics; any customer identifier or cohort capability, which
`RRA-008` excludes permanently; and any claim that a human authority approved the package.

- [ ] **Step 5: Hand the commit to Ahmed**

As Task 1 Step 7. The classifier blocks the agent from committing an approval attributed to itself.

---

### Task 3 — Slice 1: Section and ChartSpec types

**Files:**
- Modify: `src/khepri/rra/bundle.py`
- Test: `tests/rra/test_bundle_sections.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `SECTION_OVERVIEW`, `SECTION_COMPARISON`, `SECTION_CONCENTRATION`, `SECTION_GROWTH`, `SECTION_BASKET`, `ORDERED_SECTIONS: tuple[str, ...]`, `SECTION_PRESENT`, `SECTION_REFUSED`, `CHART_BAR`, `CHART_GROUPED_BAR`, `CHART_LINE`, `Section`, `ChartSpec`, and `ReportBundle.sections: tuple[Section, ...]` — the ordered sections the bundle declares, which Task 3 reconciles chart coverage against.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from khepri.rra.bundle import (
    CHART_BAR,
    ORDERED_SECTIONS,
    SECTION_COMPARISON,
    SECTION_OVERVIEW,
    SECTION_PRESENT,
    SECTION_REFUSED,
    ChartSpec,
    Section,
)


def test_ordered_sections_starts_with_overview() -> None:
    assert ORDERED_SECTIONS[0] == SECTION_OVERVIEW
    assert SECTION_COMPARISON in ORDERED_SECTIONS


def test_present_section_carries_no_reason() -> None:
    section = Section(
        section_id=SECTION_OVERVIEW,
        state=SECTION_PRESENT,
        reason=None,
        figure_ids=("F-1",),
        chart=None,
    )
    assert section.reason is None


def test_refused_section_requires_a_reason() -> None:
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state=SECTION_REFUSED,
            reason=None,
            figure_ids=(),
            chart=None,
        )


def test_chart_must_plot_at_least_one_figure() -> None:
    with pytest.raises(ValueError):
        ChartSpec(kind=CHART_BAR, figure_ids=())


def test_a_state_outside_the_governed_set_is_rejected() -> None:
    # A state the governed set does not contain must fail construction, not be
    # judged by the reason rules. `pending` with no reason satisfies both of
    # those rules, and a renderer testing `state == SECTION_REFUSED` then draws
    # an invented state as a present section.
    with pytest.raises(ValueError):
        Section(
            section_id=SECTION_OVERVIEW,
            state="pending",
            reason=None,
            figure_ids=(),
            chart=None,
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/test_bundle_sections.py -v`
Expected: FAIL with `ImportError: cannot import name 'ORDERED_SECTIONS'`

- [ ] **Step 3: Write minimal implementation**

Add to `bundle.py` beside the existing `SURFACE_*` constants:

```python
SECTION_OVERVIEW = "overview"
SECTION_COMPARISON = "comparison"
SECTION_CONCENTRATION = "concentration"
SECTION_GROWTH = "growth"
SECTION_BASKET = "basket"
ORDERED_SECTIONS = (
    SECTION_OVERVIEW,
    SECTION_COMPARISON,
    SECTION_CONCENTRATION,
    SECTION_GROWTH,
    SECTION_BASKET,
)

SECTION_PRESENT = "present"
SECTION_REFUSED = "refused"
GOVERNED_SECTION_STATES = frozenset({SECTION_PRESENT, SECTION_REFUSED})

CHART_BAR = "bar"
CHART_GROUPED_BAR = "grouped_bar"
CHART_LINE = "line"
GOVERNED_CHART_KINDS = frozenset({CHART_BAR, CHART_GROUPED_BAR, CHART_LINE})


@dataclass(frozen=True, slots=True)
class ChartSpec:
    kind: str
    figure_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in GOVERNED_CHART_KINDS:
            raise ValueError("unknown chart kind")
        if not self.figure_ids:
            raise ValueError("chart plots no figure")


@dataclass(frozen=True, slots=True)
class Section:
    section_id: str
    state: str
    reason: str | None
    figure_ids: tuple[str, ...]
    chart: ChartSpec | None

    def __post_init__(self) -> None:
        _require_section(self.section_id)
        _require_section_state(self.state, self.reason)
        _require_chart_within(self.chart, self.figure_ids)
```

Three small module-level helpers keep `__post_init__` at CC 1 and each check's operators separated — required by the *Complex Conditional* threshold:

```python
def _require_section(section_id: str) -> None:
    if section_id not in ORDERED_SECTIONS:
        raise ValueError("unknown section")


def _require_section_state(state: str, reason: str | None) -> None:
    # Membership first. The two rules below constrain the *valid* states, and a
    # state outside the set satisfies both by never matching either.
    if state not in GOVERNED_SECTION_STATES:
        raise ValueError("unknown section state")
    if state == SECTION_REFUSED and reason is None:
        raise ValueError("refused section states no reason")
    if state == SECTION_PRESENT and reason is not None:
        raise ValueError("present section states a reason")


def _require_chart_within(chart: ChartSpec | None, figure_ids: tuple[str, ...]) -> None:
    if chart is None:
        return
    if not frozenset(chart.figure_ids) <= frozenset(figure_ids):
        raise ValueError("chart plots a figure outside its section")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/test_bundle_sections.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Check Code Health before committing**

Run `code_health_review` on `src/khepri/rra/bundle.py`. It is an existing file, so the bar is "no decline" rather than 10.00 — capture its score **before** this task and compare. If it dropped, extract rather than inline.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/bundle.py tests/rra/test_bundle_sections.py
git commit --no-gpg-sign -m "feat: add governed section and chart types to the report bundle"
```

---

### Task 4 — Slice 1: Bind figures to sections and reconcile placement

**Files:**
- Modify: `src/khepri/rra/bundle.py` (`CitedFigure`, `StatedFigure`, `SurfaceLanguage`, `reconcile`, `GOVERNED_REASONS`)
- Test: `tests/rra/test_bundle_section_reconcile.py`

**Interfaces:**
- Consumes: `Section`, `ORDERED_SECTIONS` from Task 3.
- Produces: `CitedFigure.section: str`, `StatedFigure.section: str`, `SurfaceLanguage.sections: tuple[str, ...]`, and reasons `REASON_UNKNOWN_SECTION = "unknown_section"`, `REASON_FIGURE_MISPLACED = "figure_misplaced"`, `REASON_SECTION_NOT_PRESENTED = "section_not_presented"`, `REASON_SECTION_COVERAGE_DIFFERS = "section_coverage_differs_by_language"`, `REASON_SECTION_ORDER_DIFFERS = "section_order_differs_by_language"`, `REASON_CHART_FIGURE_NOT_STATED = "chart_figure_not_stated"`.

**This task changes two shared DTOs.** `CitedFigure` gains a required `section` and `SurfaceLanguage` gains a required `sections`, so every branch constructing either will fail to build once this merges. Write that into the pull request body before it happens — it is the same collision class as the alembic `down_revision` siblings the repository's change discipline already names.

**A surface states its sections; it is never asked to imply them.** The tempting shortcut is to derive
each language's section tuple by walking `entry.stated` and collecting distinct sections in order. It
is wrong in two directions at once:

- A **refused** section carries no figures by definition, so it never appears in a derived tuple. The
  required refusal heading could then be missing from every surface while reconciliation succeeded —
  which silently defeats the whole "a refused family still renders" rule.
- A section dropped from **both** languages produces two matching derived tuples, so the cross-language
  comparison passes on a report that lost an entire analysis.

Coverage inferred from content can only ever detect surfaces disagreeing with each other. The bundle is
what knows which sections should exist, so the claim is compared against the bundle.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from khepri.rra.bundle import (
    REASON_FIGURE_MISPLACED,
    REASON_SECTION_COVERAGE_DIFFERS,
    SECTION_COMPARISON,
    SECTION_OVERVIEW,
    BundleRefused,
    reconcile,
)
from tests.rra.factories import bundle_with_sections, surface_content


def test_figure_stated_in_the_wrong_section_refuses() -> None:
    bundle = bundle_with_sections()
    content = surface_content(bundle, moved={"F-1": SECTION_COMPARISON})
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_FIGURE_MISPLACED


def test_section_dropped_from_one_language_only_refuses() -> None:
    bundle = bundle_with_sections()
    content = surface_content(bundle, drop_section_from_arabic=SECTION_COMPARISON)
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_SECTION_COVERAGE_DIFFERS


def test_section_dropped_from_both_languages_refuses() -> None:
    # The case a derived tuple can never catch: both languages agree, and both
    # are wrong. Only a comparison against the bundle sees it.
    bundle = bundle_with_sections()
    content = surface_content(bundle, drop_section=SECTION_COMPARISON)
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_SECTION_NOT_PRESENTED


def test_a_refused_section_is_still_claimed_though_it_carries_no_figures() -> None:
    bundle = bundle_with_sections(refuse={SECTION_COMPARISON: "prior_window_absent"})
    content = surface_content(bundle)
    reconcile(content, bundle=bundle)
    for entry in content.languages:
        assert SECTION_COMPARISON in entry.sections
        assert not any(stated.section == SECTION_COMPARISON for stated in entry.stated)


def test_correct_placement_reconciles() -> None:
    bundle = bundle_with_sections()
    reconcile(surface_content(bundle), bundle=bundle)


def test_chart_plotting_a_figure_the_surface_did_not_state_refuses() -> None:
    bundle = bundle_with_sections()
    content = surface_content(bundle, unstate={"F-2"})
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_CHART_FIGURE_NOT_STATED
```

`unstate` drops a figure from `stated` while leaving it in the section's `ChartSpec`. This is the
one gap the structural subset rule in Task 3 does not close: a chart may only reference figures its
section declared, but the *surface* could still omit one from what it says it presented, leaving a
plotted bar with no reconciled text behind it.

Add the two factories to `tests/rra/factories.py`, following the construction the existing bundle tests already use. `surface_content` builds both languages from the bundle and applies the named mutation to Arabic only.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/test_bundle_section_reconcile.py -v`
Expected: FAIL — `StatedFigure` has no `section`.

- [ ] **Step 3: Write minimal implementation**

Add `section: str` to `CitedFigure` and to `StatedFigure`, add the four reasons to `GOVERNED_REASONS`, and extend `_reconcile_language` with one placement check:

```python
    for stated in entry.stated:
        figure = bundle.figure(stated.figure_id)
        if figure is None:
            raise BundleRefused(REASON_UNKNOWN_FIGURE)
        if stated.section != figure.section:
            # Placement is a claim like any other. A figure shown under the
            # wrong heading is cited correctly and read wrongly.
            raise BundleRefused(REASON_FIGURE_MISPLACED)
        if stated.text != figure.renderings.get(entry.language):
            raise BundleRefused(REASON_FIGURE_NOT_RECONCILED)
```

Add the chart-coverage check. `_reconcile_language` receives a `SurfaceLanguage`, which knows what
was shown but not what the bundle's sections declared, so this is called from `reconcile` — which
holds both — rather than from inside it:

```python
def _reconcile_chart(section: Section, shown: frozenset[str]) -> None:
    if section.chart is None:
        return
    if not frozenset(section.chart.figure_ids) <= shown:
        raise BundleRefused(REASON_CHART_FIGURE_NOT_STATED)


def _reconcile_charts(entry: SurfaceLanguage, bundle: ReportBundle) -> None:
    for section in bundle.sections:
        _reconcile_chart(section, entry.shown)
```

Wire it into the existing per-language loop in `reconcile`:

```python
    for entry in seen.values():
        _reconcile_language(entry, bundle)
        _reconcile_claimed_sections(entry, bundle)
        _reconcile_charts(entry, bundle)
```

Add `sections: tuple[str, ...]` to `SurfaceLanguage`, validated on construction so an invented name
cannot reach `reconcile` at all:

```python
@dataclass(frozen=True, slots=True)
class SurfaceLanguage:
    language: str
    direction: str
    sections: tuple[str, ...]
    stated: tuple[StatedFigure, ...]
    caveats: tuple[StatedCaveat, ...]
    disclosure: str

    def __post_init__(self) -> None:
        for section_id in self.sections:
            _require_section(section_id)
```

Then, in `reconcile`, two comparisons rather than one. The first is against the bundle and catches the
omission both languages share; the second is between languages and catches the omission they disagree
on. Keep each a separate helper so `reconcile`'s own complexity does not rise:

```python
def _reconcile_claimed_sections(entry: SurfaceLanguage, bundle: ReportBundle) -> None:
    if entry.sections != bundle.section_ids:
        # Compared against the bundle, not against the other language. A section
        # missing from both languages leaves them agreeing with each other and
        # disagreeing with the report that was assembled.
        raise BundleRefused(REASON_SECTION_NOT_PRESENTED)


def _reconcile_sections(coverage: list[SurfaceLanguage]) -> None:
    first = coverage[0].sections
    for other in coverage[1:]:
        if frozenset(other.sections) != frozenset(first):
            raise BundleRefused(REASON_SECTION_COVERAGE_DIFFERS)
        if other.sections != first:
            raise BundleRefused(REASON_SECTION_ORDER_DIFFERS)
```

`ReportBundle.section_ids` is a one-line property returning `tuple(s.section_id for s in self.sections)`.

Order is compared as a tuple and membership as a set, so a reordering and an omission produce different reasons rather than one ambiguous refusal.

Strictly, `_reconcile_claimed_sections` passing for every language makes `_reconcile_sections`
redundant — two tuples each equal to the bundle's are equal to each other. Both are kept deliberately:
the cross-language reasons are governed reason codes that name a real and distinct failure, and a
future change that relaxes the bundle comparison to a subset rule would silently take the
cross-language guarantee with it. The cost is two comparisons of a five-element tuple.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/test_bundle_section_reconcile.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Fix every construction site of CitedFigure and SurfaceLanguage**

Run: `uv run pytest -m 'not local_stack and not browser' -x -q`
Expected: PASS. Failures here are the required-field collision, not new bugs — fix each construction site to pass a section, and each `SurfaceLanguage` to state its sections. `build_content` in `html.py` is the one that matters: it must pass `bundle.section_ids`, not a tuple it derives from the cells it just built.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/bundle.py tests/rra/
git commit --no-gpg-sign -m "feat: reconcile figure placement and section parity across languages"
```

---

### Task 5 — Slice 1: Bind caveats to sections

**Files:**
- Modify: `src/khepri/rra/bundle.py` (`SurfaceLanguage.caveats`, `_reconcile_language`)
- Test: `tests/rra/test_bundle_section_caveats.py`

**Interfaces:**
- Consumes: `ORDERED_SECTIONS` from Task 3.
- Produces: `StatedCaveat(code: str, section: str | None)`. `SurfaceLanguage.caveats` becomes `tuple[StatedCaveat, ...]`; `ReportBundle.caveats` likewise.

`section=None` means a report-level caveat that belongs to no single analysis. No new refusal reason is needed: the existing comparison against `bundle.caveats` now compares pairs, so a misplaced caveat fails it exactly as a missing one does.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from khepri.rra.bundle import (
    REASON_CAVEAT_COVERAGE_DIFFERS,
    SECTION_BASKET,
    SECTION_COMPARISON,
    BundleRefused,
    StatedCaveat,
    reconcile,
)
from tests.rra.factories import bundle_with_sections, surface_content


def test_caveat_under_the_wrong_section_refuses() -> None:
    bundle = bundle_with_sections()
    content = surface_content(
        bundle,
        recaveat=(
            StatedCaveat(code="window_truncated", section=SECTION_BASKET),
        ),
    )
    with pytest.raises(BundleRefused) as refusal:
        reconcile(content, bundle=bundle)
    assert str(refusal.value) == REASON_CAVEAT_COVERAGE_DIFFERS


def test_report_level_caveat_carries_no_section() -> None:
    caveat = StatedCaveat(code="rows_redacted", section=None)
    assert caveat.section is None


def test_section_scoped_caveat_must_name_a_governed_section() -> None:
    with pytest.raises(ValueError):
        StatedCaveat(code="window_truncated", section="invented")
```

The bundle factory must place `window_truncated` under `SECTION_COMPARISON`, so the first test moves a caveat that genuinely belongs elsewhere.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/test_bundle_section_caveats.py -v`
Expected: FAIL with `ImportError: cannot import name 'StatedCaveat'`

- [ ] **Step 3: Write minimal implementation**

```python
@dataclass(frozen=True, slots=True)
class StatedCaveat:
    code: str
    section: str | None

    def __post_init__(self) -> None:
        if self.section is None:
            return
        _require_section(self.section)
```

`_reconcile_language`'s caveat comparison is unchanged in shape — it already compares `frozenset(entry.caveats)` against `frozenset(bundle.caveats)`, and now compares pairs because the element type changed. Keep the existing `REASON_CAVEAT_COVERAGE_DIFFERS`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/test_bundle_section_caveats.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Fix every construction site and run the suite**

Run: `uv run pytest -m 'not local_stack and not browser' -x -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/bundle.py tests/rra/
git commit --no-gpg-sign -m "feat: bind caveats to the section they qualify"
```

---

### Tasks 6–9: The four analysis families — one slice each

**These are four slices, not one.** Each merges on its own. They share no code beyond the `RRA-004`
types they read, which is why they are four files rather than one — a single `analysis.py` would fail
*Number of Functions in a Single Module* and mean-CC immediately. Each task has the identical five-step
shape: write the golden-dataset test, watch it fail, implement, watch it pass, commit.

Two of the four cannot be completed until Task 2's `RRA-004` amendment records approval. Both are
written to be *implementable now anyway*, emitting the governed refusal `aggregate_unavailable`, and
completed by a follow-on slice afterwards. `REASON_AGGREGATE_UNAVAILABLE = "aggregate_unavailable"`
joins the refusal reasons in `facts.py`.

**Shared interfaces for all four** — each module exposes exactly one entry point returning either derived facts or a refusal, so the pipeline treats them uniformly:

```python
def derive(package: FactPackage) -> tuple[Fact, ...] | RefusedResult: ...
```

`RefusedResult(metric, reason)` and `Fact` already exist in `facts.py`; no new refusal channel is needed. A `RefusedResult` becomes a `Section` with `state=SECTION_REFUSED` in Task 11's assembly.

---

### Task 6 — Slice 2: Period comparison, both governed modes

**Files:**
- Create: `src/khepri/rra/analysis/__init__.py`
- Create: `src/khepri/rra/analysis/comparison.py`
- Test: `tests/rra/analysis/test_comparison.py`

**Interfaces:**
- Consumes: `FactPackage`, `FactSeries`, `Bucket`, `Fact`, `RefusedResult`.
- Produces: `comparison.derive(package) -> tuple[Fact, ...] | RefusedResult`, and
  `MODE_PERIOD_OVER_PERIOD = "period_over_period"`, `MODE_YEAR_OVER_YEAR = "year_over_year"`.

**`RRA-008` requires two modes and they are both governed results.** Its wording is "for
period-over-period **and** year-over-year." Deriving one unnamed current/prior pair by splitting the
trend satisfies neither requirement fully — it produces a single comparison and leaves the reader
unable to tell which window it compared.

The two modes refuse **independently**. A dataset spanning eight months has period-over-period
coverage and no year-over-year coverage at all, and `RRA-008` refuses "the affected comparison, and
not the report," so one mode refusing must leave the other standing. `derive` therefore returns a
`RefusedResult` only when *both* modes refuse; a single-mode refusal is carried as that mode's own
refusal alongside the other mode's facts.

Each mode's facts carry distinct stable identities through `_identity`'s existing `scope` parameter —
`scope=(MODE_PERIOD_OVER_PERIOD,)` and `scope=(MODE_YEAR_OVER_YEAR,)` — so the same metric name in two
modes yields two fact ids and two citation ids rather than colliding.

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal

from khepri.rra.analysis import comparison
from khepri.rra.facts import RefusedResult
from tests.rra.analysis.factories import package_with_trend


def test_incomplete_window_truncates_both_sides_and_caveats() -> None:
    package = package_with_trend(current_days=15, prior_days=30)
    facts = comparison.derive(package)
    assert not isinstance(facts, RefusedResult)
    delta = next(f for f in facts if f.metric == "revenue_delta_absolute")
    assert "window_truncated" in delta.caveats


def test_absent_prior_coverage_refuses_the_comparison_only() -> None:
    package = package_with_trend(current_days=30, prior_days=0)
    result = comparison.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == "prior_window_absent"


def test_zero_base_refuses_the_percentage_but_keeps_the_absolute() -> None:
    package = package_with_trend(current_days=30, prior_days=30, prior_total=Decimal(0))
    facts = comparison.derive(package)
    assert not isinstance(facts, RefusedResult)
    metrics = {f.metric for f in facts}
    assert "revenue_delta_absolute" in metrics
    assert "revenue_delta_percent" not in metrics


def test_negative_base_refuses_the_percentage() -> None:
    package = package_with_trend(current_days=30, prior_days=30, prior_total=Decimal(-50))
    facts = comparison.derive(package)
    metrics = {f.metric for f in facts}
    assert "revenue_delta_percent" not in metrics


def test_both_governed_modes_are_emitted_with_distinct_identities() -> None:
    package = package_with_trend(months=26)
    facts = comparison.derive(package)
    modes = {f.mode for f in facts if f.metric == "revenue_delta_absolute"}
    assert modes == {MODE_PERIOD_OVER_PERIOD, MODE_YEAR_OVER_YEAR}
    ids = {f.fact_id for f in facts if f.metric == "revenue_delta_absolute"}
    citations = {f.citation_id for f in facts if f.metric == "revenue_delta_absolute"}
    assert len(ids) == 2
    assert len(citations) == 2


def test_year_over_year_refuses_alone_when_coverage_is_under_a_year() -> None:
    # Eight months has a prior month and no prior year. RRA-008 refuses the
    # affected comparison and not the report, so period-over-period survives.
    facts = comparison.derive(package_with_trend(months=8))
    assert not isinstance(facts, RefusedResult)
    modes = {f.mode for f in facts if f.metric == "revenue_delta_absolute"}
    assert modes == {MODE_PERIOD_OVER_PERIOD}
    refusal = next(r for r in comparison.refusals(package_with_trend(months=8)))
    assert refusal.reason == "prior_window_absent"
```

`Fact` has no `mode` field today. Rather than adding one, the mode is recorded the way every other
scoping dimension already is — in the metric's `scope`, which `_identity` hashes — and the test reads
it through a small `comparison.mode_of(fact)` helper that the module exposes beside `derive`. Adding a
field to the shared `Fact` DTO for one family's benefit is a wider change than this slice owns.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/analysis/test_comparison.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.rra.analysis'`

- [ ] **Step 3: Write minimal implementation**

Read `package.trend()` for the revenue series once, then derive each mode from it through one shared
windowing helper:

- **Period over period** — the last *n* buckets against the *n* before them.
- **Year over year** — the last *n* buckets against the *n* buckets one year earlier, located by period
  label rather than by offset. `period_label` gives `YYYY-MM` at month granularity and `YYYY-MM-DD` at
  day granularity, so the prior-year window is found by label arithmetic on the governed granularity and
  never by assuming twelve buckets back. A gap in coverage would make a fixed offset silently compare
  the wrong months.

Both truncate to the shorter day count and append `window_truncated` to every fact derived from a
truncated window. Each mode refuses with `prior_window_absent` when its own prior window has no
buckets; `derive` returns a `RefusedResult` only when both modes refuse. Emit the absolute delta
always; emit the percentage only when the base is strictly positive.

One windowing helper serving both modes is what keeps this file at 10.00 — two near-duplicate paths
would double the function count and the mean CC for no gain.

Keep the base test in its own helper so the *Complex Conditional* threshold is not reached:

```python
def _percentage_is_defined(base: Decimal | None) -> bool:
    if base is None:
        return False
    return base > 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/analysis/test_comparison.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Check Code Health, then commit**

`comparison.py` is a new file and must score **10.00**. Run `code_health_review` and iterate until findings are empty — "improved" is still a failure.

```bash
git add src/khepri/rra/analysis/ tests/rra/analysis/
git commit --no-gpg-sign -m "feat: derive period comparison facts with like-for-like truncation"
```

---

### Task 7 — Slice 3: Concentration

**Blocked by Task 2 for its figures.** Implement the refusal path now; complete it in a follow-on slice
once the `RRA-004` amendment records approval.

**Files:**
- Create: `src/khepri/rra/analysis/concentration.py`
- Test: `tests/rra/analysis/test_concentration.py`

**Interfaces:**
- Consumes: `FactPackage.comparison(dimension)`, and — after Task 2 — `ConcentrationCurve`.
- Produces: `concentration.derive(package) -> tuple[Fact, ...] | RefusedResult`.

**The aggregate this family needs does not exist yet, and cannot be reconstructed here.** `RRA-008`
requires concentration "over the full admissible distinct-value set, never over the truncated display
buckets." `Comparison` carries `MAX_COMPARISON_BUCKETS = 20` ranked buckets plus one aggregated
`other`, and `distinct_values` / `truncated_values` are **counts** — the omitted values and their
revenues were discarded at truncation.

An earlier revision of this plan said `Comparison` "already records `distinct_values` and
`truncated_values`, which is exactly the full-distinct-set rule `RRA-008` requires. Use them; do not
recount from the buckets." That was wrong and is corrected here. Those counts let a fact *state* that
57 values exist; they do not let anything rank 57 values, accumulate a curve across them, or measure
what share the top decile holds. Ranking the 20 survivors and labelling the result a full-set statistic
is the precise failure `RRA-008`'s wording forbids, and a test asserting `distinct.value == "57"` would
pass on exactly that fabrication.

So until Task 2's amendment lands, `derive` returns `RefusedResult("concentration",
"aggregate_unavailable")`. That is a governed refusal `RRA-008` already provides for, the section
renders its reason, and no figure is invented.

After the amendment: read `ConcentrationCurve` and emit the distinct count, the ranked count, the
cumulative curve, and the top-decile and top-quartile shares from it. Emit no classification bands.
Refuse with `distinct_set_uncomputable` when `distinct_values` is zero.

- [ ] **Step 1: Write the failing test**

Two tests now, against the refusal path. The rest arrive with the follow-on slice, and they are written
here so the shape of what the amendment must enable is on record.

```python
from khepri.rra.analysis import concentration
from khepri.rra.facts import RefusedResult
from tests.rra.analysis.factories import package_with_products


def test_refuses_while_the_full_set_aggregate_is_unavailable() -> None:
    result = concentration.derive(package_with_products(distinct=57, displayed=20))
    assert isinstance(result, RefusedResult)
    assert result.reason == "aggregate_unavailable"


def test_no_full_set_statistic_is_derived_from_display_buckets() -> None:
    # The failure this family exists to avoid. 57 distinct values reach the
    # package as 20 buckets plus `other`; nothing here may report a statistic
    # over 57 while holding 21.
    result = concentration.derive(package_with_products(distinct=57, displayed=20))
    assert isinstance(result, RefusedResult)
```

**Deferred to the follow-on slice, after Task 2:**

```python
def test_curve_is_computed_over_the_full_distinct_set_not_the_display() -> None:
    package = package_with_products(distinct=57, displayed=20, curve=True)
    facts = concentration.derive(package)
    ranked = next(f for f in facts if f.metric == "concentration_ranked_values")
    distinct = next(f for f in facts if f.metric == "concentration_distinct_values")
    assert distinct.value == "57"
    assert ranked.value == "57"


def test_top_decile_and_quartile_shares_are_emitted() -> None:
    package = package_with_products(distinct=40, displayed=20)
    metrics = {f.metric for f in concentration.derive(package)}
    assert "concentration_top_decile_share" in metrics
    assert "concentration_top_quartile_share" in metrics


def test_no_fixed_classification_bands_are_emitted() -> None:
    package = package_with_products(distinct=40, displayed=20)
    metrics = {f.metric for f in concentration.derive(package)}
    assert not any(metric.startswith("concentration_class_") for metric in metrics)


def test_uncomputable_distinct_set_refuses() -> None:
    package = package_with_products(distinct=0, displayed=0)
    result = concentration.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == "distinct_set_uncomputable"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/analysis/test_concentration.py -v`
Expected: FAIL with `ImportError: cannot import name 'concentration'`

- [ ] **Step 3: Write minimal implementation**

Return `RefusedResult("concentration", "aggregate_unavailable")`. Do not read `Comparison` at all — a
module that reads the buckets while refusing is a module one edit away from ranking them.

The follow-on slice replaces this with: rank the full set from `ConcentrationCurve`, accumulate the
cumulative share in `Decimal`, and emit the ranked count, the distinct count, the curve, and the
measured top-decile and top-quartile shares. No classification bands. Refuse with
`distinct_set_uncomputable` when `distinct_values` is zero.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/analysis/test_concentration.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Check Code Health, then commit**

```bash
git add src/khepri/rra/analysis/concentration.py tests/rra/analysis/test_concentration.py
git commit --no-gpg-sign -m "feat: derive concentration facts over the full distinct value set"
```

---

### Task 8 — Slice 4: Growth decomposition

**Files:**
- Create: `src/khepri/rra/analysis/growth.py`
- Test: `tests/rra/analysis/test_growth.py`

**Interfaces:**
- Consumes: `FactPackage`, revenue and units series.
- Produces: `growth.derive(package) -> tuple[Fact, ...] | RefusedResult`.

Formula, fixed by `RRA-008`:
`(average_selling_price_prior * units_change) + (units_current * average_selling_price_change)`
The interaction term is assigned to price, and that assignment is recorded as a fact.

- [ ] **Step 1: Write the failing test**

Additivity is asserted as **exact equality, not a tolerance** — this is the point of the whole family.

```python
from decimal import Decimal

from khepri.rra.analysis import growth
from khepri.rra.facts import RefusedResult
from tests.rra.analysis.factories import package_with_price_and_units


def test_parts_sum_exactly_to_the_revenue_change() -> None:
    package = package_with_price_and_units()
    facts = growth.derive(package)
    price = Decimal(next(f for f in facts if f.metric == "growth_price_effect").value)
    volume = Decimal(next(f for f in facts if f.metric == "growth_volume_effect").value)
    total = Decimal(next(f for f in facts if f.metric == "growth_revenue_change").value)
    assert price + volume == total


def test_interaction_assignment_is_recorded() -> None:
    facts = growth.derive(package_with_price_and_units())
    assignment = next(f for f in facts if f.metric == "growth_interaction_assigned_to")
    assert assignment.value == "price"


def test_zero_units_in_either_period_refuses() -> None:
    package = package_with_price_and_units(units_current=0)
    result = growth.derive(package)
    assert isinstance(result, RefusedResult)
    assert result.reason == "units_absent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/analysis/test_growth.py -v`
Expected: FAIL with `ImportError: cannot import name 'growth'`

- [ ] **Step 3: Write minimal implementation**

Compute in `Decimal` throughout. After computing both parts, assert their sum equals the revenue change and return `RefusedResult("growth_decomposition", "decomposition_not_additive")` if it does not — an inequality is a reconciliation failure, not a rounding artifact. Refuse with `units_absent` when units are zero in either period.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/analysis/test_growth.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Check Code Health, then commit**

```bash
git add src/khepri/rra/analysis/growth.py tests/rra/analysis/test_growth.py
git commit --no-gpg-sign -m "feat: derive price and volume growth decomposition with exact additivity"
```

---

### Task 9 — Slice 5: Basket structure

**Half of this family is computable today; half is blocked by Task 2.**

**Files:**
- Create: `src/khepri/rra/analysis/basket.py`
- Test: `tests/rra/analysis/test_basket.py`

**Interfaces:**
- Consumes: `FactPackage`, `METRIC_UNITS`, `METRIC_TRANSACTIONS`, and — after Task 2 — `TransactionMembership`.
- Produces: `basket.derive(package) -> tuple[Fact, ...] | RefusedResult`.

**Items per transaction is available now.** `METRIC_UNITS` and `METRIC_TRANSACTIONS` are both governed
facts in the package, and their quotient is the governed measure. `METRIC_TRANSACTIONS` is already
`_distinct(measures.transactions)` — a distinct count, not a row count — and it is already refused with
`incomplete_transaction_identifiers` when the identifier column has gaps, so the "never substitute row
count" requirement is satisfied by reading the governed fact rather than by counting anything here.

Note this corrects an earlier revision of the plan, which said items per transaction "divides row count
by transaction count." Row count is line-item count. `RRA-008` says *items*, and the governed items
measure is `METRIC_UNITS`.

**Attach rate is not available and cannot be derived here.** `RRA-008` requires "the share of
transactions containing a given admissible dimension value." The package carries no transaction
identifiers and no transaction-to-dimension membership; `Bucket` records `rows`. A product appearing in
40 rows may sit in 40 transactions or in one, and nothing in these aggregates distinguishes those. It
refuses with `aggregate_unavailable` until Task 2's amendment lands, then reads
`TransactionMembership`.

A partial family is not a broken one: `derive` returns the items-per-transaction fact and carries the
attach-rate refusal beside it, which is exactly `RRA-008`'s "refuse the affected result" rather than the
affected family.

- [ ] **Step 1: Write the failing test**

The third test is the one that matters most: row count is not transaction count, and mistaking them silently inflates every basket metric.

```python
from khepri.rra.analysis import basket
from khepri.rra.facts import RefusedResult
from tests.rra.analysis.factories import package_with_baskets


def test_items_per_transaction_is_emitted() -> None:
    metrics = {f.metric for f in basket.derive(package_with_baskets())}
    assert "basket_items_per_transaction" in metrics


def test_attach_rate_refuses_while_membership_is_unavailable() -> None:
    refusal = basket.refusal_for(package_with_baskets(), "basket_attach_rate")
    assert refusal.reason == "aggregate_unavailable"


def test_missing_transaction_identifier_refuses_with_a_stated_reason() -> None:
    result = basket.derive(package_with_baskets(transaction_id=False))
    assert isinstance(result, RefusedResult)
    assert result.reason == "transaction_identifier_absent"


def test_line_item_grain_is_not_mistaken_for_transaction_grain() -> None:
    # 100 rows, 25 transactions, 100 units. The denominator is the governed
    # distinct transaction count; a row-count denominator would give "1.00".
    package = package_with_baskets(rows=100, transactions=25, units=100)
    facts = basket.derive(package)
    items = next(f for f in facts if f.metric == "basket_items_per_transaction")
    assert items.value == "4.00"


def test_attach_rate_requires_an_admissible_dimension() -> None:
    refusal = basket.refusal_for(
        package_with_baskets(dimension=None), "basket_attach_rate"
    )
    assert refusal.reason == "dimension_absent"
```

`dimension_absent` takes precedence over `aggregate_unavailable`: a report with no admissible dimension
could not carry attach rate even with the amendment in place, so that is the accurate reason.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/analysis/test_basket.py -v`
Expected: FAIL with `ImportError: cannot import name 'basket'`

- [ ] **Step 3: Write minimal implementation**

Items per transaction is `METRIC_UNITS / METRIC_TRANSACTIONS`, both read as governed facts from the
package. Refuse it with `transaction_identifier_absent` when `METRIC_TRANSACTIONS` is itself refused —
read the package's own refusal rather than re-deriving the condition.

Attach rate refuses: `dimension_absent` when no admissible product or category dimension exists,
otherwise `aggregate_unavailable`. Substitute nothing.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/analysis/test_basket.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Check Code Health, then commit**

```bash
git add src/khepri/rra/analysis/basket.py tests/rra/analysis/test_basket.py
git commit --no-gpg-sign -m "feat: derive basket structure facts from transaction grain"
```

---

### Task 10 — Slice 6: The chart geometry module

**Files:**
- Create: `src/khepri/rra/rendering/charts.py`
- Test: `tests/rra/rendering/test_charts.py`

**Interfaces:**
- Consumes: `ChartSpec`, `CitedFigure`, `DIRECTION_RTL` from `bundle.py`.
- Produces: `build_chart(spec: ChartSpec, figures: tuple[CitedFigure, ...], *, direction: str, language: str) -> ChartView | None`, plus `ChartView` and `ChartMark`.

**This module returns geometry, not markup.** An earlier revision had it return an SVG fragment as a
`str`, and that cannot be rendered by these templates. `build_environment()` sets `autoescape=True`
unconditionally and `html.py` states the rule outright: "nothing reachable from the bundle is ever
marked safe … a page with one `|safe` in it has an escaping convention, not an escaping guarantee." A
`{{ section.chart_svg }}` holding a Python string reaches the reader as `&lt;svg …`, so the page would
display chart source as text — on the web surface and, through template inheritance, on the printed one.

The two exits from that are `|safe` and `Markup`, and they are the same exit: both move the escaping
decision out of the environment and into whoever remembers to apply it, on the one path customer-derived
labels travel. Chart axis labels *are* customer values.

So the boundary moves instead. This module resolves geometry to strings; a Jinja macro writes the
elements. Tags come from template source, which is trusted because it is source; labels pass through the
same autoescaping as every table cell, which is what makes a value named `<script>` inert here for the
same reason it is inert there.

```python
@dataclass(frozen=True, slots=True)
class ChartMark:
    x: str
    y: str
    width: str
    height: str


@dataclass(frozen=True, slots=True)
class ChartView:
    kind: str
    title: str
    description: str
    marks: tuple[ChartMark, ...]
    labels: tuple[str, ...]
```

Geometry is computed in `Decimal` and converted to a coordinate string only when the mark is built.
`build_chart` returns `None` rather than raising: the table is the authoritative presentation and a
chart must never suppress governed analysis.

- [ ] **Step 1: Write the failing test**

```python
from decimal import Decimal

from khepri.rra.bundle import CHART_BAR, DIRECTION_LTR, DIRECTION_RTL, ChartSpec
from khepri.rra.rendering.charts import build_chart
from tests.rra.rendering.factories import figures_for_chart


def test_a_drawable_series_yields_titled_marks() -> None:
    view = build_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        figures_for_chart(),
        direction=DIRECTION_LTR,
        language="en",
    )
    assert view.title
    assert view.description
    assert len(view.marks) == 2


def test_no_mark_coordinate_is_a_float() -> None:
    # Geometry is Decimal until the coordinate is written, and what is written
    # is a string. A float here would mean binary floating point reached the
    # surface of a governed figure.
    view = build_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        figures_for_chart(),
        direction=DIRECTION_LTR,
        language="en",
    )
    for mark in view.marks:
        assert isinstance(mark.x, str)
        assert isinstance(mark.height, str)


def test_arabic_chart_mirrors_the_category_order() -> None:
    figures = figures_for_chart()
    spec = ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2"))
    ltr = build_chart(spec, figures, direction=DIRECTION_LTR, language="en")
    rtl = build_chart(spec, figures, direction=DIRECTION_RTL, language="ar")
    assert ltr.marks[0].x != rtl.marks[0].x


def test_single_point_series_is_not_drawn() -> None:
    view = build_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1",)),
        figures_for_chart(),
        direction=DIRECTION_LTR,
        language="en",
    )
    assert view is None


def test_all_zero_series_is_not_drawn() -> None:
    view = build_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        figures_for_chart(values=(Decimal(0), Decimal(0))),
        direction=DIRECTION_LTR,
        language="en",
    )
    assert view is None


def test_figure_without_a_value_is_not_drawn() -> None:
    view = build_chart(
        ChartSpec(kind=CHART_BAR, figure_ids=("F-1", "F-2")),
        figures_for_chart(values=(Decimal(10), None)),
        direction=DIRECTION_LTR,
        language="en",
    )
    assert view is None
```

Accessibility is no longer assertable here, because this module no longer writes `role="img"` — the macro
does. Task 11 asserts it on the rendered page instead, which is a stronger claim: the earlier
string-returning design could assert `'role="img"' in svg` while the page displayed that text literally.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/rendering/test_charts.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'khepri.rra.rendering.charts'`

- [ ] **Step 3: Write minimal implementation**

Three kinds only. Dispatch through a dict lookup rather than an if-chain — a dict lowers the complexity numerator where an if-chain raises it, which is the arithmetic that decides whether this new file reaches 10.00:

```python
_GEOMETRY = {CHART_BAR: _bars, CHART_GROUPED_BAR: _grouped_bars, CHART_LINE: _line}
```

Mirror for RTL by transforming the x coordinate as `width - x - bar_width` when `direction == DIRECTION_RTL`, in one helper used by all three kinds.

**Do no escaping in this module.** Labels are carried as ordinary `str` and escaped once, by the
environment, when the macro writes them. A module that escapes them here and a template that escapes
them again produces `&amp;lt;` in a customer's product name; a module that escapes them *instead* moves
the guarantee out of the environment. Neither is what this design asks for.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/rendering/test_charts.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Check Code Health, then commit**

New file, must score **10.00**. Watch mean CC: five small functions each at CC 1–2 keep the mean well under 3.5, whereas one `build_chart` holding all three kinds will not.

```bash
git add src/khepri/rra/rendering/charts.py tests/rra/rendering/test_charts.py
git commit --no-gpg-sign -m "feat: compute governed chart geometry as an exact view model"
```

---

### Task 11 — Slice 6: Web surface — sections and charts

**Files:**
- Modify: `src/khepri/rra/rendering/templates/report.html.j2`
- Create: `src/khepri/rra/rendering/templates/_chart.svg.j2`
- Modify: `src/khepri/rra/rendering/html.py`
- Test: `tests/rra/rendering/test_html_sections.py`

**Interfaces:**
- Consumes: `Section`, `ChartSpec` (Task 3), `build_chart` (Task 10).
- Produces: an HTML surface whose `SurfaceContent` states its ordered sections, a section per figure, and a section per caveat.

`build_content` must pass `bundle.section_ids` into each `SurfaceLanguage` — not a tuple derived from the
cells it just built. Deriving it there would make the surface agree with itself by construction, which is
exactly the reconciliation this slice added.

This task also assembles `Section`s from the package: a family returning `RefusedResult` becomes `state=SECTION_REFUSED` carrying `result.reason`.

- [ ] **Step 1: Write the failing test**

```python
from khepri.rra.bundle import SECTION_COMPARISON, SECTION_CONCENTRATION
from tests.rra.rendering.factories import render_web


def test_each_section_has_its_own_heading_and_nav_entry() -> None:
    page = render_web(language="en")
    assert f'<section id="{SECTION_CONCENTRATION}"' in page
    assert f'href="#{SECTION_CONCENTRATION}"' in page


def test_a_refused_section_renders_its_governed_reason() -> None:
    page = render_web(language="en", refuse={SECTION_COMPARISON: "prior_window_absent"})
    assert f'<section id="{SECTION_COMPARISON}"' in page
    assert "prior_window_absent" in page


def test_a_drawable_section_renders_a_real_svg_element() -> None:
    # Positively assert the markup reached the page. The escaped-string design
    # this replaced would have rendered `&lt;svg` here and passed every other
    # test in this file.
    page = render_web(language="en")
    assert "<svg" in page
    assert "&lt;svg" not in page
    assert 'role="img"' in page


def test_a_chart_label_from_customer_data_is_escaped() -> None:
    page = render_web(language="en", label="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_the_table_is_present_even_when_the_chart_is_not() -> None:
    page = render_web(language="en", undrawable={SECTION_CONCENTRATION})
    assert "<svg" not in page
    assert "<table" in page


def test_existing_sections_keep_their_place() -> None:
    page = render_web(language="en")
    for anchor in ("caveats", "commentary", "citations", "provenance"):
        assert f'href="#{anchor}"' in page


def test_an_undrawable_chart_emits_a_governed_caveat() -> None:
    content = render_web_content(language="en", undrawable={SECTION_CONCENTRATION})
    codes = {
        caveat.code
        for caveat in content.caveats
        if caveat.section == SECTION_CONCENTRATION
    }
    assert "chart_not_drawn" in codes
```

The last test is the one that keeps a chart failure honest. `render_chart` returning `None` is not
by itself a disclosure — a section would simply look sparse, and a reader could not tell "there was
nothing to show" from "we could not show it". The caveat is what carries that distinction, so the
assembly emits `chart_not_drawn` scoped to the section whenever `render_chart` returns `None`.
`render_web_content` returns the `SurfaceContent` rather than the page string.

The fourth test guards the regression this design is most likely to cause: `ORDERED_SECTIONS` covers figure-bearing analysis sections only, and the four existing sections must not fall out of the navigation.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/rendering/test_html_sections.py -v`
Expected: FAIL — the template renders one figures table, not a section per family.

- [ ] **Step 3: Write minimal implementation**

Replace the single `#figures` section with a loop over `sections`, each rendering heading, chart, then table. The refused branch renders the reason and no table.

Write the SVG in `_chart.svg.j2` as a macro. The elements are template source; every label goes through
the environment's autoescaping, and nothing is marked safe:

```jinja
{% macro chart(view, section_id) %}
<svg role="img" aria-labelledby="{{ section_id }}-ct {{ section_id }}-cd"
     viewBox="0 0 640 320" class="chart chart--{{ view.kind }}">
  <title id="{{ section_id }}-ct">{{ view.title }}</title>
  <desc id="{{ section_id }}-cd">{{ view.description }}</desc>
  {% for mark in view.marks %}
  <rect x="{{ mark.x }}" y="{{ mark.y }}"
        width="{{ mark.width }}" height="{{ mark.height }}" />
  {% endfor %}
  {% for label in view.labels %}
  <text class="chart__label">{{ label }}</text>
  {% endfor %}
</svg>
{% endmacro %}
```

Then in the parent template:

```jinja
{% from "_chart.svg.j2" import chart %}
{% for section in sections %}
<section id="{{ section.section_id }}" aria-labelledby="{{ section.section_id }}-heading">
<h2 id="{{ section.section_id }}-heading">{{ chrome.sections[section.section_id] }}</h2>
{% if section.state == refused_state %}
<p class="refused" data-reason="{{ section.reason }}">{{ chrome.refused[section.reason] }}</p>
{% else %}
{% if section.chart %}{{ chart(section.chart, section.section_id) }}{% endif %}
{{ section_table(section) }}
{% endif %}
</section>
{% endfor %}
```

`section.chart` is the `ChartView` from Task 10, or `None`. A macro's output is markup because the macro
*is* template source — which is the same reason `html.py` already includes the stylesheet as template
source rather than passing it in as a variable. This follows the guarantee the module already documents
instead of adding an exception to it.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/rendering/test_html_sections.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/ tests/rra/rendering/
git commit --no-gpg-sign -m "feat: render report sections and charts on the web surface"
```

---

### Task 12 — Slice 6: PDF pagination

**Files:**
- Modify: `src/khepri/rra/rendering/templates/report.print.css`
- Test: `tests/rra/rendering/test_pdf_sections.py` (marked `browser`)

**Interfaces:**
- Consumes: the template from Task 11. `report.pdf.html.j2` is **not modified** — it extends the parent and fills two blocks, and that inheritance is what keeps Arabic/English parity in one place, and is also what carries the chart macro onto the printed page with no PDF-specific chart code.

The spec requires a refused section to render its reason on all three surfaces. There is no separate
PDF test for it because there is no separate PDF markup: every heading, section and refusal on the
printed page comes from the parent template, so Task 10's refusal test covers this surface too. Only
pagination is genuinely new here, and that is what these two tests exercise.

- [ ] **Step 1: Write the failing test**

```python
import pytest

from tests.rra.rendering.factories import render_pdf_pages


@pytest.mark.browser
def test_each_section_starts_on_its_own_page() -> None:
    pages = render_pdf_pages(language="en")
    assert pages["concentration"] != pages["comparison"]


@pytest.mark.browser
def test_arabic_paginates_identically() -> None:
    assert render_pdf_pages(language="ar").keys() == render_pdf_pages(language="en").keys()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/rendering/test_pdf_sections.py -v -m browser`
Expected: FAIL — sections currently flow continuously.

- [ ] **Step 3: Write minimal implementation**

Add to the print stylesheet, beside the existing `break-inside`/`break-after` rules:

```css
  main > section + section {
    break-before: page;
  }
```

`section + section` rather than `section` so the first section does not force a leading blank page.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/rendering/test_pdf_sections.py -v -m browser`
Expected: PASS (2 tests). These skip without the pinned Chromium.

- [ ] **Step 5: Commit**

```bash
git add src/khepri/rra/rendering/templates/report.print.css tests/rra/rendering/test_pdf_sections.py
git commit --no-gpg-sign -m "feat: start each report section on its own printed page"
```

---

### Task 13 — Slice 7: Workbook — a sheet per section and native charts

**Blocked by Task 1.** Do not write a numeric cell before the `KHEPRI-DEC-005` approval package records approval.

**Split this slice at the numeric write.** The per-section worksheets need no amendment and can merge as
soon as slice 1 does; only the native chart path is gated. Writing both together parks the whole slice
behind a human approval for no reason.

**Files:**
- Modify: `src/khepri/rra/rendering/excel.py`
- Test: `tests/rra/rendering/test_excel_sections.py`

**Interfaces:**
- Consumes: `Section` (Task 3), `StatedCaveat` (Task 5).
- Produces: fifteen worksheets — seven per language plus a shared `provenance`.

The module docstring currently argues charts out. **Rewrite that paragraph** — leaving it would leave the file asserting the opposite of what it does, which is worse than either position.

- [ ] **Step 1: Write the failing test**

```python
from tests.rra.rendering.factories import workbook_sheets, workbook_values


def test_one_worksheet_per_section_per_language() -> None:
    names = workbook_sheets()
    for section in ("overview", "comparison", "concentration", "growth", "basket"):
        assert f"ar_{section}" in names
        assert f"en_{section}" in names
    assert "provenance" in names


def test_chartdata_carries_no_citation_and_no_authoritative_figure() -> None:
    cells = workbook_values("en_chartdata")
    assert not any(value.startswith("C-") for value in cells.text_values)


def test_every_numeric_chart_cell_matches_its_authoritative_string() -> None:
    numeric = workbook_values("en_chartdata").numeric_cells
    authoritative = workbook_values("en_concentration").text_values
    for value in numeric:
        assert format(value, "f") in authoritative


def test_stated_never_contains_a_chartdata_cell() -> None:
    stated = {entry.figure_id for entry in workbook_values("en_chartdata").stated}
    assert stated == set()


def test_a_refused_section_still_gets_its_worksheet() -> None:
    names = workbook_sheets(refuse={"comparison": "prior_window_absent"})
    assert "en_comparison" in names
    assert "ar_comparison" in names


def test_the_arabic_chart_axis_is_reversed() -> None:
    assert workbook_values("ar_concentration").chart_axis_reversed is True
    assert workbook_values("en_concentration").chart_axis_reversed is False
```

The mirroring test matters for the same reason it did for SVG in Task 10, and `reconcile` cannot
catch it: a spreadsheet category axis defaults left-to-right regardless of the declared direction,
so an Arabic chart would plot its first category on the wrong side while every text cell reconciles
perfectly.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/rra/rendering/test_excel_sections.py -v`
Expected: FAIL — the workbook writes one report sheet per language.

- [ ] **Step 3: Write minimal implementation**

Split `_write_report` into a per-section writer. Add `_write_chartdata`, the only place in the module permitted to call a numeric write, and add the native chart via `workbook.add_chart` addressing that worksheet. Every other cell still goes through `write_string`. Reverse the category axis for Arabic.

Keep the numeric write isolated in one small function with a comment naming its authority:

```python
def _write_chart_value(
    sheet: Worksheet, row: int, column: int, figure: CitedFigure
) -> None:
    # The single numeric write in this module. APP-013 permits it solely as a
    # chart series address, on a worksheet holding no authoritative figure and
    # no citation. The authoritative figure is the string on the section sheet.
    #
    # Quantized to the figure's own recorded precision before narrowing, so the
    # double is the nearest representation of the governed string rather than
    # of some longer Decimal the string never claimed. APP-013 narrows the
    # binary floating-point prohibition; it does not relax it, and an
    # unquantized float(value) would be the relaxation it refuses.
    quantized = figure.value.quantize(Decimal(1).scaleb(-figure.precision))
    sheet.write_number(row, column, float(quantized))
```

The round trip is what makes the "faithful copy at write time" claim true rather than asserted:
`format(...)` on the value read back must equal the authoritative string, which is exactly what the
third test in Step 1 checks. If that test fails after this change, the precision is wrong — fix the
quantization, not the test.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/rra/rendering/test_excel_sections.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run the whole gate**

```bash
uv run khepri-gov validate
uv run ruff check .
uv run pytest -m 'not local_stack and not browser'
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/khepri/rra/rendering/excel.py tests/rra/rendering/test_excel_sections.py
git commit --no-gpg-sign -m "feat: write one worksheet per section with a native governed chart"
```

---

## Pull request notes

Write these into each PR body **before** opening it, because all three are predictable:

1. **Shared DTO collision.** `CitedFigure` gains a required `section` field and `SurfaceLanguage` gains a required `sections` field (Task 4), and the caveat type changes shape (Task 5). Any branch constructing one fails to build once slice 1 merges; the second to merge fixes the fixtures.
2. **Package version collision.** Slice 0b moves `PACKAGE_VERSION` to `rra004.package.v2`, changing the package document shape and every digest derived from it. It is confined to its own slice so the shape change arrives alone rather than being diagnosed through a renderer.
3. **Serial merges.** Branch protection requires branches be up to date, so merging any PR invalidates every other PR's checks. With eight slices this is the dominant cost: budget `update-branch` → poll until `CLEAN` → squash-merge, about two minutes apiece, and merge in dependency order (0a/0b and 1 first, then 2 and 4, then 6, then 7).

Unresolved review comments block merging in this repository, so expect to answer every automated review
thread on each slice rather than only the ones that change code.

## Findings folded into this plan

Seven review findings were raised against the first revision of this plan and six were confirmed against
the code and `RRA-008` before being fixed here. They are recorded because each one was a case of the plan
reading as correct while being unimplementable:

| Finding | Where it now lives |
|---|---|
| Concentration cannot use `distinct_values` as a full set | Task 2 (the `RRA-004` amendment) and Task 7 |
| Attach rate has no transaction membership | Task 2 and Task 9 |
| Year-over-year comparison missing entirely | Task 6 |
| Section coverage inferred from figure rows | Task 4 |
| SVG string rendered as escaped text | Tasks 10 and 11 |
| `Section` accepts a state outside the governed set | Task 3 |
| Four analysis slices combined into one | The slice table at the top |

The first two were deeper than reported: the remedy is not a code change but an `RRA-004` amendment,
because `RRA-008` excludes changing the fact-package specification it builds on.
