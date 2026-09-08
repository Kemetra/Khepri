"""C1-07: the Compare entry on the Analyses surface (`RCA-005` `FR-132`).

The comparison routes are C1-06's. This module asserts that a member can ask from Analyses
and that the form posts the ordered pair those routes already read.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.runtime.shell_api import SHELL_PREFIX, ShellServices, add_shell_routes
from khepri.runtime.shell_copy import SHELL_COPY
from khepri.runtime.shell_workspace import (
    CompareCandidate,
    DataReference,
    SpineRow,
    compare_candidates,
    moment,
)
from tests.c106_support import compare_form_address, completed_pair, shell_with_comparisons
from tests.test_r807_shell_quality import (
    NOW as STUB_NOW,
)
from tests.test_r807_shell_quality import (
    _StubBridge,
    _StubInvitations,
    _StubIsolation,
    _StubOrganizations,
    _StubProvenance,
    _StubRecords,
    _StubResolver,
)
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import analyses_address, completed_run

EN = SHELL_COPY["en"]
AR = SHELL_COPY["ar"]
NOW = datetime(2026, 8, 22, tzinfo=UTC)


class _FormParser(HTMLParser):
    """Collects the Compare form's action, selects, and visible option text."""

    def __init__(self) -> None:
        super().__init__()
        self.action = ""
        self.method = ""
        self.values: dict[str, list[str]] = {}
        self.selected: dict[str, str] = {}
        self.option_text: dict[str, list[str]] = {}
        self._select = ""
        self._option = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        named = dict(attrs)
        opener = {"form": self._open_form, "select": self._open_select, "option": self._open_option}
        handler = opener.get(tag)
        if handler is not None:
            handler(named)

    def _open_form(self, named: dict[str, str | None]) -> None:
        action = named.get("action") or ""
        if not action.endswith("/analyses/compare"):
            return
        self.action = action
        self.method = (named.get("method") or "").lower()

    def _open_select(self, named: dict[str, str | None]) -> None:
        self._select = named.get("name") or ""
        self.values[self._select] = []
        self.option_text[self._select] = []

    def _open_option(self, named: dict[str, str | None]) -> None:
        if not self._select:
            return
        value = named.get("value") or ""
        self.values[self._select].append(value)
        if "selected" in named:
            self.selected[self._select] = value
        self._option = value
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._option:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "option" and self._select:
            self.option_text[self._select].append("".join(self._text).strip())
            self._option = ""
        if tag == "select":
            self._select = ""


def _parse(html: str) -> _FormParser:
    parser = _FormParser()
    parser.feed(html)
    return parser


def _visible(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html)


@dataclass(frozen=True, slots=True)
class _Spec:
    """One spine row to hand the candidate helper.

    `at` is when the data was submitted and `started` when its run began: production reads
    those from two independent clocks, and a fixture that collapses them cannot say which one
    an order assertion means. `report_key` is stated rather than fixed, so the rule's treatment
    of an unreachable report is asserted instead of assumed.
    """

    version_id: str
    state_key: str | None = "run_state_completed"
    kind: str = "live"
    at: datetime = NOW
    started: datetime | None = None
    report_key: str = "report_available"


def _spine(spec: _Spec) -> SpineRow:
    submitted = moment(spec.at)
    tombstone = spec.kind == "tombstone"
    data_gone = spec.kind == "deleted_data"
    return SpineRow(
        started=moment(spec.started if spec.started is not None else spec.at),
        data=DataReference(
            submitted=submitted,
            anchor=None if data_gone else spec.version_id,
            deleted=data_gone,
        ),
        state_key=None if tombstone else spec.state_key,
        report_key=None if tombstone else spec.report_key,
        retention_key="retention_deleted" if tombstone else "retention_kept",
        deleted=submitted if tombstone else None,
        run_id=None if tombstone else f"run-{spec.version_id}",
    )


def test_compare_candidates_keep_completed_live_rows_only() -> None:
    rows = (
        _spine(_Spec("ver-new")),
        _spine(_Spec("ver-started", state_key="run_state_started")),
        _spine(_Spec("ver-failed", state_key="run_state_failed")),
    )

    found = compare_candidates(rows)

    assert found == (CompareCandidate(version_id="ver-new", submitted=moment(NOW), position=1),)


def test_compare_candidates_exclude_deleted_data() -> None:
    rows = (_spine(_Spec("ver-gone", kind="deleted_data")), _spine(_Spec("ver-live")))

    found = compare_candidates(rows)

    assert tuple(item.version_id for item in found) == ("ver-live",)


def test_compare_candidates_exclude_tombstones() -> None:
    gone = _spine(_Spec("ver-dead", kind="tombstone"))
    live = _spine(_Spec("ver-live"))

    found = compare_candidates((gone, live))

    assert tuple(item.version_id for item in found) == ("ver-live",)


def test_compare_candidates_deduplicate_by_version_id() -> None:
    first = _spine(_Spec("ver-a"))
    again = _spine(_Spec("ver-a", at=NOW - timedelta(hours=1)))

    found = compare_candidates((first, again))

    assert found == (CompareCandidate(version_id="ver-a", submitted=moment(NOW), position=1),)


def test_compare_candidates_preserve_spine_order() -> None:
    """Spine order is run-start order, which the caller has already sorted. The two clocks are
    crossed here -- the row that started later carries the earlier submission -- so an
    implementation that re-sorted on the submission instant would return the other order."""
    started_later = _spine(_Spec("ver-new", at=NOW - timedelta(hours=1), started=NOW))
    started_earlier = _spine(_Spec("ver-old", at=NOW, started=NOW - timedelta(hours=1)))

    found = compare_candidates((started_later, started_earlier))

    assert tuple(item.version_id for item in found) == ("ver-new", "ver-old")


def test_compare_candidates_keep_a_row_whose_report_is_unavailable() -> None:
    """The candidate rule is reachability-blind by design: a completed run whose report is not
    available is still a comparable entry, and the comparison itself states any refusal in its
    own governed wording rather than the entry disappearing from the form without explanation."""
    rows = (_spine(_Spec("ver-unreachable", report_key="report_unavailable")),)

    found = compare_candidates(rows)

    assert tuple(item.version_id for item in found) == ("ver-unreachable",)


class _OperandParser(HTMLParser):
    """The comparison result page's operand list: each label with the pair of ids it carries.

    A `<li>` holds one label, a Data-entry link naming a version, and a Passport link naming a
    run. Reading them together is what distinguishes a correct page from one that attached the
    baseline's run to the subject's row.
    """

    def __init__(self) -> None:
        super().__init__()
        self.operands: dict[str, tuple[str, str]] = {}
        self._label = ""
        self._version = ""
        self._run = ""
        self._in_label = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        named = dict(attrs)
        if tag == "span" and named.get("class") == "row-label":
            self._in_label = True
        if tag == "a":
            self._read_link(named)

    def _read_link(self, named: dict[str, str | None]) -> None:
        href = named.get("href") or ""
        kind = named.get("class") or ""
        if kind == "data-reference" and "#data-" in href:
            self._version = href.split("#data-", 1)[1]
        if kind == "compare-passport" and "/analyses/" in href:
            self._run = href.rsplit("/analyses/", 1)[1]

    def _wants_label(self, text: str) -> bool:
        """The first non-empty label text inside a `<li>` names the operand."""
        if not self._in_label:
            return False
        return bool(text) and not self._label

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if self._wants_label(text):
            self._label = text

    def handle_endtag(self, tag: str) -> None:
        if tag == "span":
            self._in_label = False
        if tag == "li" and self._label:
            self.operands[self._label] = (self._version, self._run)
            self._label = self._version = self._run = ""


def _operands(html: str) -> dict[str, tuple[str, str]]:
    parser = _OperandParser()
    parser.feed(html)
    return parser.operands


def test_two_entries_submitted_in_one_minute_are_distinguishable() -> None:
    """`created_at` carries no uniqueness constraint and the instant is minute-resolution, so
    two entries seconds apart share their visible text. Each option states its position too,
    which is also the list's own order -- the alternative, a navigable anchor as `DataReference`
    uses, is not open to an `<option>`, which may hold text only."""
    same_minute = NOW.replace(second=0)
    rows = (
        _spine(_Spec("ver-first", at=same_minute, started=same_minute)),
        _spine(
            _Spec(
                "ver-second",
                at=same_minute.replace(second=40),
                started=same_minute.replace(second=40),
            )
        ),
    )

    found = compare_candidates(rows)

    assert len({item.submitted.text for item in found}) == 1
    assert tuple(item.position for item in found) == (1, 2)


def test_a_completed_pair_renders_the_compare_form(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    newer, older = j.w.store.dataset_versions_for_scope(who.owner_id)
    page = shell_with_comparisons(j, who, tmp_path).get(analyses_address(who))
    form = _parse(page.text)

    assert page.status_code == 200
    assert form.method == "post"
    assert form.action == compare_form_address(who)
    assert form.values["subject"] == form.values["baseline"] == [newer.version_id, older.version_id]
    assert form.selected["subject"] == newer.version_id
    assert form.selected["baseline"] == older.version_id
    assert form.option_text["subject"] == [
        f"1. {moment(newer.created_at).text}",
        f"2. {moment(older.created_at).text}",
    ]
    assert pair.subject.version_id in form.values["subject"]
    assert pair.baseline.version_id in form.values["subject"]
    assert EN["compare_submit"] in page.text
    assert EN["compare_pick_intro"] in page.text


def test_one_completed_run_offers_no_compare_form_and_no_disabled_control(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    completed_run(j, who)
    page = shell_with_comparisons(j, who, tmp_path).get(analyses_address(who)).text

    assert 'action="' not in page or "/analyses/compare" not in page
    assert "<select" not in page
    assert "disabled" not in page.lower()
    assert EN["compare_submit"] not in page


def _unwired_analyses_page() -> str:
    """The r807 stub shape: workspace wired, `comparisons` left unset."""
    app = FastAPI()
    add_shell_routes(
        app,
        services=ShellServices(
            resolver=_StubResolver(),
            organizations=_StubOrganizations(),
            invitations=_StubInvitations(),
            records=_StubRecords(),
            isolation=_StubIsolation(),
            provenance=_StubProvenance(),
            bridge=_StubBridge(),
        ),
        clock=lambda: STUB_NOW,
    )
    client = TestClient(app, base_url="https://testserver")
    client.cookies.set(SESSION_COOKIE, "a-session-token")
    return client.get(f"{SHELL_PREFIX}/en/org-acme/analyses").text


def test_unwired_comparisons_offer_no_compare_form() -> None:
    page = _unwired_analyses_page()

    assert "/analyses/compare" not in page
    assert "<select" not in page
    assert "disabled" not in page.lower()


def test_posting_the_form_defaults_renders_the_admitted_result(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    client = shell_with_comparisons(j, who, tmp_path)
    form = _parse(client.get(analyses_address(who)).text)
    posted = client.post(
        form.action,
        data={"subject": form.selected["subject"], "baseline": form.selected["baseline"]},
    )

    assert posted.status_code == 200
    assert EN["compare_passport"] in posted.text
    # Per operand, not per page: both Passport links land in one body, so a subject/baseline
    # swap is invisible to a membership check over the whole page (review on `#411`). The
    # expectation is what the form posted -- the newest entry as subject -- which is the
    # reverse of the fixture's own field names, so a page echoing the fixture would fail here.
    runs = {run.version_id: run.run_id for run in j.w.store.analysis_runs_for_scope(who.owner_id)}
    posted_subject = form.selected["subject"]
    posted_baseline = form.selected["baseline"]
    assert {pair.subject.version_id, pair.baseline.version_id} == {posted_subject, posted_baseline}
    operands = _operands(posted.text)
    assert operands[EN["compare_subject"]] == (posted_subject, runs[posted_subject])
    assert operands[EN["compare_baseline"]] == (posted_baseline, runs[posted_baseline])


def test_arabic_labels_precede_their_controls_inside_rtl(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    completed_pair(j, who)
    page = shell_with_comparisons(j, who, tmp_path).get(analyses_address(who, language="ar")).text

    assert 'dir="rtl"' in page
    assert page.index('dir="rtl"') < page.index("<form")
    # The option text is a mixed-direction instant (digits plus a Latin "UTC"), so on an
    # RTL page its segments reorder unless the option states its own direction, as every
    # other timestamp in this template does (review on `#411`).
    for option in re.findall(r"<option [^>]*>", page):
        assert 'dir="ltr"' in option
    assert page.index('for="compare-subject"') < page.index('id="compare-subject"')
    assert page.index('for="compare-baseline"') < page.index('id="compare-baseline"')
    assert AR["compare_submit"] in page
    assert AR["compare_pick_intro"] in page


def test_version_identifiers_appear_only_as_option_values(tmp_path) -> None:
    j = journey()
    who = member(j.w)
    pair = completed_pair(j, who)
    page = shell_with_comparisons(j, who, tmp_path).get(analyses_address(who)).text
    visible = _visible(page)

    for version_id in (pair.subject.version_id, pair.baseline.version_id):
        assert f'value="{version_id}"' in page
        assert version_id not in visible
