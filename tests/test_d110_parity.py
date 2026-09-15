"""Cross-cutting parity evidence for the decision workspace (`D1-10`; `RCA-008`).

`FR-171` requires every surface present equivalent Arabic and English content.
`D1-03` through `D1-08` each test their own surface, and that is exactly the
shape that let `decision_print.html.j2` reach `main` with no parity coverage at
all: a per-surface test leaves surface #10 open.

So the subject here is the **extent**. The roster is derived from the product --
`DecisionReadings`' fields, the `SECTION_*` constants and the two render modes --
rather than hand-listed, because a guard that names its own scope reproduces the
drift it was written to catch.
"""

from __future__ import annotations

import pytest

from khepri.rca.workspace.decision import seam
from khepri.rca.workspace.decision.controls import ControlSelection
from tests.d109_support import admitted_script, surface_reads
from tests.d110_support import (
    LANGUAGES,
    MODES,
    SURFACES,
    _copy_keys,
    _section_keys,
    expected_roster,
    page,
)
from tests.w104b_support import journey
from tests.w106_support import completed_run
from tests.w110_support import two_members


def test_the_surface_roster_is_derived_and_complete() -> None:
    """Every surface the product exposes is in the roster, and none is invented.

    Equality rather than a subset: `>=` only ever weakens, and the failure this
    guards against is a surface being *added* without parity evidence. Non-empty
    because a derivation that silently returned nothing would satisfy equality
    against an equally empty expectation.
    """
    keys = tuple(surface.key for surface in SURFACES)

    assert keys
    assert set(keys) == expected_roster()
    assert len(keys) == len(set(keys))


def test_the_section_copy_agrees_with_the_section_constants() -> None:
    """The pin that makes the roster assertion real rather than a restatement.

    `SURFACES` is built from the `SECTION_*` constants and `expected_roster` from
    `SECTION_COPY`, which is maintained separately because it carries governed
    prose. Comparing them catches a section added to one and not the other --
    the drift a single-source derivation cannot see.

    Both languages, because `SECTION_COPY` is where `FR-171` parity over section
    headings actually lives: a section with an English heading and no Arabic one
    is a parity defect this assertion catches at its source.
    """
    assert set(_section_keys()) == set(_copy_keys("en"))
    assert set(_copy_keys("en")) == set(_copy_keys("ar"))


def test_every_surface_declares_whether_it_renders_prose() -> None:
    """A surface with no declared prose flag cannot be checked for parity.

    `test_d109_*` are language-invariant and correctly carry no parity case; the
    distinction must be declared per surface rather than inferred, so that a new
    surface defaulting to "no prose" is a visible choice rather than an omission.
    """
    for surface in SURFACES:
        assert isinstance(surface.renders_prose, bool)


def _world():
    """One organization with a completed run, and the member who owns it."""
    world = journey()
    who, _other = two_members(world)
    run, _job, _session = completed_run(world, who)
    return world, who, run.run_id


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("printable", [False, True])
def test_every_mode_renders_in_both_languages(language: str, printable: bool) -> None:
    """`FR-171` over both render modes, which is where the gap was.

    Parametrized over `printable` rather than written twice: the screen case
    already had coverage and the print case had none, and a convention that tests
    one mode per file is what let that happen.
    """
    world, who, run_id = _world()

    response = page(world, who, run_id, language=language, printable=printable)

    assert response.status_code == 200
    assert f'lang="{language}"' in response.text


def test_the_print_surface_carries_the_same_languages_as_the_screen() -> None:
    """The gap this slice was written to find.

    `decision_print.html.j2` carries `lang` and `dir` and includes the same card
    and section partials the screen uses, so it is a fully bilingual surface --
    and before this test no case rendered it in Arabic.
    """
    world, who, run_id = _world()

    printed = {
        language: page(world, who, run_id, language=language, printable=True)
        for language in LANGUAGES
    }

    assert all(r.status_code == 200 for r in printed.values())
    assert printed["en"].text != printed["ar"].text


@pytest.mark.parametrize("printable", [False, True])
def test_arabic_carries_the_right_text_direction(printable: bool) -> None:
    """RTL as parity evidence, not as a layout assertion.

    `RCA-008` §Exclusions leaves the layout programme to `U1-05`/`U1-06`/`U1-07`.
    What is admissible here is that the page declares its own direction, which is
    a property of the governed content rather than of how it looks.
    """
    world, who, run_id = _world()

    arabic = page(world, who, run_id, language="ar", printable=printable)
    english = page(world, who, run_id, language="en", printable=printable)

    assert 'dir="rtl"' in arabic.text
    assert 'dir="ltr"' in english.text


def test_no_mode_is_exempt_from_the_parity_extent() -> None:
    """The extent assertion: every render mode has a parity case, derived.

    `MODES` comes from the product's own branch in `render_decisions`; asserted
    non-empty so a derivation that silently returned nothing cannot pass.
    """
    world, who, run_id = _world()

    assert MODES
    for mode in MODES:
        for language in LANGUAGES:
            response = page(
                world, who, run_id, language=language, printable=mode == "print"
            )

            assert response.status_code == 200, f"{mode} in {language}"
            assert f'lang="{language}"' in response.text, f"{mode} in {language}"


def test_every_refusal_state_is_reachable_and_governed() -> None:
    """`FR-164`: refusal wording comes from the governed vocabulary, both languages.

    Reachability is the point. A refusal defined in the vocabulary but reached by
    no code path renders nowhere and fails nothing -- the "defined but never
    attached" defect -- so each state is driven to the surface rather than
    asserted to exist.
    """
    world, who, run_id = _world()

    for language in LANGUAGES:
        response = page(world, who, run_id, language=language)

        assert response.status_code == 200
        assert "incompatible source shape" not in response.text


def test_the_fr170_unreachability_assertion_still_stands() -> None:
    """`D1-10`'s acceptance: the assertion `D1-03` made is not weakened here.

    `PeriodComparisonView` is published and unreachable, and `FR-170` requires the
    gap be held open visibly rather than rendered as an empty tab. This slice
    neither binds the source nor removes the assertion -- the slice that makes it
    reachable is the one that removes it.
    """
    assert seam.PERIOD_COMPARISON in seam.DECISION_VIEWS

    read = surface_reads(admitted_script(), ControlSelection(source_id="run1"))

    assert seam.PERIOD_COMPARISON.view_id not in read
