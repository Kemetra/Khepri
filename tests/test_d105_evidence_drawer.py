"""`D1-05` -- S-9's figure half, the card's evidence action, and the drawer.

Authority: active `RCA-008` `FR-159`, `FR-161`, `FR-162`, `FR-164`, `FR-171`.

The read model is driven through a fake port, as `D1-02`'s, `D1-03`'s and
`D1-04`'s were: what is under test is the selection. **Two cases are driven
through the real projector instead**, and deliberately -- `ReportEvidenceView`
publishes a `provenance` and an `absence` column that `RRA-014`'s
`_FIELD_READERS` gives no reader, so both project as stated absences, and the
drawer reads provenance from the evidence records instead. A hand-built
projection could assert the drawer's behaviour but not that fact about the view,
and the day `RRA-014` gives those columns readers this module needs to be looked
at rather than to keep silently double-sourcing.

**The drawer is asserted to be a disclosure and not an address** (`FR-161`: not
"deferred to a terminal page"), which is a negative about the route table rather
than about the template, because a template can only fail to link to a page that
exists.
"""

from __future__ import annotations

import dataclasses
import re
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.organizations import Organization
from khepri.rca.semantic_queries import ports
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.decision import card, evidence, seam
from khepri.rra import facts
from khepri.rra.bundle import (
    NARRATIVE_OMITTED,
    SECTION_PRESENT,
    BundleIdentity,
    CitedEvidence,
    CitedFigure,
    ReportBundle,
    Section,
)
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.semantic_views import compatibility, projection, registry
from khepri.runtime import shell_decisions
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes

LANGUAGES = ("en", "ar")
NOW = datetime(2026, 9, 12, tzinfo=UTC)

_EVIDENCE_FIELDS = ("figure", "evidence", "provenance", "absence")
_OVERVIEW_FIELDS = ("metric", "value", "population", "versions")
_AVAILABILITY_FIELDS = ("metric", "availability", "reason", "versions")

#: Every line `FR-162` requires a card expose "directly or through one action",
#: as the template marks them. `comparison` is absent on purpose: the
#: requirement says "comparison **only when compatible**", and `FR-170`'s source
#: is unreachable, so a comparison line here would be the invented figure
#: `FR-164` forbids rather than the requirement met.
_FR162_LINES = (
    "label",
    "value",
    "unit",
    "status",
    "population",
    "formula",
    "versions",
    "filters",
    "period",
    "evidence",
    "caveats",
)


# --- the scripted port, as the three slices before this one built it ---------


class _ScriptedPort:
    """Answers per `view_id`, so one read can miss while the others admit."""

    def __init__(self, outcomes: dict[str, ports.ViewOutcome | None]) -> None:
        """Answer each view with what it was scripted to answer."""
        self.outcomes = outcomes
        self.requests: list[ports.SemanticViewRequest] = []

    def project(
        self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
    ) -> ports.ViewOutcome | None:
        """Record the request verbatim, and answer as scripted."""
        self.requests.append(request)
        return self.outcomes.get(request.view_id)


class _FakeIsolation:
    """One owner id for any pair; scoping is not what these cases test."""

    def resolve_scope(self, account_id: str, organization_id: str) -> str:
        """One owner id, so the port decides every answer."""
        return f"owner-of-{organization_id}"


class _FakeSources:
    """A source reader that always finds the run."""

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> object:
        """A source the fake port never inspects."""
        return object()


def _actions(port: _ScriptedPort) -> SemanticQueryActions:
    """The real orchestration over a fake door and a scripted port."""
    return SemanticQueryActions(_FakeIsolation(), _FakeSources(), port)


@dataclasses.dataclass(frozen=True, slots=True)
class _Record:
    """One cited evidence record as the port publishes it.

    A local shape rather than `CitedEvidence` because the read model is
    `khepri.rca`'s and may not import `khepri.rra`: a test that handed it the
    real record would assert an import the module is forbidden to make.
    """

    citation_id: str
    metric: str
    unit_kind: object = "monetary"
    formula_version: object = "rra004.formula.v1"
    precision: object | None = 2
    inputs: object | None = ("fct_a",)
    provenance: object | None = (("subject", "v1"),)


#: A complete record and one stating all three governed absences.
_STATED = _Record(citation_id="cit_revenue", metric="revenue")
_UNSTATED = _Record(
    citation_id="cit_gross_profit",
    metric="gross_profit",
    precision=None,
    inputs=None,
    provenance=None,
)

#: The absences `_UNSTATED` states, in the order `RRA-014` states them.
_UNSTATED_ABSENCES = (
    ("cit_gross_profit", "precision"),
    ("cit_gross_profit", "inputs"),
    ("cit_gross_profit", "provenance"),
)


def _evidence_outcome(
    records: tuple[_Record, ...] = (_STATED,),
    absences: tuple[tuple[str, str], ...] = (),
) -> ports.ViewOutcome:
    """An admitted S-9 outcome carrying rows, records and stated absences."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.REPORT_EVIDENCE.view_id,
            view_version=seam.REPORT_EVIDENCE.view_version,
            fields=_EVIDENCE_FIELDS,
            rows=tuple(
                (f"fig_{record.metric}", record.citation_id, None, None)
                for record in records
            ),
            evidence=records,
            evidence_absences=absences,  # type: ignore[arg-type]
        ),
        effective=ports.EffectiveRequest(dimensions=("period",)),
    )


def _request() -> evidence.EvidenceRequest:
    """One member asking for one run's evidence."""
    return evidence.EvidenceRequest(
        organization_id="org-1", account_id="acct-1", source_id="run-1"
    )


def _read(outcome: ports.ViewOutcome | None) -> evidence.EvidenceReading:
    """One S-9 read against a port scripted to answer that view alone."""
    port = _ScriptedPort({seam.REPORT_EVIDENCE.view_id: outcome})
    return evidence.read_evidence(_actions(port), _request())


# --- FR-160: S-9 is read at its literal version, and no other view ----------


def test_the_evidence_version_is_a_literal_the_registry_still_publishes() -> None:
    """`FR-160` -- pinned here, asserted against the registry there."""
    published = registry.define_view(seam.REPORT_EVIDENCE.view_id)
    assert published.view_version == seam.REPORT_EVIDENCE.view_version
    assert published.empty_result_rule == seam.REPORT_EVIDENCE.empty_rule


def test_the_drawer_reads_only_the_evidence_view() -> None:
    """`FR-160` -- named exactly, and no second view fetched to fill anything in."""
    port = _ScriptedPort({seam.REPORT_EVIDENCE.view_id: _evidence_outcome()})
    evidence.read_evidence(_actions(port), _request())
    assert [asked.view_id for asked in port.requests] == [seam.REPORT_EVIDENCE.view_id]
    assert port.requests[0].view_version == seam.REPORT_EVIDENCE.view_version


def test_the_evidence_read_names_no_metric_so_the_view_selects() -> None:
    """`FR-135` -- an empty selection asks for the definition's published one."""
    port = _ScriptedPort({seam.REPORT_EVIDENCE.view_id: _evidence_outcome()})
    evidence.read_evidence(_actions(port), _request())
    assert port.requests[0].metrics == ()
    assert port.requests[0].dimensions == ()


# --- FR-137: this view admits no filter, so the drawer sends none ------------


def test_the_evidence_request_carries_no_filter_because_the_view_admits_none() -> None:
    """`FR-137` -- a forwarded filter would refuse every figure the drawer opened on."""
    assert registry.define_view(seam.REPORT_EVIDENCE.view_id).request_filter_allowlist == ()
    port = _ScriptedPort({seam.REPORT_EVIDENCE.view_id: _evidence_outcome()})
    evidence.read_evidence(_actions(port), _request())
    assert port.requests[0].filters == ()


def test_the_evidence_request_has_no_filters_field_to_forward() -> None:
    """The absence is on the type, so no caller can supply one to be dropped."""
    named = {field.name for field in dataclasses.fields(evidence.EvidenceRequest)}
    assert "filters" not in named


# --- FR-159: the entries are the projection's, grouped for layout -----------


def test_an_entry_carries_what_the_record_states_and_nothing_it_does_not() -> None:
    """`FR-159` -- select and pass through. Precision is the record's, not re-derived."""
    entry = _read(_evidence_outcome()).entries[0]
    assert entry.citation == "cit_revenue"
    assert entry.metric == "revenue"
    assert entry.unit_kind == "monetary"
    assert entry.precision == 2
    assert entry.inputs == ("fct_a",)
    assert entry.provenance == (("subject", "v1"),)


def test_an_entry_names_the_figures_its_citation_appears_against() -> None:
    """The view's own rows, grouped by citation. Layout, not derivation."""
    entry = _read(_evidence_outcome()).entries[0]
    assert entry.figures == ("fig_revenue",)


def test_the_evidence_reading_keeps_no_effective_request_of_its_own() -> None:
    """The filters a card states are the ones that applied to its own figure.

    `FR-162` requires a card expose "the effective filters and period", and the
    card's figure is S-1's. Keeping S-9's applied request here as well would put
    two effective requests on one surface with one of them rendered, which is the
    second truth `FR-135` bars.
    """
    named = {field.name for field in dataclasses.fields(evidence.EvidenceReading)}
    assert "effective" not in named


# --- FR-140: an absence is data on an admitted reading, never a refusal ------


def test_a_governed_absence_is_named_against_its_own_citation() -> None:
    """`FR-140` -- "the record says there is none", carried to the reader as that."""
    reading = _read(_evidence_outcome((_STATED, _UNSTATED), _UNSTATED_ABSENCES))
    absent = {entry.metric: entry.absences for entry in reading.entries}
    assert absent["gross_profit"] == ("precision", "inputs", "provenance")
    assert absent["revenue"] == ()


def test_an_absence_leaves_the_reading_admitted_and_unrefused() -> None:
    """`D1-01` §4 -- every view's `required_evidence` is `()`, so this is data."""
    reading = _read(_evidence_outcome((_UNSTATED,), _UNSTATED_ABSENCES))
    assert reading.status == ports.KIND_ADMITTED
    assert reading.refusal is None
    assert reading.entries[0].absences


def test_an_empty_evidence_projection_states_absence_rather_than_no_rows() -> None:
    """`FR-163` -- S-9's governed rule is `stated_absence`, and it says so."""
    outcome = _evidence_outcome(())
    empty = dataclasses.replace(outcome.projection, is_empty=True)  # type: ignore[arg-type]
    reading = _read(dataclasses.replace(outcome, projection=empty))
    assert reading.empty_rule == seam.EMPTY_STATED_ABSENCE


# --- the two cases driven through the real projector ------------------------


def _bundle(evidence_records: tuple[CitedEvidence, ...]) -> ReportBundle:
    """One single-population bundle carrying one figure per evidence record."""
    figures = tuple(
        CitedFigure(
            figure_id=f"fig_{record.metric}",
            citation_id=record.citation_id,
            fact_id="fct_000000000000000000000000",
            metric=record.metric,
            unit_kind="monetary",
            kind="value",
            section="overview",
            label=None,
            value=Decimal("500.50"),
            renderings={LANGUAGE_ENGLISH: "500.50", LANGUAGE_ARABIC: "٥٠٠٫٥٠"},
        )
        for record in evidence_records
    )
    return ReportBundle(
        identity=BundleIdentity(
            package_version="rra004.package.v1",
            formula_version="rra004.formula.v1",
            mapping_version="rra004.mapping.v1",
            narrative_version="rra005.narrative.v1",
            profile_digest="0" * 64,
            source_sha256_hex="1" * 64,
            monetary_precision=2,
            row_count=3,
        ),
        figures=figures,
        caveats=(),
        narrative_state=NARRATIVE_OMITTED,
        sections=(
            Section(
                section_id="overview",
                state=SECTION_PRESENT,
                reason=None,
                figure_ids=tuple(figure.figure_id for figure in figures),
                chart=None,
            ),
        ),
        evidence=evidence_records,
    )


def _projected(records: tuple[CitedEvidence, ...]) -> object:
    """`ReportEvidenceView` over a real bundle, through `RRA-014`'s own projector."""
    definition = registry.define_view(seam.REPORT_EVIDENCE.view_id)
    request = compatibility.SemanticViewRequest(
        view_id=definition.view_id,
        view_version=definition.view_version,
        metrics=(),
        dimensions=(),
        filters=(),
    )
    return projection.project(request, (_bundle(records),)).projection


def _cited(citation_id: str, metric: str, *, complete: bool) -> CitedEvidence:
    """One real evidence record, either fully stated or stating its absences."""
    return CitedEvidence(
        citation_id=citation_id,
        metric=metric,
        unit_kind="monetary",
        formula_version="rra004.formula.v1",
        precision=2 if complete else None,
        inputs=("fct_a",) if complete else None,
        provenance=(("subject", "v1"),) if complete else None,
    )


def test_the_views_provenance_and_absence_columns_are_stated_absences() -> None:
    """Why the drawer reads the records instead of the rows.

    `_FIELD_READERS` gives `figure` and `evidence` readers and gives these two
    none, so `_unstated` answers both -- "a field no member of `RenderableBundle`
    states, an absence and not a blank". `RCA-008` §Exclusions bars this
    specification from changing that, so this asserts the fact rather than fixing
    it: the day `RRA-014` publishes readers for them, this fails and `evidence.py`
    is looked at rather than left double-sourcing one figure.
    """
    projected = _projected((_cited("cit_revenue", "revenue", complete=True),))
    named = dict(zip(projected.fields, projected.rows[0], strict=True))  # type: ignore[attr-defined]
    assert named["figure"] == "fig_revenue"
    assert named["evidence"] == "cit_revenue"
    assert named["provenance"] is None
    assert named["absence"] is None


def test_a_governed_absence_arrives_as_a_citation_and_kind_pair() -> None:
    """`evidence_absences` is pairs, whatever `ports.ViewProjection` annotates.

    `RRA-014` builds `(citation_id, one of precision | inputs | provenance)` and
    the adapter hands the outcome back unchanged, while `RCA-006`'s port declares
    `tuple[str, ...]`. §Exclusions bars this slice from editing either module, so
    the shape is asserted where it is produced and modelled correctly here.
    """
    projected = _projected((_cited("cit_gross_profit", "gross_profit", complete=False),))
    assert set(projected.evidence_absences) == {  # type: ignore[attr-defined]
        ("cit_gross_profit", "precision"),
        ("cit_gross_profit", "inputs"),
        ("cit_gross_profit", "provenance"),
    }


# --- FR-165 and the dispatch rule -------------------------------------------


def test_the_drawer_can_answer_unavailable_on_its_own() -> None:
    """`FR-165` -- content-free, and the cards beside it still render."""
    reading = _read(None)
    assert reading.status == ports.KIND_UNAVAILABLE
    assert reading.entries == ()
    assert reading.refusal is None


def test_a_refused_outcome_carrying_a_projection_is_still_refused() -> None:
    """The kind decides, never the payload -- carried from `#446`."""
    refusal = ports.ViewRefusal(cause="view_incompatible_source_shape")
    outcome = dataclasses.replace(
        _evidence_outcome(), kind=ports.KIND_REFUSED, refusal=refusal
    )
    reading = _read(outcome)
    assert reading.status == ports.KIND_REFUSED
    assert reading.entries == ()
    assert reading.refusal is refusal


# --- FR-162: the card's evidence action -------------------------------------


def _availability(rows: tuple[tuple[object, ...], ...]) -> ports.ViewOutcome:
    """S-6's governed four-state for the metrics a case names."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.METRIC_AVAILABILITY.view_id,
            view_version=seam.METRIC_AVAILABILITY.view_version,
            fields=_AVAILABILITY_FIELDS,
            rows=rows,
        ),
    )


def _overview(caveats: tuple[object, ...] = ()) -> ports.ViewOutcome:
    """S-1 publishing two figures, qualified by whatever caveats a case supplies."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.EXECUTIVE_OVERVIEW.view_id,
            view_version=seam.EXECUTIVE_OVERVIEW.view_version,
            fields=_OVERVIEW_FIELDS,
            rows=(
                ("revenue", "700.00", "complete", ()),
                ("gross_profit", "120.00", "complete", ()),
            ),
            caveats=caveats,
        ),
        effective=ports.EffectiveRequest(dimensions=("period",)),
    )


def _cards(evidence_outcome: ports.ViewOutcome | None, **kw: object) -> card.CardsReading:
    """One S-1 read with S-6 and S-9 beside it, each scripted independently."""
    port = _ScriptedPort(
        {
            seam.EXECUTIVE_OVERVIEW.view_id: _overview(**kw),  # type: ignore[arg-type]
            seam.METRIC_AVAILABILITY.view_id: _availability(
                (("revenue", card.AVAILABILITY_AVAILABLE, None, ()),)
            ),
            seam.REPORT_EVIDENCE.view_id: evidence_outcome,
        }
    )
    return card.read_cards(
        _actions(port),
        card.CardsRequest(organization_id="org-1", account_id="acct-1", source_id="run-1"),
    )


def test_a_card_carries_the_evidence_action_for_its_own_metric() -> None:
    """`FR-162` -- "an evidence action", which `D1-03` named and left empty."""
    reading = _cards(_evidence_outcome((_STATED, _UNSTATED), _UNSTATED_ABSENCES))
    actions = {one.metric: one.evidence for one in reading.cards}
    assert actions["revenue"].entries[0].citation == "cit_revenue"
    assert actions["gross_profit"].entries[0].citation == "cit_gross_profit"


def test_a_card_whose_metric_the_evidence_view_did_not_cite_says_so() -> None:
    """An action with no entries, never an entry borrowed from another metric."""
    reading = _cards(_evidence_outcome((_STATED,)))
    actions = {one.metric: one.evidence for one in reading.cards}
    assert actions["gross_profit"].entries == ()
    assert actions["gross_profit"].unavailable is False


def test_an_unavailable_evidence_read_leaves_every_card_rendered() -> None:
    """`FR-165` -- partial success. The figures stay; the drawer says it is missing."""
    reading = _cards(None)
    assert len(reading.cards) == 2
    assert all(one.evidence.unavailable for one in reading.cards)
    assert all(one.evidence.entries == () for one in reading.cards)


def test_the_cards_carry_the_effective_request_their_own_figures_applied() -> None:
    """`FR-137`/`FR-162` -- the filter line states what applied to *this* view."""
    reading = _cards(_evidence_outcome())
    assert reading.effective is not None
    assert reading.effective.dimensions == ("period",)


def test_the_caveat_count_cannot_reach_the_status_selection() -> None:
    """`FR-162` requires a count; `FR-159` bars a derived figure. Both hold."""
    one = _cards(_evidence_outcome(), caveats=("caveat_a",))
    three = _cards(_evidence_outcome(), caveats=("caveat_a", "caveat_b", "caveat_c"))
    assert {card_.status for card_ in one.cards} == {card_.status for card_ in three.cards}


# --- the surface: the drawer is a disclosure, not an address ----------------


class _Context:
    """A resolved actor in one organization, as `ActorResolver` answers one."""

    def __init__(self, organization_id: str | None = "org-acme") -> None:
        """One owner of `org-acme` unless the case names another scope."""
        self.account_id = "acct-1"
        self.organization_id = organization_id
        self.role = "owner"

    @property
    def is_owner(self) -> bool:
        """Owner everywhere; the decision surface is a read and never asks."""
        return True


class _StubResolver:
    """The scope door, answering one context."""

    def for_request(
        self, token: str, *, organization_id: str | None = None, now: object = None
    ) -> _Context:
        """The session's context."""
        return _Context()

    def require_owner(
        self, token: str, *, organization_id: str, now: object = None
    ) -> _Context:  # pragma: no cover
        """Never reached: nothing on this surface is owner-gated."""
        raise AssertionError("the decision surface is a read")


class _StubOrganizations:
    """One membership, so the frame resolves rather than the chooser rendering."""

    def organizations_for_account(self, account_id: str) -> list[Organization]:
        """The one organization every case in this file acts in."""
        return [
            Organization._from_storage(
                organization_id="org-acme", name="Acme", created_at=NOW
            )
        ]


class _StubDecisions:
    """S-1, S-6 and S-9 for any request, so the surface has a drawer to render."""

    def request(self, asked: object) -> ports.ViewOutcome:
        """Each view answered as itself; `FR-165` makes them independent."""
        view_id = asked.view.view_id  # type: ignore[attr-defined]
        if view_id == seam.METRIC_AVAILABILITY.view_id:
            return _availability((("revenue", card.AVAILABILITY_AVAILABLE, None, ()),))
        if view_id == seam.REPORT_EVIDENCE.view_id:
            return _evidence_outcome((_STATED, _UNSTATED), _UNSTATED_ABSENCES)
        return _overview()


def _app() -> FastAPI:
    """A shell wired with the decision collaborator."""
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(),
            organizations=_StubOrganizations(),
            decisions=_StubDecisions(),
        ),
        clock=lambda: NOW,
    )
    return app


def _client(app: FastAPI) -> TestClient:
    """That shell with a session cookie on it."""
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client


def _address(language: str = "en") -> str:
    """The decision surface's address for one completed run."""
    return f"{SHELL_PREFIX}/{language}/org-acme/decisions/run-a"


def _page(language: str = "en") -> str:
    """The rendered decision surface in one language."""
    return _client(_app()).get(_address(language)).text


def test_the_drawer_has_no_address_of_its_own() -> None:
    """`FR-161` -- reachable from the surface carrying the figure, never deferred."""
    paths = {getattr(route, "path", "") for route in _app().routes}
    assert not [path for path in paths if "evidence" in path]
    assert len([path for path in paths if "decisions" in path]) == 1


def test_the_drawer_arrives_in_the_same_response_as_the_figure() -> None:
    """A disclosure and not a link: opening it needs no second request."""
    body = _page()
    assert "cit_revenue" in body
    assert body.count('class="decision-drawer"') == 2


@pytest.mark.parametrize("line", _FR162_LINES)
def test_every_line_fr162_requires_is_on_the_card_or_in_its_drawer(line: str) -> None:
    """`FR-162` -- asserted against the requirement's own list, so a drop fails."""
    assert f'data-line="{line}"' in _page()


def test_no_comparison_line_is_rendered_while_its_source_is_unreachable() -> None:
    """`FR-162` says "comparison only when compatible"; `FR-170` says it is not."""
    body = _page()
    assert 'data-line="comparison"' not in body
    assert shell_decisions.COMPARISON_UNREACHABLE["en"] in body


def test_a_stated_absence_renders_as_data_rather_than_as_a_refusal() -> None:
    """`FR-140`/`FR-164` -- the record said there is none, and the drawer says that."""
    body = _page()
    assert 'class="decision-absence"' in body
    assert 'class="decision-refusal"' not in body


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_drawer_states_no_less_in_one_language_than_the_other(language: str) -> None:
    """`FR-171` -- same drawers, same entries, same absences in both."""
    body = _page(language)
    assert body.count('class="decision-drawer"') == 2
    assert body.count('class="decision-absence"') == _page("en").count(
        'class="decision-absence"'
    )


def test_the_absence_literals_are_the_ones_rra014_states() -> None:
    """Pinned in the shell, asserted against the source here.

    `RCA-007`'s
    `test_the_adapter_is_the_only_runtime_module_reaching_the_projection` makes
    `semantic_view_adapter.py` the one runtime module that may import the
    semantic-view package, because a second one is what a second composition
    root would look like. So the three absence kinds are literals in
    `shell_decisions.py` and this asserts them, exactly as `D1-03` asserts the
    availability literals against `khepri.rra.definitions`.
    """
    stated = {
        projection.ABSENCE_PRECISION,
        projection.ABSENCE_INPUTS,
        projection.ABSENCE_PROVENANCE,
    }
    for language in LANGUAGES:
        assert set(shell_decisions.ABSENCE_WORDING[language]) == stated


def test_the_unit_literals_are_the_ones_rra004_states() -> None:
    """The three governed unit kinds, keyed by the constants themselves."""
    stated = {facts.UNIT_MONETARY, facts.UNIT_COUNT, facts.UNIT_RATIO}
    for language in LANGUAGES:
        assert set(shell_decisions.UNIT_WORDING[language]) == stated


def test_every_string_the_drawer_adds_exists_in_both_governed_languages() -> None:
    """`FR-171` -- a key present in one language and absent in the other is a gap."""
    assert set(shell_decisions.DECISION_COPY["en"]) == set(
        shell_decisions.DECISION_COPY["ar"]
    )


def test_an_unavailable_drawer_says_that_and_says_nothing_more() -> None:
    """`FR-165` -- the unavailable outcome is content-free."""
    reading = _cards(None)
    view = shell_decisions.decision_view(reading, language="en")
    drawers = [one.drawer for one in view.cards]
    assert all(one.unavailable for one in drawers)
    assert all(one.entries == () for one in drawers)


def test_the_period_the_drawer_states_is_the_run_the_surface_names() -> None:
    """`FR-166` -- the period is a source selector, so the run is the period."""
    assert re.search(r'data-line="period"[^>]*>\s*run-a', _page()) is not None
