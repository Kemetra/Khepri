"""C1-06 authorized comparison orchestration (`RCA-005` `FR-130`--`FR-133`).

Every case runs through the real isolation door and the W1 workspace stores. A
stub store would answer any key and hide the uniform refusal `FR-130` requires.
"""

from __future__ import annotations

import asyncio
import base64
import re
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from khepri.rca.workspace.audit import (
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    OUTCOME_COMPLETED,
    OUTCOME_REFUSED,
)
from khepri.rca.workspace.comparisons import ComparisonActor, ComparisonRequest
from khepri.rra.analysis.dataset_period import CAUSE_UNORDERED_PAIR
from khepri.rra.bundle import REQUIRED_SURFACES, reconcile
from khepri.rra.rendering.excel import ExcelSurfaceRenderer, WorkbookUnavailable
from khepri.rra.rendering.html import HtmlReportRenderer
from khepri.rra.rendering.pdf import PdfReportRenderer
from khepri.runtime.shell_copy import SHELL_COPY
from khepri.runtime.shell_workspace import moment
from tests.c105_support import _Printer
from tests.c106_support import (
    compare_address,
    compare_form_address,
    comparison_actions,
    completed_pair,
    shell_with_comparisons,
)
from tests.w104_support import member
from tests.w104b_support import commercial_client, journey, submit
from tests.w107_support import deletion_service

UNFINISHED_CSV = (
    b"date,revenue,units,invoice_no,category,branch\n2026-03-02,10.00,1,INV-20,Snacks,Cairo\n"
)

EN = SHELL_COPY["en"]
AR = SHELL_COPY["ar"]
MISSING_ID = "dsv_does_not_exist"


def _actor(who) -> ComparisonActor:
    return ComparisonActor(account_id=who.account_id)


def _request(
    who, subject_id: str, baseline_id: str, extra: tuple[str, ...] = ()
) -> ComparisonRequest:
    return ComparisonRequest(
        actor=_actor(who),
        organization_id=who.organization_id,
        subject_version_id=subject_id,
        baseline_version_id=baseline_id,
        extra_version_ids=extra,
    )


def _table_counts(factory) -> dict[str, int]:
    """Every table on the engine this request path reaches -- not one prefix of one metadata.

    Review found the earlier census (`rca_workspace_*` in the RCA metadata) could not enforce
    "no row except the audit event": nine RCA tables and every `rra_` table were outside it.
    """
    with factory() as database:
        names = sorted(sa_inspect(database.get_bind()).get_table_names())
        return {
            name: int(database.scalar(text(f'SELECT count(*) FROM "{name}"')) or 0)
            for name in names
        }


def _audit_text(event) -> str:
    return "".join(
        str(part)
        for part in (
            event.event_id,
            event.owner_id,
            event.actor_account_id,
            event.action,
            event.outcome,
            event.object_kind,
            event.object_id,
        )
    )


def test_cross_organization_pair_matches_a_nonexistent_id(tmp_path) -> None:
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    pair = completed_pair(j, owner)
    foreign = completed_pair(j, stranger)
    actions = comparison_actions(j, tmp_path)
    now = j.clock()

    cross = actions.request(
        _request(owner, foreign.subject.version_id, pair.baseline.version_id), now=now
    )
    missing = actions.request(_request(owner, MISSING_ID, pair.baseline.version_id), now=now)

    assert cross == missing
    assert cross.unavailable
    assert cross.surfaces is None
    assert cross.bundle is None


def test_a_renderer_fault_is_governed_audited_once_and_leaves_no_workbook(tmp_path) -> None:
    """A fault in any renderer owes three things: the uniform unavailable outcome, exactly
    one audit event (`FR-133`), and an empty render directory (`RRA-006` §Not stored).

    Review found the surfaces rendered twice, once inside the assembler -- which turns a
    fault into an incomplete bundle -- and once outside it, unguarded, so a fault there
    escaped the request before the audit write. One pass now, inside the assembler.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)
    fault = WorkbookUnavailable("The Excel surface could not be read.")
    j.clock.advance(timedelta(minutes=1))
    before = len(j.w.audit.events_for_scope(who.owner_id))

    with patch.object(ExcelSurfaceRenderer, "render_materialized", side_effect=fault):
        outcome = actions.request(
            _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
        )

    added = j.w.audit.events_for_scope(who.owner_id)[before:]
    assert outcome.unavailable
    assert [event.action for event in added] == [ACTION_RUN_FAILED]
    assert not any(tmp_path.iterdir())


def test_a_scratch_directory_failure_is_governed_and_audited_once(tmp_path) -> None:
    """The per-request render directory can fail to allocate (the configured directory
    gone or unwritable); that is a failure to render and owes the same governed shape."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)
    j.clock.advance(timedelta(minutes=1))
    before = len(j.w.audit.events_for_scope(who.owner_id))

    with patch(
        "khepri.runtime.comparison_assembly.tempfile.mkdtemp",
        side_effect=OSError("no scratch directory"),
    ):
        outcome = actions.request(
            _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
        )

    added = j.w.audit.events_for_scope(who.owner_id)[before:]
    assert outcome.unavailable
    assert [event.action for event in added] == [ACTION_RUN_FAILED]


def test_each_surface_is_rendered_once_and_its_claim_describes_the_delivered_bytes(
    tmp_path,
) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)
    calls = {"html": 0, "pdf": 0, "excel": 0}

    def counting(name: str, original: Any) -> Any:
        def render(self: Any, bundle: Any) -> Any:
            calls[name] += 1
            return original(self, bundle)

        return render

    with (
        patch.object(
            HtmlReportRenderer, "render_html", counting("html", HtmlReportRenderer.render_html)
        ),
        patch.object(
            PdfReportRenderer, "render_pdf", counting("pdf", PdfReportRenderer.render_pdf)
        ),
        patch.object(
            ExcelSurfaceRenderer,
            "render_materialized",
            counting("excel", ExcelSurfaceRenderer.render_materialized),
        ),
    ):
        outcome = actions.request(
            _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
        )

    assert outcome.admitted
    assert calls == {"html": 1, "pdf": 1, "excel": 1}
    surfaces = outcome.surfaces
    assert surfaces is not None
    assert surfaces.claims["excel"].output_size_bytes == len(surfaces.excel)


def test_two_requests_for_one_pair_never_share_a_workbook_path(tmp_path) -> None:
    """The workbook is named by `bundle_id`, so one pair is one name; two requests for
    that pair in one process would race on it -- one request's cleanup or replace failing
    the other's read. Each request renders into a directory of its own instead."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)
    request = _request(who, pair.subject.version_id, pair.baseline.version_id)
    seen: list[Path] = []
    original = ExcelSurfaceRenderer.render

    def recording(self: ExcelSurfaceRenderer, bundle: Any) -> Any:
        seen.append(self.path_for(bundle))
        return original(self, bundle)

    with patch.object(ExcelSurfaceRenderer, "render", recording):
        first = actions.request(request, now=j.clock())
        second = actions.request(request, now=j.clock())

    assert first.admitted and second.admitted
    assert seen, "the workbook was never written"
    assert len({path.parent for path in seen}) == 2
    assert not any(tmp_path.iterdir())


class _CountingAssembly:
    """The real assembly port behind a call counter."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.calls = 0

    def unordered_refusal(self) -> Any:
        return self._inner.unordered_refusal()

    def assemble_pair(self, owner_id: str, pair: Any, *, now: Any) -> Any:
        self.calls += 1
        return self._inner.assemble_pair(owner_id, pair, now=now)


def test_a_foreign_baseline_never_reaches_the_package_loader(tmp_path) -> None:
    """Both versions are read under the caller's scope before any package is loaded.

    Mutation testing found that checking only the subject for absence survived every
    test: a foreign baseline still ended unavailable, because the assembly failed to
    find its run. Same outcome, wrong mechanism -- the isolation door is the version
    store read, and an out-of-scope baseline must never reach the package loader.
    """
    from khepri.rca.workspace.comparisons import ComparisonActions

    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    pair = completed_pair(j, owner)
    foreign = completed_pair(j, stranger)
    real = comparison_actions(j, tmp_path)
    spy = _CountingAssembly(real._assembly)
    actions = ComparisonActions(real._isolation, real._stores, spy)

    outcome = actions.request(
        _request(owner, pair.subject.version_id, foreign.baseline.version_id), now=j.clock()
    )

    assert outcome.unavailable
    assert spy.calls == 0


def test_three_ids_and_self_pair_refuse_before_any_store_read(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)
    now = j.clock()
    store = j.w.store

    with patch.object(store, "get_dataset_version", wraps=store.get_dataset_version) as spy:
        three = actions.request(
            _request(
                who,
                pair.subject.version_id,
                pair.baseline.version_id,
                extra=(pair.subject.version_id,),
            ),
            now=now,
        )
        self_pair = actions.request(
            _request(who, pair.subject.version_id, pair.subject.version_id), now=now
        )
        spy.assert_not_called()

    assert three.refused
    assert self_pair.refused
    assert three.refusal.cause == CAUSE_UNORDERED_PAIR
    assert self_pair.refusal.cause == CAUSE_UNORDERED_PAIR
    assert three.surfaces is None


def test_deleted_version_refuses_uniformly(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    deletion_service(j).delete_version(
        who.owner_id, pair.subject.version_id, actor_account_id=who.account_id, now=j.clock()
    )
    actions = comparison_actions(j, tmp_path)

    deleted = actions.request(
        _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
    )
    missing = actions.request(_request(who, MISSING_ID, pair.baseline.version_id), now=j.clock())

    assert deleted == missing
    assert deleted.unavailable


def test_admitted_pair_renders_three_surfaces_and_reconciles(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    outcome = comparison_actions(j, tmp_path).request(
        _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
    )

    assert outcome.admitted
    assert outcome.surfaces is not None
    assert set(outcome.surfaces.claims) == set(REQUIRED_SURFACES)
    assert outcome.bundle is not None
    for claim in outcome.surfaces.claims.values():
        reconcile(claim, bundle=outcome.bundle)


def test_an_admitted_request_leaves_no_workbook_on_disk(tmp_path) -> None:
    """`RRA-006` §Not stored: rendered on request, retained nowhere -- including temp.

    The workbook renderer writes a file to reach its bytes; the bytes travel in the
    outcome and the file is removed at once, so the render directory holds nothing
    between requests and a long-lived process keeps no comparison on disk.
    """
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    outcome = comparison_actions(j, tmp_path).request(
        _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
    )

    assert outcome.admitted
    assert outcome.surfaces is not None and outcome.surfaces.excel
    assert list(tmp_path.iterdir()) == []


def test_exactly_one_audit_event_per_request_in_both_outcomes(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    actions = comparison_actions(j, tmp_path)
    audit = j.w.audit
    j.clock.advance(timedelta(minutes=1))
    before = len(audit.events_for_scope(who.owner_id))

    admitted = actions.request(
        _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
    )
    j.clock.advance(timedelta(seconds=1))
    refused = actions.request(
        _request(who, pair.subject.version_id, pair.subject.version_id), now=j.clock()
    )

    events = audit.events_for_scope(who.owner_id)
    added = events[before:]
    assert admitted.admitted
    assert refused.refused
    assert len(added) == 2
    completed, failed = added
    assert completed.action == ACTION_RUN_COMPLETED
    assert completed.outcome == OUTCOME_COMPLETED
    assert completed.object_kind is None
    assert completed.object_id is None
    assert failed.action == ACTION_RUN_FAILED
    assert failed.outcome == OUTCOME_REFUSED
    assert failed.object_kind is None
    assert failed.object_id is None


def test_a_request_writes_no_row_except_the_audit_event(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    before = _table_counts(j.w.factory)

    comparison_actions(j, tmp_path).request(
        _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
    )

    after = _table_counts(j.w.factory)
    audit = "rca_workspace_audit_events"
    assert after[audit] == before[audit] + 1
    others = {name: after[name] for name in after if name != audit}
    expected = {name: before[name] for name in before if name != audit}
    assert others == expected
    # The census reaches the tables this path reads through, so a stray write there would show.
    assert "rra_fact_packages" in before and "rca_accounts" in before


def test_refusal_detail_never_reaches_the_audit_record(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    j.clock.advance(timedelta(minutes=1))
    outcome = comparison_actions(j, tmp_path).request(
        _request(who, pair.subject.version_id, pair.subject.version_id), now=j.clock()
    )
    events = j.w.audit.events_for_scope(who.owner_id)
    event = next(item for item in reversed(events) if item.object_id is None)
    recorded = _audit_text(event)

    assert outcome.refused
    assert pair.subject.version_id not in recorded
    assert pair.baseline.version_id not in recorded
    for language, wording in outcome.refusal.wording.items():
        del language
        assert wording not in recorded
    assert "unordered" not in recorded


def test_the_result_page_names_both_versions_and_links_both_passports(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    client = shell_with_comparisons(j, who, tmp_path)
    page = client.get(compare_address(who, pair.subject.version_id, pair.baseline.version_id))

    assert page.status_code == 200
    body = page.text
    assert EN["compare_subject"] in body
    assert EN["compare_baseline"] in body
    # `FR-132` names both versions the way the Passport names its data (`FR-119`): the
    # submission instant, linking to the Data entry, with the identifier in the anchor.
    for version in (pair.subject, pair.baseline):
        assert f"/data#data-{version.version_id}" in body
        assert moment(version.created_at).text in body
    assert f"/analyses/{pair.subject_run.run_id}" in body
    assert f"/analyses/{pair.baseline_run.run_id}" in body
    assert EN["compare_passport"] in body


def test_the_arabic_page_is_rtl(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    client = shell_with_comparisons(j, who, tmp_path)
    page = client.get(
        compare_address(who, pair.subject.version_id, pair.baseline.version_id, language="ar")
    )

    assert page.status_code == 200
    assert 'dir="rtl"' in page.text
    assert AR["compare_subject"] in page.text
    assert AR["compare_baseline"] in page.text
    # The offered document's own `lang` attribute is the evidence that the Arabic
    # rendering, not the English one, is what this page hands off.
    offered = _offered_html(page.text)
    assert 'lang="ar"' in offered
    assert 'lang="en"' not in offered


def _offered_html(page_text: str) -> str:
    """The HTML surface behind the page's download link, decoded."""
    found = re.search(r'href="data:text/html; charset=utf-8;base64,([^"]+)"', page_text)
    assert found is not None, "the page offers no HTML surface"
    return base64.b64decode(found.group(1)).decode("utf-8")


def test_http_cross_organization_matches_nonexistent_byte_for_byte(tmp_path) -> None:
    j = journey()
    owner = member(j.w)
    stranger = member(j.w, email="other@example.test", name="Other")
    pair = completed_pair(j, owner)
    foreign = completed_pair(j, stranger)
    client = shell_with_comparisons(j, owner, tmp_path)

    cross = client.get(compare_address(owner, foreign.subject.version_id, pair.baseline.version_id))
    missing = client.get(compare_address(owner, MISSING_ID, pair.baseline.version_id))

    assert cross.status_code == missing.status_code == 404
    assert cross.text == missing.text


def test_post_form_renders_the_same_admitted_pair(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    client = shell_with_comparisons(j, who, tmp_path)
    posted = client.post(
        compare_form_address(who),
        data={
            "subject": pair.subject.version_id,
            "baseline": pair.baseline.version_id,
        },
    )

    assert posted.status_code == 200
    assert EN["compare_subject"] in posted.text
    assert f"/analyses/{pair.subject_run.run_id}" in posted.text
    assert f"/analyses/{pair.baseline_run.run_id}" in posted.text


class _LoopRefusingPrinter:
    """Behaves as Playwright's synchronous API does: refuses to start on a thread that is
    running an asyncio event loop, and prints normally anywhere else."""

    def print_to_pdf(self, page: Any) -> bytes:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _Printer().print_to_pdf(page)
        raise RuntimeError("Sync API inside the asyncio loop")


def test_the_posted_form_renders_off_the_event_loop(tmp_path) -> None:
    """The POST handler is a coroutine; the render behind it launches Chromium through
    Playwright's synchronous API, which refuses to start on the event loop. Review found the
    admitted pair therefore came back as the uniform unavailable page from the form while the
    same pair rendered from the GET address. The render must run off the loop on both paths."""
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    client = shell_with_comparisons(j, who, tmp_path, printer=_LoopRefusingPrinter())
    data = {"subject": pair.subject.version_id, "baseline": pair.baseline.version_id}

    posted = client.post(compare_form_address(who), data=data)
    fetched = client.get(compare_address(who, pair.subject.version_id, pair.baseline.version_id))

    assert posted.status_code == fetched.status_code == 200
    assert 'lang="en"' in _offered_html(posted.text)
    assert 'lang="en"' in _offered_html(fetched.text)


def test_the_posted_form_renders_with_the_production_printer(tmp_path) -> None:
    """The same path against the printer production wires, which a fake cannot stand in for."""
    from khepri.rra.rendering.chromium import launch_chromium
    from khepri.runtime.wiring import _OnDemandPrinter

    try:
        with launch_chromium():
            pass
    except Exception as error:  # noqa: BLE001 - the pinned browser is an environment fact
        pytest.skip(f"Pinned Chromium is unavailable: {error}")
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    client = shell_with_comparisons(j, who, tmp_path, printer=_OnDemandPrinter())

    posted = client.post(
        compare_form_address(who),
        data={"subject": pair.subject.version_id, "baseline": pair.baseline.version_id},
    )

    assert posted.status_code == 200
    assert 'lang="en"' in _offered_html(posted.text)


def test_a_version_with_no_completed_run_is_uniformly_unavailable(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    client, _session = commercial_client(j, who)
    submit(client, UNFINISHED_CSV)
    unfinished = [
        version
        for version in j.w.store.dataset_versions_for_scope(who.owner_id)
        if version.version_id not in {pair.subject.version_id, pair.baseline.version_id}
    ][0]
    actions = comparison_actions(j, tmp_path)

    none = actions.request(
        _request(who, unfinished.version_id, pair.baseline.version_id), now=j.clock()
    )
    missing = actions.request(_request(who, MISSING_ID, pair.baseline.version_id), now=j.clock())

    assert none == missing
    assert none.unavailable
