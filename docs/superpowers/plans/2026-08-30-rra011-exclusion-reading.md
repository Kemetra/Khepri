# F8 — does `RRA-011`'s re-derivation Exclusion prohibit constructing a bundle?

**OWNER DECISION REQUIRED.** This document asks one question and does not answer it. It also
replaces a guard that measured nothing, which is not in question.

**Raised on:** `main` at `bc96a65`, after `#343` merged and `#344` was closed.

---

## What was found

`#344` proposed recording `M2` as reached. Review raised a `P1` against it: every catalog `GET`
re-derives published figures, contrary to `RRA-011`'s Exclusion.

**The mechanism is confirmed, and it is not what `#343` believed it had fixed.** `_session_bundle`
calls `ReportBundle.of(package)`, and that constructor calls `family.derive(package)`
(`bundle.py:1638`) and `concentration.curve_series(package)` (`bundle.py:1728`) as it assembles.
Measured: two `curve_series` calls per bundle construction.

`#343` had already answered an earlier version of this finding by removing a *direct*
`family.derive` call from `report_api.py`. That fix was real but addressed one call site, and the
work continued one frame deeper.

**Its guard was worse than nothing.** `test_no_catalog_route_recomputes_a_published_figure` read
`report_api.py` and asserted the strings `family.derive` and `curve_series` were absent from it. It
passed against exactly the behaviour it was written to prevent, because a string search over one file
cannot see the call move into a collaborator. That test is replaced, unconditionally and regardless
of how the question below is answered, with one that counts the calls — see *What is fixed here*.

---

## The question

**Does `RRA-011`:204's Exclusion prohibit a catalog route from constructing a `ReportBundle`?**

### Reading A — it does

> *"Any calculation, re-derivation, re-rounding, or re-formatting of a published figure. A catalog
> surface repeats a value; it never recomputes one."*

Constructing a bundle executes the analysis families. On a plain reading of "re-derivation", the read
path performs one. Under this reading the catalog's package-scoped routes are outside the
specification as merged, and `M2` condition 1 does not hold.

### Reading B — it does not

Three things in the same specification point the other way.

1. **The Requirements presuppose the route holds a bundle.** `RRA-011`:169-170: *"Expose exactly one
   evidence projection per fact. A catalog route MUST read the projection the report surfaces already
   render from, never assemble a second one **from the bundle** directly."* The prohibition is on
   assembling a *second* projection from a bundle the route evidently has.
2. **The mandated projection is unreachable without one.** That projection is `_audit_region`, whose
   only caller is `build_context(bundle, language, cells)` (`html.py:591`). There is no path to it
   that does not take a bundle.
3. **No store persists a `ReportBundle`.** Verified: it appears in no persistence module, and
   `bundle_id` hashes a narrative nothing retains (`#343`'s Finding F4). `ReportBundle.of` is called
   in three places — `pipeline.py:352`, `benchmark_trial.py:127`, and `report_api.py:761`.

Under Reading A, `RRA-011` mandates a route that no implementation can satisfy: it requires serving a
projection reachable only through an object the route may not construct and no store holds. Under
Reading B, "repeats a value" prohibits the catalog *publishing a figure it computed itself* — which
the surfaces do not do, and which `test_no_catalog_response_carries_a_figure_value` proves: no
rendered value, no `text`, no `value` field reaches any catalog response.

### Why this is not mine to settle

The two readings differ on whether a merged surface is admissible, and one of them makes an active
specification unimplementable. `AGENTS.md` makes that an owner reading. Choosing Reading B silently
would be resolving a governance question by preferring the answer that keeps my own slice; choosing
Reading A silently would withdraw a merged surface on an interpretation the specification's own
Requirements contradict.

**What follows from each:**

| | Reading A | Reading B |
|---|---|---|
| `M2` §7 condition 1 | Does not hold | Holds, pending condition 4's re-run |
| `#343`'s package routes | Outside specification; must read a retained projection | Admissible as merged |
| Work implied | Retain the bundle or its projection — an `RRA-004`/`RRA-006` change, since neither currently persists one | None |
| `RRA-011`:169-170 | Must be amended, being unsatisfiable as written | Unchanged |

---

## What is fixed here, regardless of the answer

`test_no_catalog_route_recomputes_a_published_figure` is replaced by
`test_a_catalog_read_derives_analysis_facts_through_bundle_construction`, which patches
`concentration.curve_series`, drives a real catalog `GET`, and asserts the call count is **non-zero**.

It records the behaviour as it is rather than as either reading would prefer. If the owner adopts
Reading A the assertion inverts to zero and the route changes; if Reading B, the test stands as the
statement that this is understood and accepted. Either way the next reader measures the behaviour
instead of inferring it from a string search that could not see it.

---

## Standing

`M2` is **not** recorded as reached. `#344` was closed rather than revised, and `#342`'s assessment —
condition 1 failing — remains the accurate record of the tree until this question is answered.

Two things are owed before `M2` can be reassessed, and only the first depends on this question:

1. **This reading.** Owner's.
2. **Condition 4's delivery stages, re-run on the current tree.** `#344`'s journey stopped at fact
   publication and never exercised worker completion, bundle, HTML, evidence, PDF or Excel. §7.4 says
   *full* journey, and `#343` changed `report_api.py` and the API wiring, so `#342`'s delivery
   evidence cannot simply be inherited. This is owed under either reading.

`#343`'s catalog surfaces stay merged meanwhile. Under Reading B they are correct; under Reading A
they are admissible but incomplete, and no wrong figure is published either way — the catalog serves
no value, and the whole-repo suite is green at 3,910 passed.
