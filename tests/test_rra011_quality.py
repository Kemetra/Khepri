"""`AnalysisQualitySummary`: what one package answered, and what it did not.

`RRA-011` authorizes an aggregation and forbids a measurement. This summary
counts and groups outcomes a bundle already carries — it computes no figure,
scores nothing, and expresses **availability, never certainty**. A reader learns
what the system could and could not answer, not how much to trust an answer it
gave.

Two boundaries this suite exists to hold:

- **No Internal-tier field.** `Section.state` is Internal, and `RRA-009` renders
  an Internal field on no customer surface. A summary that classified sections by
  `state` would leak it through a catalog surface; classifying by whether a
  reason is present reaches the same answer from Audit-tier evidence.
- **No score.** `RRA-011` excludes a confidence score, a quality score, or a
  completeness percentage by name. Counts and codes only.
"""

from __future__ import annotations

import dataclasses

from khepri.rra import definitions
from khepri.rra.bundle import (
    SECTION_GROWTH,
    SECTION_PRESENT,
    SECTION_REASON_PRIOR_WINDOW_ABSENT,
    SECTION_REFUSED,
    Section,
)
from tests.rra009_fixtures import rich_bundle


def _summary():
    return definitions.summarize(rich_bundle())


def test_the_summary_counts_what_the_bundle_published_and_refused() -> None:
    """Counts reconcile against the bundle they came from.

    Derived independently here: the expectation walks the bundle's own sections
    rather than reading the summary's arithmetic back, so a summary that counted
    the same thing twice would fail rather than agree with itself.
    """
    bundle = rich_bundle()
    summary = definitions.summarize(bundle)

    published = [s for s in bundle.sections if s.state == SECTION_PRESENT]
    refused = [s for s in bundle.sections if s.state == SECTION_REFUSED]

    assert summary.answered == len(published)
    assert summary.refused == len(refused)
    assert summary.answered + summary.refused == len(bundle.sections)


def test_a_refused_section_names_its_reason() -> None:
    """A count alone tells a reader nothing they can act on.

    `RRA-008` refuses the affected analysis rather than the report, so the
    question a reader has is *which* analysis and *why* — and the reason is the
    Audit-tier evidence that answers it.

    **Built with a refusal rather than read off the rich fixture.** That fixture
    refuses nothing, so a loop over its empty `refusals` would pass while proving
    the opposite of what this test is named for. The bundle here is replaced with
    one carrying a refused section, so the assertion has something to fail on.
    """
    bundle = rich_bundle()
    refused = Section(
        section_id=SECTION_GROWTH,
        state=SECTION_REFUSED,
        reason=SECTION_REASON_PRIOR_WINDOW_ABSENT,
        figure_ids=(),
        chart=None,
    )
    # A refused section carries no figures, so the figures it indexed go with it:
    # `ReportBundle` requires sections and figures to agree about placement, and
    # substituting the section alone would raise before the summary was reached.
    kept = tuple(s for s in bundle.sections if s.section_id != SECTION_GROWTH)
    dropped = {
        figure_id
        for s in bundle.sections
        if s.section_id == SECTION_GROWTH
        for figure_id in s.figure_ids
    }
    sections = tuple(
        refused if s.section_id == SECTION_GROWTH else s for s in bundle.sections
    )
    summary = definitions.summarize(
        dataclasses.replace(
            bundle,
            sections=sections,
            figures=tuple(f for f in bundle.figures if f.figure_id not in dropped),
            caveats=tuple(c for c in bundle.caveats if c.section != SECTION_GROWTH),
        )
    )

    assert summary.refused == 1
    assert summary.refusals == ((SECTION_GROWTH, SECTION_REASON_PRIOR_WINDOW_ABSENT),)
    assert summary.answered == len(kept)


def test_classifying_by_reason_matches_the_state_the_bundle_recorded() -> None:
    """The Internal field is avoided without losing the answer it would give.

    `Section` enforces the invariant that a refused section carries a reason and
    a present one carries none, so reading `reason` is exactly equivalent to
    reading `state` — and `state` is the Internal-tier field a catalog surface
    may not touch.
    """
    bundle = rich_bundle()

    by_state = {s.section_id for s in bundle.sections if s.state == SECTION_REFUSED}
    by_reason = {s.section_id for s in bundle.sections if s.reason is not None}

    assert by_state == by_reason


def test_the_summary_carries_no_internal_tier_field() -> None:
    """`Section.state` is Internal and must not reach a catalog surface.

    `_audit_region` drops it for this reason, stating that handing it to a
    consumer would be handing them a field they must remember not to render.
    """
    fields = {f.name for f in dataclasses.fields(definitions.AnalysisQualitySummary)}

    assert "state" not in fields
    assert "states" not in fields


def test_the_summary_states_no_score() -> None:
    """`RRA-011` excludes a confidence, quality, or completeness measure by name."""
    fields = {f.name for f in dataclasses.fields(definitions.AnalysisQualitySummary)}
    forbidden = {"score", "confidence", "quality", "completeness", "percentage", "ratio"}

    assert not (fields & forbidden)


def test_caveated_answers_are_counted_apart_from_clean_ones() -> None:
    """"Answered" and "answered with a qualification" are different outcomes.

    Collapsing them would tell a reader everything succeeded when some of it
    succeeded conditionally, which is the disclosure `RRA-009`'s caveats exist to
    make.
    """
    bundle = rich_bundle()
    summary = definitions.summarize(bundle)

    # Derived here rather than read back: a summary that collapsed the two would
    # report every answered section as caveated, and `caveated <= answered` alone
    # cannot see that -- it holds when they are equal. A mutation check found
    # exactly that hole.
    qualified = {c.section for c in bundle.caveats if c.section is not None}
    expected = len({s.section_id for s in bundle.sections if s.reason is None} & qualified)

    assert summary.caveated == expected
    assert summary.caveated < summary.answered
    assert summary.caveats


def test_the_summary_lists_which_sections_it_answered() -> None:
    """`RRA-011`:184-187 asks *which*, not only how many.

    Two bundles differing in which section answered produced identical summaries
    while `answered` was a bare count, so a reader could not tell a report that
    published the comparison from one that published the basket. The list is
    derived from the bundle here rather than read back from the summary, so a
    summary listing a section the bundle never answered fails on one side only.
    """
    bundle = rich_bundle()
    summary = definitions.summarize(bundle)

    expected = tuple(s.section_id for s in bundle.sections if s.reason is None)

    assert summary.answered_sections == expected
    assert len(summary.answered_sections) == summary.answered


def test_the_summary_lists_which_sections_carried_a_caveat() -> None:
    """A count of qualifications cannot say which analysis was qualified."""
    bundle = rich_bundle()
    summary = definitions.summarize(bundle)

    qualified = {c.section for c in bundle.caveats if c.section is not None}
    expected = tuple(
        s.section_id
        for s in bundle.sections
        if s.reason is None and s.section_id in qualified
    )

    assert summary.caveated_sections == expected
    assert len(summary.caveated_sections) == summary.caveated


def test_a_caveated_section_is_also_an_answered_one() -> None:
    """The two lists mirror the two counts, which overlap by construction.

    A caveated analysis was still answered -- the reader gets it, qualified --
    so `caveated_sections` is a subset rather than a disjoint set, exactly as
    `caveated` is counted within `answered`. Stated as a test because a surface
    rendering both lists must know it rather than infer it, and a later change
    making them disjoint would silently break `len(list) == count`.
    """
    summary = definitions.summarize(rich_bundle())

    assert set(summary.caveated_sections) <= set(summary.answered_sections)
    assert summary.answered + summary.refused == len(rich_bundle().sections)


def test_the_summary_says_which_caveat_qualified_which_section() -> None:
    """A code and a section list cannot be recombined into the association.

    `chart_not_drawn` qualifies two different sections in this bundle, so a
    reader given the codes and the sections separately cannot tell whether one
    code hit both or two codes hit one each. The pairs are the only thing that
    answers it.
    """
    bundle = rich_bundle()
    summary = definitions.summarize(bundle)

    expected = tuple(
        sorted(
            (c.code, c.section)
            for c in bundle.caveats
            if c.section is not None and ":" not in c.code
        )
    )

    assert summary.caveat_sections == expected
    # The duplicated code is the case that proves pairs rather than two lists.
    assert ("chart_not_drawn", "overview") in summary.caveat_sections
    assert ("chart_not_drawn", "comparison") in summary.caveat_sections


def test_a_report_level_caveat_is_associated_with_no_section() -> None:
    """`section=None` qualifies the dataset, not one analysis.

    `currency_not_declared` and `negative_revenue_present` qualify the whole
    package, so pairing them with a section would state a scope the bundle never
    claimed. They stay in `caveats`, which is report-wide already.
    """
    bundle = rich_bundle()
    summary = definitions.summarize(bundle)

    report_level = {c.code for c in bundle.caveats if c.section is None}
    assert report_level

    assert not (report_level & {code for code, _ in summary.caveat_sections})
    assert report_level <= set(summary.caveats)
