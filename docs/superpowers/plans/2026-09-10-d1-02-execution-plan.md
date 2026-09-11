# `D1-02` — The decision read path and the executive overview read model

> **Execution plan** (the `W1-09` tier). Parent: the allocation plan at
> `docs/superpowers/plans/2026-09-10-d1-02-10-decision-workspace-allocation-plan.md`.
> **Authority:** active `RCA-008` (`#444`, `2734886`) — `FR-159`, `FR-160`, `FR-163`,
> `FR-165`, `FR-168`.

**Deliverable:** `src/khepri/rca/workspace/decision/` — `seam.py` (the eight view identities as
literals, and the one call shape) and `overview.py` (S-1). **No route, no template, no stylesheet
rule.** `D1-03` is the first slice with a surface.

---

## The design decision this slice turns on

`FR-135` forbids retyping a metric code and `RCA-006` forbids `khepri.rca` importing
`khepri.rra`. Taken together those look like a contradiction: the read model must say which metrics
it wants, and the only governed list of them lives on the other side of the seam.

**It is not a contradiction, because an empty `metrics` tuple already means the right thing.**
`compatibility.py:68-72` — "An empty `metrics` or `dimensions` asks for the definition's own
published selection rather than for nothing" — and `projection.py:334` implements it: "an empty
tuple is *the view's own selection* and never *none*."

So the read model **names no metric at all**. It names a view identity and a source, and the
registry supplies the ten core metrics. That satisfies `FR-135` without an import, and it means a
metric added to the core contract reaches S-1 with no edit here.

**What the read model does hold as literals is view identity**, because `FR-160` requires exactly
that: `view_id`, `view_version`, and — for `FR-163` — the published `empty_result_rule`. Each is
asserted against the registry in test, which is where the staleness risk is answered.

---

## Files

```text
src/khepri/rca/workspace/decision/__init__.py   NEW
src/khepri/rca/workspace/decision/seam.py       NEW
src/khepri/rca/workspace/decision/overview.py   NEW
tests/test_d102_decision_seam.py                NEW
```

`RCA-005`'s existing files under `workspace/` are untouched; `decision/` is a new subpackage so
that constraint is checkable by path.

---

## Steps

### RED

- [ ] `tests/test_d102_decision_seam.py`, failing because the package does not exist:
  - **Source map.** `DECISION_VIEWS` names exactly the eight published views, and each identity's
    `view_id`, `view_version` and `empty_rule` equal what the registry publishes. This is the test
    that makes the literals safe.
  - **`FR-160` literals.** Every `view_version` in `seam.py` appears as a string literal in the
    module's own AST — not a call result, not an f-string, not a name resolved elsewhere.
  - **`FR-160` no read-time enumeration.** No module under `decision/` calls
    `published_versions`, `published_history`, `view_ids` or `define_view`.
  - **`FR-159` no arithmetic.** AST over `decision/`: no `+ - * / // % **`, no augmented
    assignment with them, and no call to `sum`, `min`, `max`, `round`, `abs`, `sorted` or `.sort`.
    Ordering is the view's (`FR-134` makes output order part of view identity), so a read model
    has nothing to sort.
  - **`FR-159` no RRA import and no raw rows.** Nothing under `decision/` imports `khepri.rra`,
    nor `khepri.rca.workspace.store` / `persistence`.
  - **The seam names no metric.** The `SemanticViewRequest` reaching the port has `metrics == ()`
    and `dimensions == ()` — the published-selection contract above, asserted rather than assumed.
  - **`FR-165` partial success and content-free unavailable.** An unavailable outcome yields a
    reading with `status == "unavailable"`, no figures, and **no reason field at all**.
  - **A refusal is carried, not flattened.** A refused outcome keeps `ViewRefusal` intact so the
    surface can render governed bilingual wording (`FR-164`, `D1-03`).
  - **`FR-163` both rules representable.** `EMPTY_STATED_ABSENCE != EMPTY_STATED_NO_ROWS`, both
    appear across `DECISION_VIEWS`, and an empty admitted projection reports its view's rule.
  - **Layout only.** `fields`→row zipping is `strict=True`, and a row of the wrong width raises
    rather than silently truncating.

### GREEN

- [ ] `seam.py`: `ViewIdentity`, the eight identities, `DECISION_VIEWS`, `DecisionRead`, `read`.
- [ ] `overview.py`: `OverviewFigure`, `OverviewReading`, `OverviewRequest`, `read_overview`.
- [ ] `__init__.py` re-exporting nothing that widens the surface.

### Gates

- [ ] `uv run khepri-gov validate`
- [ ] `uv run ruff check .`
- [ ] `uv run pytest`
- [ ] Every new file scores 10.00 in CodeScene; no tracked hotspot declines.

---

## Not in this slice

- **No route.** `D1-03`.
- **No metric card.** `FR-162` is `D1-03`'s; this slice carries the read only.
- **No Period Comparison read.** `FR-170` holds its source open; `PERIOD_COMPARISON` appears in
  `DECISION_VIEWS` as an identity so the source map is complete, and nothing calls it.
- **No availability qualification.** `MetricAvailabilityView` is `D1-04`'s (`FR-167`).
