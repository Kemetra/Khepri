"""#531 -- the report bundle carries the package's per-result refusals.

Authority: the owner's `#531` decision (2026-09-24, a narrow extension of
`RenderableBundle`), the `RRA-006` Requirements clause it adds, and active
`RRA-014` `FR-140` ("every source refusal ... survives projection").

`#551` found the `RRA-004` headline refusals on `FactPackage.refusals` and nowhere
on the bundle, so `MetricAvailabilityView` stated nothing about a refused gross
margin. These tests read real `ReportBundle.of(package())` output and the real
projector; the expected metric set is written out rather than derived from the
package, so a refusal the bundle drops cannot be dropped from both sides at once.
"""

from __future__ import annotations

from types import SimpleNamespace

from khepri.rca.semantic_queries import ports
from khepri.rca.semantic_queries.queries import SemanticQueryActions
from khepri.rca.workspace.decision import limits
from khepri.rra import definitions
from khepri.rra.bundle import BUNDLE_VERSION, ReportBundle
from khepri.rra.semantic_views import projection
from tests.test_issue519_semantic_view_readers import (
    _AVAILABILITY,
    _by_metric,
    _Isolation,
    _ProjectingPort,
    _real_crossversion,
    _request,
    _rows,
    _Sources,
)
from tests.test_rra006_bundle import package

_REFUSED = "required_input_unavailable"

#: What `#551` probed on the golden package, stated independently of it.
_HEADLINE_REFUSED = (
    "cost",
    "discount",
    "gross_margin",
    "gross_profit",
    "returns",
    "revenue_by_channel",
    "revenue_by_product",
    "units_by_channel",
    "units_by_product",
)

#: The subset `MetricAvailabilityView`'s metric allowlist admits.
_AVAILABILITY_REFUSED = ("cost", "discount", "gross_margin", "gross_profit", "returns")


def _real() -> ReportBundle:
    return ReportBundle.of(package())


def test_the_real_bundle_carries_every_headline_refusal() -> None:
    carried = _real().refusals

    assert tuple(sorted(refusal.metric for refusal in carried)) == _HEADLINE_REFUSED
    assert {refusal.reason for refusal in carried} == {_REFUSED}


def test_a_refused_gross_margin_is_stated_unavailable_with_its_reason() -> None:
    """The flip of `#551`'s pin: the row now exists and names why."""
    rows = _by_metric(_rows(_AVAILABILITY, _real()))

    assert rows["gross_margin"]["availability"] == definitions.UNAVAILABLE
    assert rows["gross_margin"]["reason"] == _REFUSED


def test_every_allowlisted_headline_refusal_has_a_row_and_no_other_does() -> None:
    rows = _by_metric(_rows(_AVAILABILITY, _real()))
    unavailable = tuple(
        sorted(
            metric
            for metric, row in rows.items()
            if row["availability"] == definitions.UNAVAILABLE and row["reason"] == _REFUSED
        )
    )

    assert unavailable == _AVAILABILITY_REFUSED


def test_a_source_without_refusals_is_not_a_bundle() -> None:
    """Fail closed: a missing member must refuse, never read as "none refused"."""
    real = _real()
    source = SimpleNamespace(
        identity=real.identity,
        figures=real.figures,
        caveats=real.caveats,
        evidence=real.evidence,
        sections=real.sections,
        bundle_version=real.bundle_version,
    )
    outcome = projection.project(_request(_AVAILABILITY), (source,))

    assert not outcome.admitted


def test_the_limits_surface_reports_the_refused_headline_metric() -> None:
    actions = SemanticQueryActions(_Isolation(), _Sources(), _ProjectingPort(_real()))
    reading = limits.read_limits(
        actions,
        limits.LimitsRequest(organization_id="org-1", account_id="acct-1", source_id="run-1"),
    )

    assert reading.status == ports.KIND_ADMITTED
    stated = {limit.metric: limit for limit in reading.availabilities}
    assert stated["gross_margin"].availability == definitions.UNAVAILABLE
    assert stated["gross_margin"].reason == _REFUSED


def test_the_two_population_bundle_states_no_headline_refusal() -> None:
    assert _real_crossversion().refusals == ()


def test_refusals_leave_both_documents_and_the_bundle_version_unchanged() -> None:
    """The identity already digests what the refusals derive from (`evidence`'s precedent)."""
    assert "refusals" not in _real().as_document()
    assert "refusals" not in _real_crossversion().as_document()
    assert BUNDLE_VERSION == "rra006.bundle.v8"
