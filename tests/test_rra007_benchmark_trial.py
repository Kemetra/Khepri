from __future__ import annotations

import pytest

from khepri.rra.benchmark_trial import (
    DeterministicReportTrial,
    TrialOutcome,
    TrialPorts,
    build_benchmark_package,
)
from khepri.rra.benchmark_workload import BenchmarkDataset, BenchmarkWorkload
from khepri.rra.bundle import (
    NARRATIVE_INCLUDED,
    NARRATIVE_OMITTED,
    REQUIRED_SURFACES,
    SURFACE_PDF,
    SURFACE_WEB,
)
from khepri.rra.facts import FactPackage
from khepri.rra.narrative import (
    LANGUAGE_ARABIC,
    LANGUAGE_ENGLISH,
    LanguageNarrative,
    NarrativeDraft,
    NarrativeSection,
)
from tests.rra003_contract_fixtures import REFUSAL_WINDOW
from tests.rra_benchmark_fakes import (
    BrokenRenderer,
    Renderer,
    faithful_renderers,
    renderers_but,
)

WORKLOAD = BenchmarkWorkload(sample_count=2, rows_per_dataset=8)


def dataset() -> BenchmarkDataset:
    return WORKLOAD.datasets()[0]


class Narrator:
    """A provider boundary that either answers or does not."""

    def __init__(self, *, answers: bool) -> None:
        self._answers = answers

    def draft(self, package: FactPackage) -> NarrativeDraft | None:
        if not self._answers:
            return None
        return NarrativeDraft(
            adapter_version="benchmark.adapter.v1",
            request_digest=package.digest,
            languages=tuple(
                LanguageNarrative(
                    language=language,
                    sections=(
                        NarrativeSection(
                            section_id="summary",
                            text="text",
                            cited_fact_ids=(package.facts[0].fact_id,),
                            caveats=(),
                        ),
                    ),
                )
                for language in (LANGUAGE_ARABIC, LANGUAGE_ENGLISH)
            ),
        )


class Clock:
    """A monotonic reading in milliseconds, one tick per call."""

    def __init__(self) -> None:
        self.reading = 0

    def __call__(self) -> int:
        self.reading += 1
        return self.reading


def trial(
    *,
    renderers: tuple[Renderer, ...] | None = None,
    narrator: Narrator | None = None,
) -> DeterministicReportTrial:
    surfaces = renderers or faithful_renderers()
    return DeterministicReportTrial(
        ports=TrialPorts(renderers=surfaces, narrator=narrator),
        monotonic_ms=Clock(),
    )


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_a_generated_dataset_is_one_the_report_path_can_measure() -> None:
    # A workload the profiler or the mapper refuses would measure a refusal
    # rather than a report, and certify nothing while looking busy.
    package = build_benchmark_package(dataset())

    assert package.facts != ()
    assert package.row_count == 8


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_the_trial_runs_the_report_path_and_names_every_surface() -> None:
    built = trial()

    outcome = built.run(dataset())

    assert outcome.complete is True
    assert outcome.surfaces == REQUIRED_SURFACES


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_the_trial_reports_when_it_began_from_the_injected_clock() -> None:
    clock = Clock()
    built = DeterministicReportTrial(
        ports=TrialPorts(renderers=faithful_renderers()),
        monotonic_ms=clock,
    )

    outcome = built.run(dataset())

    assert outcome.started_at_ms == 1


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_a_report_measured_without_a_provider_omits_the_narrative() -> None:
    renderers = faithful_renderers()

    trial(renderers=renderers).run(dataset())

    assert renderers[0].seen[0].narrative_state == NARRATIVE_OMITTED


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_a_provider_that_answered_is_measured_inside_the_report() -> None:
    renderers = faithful_renderers()

    outcome = trial(renderers=renderers, narrator=Narrator(answers=True)).run(dataset())

    assert outcome.complete is True
    assert renderers[0].seen[0].narrative_state == NARRATIVE_INCLUDED


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_a_provider_that_did_not_answer_measures_no_complete_bundle() -> None:
    # A report the pipeline would refuse to deliver is not a complete bundle,
    # and a benchmark that counted it would certify an objective never met.
    outcome = trial(narrator=Narrator(answers=False)).run(dataset())

    assert outcome.complete is False
    assert outcome.surfaces == ()


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_a_surface_that_failed_measures_no_complete_bundle() -> None:
    outcome = trial(renderers=renderers_but(BrokenRenderer(SURFACE_PDF))).run(dataset())

    assert outcome.complete is False
    assert SURFACE_PDF not in outcome.surfaces


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_a_missing_renderer_measures_no_complete_bundle() -> None:
    outcome = trial(renderers=(Renderer(SURFACE_WEB), Renderer(SURFACE_PDF))).run(dataset())

    assert outcome.complete is False


@pytest.mark.xfail(reason=REFUSAL_WINDOW, strict=True)
def test_the_same_dataset_is_measured_over_the_same_report_twice() -> None:
    # The measured path has to be reproducible, or two runs of one approved
    # workload are two different measurements.
    first = faithful_renderers()
    second = faithful_renderers()

    trial(renderers=first).run(dataset())
    trial(renderers=second).run(dataset())

    assert first[0].seen[0].bundle_id == second[0].seen[0].bundle_id


@pytest.mark.parametrize(
    "surfaces",
    [
        pytest.param((), id="no_surfaces"),
        pytest.param((SURFACE_WEB, SURFACE_PDF), id="a_partial_export"),
    ],
)
def test_an_outcome_claiming_a_complete_bundle_must_name_every_surface(
    surfaces: tuple[str, ...],
) -> None:
    with pytest.raises(ValueError, match="required surface"):
        TrialOutcome(started_at_ms=1, surfaces=surfaces, complete=True)
