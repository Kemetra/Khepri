"""C1-06 authorized comparison orchestration (`RCA-005` `FR-130`--`FR-133`).

Every case runs through the real isolation door and the W1 workspace stores. A
stub store would answer any key and hide the uniform refusal `FR-130` requires.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import text

from khepri.rca.persistence import Base as RcaBase
from khepri.rca.workspace.audit import (
    ACTION_RUN_COMPLETED,
    ACTION_RUN_FAILED,
    OUTCOME_COMPLETED,
    OUTCOME_REFUSED,
)
from khepri.rca.workspace.comparisons import ComparisonActor, ComparisonRequest
from khepri.rra.analysis.dataset_period import CAUSE_UNORDERED_PAIR
from khepri.rra.bundle import REQUIRED_SURFACES, reconcile
from khepri.runtime.shell_copy import SHELL_COPY
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


def _workspace_counts(factory) -> dict[str, int]:
    names = sorted(name for name in RcaBase.metadata.tables if name.startswith("rca_workspace_"))
    with factory() as database:
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
    before = _workspace_counts(j.w.factory)

    comparison_actions(j, tmp_path).request(
        _request(who, pair.subject.version_id, pair.baseline.version_id), now=j.clock()
    )

    after = _workspace_counts(j.w.factory)
    audit = "rca_workspace_audit_events"
    assert after[audit] == before[audit] + 1
    others = {name: after[name] for name in after if name != audit}
    expected = {name: before[name] for name in before if name != audit}
    assert others == expected
    assert sa_inspect(j.w.factory().bind).get_table_names()


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
