"""`T1-08`: the catalog evidence surface, proved against the surface it mirrors.

`test_rra011_parity.py` already covers parity, fail-closed, and no-duplicate-truth
over the metric, definition, and quality *functions*. What could not exist until
`T1-05` is the **evidence** half of the same guarantee -- "every displayed figure
has one definition and evidence path" -- and the HTTP boundary those answers cross.

The oracle here is deliberately external. Every expectation is derived from the
already-shipped rendering path (`build_cells`, `build_context`, and the evidence
template they feed), which this slice does not write. A test whose expectation came
from the route it tests would pass against any route; these fail unless the catalog
and the report agree about one bundle.

Written flat, one question per test and no helper pyramid, because extracting
shared setup raises the module's complexity mean and every new file is held to a
CodeScene score of 10.00.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from khepri.rra import report_api
from khepri.rra.api import create_app
from khepri.rra.bundle import ReportBundle
from khepri.rra.facts import FactPackage
from khepri.rra.packages import FactPackageRecord, PackageCorrupted
from khepri.rra.persistence import Base, SqlSessionStore
from khepri.rra.rendering.html import build_cells, build_context
from khepri.rra.reports import ReportServices
from khepri.rra.sessions import InvitationService, SessionExpired
from tests.test_rra006_html_sections import ROWS, package_for

LANGUAGES = ("en", "ar")
NOW = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
QUALITY = "/api/v1/beta/catalog/quality"
EVIDENCE = "/api/v1/beta/catalog/citations"


@dataclass
class FakeReportService:
    """The catalog reads no job, so this satisfies the field and answers nothing."""

    def request_report(self, **_: object) -> object:
        raise NotImplementedError

    def get_session_job(self, **_: object) -> None:
        return None


@dataclass
class FakeBundleService:
    """Likewise: the catalog is session scoped and reads no delivery."""

    def get_session_bundle(self, **_: object) -> None:
        return None


class FakePackageReader:
    """One published package for whichever session asks.

    The package is the shared fixture's, so every expectation in this module can
    be derived from `package_for(ROWS, ...)` independently of the route.
    """

    def get_session_package(
        self,
        *,
        session_id: str,
        now: datetime,
    ) -> FactPackageRecord:
        package = package_for(ROWS, published=True)
        return FactPackageRecord(
            package_id="pkg_catalog",
            owner_id="own_catalog",
            session_id=session_id,
            profile_id="prf_catalog",
            package_version=package.package_version,
            formula_version=package.formula_version,
            mapping_version=package.mapping_version,
            profile_document_digest=package.profile_digest,
            source_sha256_hex=package.source_sha256_hex,
            package_digest=package.digest,
            row_count=package.row_count,
            created_at=now,
            document=package.as_document(),
        )


def test_the_audit_region_names_no_fact_identifier() -> None:
    """Why the evidence route is keyed on a citation rather than a fact.

    `_identity` (`facts.py:2211`) derives `fct_<digest[:24]>` and
    `cit_<digest[:12]>` from one digest, so the two are different strings for the
    same fact. `FigureCell` carries the citation and deliberately drops the fact
    identifier, so no `fact_id` reaches the audit region at all.

    A route keyed on `fact_id` could therefore only answer by reading
    `bundle.figures` itself -- a second projection assembled from the bundle,
    which `RRA-011` forbids in the same sentence that requires exactly one. This
    test pins the reason so a later slice cannot "helpfully" add the field back.
    """
    bundle = ReportBundle.of(package_for(ROWS, published=True))
    cells = build_cells(bundle, "en")

    audit = build_context(bundle, "en", cells)["audit"]

    assert {figure.fact_id for figure in bundle.figures}
    assert not any(hasattr(cell, "fact_id") for cell in audit["figures"])


def test_one_citation_answers_for_every_cell_that_quotes_it() -> None:
    """A series has one citation and many cells, so evidence groups rather than pairs.

    Measured rather than assumed: the shared fixture renders 49 figures over 22
    citations. An evidence surface that assumed one cell per citation would answer
    for the first and silently drop the rest.
    """
    bundle = ReportBundle.of(package_for(ROWS, published=True))
    cells = build_cells(bundle, "en")

    citations = {cell.citation_id for cell in cells}

    assert len(cells) > len(citations)
    assert citations == set(build_context(bundle, "en", cells)["audit"]["citations"])


def test_every_cell_carries_a_citation_the_audit_region_lists() -> None:
    """No figure is displayed whose evidence path the audit region omits.

    This is the `T1-08` acceptance clause -- "every displayed figure has one
    definition and evidence path" -- read against the citation half.
    """
    for language in LANGUAGES:
        bundle = ReportBundle.of(package_for(ROWS, published=True))
        cells = build_cells(bundle, language)
        audit = build_context(bundle, language, cells)["audit"]

        listed = set(audit["citations"])

        assert listed
        assert all(cell.citation_id in listed for cell in cells)


def test_the_audit_region_states_a_reason_for_every_refused_section() -> None:
    """A refused section is the one carrying a reason, never the one carrying a state.

    `Section.state` is Internal tier and reaches no customer surface, so the audit
    region identifies refusal by `reason is not None`. The catalog must classify
    the same way or the two surfaces disagree about which analyses were answered.
    """
    bundle = ReportBundle.of(package_for(ROWS, published=False))
    cells = build_cells(bundle, "en")

    audit = build_context(bundle, "en", cells)["audit"]

    refused = [entry for entry in audit["sections"] if entry["reason"] is not None]

    assert refused
    assert all(set(entry) == {"section_id", "reason"} for entry in audit["sections"])


def test_the_audit_region_carries_no_internal_tier_field() -> None:
    """`state` and `narrative_state` are Internal and appear on no catalog surface.

    Asserted against the projection itself rather than a response model, so it
    holds for every surface reading it -- including the ones this slice adds.
    """
    bundle = ReportBundle.of(package_for(ROWS, published=True))
    cells = build_cells(bundle, "en")

    audit = build_context(bundle, "en", cells)["audit"]

    assert "narrative_state" not in audit
    assert all("state" not in entry for entry in audit["sections"])


# --- the HTTP boundary ------------------------------------------------------
#
# Everything above characterizes the projection. Nothing above fails if a route
# assembles its own dict from the bundle instead of reading that projection --
# which is the second projection `RRA-011` forbids. These bind the two together.


def _harness() -> tuple[TestClient, str]:
    """A configured app and a consented session holding one published package."""
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    invitations = InvitationService(
        SqlSessionStore(sessionmaker(engine, expire_on_commit=False))
    )
    packages = FakePackageReader()
    app = create_app(
        service=invitations,
        clock=lambda: NOW,
        report_services=ReportServices(
            jobs=FakeReportService(),
            bundles=FakeBundleService(),
            packages=packages,
        ),
    )
    client = TestClient(app, base_url="https://testserver")
    token = invitations.issue_invitation(expires_at=NOW + timedelta(hours=1))
    client.post("/api/v1/beta/sessions/redeem", json={"token": token})
    client.post("/api/v1/beta/consent", json={"consent_version": "beta-privacy-v1"})
    return client, client.cookies["khepri_beta_session"]


def test_the_evidence_route_reads_the_shared_projection_and_no_other_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The discriminating test: the handler must *call* `build_context`, and read only `audit`.

    An output comparison cannot prove this. `_audit_region` copies the bundle's
    sections and caveats faithfully, so a handler that assembled its own dict from
    `bundle.sections` and `bundle.caveats` produces byte-identical output -- I
    checked, and every other test in this module passes against exactly that
    mutant. "Reads exactly one projection" is a claim about where the answer came
    from, not about what it contains, so it is asserted where it lives: at the
    call.

    The context is wrapped so that reading any key other than `audit` fails. That
    is the tier defence stated as a test rather than as a docstring --
    `narrative_state` sits beside `audit` at the top level and is Internal tier.
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
    citation = build_cells(ReportBundle.of(package_for(ROWS, published=True)), "en")[
        0
    ].citation_id

    answer = client.get(f"{EVIDENCE}/{citation}/evidence/en")

    assert answer.status_code == 200
    assert "__called__" in seen
    assert set(seen) == {"__called__", "audit"}


def test_the_evidence_route_reports_what_the_audit_region_holds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """And having read that projection, it reports it rather than something else.

    Paired with the test above: that one proves the handler reads `audit` and
    nothing else, this one proves what it read is what it answered. A handler
    passing both cannot have assembled a second projection, because the first
    would have caught the assembly and this one catches a divergent answer.

    The projection is emptied of its sections here, so a handler holding its own
    copy of `bundle.sections` answers with five where the projection now offers
    none.
    """
    real = report_api.build_context

    def hollowed(*args: object, **kwargs: object) -> dict:
        context = dict(real(*args, **kwargs))
        context["audit"] = {**context["audit"], "sections": []}
        return context

    monkeypatch.setattr(report_api, "build_context", hollowed)
    client, _ = _harness()
    citation = build_cells(ReportBundle.of(package_for(ROWS, published=True)), "en")[
        0
    ].citation_id

    body = client.get(f"{EVIDENCE}/{citation}/evidence/en").json()

    assert body["sections"] == []


def test_the_evidence_response_omits_the_unreproducible_keys() -> None:
    """`provenance` and `passages` are absent, not empty.

    Both depend on the narrative, which nothing persists, so a rebuilt bundle
    cannot reproduce them. Emitting either as an empty list would report "none"
    where the honest answer is "not available here".
    """
    client, _ = _harness()
    citation = build_cells(ReportBundle.of(package_for(ROWS, published=True)), "en")[
        0
    ].citation_id

    body = client.get(f"{EVIDENCE}/{citation}/evidence/en").json()

    assert "provenance" not in body
    assert "passages" not in body


def test_no_catalog_response_carries_an_internal_tier_field() -> None:
    """No `state`, and no `narrative_state`, anywhere a customer can read."""
    client, _ = _harness()
    citation = build_cells(ReportBundle.of(package_for(ROWS, published=True)), "en")[
        0
    ].citation_id

    bodies = [
        client.get(f"{EVIDENCE}/{citation}/evidence/en").json(),
        client.get(f"{QUALITY}/en").json(),
    ]

    assert all("narrative_state" not in body for body in bodies)
    assert all("state" not in entry for entry in bodies[0]["sections"])


def test_the_evidence_response_names_populations_only_on_a_basis() -> None:
    """Package-level reconciliation carries populations; no figure does.

    A `Fact` carries no population and a package retains several bases with
    different ones, so selecting one for a figure would present an inference as
    a record.
    """
    client, _ = _harness()
    citation = build_cells(ReportBundle.of(package_for(ROWS, published=True)), "en")[
        0
    ].citation_id

    body = client.get(f"{EVIDENCE}/{citation}/evidence/en").json()

    assert "population" not in body
    assert all(basis["population"] for basis in body["reconciliation"])


def test_an_unknown_code_refuses_at_every_catalog_route() -> None:
    """Fail-closed at the boundary, not merely in the function beneath it."""
    client, _ = _harness()

    answers = [
        client.get("/api/v1/beta/catalog/metrics/revenues/en"),
        client.get("/api/v1/beta/catalog/populations/sales_postd"),
        client.get("/api/v1/beta/catalog/reasons/zero_denominatr/result/en"),
        client.get("/api/v1/beta/catalog/caveats/currency_not_declard/en"),
        client.get(f"{EVIDENCE}/cit_000000000000/evidence/en"),
    ]

    assert [answer.status_code for answer in answers] == [404, 404, 404, 404, 404]


def test_a_reason_refuses_at_a_scope_it_is_not_stated_at() -> None:
    """An ungoverned scope is refused by the catalog, not by a second regex.

    The path constraint bounds the segment; `explain_reason` decides
    admissibility. One gate, so the two cannot drift.
    """
    client, _ = _harness()

    answer = client.get("/api/v1/beta/catalog/reasons/zero_denominator/footnote/en")

    assert answer.status_code == 404


def test_every_catalog_route_requires_a_beta_session() -> None:
    """Including the registry reads, which touch no store at all."""
    client, _ = _harness()
    client.cookies.clear()

    answers = [
        client.get("/api/v1/beta/catalog/metrics/revenue/en"),
        client.get("/api/v1/beta/catalog/populations/complete_sales"),
        client.get(f"{QUALITY}/en"),
        client.get(f"{EVIDENCE}/cit_000000000000/evidence/en"),
    ]

    assert all(answer.status_code == 401 for answer in answers)


def test_the_catalog_routes_are_absent_without_a_package_reader() -> None:
    """A deployment supplying no reader declares no catalog, rather than one that refuses."""
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    client = TestClient(
        create_app(
            service=InvitationService(
                SqlSessionStore(sessionmaker(engine, expire_on_commit=False))
            ),
            clock=lambda: NOW,
        ),
        base_url="https://testserver",
    )

    answer = client.get("/api/v1/beta/catalog/metrics/revenue/en")

    assert answer.status_code == 404


def test_no_catalog_response_carries_a_figure_value() -> None:
    """The catalog says what a code means, never what it measured.

    `FigureCell` carries the rendered `text` of a figure, and the evidence route
    holds a list of those cells while it works. Only `figure_id` is taken from
    them. A response carrying `text` would be an `RRA-006` report surface wearing
    the catalog's name -- and it would be a second place a number is published,
    formatted by something other than the renderer that owns formatting.
    """
    client, _ = _harness()
    bundle = ReportBundle.of(package_for(ROWS, published=True))
    cells = build_cells(bundle, "en")

    body = client.get(f"{EVIDENCE}/{cells[0].citation_id}/evidence/en").json()

    # Compared field by field rather than as a substring of the whole document:
    # a rendered figure may be "2", which occurs inside a digest by coincidence
    # and would make a substring test fail on a response carrying no figure.
    assert "text" not in body
    assert not any(isinstance(value, str) and value in {c.text for c in cells}
                   for value in body.values())


def test_an_unreadable_stored_package_refuses_rather_than_breaking() -> None:
    """A rebuild that raises reaches the caller as its governed status, not a 500.

    `rebuild_fact_package` runs inside `_found`, not after it. A document that is
    digest-consistent but structurally invalid -- a legacy shape, a field a newer
    build enumerates and an older one did not write -- raises `PackageCorrupted`
    from the rebuild itself, and that refusal has a row in `_REPORT_REFUSALS`.
    Outside the guard it escaped unhandled, which reports a refused read as a
    broken server.
    """
    client, _ = _harness()

    def unreadable(_: object) -> FactPackage:
        raise PackageCorrupted("Stored fact package is unreadable.")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(report_api, "rebuild_fact_package", unreadable)
        answer = client.get(f"{QUALITY}/en")

    assert answer.status_code == 503


def test_a_registry_read_resolves_the_session_it_claims() -> None:
    """An invented cookie is refused by the registry routes, not answered.

    These read no store, so the cookie check alone left them the one surface here
    that served content to a caller whose session was never resolved. Every
    sibling pairs that check with a store read that does the resolving; these now
    resolve through `get_session_package`, whose refusals already have governed
    statuses.
    """
    client, _ = _harness()

    def expired(_self: object, **_: object) -> FactPackageRecord:
        raise SessionExpired("Session content has expired.")

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(FakePackageReader, "get_session_package", expired)
        answers = [
            client.get("/api/v1/beta/catalog/metrics/revenue/en"),
            client.get("/api/v1/beta/catalog/populations/complete_sales"),
            client.get("/api/v1/beta/catalog/reasons/zero_denominator/result/en"),
            client.get("/api/v1/beta/catalog/caveats/currency_not_declared/en"),
        ]

    assert [answer.status_code for answer in answers] == [401, 401, 401, 401]


def test_a_registry_read_answers_a_session_that_published_nothing() -> None:
    """A definition does not depend on having published, so absence resolves.

    `get_session_package` returns `None` for a live session that has uploaded
    nothing. Treating that as a refusal would conflate "no package yet" with "no
    session" -- two different findings -- and would make the catalog unreadable
    at exactly the point in the journey where a reader most wants to know what a
    metric means.
    """
    client, _ = _harness()

    def nothing_published(_self: object, **_: object) -> None:
        return None

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(FakePackageReader, "get_session_package", nothing_published)
        answer = client.get("/api/v1/beta/catalog/metrics/revenue/en")

    assert answer.status_code == 200


def test_the_evidence_response_states_the_unit_and_precision_of_its_fact() -> None:
    """`RRA-011` puts unit kind and precision at package scope, on the `Fact`.

    Read from the package rather than the audit region, which carries neither,
    and paired with the inputs roadmap:745 names. The fact's `value` is not among
    them: the catalog says what a figure is made of, never what it measured.
    """
    client, _ = _harness()
    package = package_for(ROWS, published=True)
    citation = build_cells(ReportBundle.of(package), "en")[0].citation_id
    fact = next(
        entry
        for entry in (*package.facts, *package.series, *package.comparisons)
        if entry.citation_id == citation
    )

    body = client.get(f"{EVIDENCE}/{citation}/evidence/en").json()

    assert body["unit_kind"] == fact.unit_kind
    assert body["precision"] == fact.precision
    assert body["inputs"] == list(fact.inputs)
    assert "value" not in body


def test_the_quality_summary_says_its_refusals_in_the_readers_language() -> None:
    """The route is language-keyed, so the body must differ between languages.

    Without the governed prose beside each code the two answers would be
    byte-identical and the path segment would promise a bilingual answer the
    response did not give.
    """
    client, _ = _harness()

    english = client.get(f"{QUALITY}/en").json()
    arabic = client.get(f"{QUALITY}/ar").json()

    assert english != arabic
    assert all(entry["wording"] for entry in english["refused_results"])
    assert all(
        entry["wording"] != mirror["wording"]
        for entry, mirror in zip(
            english["refused_results"], arabic["refused_results"], strict=True
        )
    )
