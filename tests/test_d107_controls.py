"""`D1-07` -- the visible controls, and what each one actually is.

Authority: active `RCA-008` `FR-166`, plus `FR-137`/`FR-164` for the refusal
path, `FR-165` for the degraded selector, `FR-169` for retention and `FR-171`
for parity.

**The literal allowlist is asserted against the registry, for every view.**
`controls.VIEW_FILTERS` is a literal because `RCA-006` forbids `khepri.rca`
importing `khepri.rra`, which is the same trade `seam.py` makes for the version
pins and pays for the same way. The assertion loops `DECISION_VIEWS` and checks
extent as well as content: a sample test naming three views leaves the fourth
open the day somebody widens its allowlist, which is
`[[a-membership-table-needs-an-extent-assertion]]`.

**The refusal case drives the real projector.** A scripted port would answer
whatever the case scripted, so a test asserting "an unsupported filter is
refused" over a fake proves only that the fake was told to refuse. The two cases
that matter -- `period=` earns `CAUSE_UNKNOWN_FILTER`, and a supported filter
does not -- read through `projection.project` and `RRA-014`'s own registry.

**What reached which view is asserted on the port's recorded requests**, not on
rendered values. A value assertion cannot tell a filter that was routed away
from a filter that was silently dropped, which is
`[[a-batching-fix-regresses-the-single-item-caller]]` in this slice's shape.
"""

from __future__ import annotations

import re

import pytest

from khepri.rca.semantic_queries import ports
from khepri.rca.workspace.decision import controls, seam
from khepri.rra import facts
from khepri.rra.semantic_views import refusals, registry
from khepri.runtime import shell_controls, shell_decisions
from tests import d105_support as support

#: The page's own address, and the one every case here drives.
_RUN = "run-a"


def _echo_client(records: object | None = None) -> tuple[support.EchoPort, object]:
    """A client over a port that admits everything and echoes its own filters."""
    port = support.EchoPort(support.VIEW_FIELDS)
    return port, support.client(support.actions(port), records)


class TestTheAllowlistMatchesTheRegistry:
    """`FR-166` -- the literal table and what `RRA-014` actually publishes."""

    def test_every_decision_view_is_named_and_matches_its_definition(self) -> None:
        """Extent and content, for all eight, from the registry itself.

        Extent as well as content because `VIEW_FILTERS` is a mapping and a
        mapping cannot fail on a view it never names. A view added to
        `DECISION_VIEWS` without an entry here would silently offer no filters.
        """
        assert set(controls.VIEW_FILTERS) == {
            identity.view_id for identity in seam.DECISION_VIEWS
        }
        for identity in seam.DECISION_VIEWS:
            published = registry.define_view(identity.view_id).request_filter_allowlist
            assert controls.supported_by(identity) == published, identity.view_id

    def test_the_three_filter_dimensions_are_the_registry_s_own_spelling(self) -> None:
        """`store`, `product`, `category` -- spelled as `khepri.rra.facts` spells them."""
        assert controls.FILTER_STORE == facts.SEMANTIC_STORE
        assert controls.FILTER_PRODUCT == facts.SEMANTIC_PRODUCT
        assert controls.FILTER_CATEGORY == facts.SEMANTIC_CATEGORY

    def test_the_offered_dimensions_are_exactly_what_some_view_admits(self) -> None:
        """No control is offered for a dimension nothing admits, and none is missed."""
        published = {
            name
            for identity in seam.DECISION_VIEWS
            for name in registry.define_view(identity.view_id).request_filter_allowlist
        }
        assert set(controls.FILTER_DIMENSIONS) == published
        assert controls.FILTER_DIMENSIONS

    def test_no_published_view_admits_a_period_filter(self) -> None:
        """`D1-01`'s F-2, asserted against the registry rather than quoted.

        This is the finding the whole slice rests on. If a view ever admits
        `period`, the modelling this slice chose stops being the right one and
        that must fail here rather than being discovered by a reader.
        """
        for identity in seam.DECISION_VIEWS:
            admitted = registry.define_view(identity.view_id).request_filter_allowlist
            assert "period" not in admitted, identity.view_id


class TestRoutingSendsAndNeverDrops:
    """`FR-166`/`FR-137` -- each view gets what its own definition admits."""

    def test_a_store_filter_reaches_branch_performance_only(self) -> None:
        """`BranchPerformanceView` admits `store`; the other three do not."""
        port, client = _echo_client()
        client.get(f"{support.address()}?store=s-1")

        assert port.filters_for(seam.BRANCH_PERFORMANCE.view_id) == (("store", "s-1"),)
        assert port.filters_for(seam.PRODUCT_CATEGORY.view_id) == ()
        assert port.filters_for(seam.BASKET.view_id) == ()
        assert port.filters_for(seam.CONCENTRATION.view_id) == ()

    def test_a_product_filter_reaches_both_views_that_admit_it(self) -> None:
        """`ProductCategoryView` and `ConcentrationView`, and not `BasketView`.

        The case `read_surface` exists in its current shape for: S-5 is one
        surface reading two views, and one shared request would refuse Basket
        every time a reader filtered by product.
        """
        port, client = _echo_client()
        client.get(f"{support.address()}?product=p-1")

        assert port.filters_for(seam.PRODUCT_CATEGORY.view_id) == (("product", "p-1"),)
        assert port.filters_for(seam.CONCENTRATION.view_id) == (("product", "p-1"),)
        assert port.filters_for(seam.BASKET.view_id) == ()

    def test_a_category_filter_reaches_both_views_that_admit_it(self) -> None:
        """`ProductCategoryView` and `ConcentrationView`, as `product` does.

        `#507` item 5. `test_routing_is_derived_from_the_table_and_not_from_a
        _second_copy` bounds routing *above* by each view's allowlist, which a
        `routed_to` returning `()` satisfies for every view. `store` and
        `product` have positive cases that catch that; `category` had none,
        while `registry.py` admits it on these two -- so a mutant dropping
        `category` from routing passed the file.
        """
        port, client = _echo_client()
        client.get(f"{support.address()}?category=c-1")

        assert port.filters_for(seam.PRODUCT_CATEGORY.view_id) == (("category", "c-1"),)
        assert port.filters_for(seam.CONCENTRATION.view_id) == (("category", "c-1"),)
        assert port.filters_for(seam.BASKET.view_id) == ()

    def test_the_cards_views_are_never_sent_a_filter(self) -> None:
        """All three publish `request_filter_allowlist=()`; a filter would refuse them."""
        port, client = _echo_client()
        client.get(f"{support.address()}?store=s-1&product=p-1&category=c-1")

        for identity in (
            seam.EXECUTIVE_OVERVIEW,
            seam.METRIC_AVAILABILITY,
            seam.REPORT_EVIDENCE,
        ):
            assert port.filters_for(identity.view_id) == (), identity.view_id

    def test_an_unroutable_parameter_still_reaches_a_view(self) -> None:
        """The case routing could swallow, asserted on the wire.

        A parameter no view admits routes to nothing, and a page that stopped
        there would render clean and unfiltered for a request it never honored.
        It must reach a read that refuses it.
        """
        port, client = _echo_client()
        client.get(f"{support.address()}?period=2026-08")

        sent = [request.filters for request in port.requests]
        assert ("period", "2026-08") in [
            pair for filters in sent for pair in filters
        ], "an unsupported parameter was dropped instead of being refused"

    def test_selection_keeps_every_parameter_the_reader_asked_for(self) -> None:
        """`selection_from` narrows nothing; only blank members are omitted."""
        selection = controls.selection_from(
            _RUN, (("store", "s-1"), ("period", "2026-08"), ("product", ""))
        )
        assert selection.filters == (("store", "s-1"), ("period", "2026-08"))

    def test_routing_is_derived_from_the_table_and_not_from_a_second_copy(self) -> None:
        """Every routed pair is one the view's own allowlist names, for all eight."""
        selection = controls.selection_from(
            _RUN, (("store", "s"), ("product", "p"), ("category", "c"), ("period", "x"))
        )
        for identity in seam.DECISION_VIEWS:
            routed = controls.routed_to(identity, selection)
            admitted = registry.define_view(identity.view_id).request_filter_allowlist
            assert {name for name, _ in routed} <= set(admitted), identity.view_id


class TestTheGovernedRefusalIsRendered:
    """`FR-137`/`FR-164` -- the real projector, and `RRA-014`'s own wording."""

    def _real_client(self) -> object:
        """A client whose port is `RRA-014`'s actual projection."""
        from khepri.rra.semantic_views import projection

        class RealPort:
            """The published projector, over a bundle the registry admits."""

            def project(
                self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
            ) -> object:
                """Exactly what a deployed read performs."""
                return projection.project(request, sources)

        return support.client(support.actions(RealPort()))

    def test_an_unsupported_parameter_is_refused_by_the_real_projector(self) -> None:
        """`period=` earns `CAUSE_UNKNOWN_FILTER` rather than an unfiltered page.

        Asserted against the governed wording the reader is actually shown, so a
        refusal that reached the page as a bare cause code would fail here too.
        """
        wording = refusals.refusal_wording(refusals.CAUSE_UNKNOWN_FILTER)["en"]
        body = self._real_client().get(f"{support.address()}?period=2026-08").text

        assert wording in body
        assert 'data-control="unsupported"' in body

    def test_an_unfiltered_request_states_no_refusal(self) -> None:
        """The control that makes the case above mean something."""
        wording = refusals.refusal_wording(refusals.CAUSE_UNKNOWN_FILTER)["en"]
        body = self._real_client().get(support.address()).text

        assert wording not in body
        assert 'data-control="unsupported"' not in body


class TestTheSourceSelectorIsThePeriod:
    """`FR-166` -- choosing a period is choosing a `source_id`."""

    def test_completed_runs_are_offered_and_the_current_one_is_marked(self) -> None:
        """Each option re-addresses this surface; none links elsewhere."""
        records = support.StubRecords(
            (support.StubRun(_RUN), support.StubRun("run-b"))
        )
        _, client = _echo_client(records)
        body = client.get(support.address()).text

        assert f'data-source="{_RUN}"' in body
        assert 'data-source="run-b"' in body
        assert re.search(rf'data-source="{_RUN}"[^>]*data-selected="true"', body)

    def test_an_incomplete_run_is_not_offered(self) -> None:
        """`FR-166` names a **completed** run; an incomplete one can only refuse."""
        records = support.StubRecords(
            (support.StubRun(_RUN), support.StubRun("run-live", state="started"))
        )
        _, client = _echo_client(records)
        body = client.get(support.address()).text

        assert 'data-source="run-live"' not in body

    def test_the_selector_resolves_scope_through_the_existing_bridge(self) -> None:
        """`resolve_scope`'s opaque owner id, and no second scope path."""
        records = support.StubRecords((support.StubRun(_RUN),))
        _, client = _echo_client(records)
        client.get(support.address())

        assert records.scopes == ["owner-of-org-acme"]

    def test_a_records_collaborator_without_the_read_degrades_the_control_only(
        self,
    ) -> None:
        """`FR-165` -- a reader that cannot answer is not a page that fails.

        The defect the full suite found: probing for the field rather than the
        method let an `AttributeError` from a `records` object wired for other
        surfaces reach the page. A deployment is not obliged to carry every read
        this surface would like.
        """

        class RecordsWithoutRuns:
            """A record reader that serves the history surfaces and not this one."""

            def history_for_scope(self, owner_id: str) -> object:
                """The read this collaborator does carry."""
                return object()

        _, client = _echo_client(RecordsWithoutRuns())
        response = client.get(support.address())

        assert response.status_code == 200
        assert 'class="decision-no-sources"' in response.text

    def test_a_deployment_without_a_record_reader_degrades_the_control_only(self) -> None:
        """`FR-165`: the page renders with no selector rather than failing whole."""
        _, client = _echo_client(records=None)
        response = client.get(support.address())

        assert response.status_code == 200
        assert 'class="decision-no-sources"' in response.text
        assert 'data-source=' not in response.text


class TestAppliedStateStaysVisible:
    """`FR-166`/`FR-169` -- visible in the address, retained nowhere."""

    def test_the_language_switch_carries_the_applied_filters(self) -> None:
        """The regression this slice was most likely to ship.

        `surface_path` feeds the alternate-language link, and a tail without the
        query string drops every filter the moment a reader switches language.
        """
        _, client = _echo_client()
        body = client.get(f"{support.address()}?store=s-1").text

        href = re.search(r'class="frame-language"\s+href="([^"]+)"', body)
        assert href is not None
        assert href.group(1).endswith(f"/org-acme/decisions/{_RUN}?store=s-1")

    def test_the_applied_filter_is_shown_in_its_own_control(self) -> None:
        """A reader can see what is applied without reading the address."""
        _, client = _echo_client()
        body = client.get(f"{support.address()}?store=s-1").text

        assert re.search(
            r'data-filter="store".*?value="s-1"', body, re.S
        ), "the store control did not carry the applied value"

    def test_only_admitted_dimensions_get_a_control(self) -> None:
        """No control exists for a dimension no view admits, so none can be composed."""
        _, client = _echo_client()
        body = client.get(support.address()).text

        for dimension in controls.FILTER_DIMENSIONS:
            assert f'data-filter="{dimension}"' in body
        assert 'data-filter="period"' not in body
        assert 'name="period"' not in body

    def test_two_requests_retain_nothing_between_them(self) -> None:
        """`FR-169` -- no remembered filter state, per viewer or otherwise."""
        _, client = _echo_client()
        client.get(f"{support.address()}?store=s-1")
        second = client.get(support.address()).text

        assert 'value="s-1"' not in second

    def test_each_section_states_its_own_applied_request(self) -> None:
        """`FR-137`/`FR-161` -- routing means two sections can differ, so each says.

        The assertion that makes per-view routing honest: Concentration is built
        with `product` and Basket without it, and the page says so on each
        rather than stating one population for both.
        """
        _, client = _echo_client()
        body = client.get(f"{support.address()}?product=p-1").text

        sections = dict(
            re.findall(
                r'data-section="(\w+)".*?class="decision-section-filters"[^>]*>(.*?)</p>',
                body,
                re.S,
            )
        )
        assert "product=p-1" in sections[shell_decisions.SECTION_CONCENTRATION]
        assert "product=p-1" not in sections[shell_decisions.SECTION_BASKET]


class TestOrganizationIsolation:
    """`FR-042` -- the address names the surface, the session names the scope."""

    def test_another_organizations_address_is_refused_with_filters_present(self) -> None:
        """A filter on the address does not open a scope the session does not hold.

        With filters present, because that is the path this slice added and an
        isolation test over the unfiltered address would not cover it.
        """
        port, client = _echo_client(support.StubRecords((support.StubRun(_RUN),)))
        response = client.get(
            support.address().replace("org-acme", "org-other") + "?store=s-1"
        )

        # The uniform surface `FR-050` requires: one answer for every cause a
        # reader must not tell apart, so it is indistinguishable from an unknown
        # address rather than saying "wrong organization".
        assert response.status_code == 404
        assert shell_decisions.DECISION_COPY["en"]["title"] not in response.text
        assert 'data-filter="store"' not in response.text
        assert port.requests == [], "a read was performed for a scope the session lacks"


class TestLanguageParity:
    """`FR-171` -- equivalent content in both governed languages."""

    def test_both_languages_name_every_control(self) -> None:
        """Key sets compared, so a label added to one language fails here."""
        english = set(shell_controls.CONTROL_COPY["en"])
        arabic = set(shell_controls.CONTROL_COPY["ar"])
        assert english == arabic
        assert english

    @pytest.mark.parametrize("language", support.LANGUAGES)
    def test_the_controls_render_in_both_languages(self, language: str) -> None:
        """Every offered control is present whichever language the address names."""
        _, client = _echo_client(support.StubRecords((support.StubRun(_RUN),)))
        body = client.get(f"{support.address(language)}?store=s-1").text

        assert shell_controls.CONTROL_COPY[language]["controls_label"] in body
        for dimension in controls.FILTER_DIMENSIONS:
            assert f'data-filter="{dimension}"' in body
        assert 'value="s-1"' in body

    @pytest.mark.parametrize("language", support.LANGUAGES)
    def test_the_governed_refusal_is_shown_in_the_page_language(
        self, language: str
    ) -> None:
        """`FR-164`/`FR-171` -- a refusal is not dropped by either language."""
        from khepri.rra.semantic_views import projection

        class RealPort:
            """The published projector."""

            def project(
                self, request: ports.SemanticViewRequest, sources: tuple[object, ...]
            ) -> object:
                """Exactly what a deployed read performs."""
                return projection.project(request, sources)

        client = support.client(support.actions(RealPort()))
        body = client.get(f"{support.address(language)}?period=2026-08").text

        assert refusals.refusal_wording(refusals.CAUSE_UNKNOWN_FILTER)[language] in body


class TestTheSliceAddedNoRetention:
    """`FR-168`/`FR-169` -- no cache, no stored state, no extra read."""

    def test_an_ordinary_request_performs_the_seven_reads_it_always_did(self) -> None:
        """The unsupported read happens only when something unsupported was asked."""
        port, client = _echo_client()
        client.get(f"{support.address()}?store=s-1")

        assert len(port.requests) == 7

    def test_an_unsupported_parameter_costs_exactly_one_more_read(self) -> None:
        """One refusal read, and only on the request that earned it."""
        port, client = _echo_client()
        client.get(f"{support.address()}?period=2026-08")

        assert len(port.requests) == 8
