"""`D1-05` -- the evidence drawer, its two authorities, and the absence that is not a refusal.

Authority: active `RCA-008` `FR-159`, `FR-161`, `FR-162` (evidence action), `FR-164`.

The read model is driven through a fake port, as `D1-02`, `D1-03` and `D1-04`
were: what is under test is the *selection and attribution*, and a real
projection would put a pipeline between the inputs and the choice.

**The central assertion is negative.** An evidence absence is data on an admitted
projection and may never present as a view refusal. `D1-01` section 4 established
that every view's `required_evidence` is `()` at v1 deliberately, and `FR-141`
makes a required-but-absent code a refusal *cause* -- so a slice that populated
that tuple would convert ordinary absences into refused views. The registry
extent assertion below exists so that cannot happen quietly.
"""

from __future__ import annotations

import dataclasses

import pytest

from khepri.rca.semantic_queries import ports
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision import evidence, seam
from khepri.rra import definitions
from khepri.rra.semantic_views import registry
from khepri.runtime.metric_definitions import CatalogDefinitions

LANGUAGES = ("en", "ar")

_EVIDENCE_FIELDS = ("figure", "evidence", "provenance", "absence")


class _ScriptedPort:
    """Answers per `view_id`, recording what was asked verbatim."""

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
        """One owner id; scoping is not what the read-model cases are testing."""
        return f"owner-of-{organization_id}"


class _FakeSources:
    """A source reader that always finds the run, so the port decides every answer."""

    def get_analysis_run(self, run_id: str, owner_id: str | None = None) -> object:
        """A source the fake port never inspects."""
        return object()


def _actions(port: _ScriptedPort) -> SemanticQueryActions:
    """The real orchestration over a fake door and a scripted port."""
    return SemanticQueryActions(_FakeIsolation(), _FakeSources(), port)


def _projection(
    rows: tuple[tuple[object, ...], ...],
    absences: tuple[str, ...] = (),
) -> ports.ViewOutcome:
    """An admitted evidence outcome in the view's published field order."""
    return ports.ViewOutcome(
        kind=ports.KIND_ADMITTED,
        projection=ports.ViewProjection(
            view_id=seam.REPORT_EVIDENCE.view_id,
            view_version=seam.REPORT_EVIDENCE.view_version,
            fields=_EVIDENCE_FIELDS,
            rows=rows,
            evidence_absences=absences,
        ),
    )


def _request(metric: str = "revenue", language: str = "en") -> evidence.DrawerRequest:
    """One member opening the drawer on one figure of one run."""
    return evidence.DrawerRequest(
        organization_id="org-1",
        account_id="acct-1",
        source_id="run-1",
        metric=metric,
        language=language,
    )


def _catalog() -> CatalogDefinitions:
    """The real catalog adapter, bound where the composition root binds it.

    Real rather than a fake: what these cases assert is that the drawer reports
    the governed catalog's own answer, and a fake would let the module coin a
    wording while the test still passed.
    """
    return CatalogDefinitions()


def _read(outcome: ports.ViewOutcome | None, **kw: object) -> evidence.DrawerReading:
    """One drawer read against a port scripted to answer the evidence view alone."""
    port = _ScriptedPort({seam.REPORT_EVIDENCE.view_id: outcome})
    return evidence.read_drawer(
        _actions(port),
        _request(**kw),  # type: ignore[arg-type]
        definitions=_catalog(),
    )


# --- The central assertion: an absence is data, never a refusal ---------------


def test_an_evidence_absence_renders_as_data_and_not_as_a_refusal() -> None:
    """`FR-141` and `D1-01` section 4 -- the absence is on an *admitted* projection.

    A reader that mapped `evidence_absences` onto a refusal would tell a customer
    the view refused when the governed answer is that the record says there is
    none.
    """
    reading = _read(_projection((), absences=("no_source_document",)))

    assert reading.status == ports.KIND_ADMITTED
    assert reading.refusal is None
    assert reading.absences == ("no_source_document",)


def test_an_absence_does_not_suppress_the_figures_beside_it() -> None:
    """An absence qualifies the drawer; it does not empty it."""
    reading = _read(
        _projection(
            (("revenue", "invoice-1", "pkg-1", ""),), absences=("no_provenance",)
        )
    )

    assert reading.absences == ("no_provenance",)
    assert len(reading.items) == 1


# --- The definition half comes from the catalog, in both languages ------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_definition_half_is_the_governed_catalog_entry(language: str) -> None:
    """`FR-159` admits the definition because it is structure, not a figure."""
    reading = _read(_projection(()), metric="revenue", language=language)

    expected = definitions.define_metric("revenue")
    assert reading.definition is not None
    assert reading.definition.code == "revenue"
    assert reading.definition.formula_version == expected.formula_version
    assert reading.definition.description == definitions.describe_metric(
        "revenue", language
    )


# --- An unknown code refuses, rather than opening an empty drawer -------------


def test_an_unknown_metric_code_refuses_rather_than_opening_empty() -> None:
    """`FR-164` -- a blank drawer is indistinguishable from having no evidence."""
    with pytest.raises(definitions.UnknownCode):
        _read(_projection(()), metric="not-a-metric")


# --- The two halves stay attributed to their own authority --------------------


def test_the_two_halves_are_not_merged_into_one_record() -> None:
    """Two authorities, named separately, as `limits.py` keeps them.

    A flattened record would have to invent a field name for at least one half,
    and a reader could no longer tell which authority published what.
    """
    reading = _read(_projection((("revenue", "invoice-1", "pkg-1", ""),)))

    assert reading.definition is not None
    assert dataclasses.is_dataclass(reading.definition)
    assert reading.items and dataclasses.is_dataclass(reading.items[0])
    shared = set(dataclasses.asdict(reading.definition)) & set(
        dataclasses.asdict(reading.items[0])
    )
    assert shared == set()


# --- FR-160: its own view, at its own literal version, and nothing else -------


def test_the_drawer_reads_only_the_evidence_view_at_its_pinned_version() -> None:
    """`FR-160` -- named exactly, with no second view fetched to fill anything in."""
    port = _ScriptedPort({seam.REPORT_EVIDENCE.view_id: _projection(())})
    evidence.read_drawer(_actions(port), _request(), definitions=_catalog())

    assert [asked.view_id for asked in port.requests] == [seam.REPORT_EVIDENCE.view_id]
    assert port.requests[0].view_version == seam.REPORT_EVIDENCE.view_version


def test_the_drawer_sends_no_filter_the_view_does_not_admit() -> None:
    """The view's `request_filter_allowlist` is empty, so nothing may be sent."""
    port = _ScriptedPort({seam.REPORT_EVIDENCE.view_id: _projection(())})
    evidence.read_drawer(_actions(port), _request(), definitions=_catalog())

    assert port.requests[0].filters == ()


# --- The kind decides, never the payload -------------------------------------


def test_a_refused_outcome_reports_its_refusal_and_no_items() -> None:
    """`admitted_projection`'s rule, at this surface: a refusal shows no rows."""
    refusal = ports.ViewRefusal(
        cause="incompatible_shape",
        wording_pairs=(("en", "This view cannot read that source."), ("ar", "-")),
    )
    outcome = ports.ViewOutcome(
        kind=ports.KIND_REFUSED,
        refusal=refusal,
        projection=ports.ViewProjection(
            view_id=seam.REPORT_EVIDENCE.view_id,
            view_version=seam.REPORT_EVIDENCE.view_version,
            fields=_EVIDENCE_FIELDS,
            rows=(("revenue", "invoice-1", "pkg-1", ""),),
        ),
    )

    reading = _read(outcome)

    assert reading.status == ports.KIND_REFUSED
    assert reading.refusal is refusal
    assert reading.items == ()


def test_an_unavailable_read_says_nothing_about_why() -> None:
    """`FR-165` -- the unavailable outcome is content-free."""
    reading = _read(ports.ViewOutcome(kind=ports.KIND_UNAVAILABLE))

    assert reading.status == ports.KIND_UNAVAILABLE
    assert reading.items == ()
    assert reading.refusal is None


# --- The extent assertion that keeps absences from becoming refusals ---------


def test_every_published_view_still_requires_no_evidence() -> None:
    """`D1-01` section 4 -- `required_evidence` is `()` across the whole registry.

    Derived from what the registry publishes rather than from a list here, so a
    later slice that populates one entry fails this rather than silently
    converting that view's ordinary absences into `FR-141` refusals.
    """
    view_ids = registry.view_ids()
    assert view_ids, "no published views -- this guard is reading the wrong registry"

    populated = tuple(
        sorted(
            view_id
            for view_id in view_ids
            if registry.define_view(view_id).required_evidence != ()
        )
    )
    assert populated == (), (
        f"{populated} now require evidence, which makes an absent code an FR-141 "
        f"refusal cause -- ordinary evidence absences would present as refused views"
    )


# --- The package boundary that forced the injection --------------------------


def test_the_drawer_module_imports_no_rra_module() -> None:
    """`R7-01` section 3 -- a bridge inside `khepri.rca` makes every RCA test
    transitively depend on RRA, and `RCA-006`'s boundary bars it outright.

    The catalog lives in `khepri.rra.definitions`, so the drawer declares a
    Protocol and the composition root binds the adapter -- `ports.py`'s rule,
    "the consumer owns the Protocol; the composition root binds the
    implementation". Asserted here as well as by the repo-wide scan because this
    module is the one that wanted the import.
    """
    import ast
    import pathlib

    source = pathlib.Path(evidence.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)

    assert imported, "no imports parsed -- this guard is reading the wrong module"
    offenders = [name for name in imported if name.startswith("khepri.rra")]
    assert offenders == [], offenders
