"""RRA-011's RED tests: the citation route still assembles its own evidence projection.

`RRA-011`:169-170 requires a catalog route to read the projection the report surfaces
already render from, never assemble a second one. Before `RRA-013` there was no shared
per-citation projection to read; since `#355` the audit context carries one under
`evidence`, and the route's own `_cited_figure` is the second projection the rule
forbids. Every RED test here fails on this tree, strict `xfail`, and each docstring says
what it waits for.

Plan: `docs/superpowers/plans/2026-09-03-rra-011-route-reads-bundle-evidence-plan.md`.
Authority: active `RRA-011`.
"""

from __future__ import annotations

import pytest

from khepri.rra import report_api
from khepri.rra.bundle import SECTION_COMPARISON, ReportBundle
from khepri.rra.rendering.html import build_cells, build_context
from tests.test_rra011_catalog_routes import EVIDENCE, ROWS, _harness, package_for

RED = pytest.mark.xfail(strict=True, reason="RRA-011 RED: the route still assembles its own projection.")

#: The evidence fields the audit entry and the route response must agree on, exactly.
SHARED_FIELDS = ("metric", "unit_kind", "formula_version", "precision", "inputs", "definition")


def citations_by_shape() -> dict[str, str]:
    """One citation per record shape: a retained fact, a retained series, a derived figure."""
    package = package_for(ROWS, published=True)
    bundle = ReportBundle.of(package)
    retained = {record.citation_id for record in (*package.facts, *package.series, *package.comparisons)}
    shapes = {
        "fact": package.facts[0].citation_id,
        "series": package.series[0].citation_id,
        "derived": next(
            figure.citation_id
            for figure in bundle.figures
            if figure.section == SECTION_COMPARISON and figure.citation_id not in retained
        ),
    }
    return shapes


def shared_entry(citation_id: str, language: str = "en") -> dict[str, object]:
    bundle = ReportBundle.of(package_for(ROWS, published=True))
    audit = build_context(bundle, language, build_cells(bundle, language))["audit"]
    return audit["evidence"][citation_id]


@RED
@pytest.mark.parametrize("shape", ("fact", "series", "derived"))
def test_the_route_answers_from_the_bundle_evidence_entry(shape: str) -> None:
    """The route's per-figure block equals the shared projection's entry, field by field.

    RED while `_cited_figure` re-derives these values on its own: the two agree today by
    construction, so this test cannot tell them apart by output. It becomes meaningful
    together with `test_the_second_projection_is_gone`, and is kept RED with it so the
    pair land as one claim.
    """
    citation = citations_by_shape()[shape]
    client, _ = _harness()
    answer = client.get(f"{EVIDENCE}/{citation}/evidence/en")
    assert answer.status_code == 200, answer.text
    body = answer.json()
    entry = shared_entry(citation)
    for field in SHARED_FIELDS:
        assert body[field] == entry[field], f"{shape}.{field}: route {body[field]!r} != entry {entry[field]!r}"
    assert not hasattr(report_api, "_cited_figure"), "the route still has its own projection to disagree with"


@RED
def test_the_second_projection_is_gone() -> None:
    """A retired helper that survives is a helper someone will call.

    `_cited_figure`, `_stored_fact` and `_by_citation` are the second projection.
    Once the route reads the audit entry they have no caller and must not remain.
    """
    for name in ("_cited_figure", "_stored_fact", "_by_citation"):
        assert not hasattr(report_api, name), f"report_api still defines {name}"


def test_the_route_still_reads_only_the_audit_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not RED: the existing discipline, restated so a rewrite cannot loosen it.

    The handler must call `build_context` and read only `audit` from it -- the tier
    defence against `narrative_state`, which sits beside `audit` and is Internal.
    """
    seen: list[str] = []
    real = report_api.build_context

    class OnlyAudit(dict):
        def __getitem__(self, key: str) -> object:
            seen.append(key)
            return super().__getitem__(key)

    def spy(*args: object, **kwargs: object) -> OnlyAudit:
        seen.append("__called__")
        return OnlyAudit(real(*args, **kwargs))

    monkeypatch.setattr(report_api, "build_context", spy)
    client, _ = _harness()
    answer = client.get(f"{EVIDENCE}/{citations_by_shape()['fact']}/evidence/en")
    assert answer.status_code == 200
    assert set(seen) == {"__called__", "audit"}
