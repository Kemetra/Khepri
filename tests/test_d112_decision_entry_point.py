"""`D1-12` — the decision surface is reachable without composing an address (`RCA-008` §Scope).

The `M4` acceptance measurement of 2026-09-16 found every decision-surface capability built,
correct and bilingual, and reachable by **nobody**: `/decisions/{source}` was linked from no
shipped surface, and its `{source}` segment needs a run identifier no surface offered for that
purpose. Clauses 3 and 4 of the `M4` exit gate failed on that alone.

**This module is the assertion whose absence let that ship.** Every existing decision test supplies
the address itself, which proves the route answers — never that a reader can arrive. These tests
navigate: they follow rendered `href`s from the Analyses destination and assert the decision
surface is among the places those links lead.

**The entry point is on the Analysis Passport, not in the frame's destination set.** Two reasons,
both recorded here because a later slice will be tempted by the nav bar. First, `shell_copy.py`
records that "design language §3.5 settles the set as Overview · Data · Analyses · Team"; editing
that set is the navigation *programme* `RCA-008` §Exclusions reserves to `U1-03`/`U1-05`/`U1-06`/
`U1-07`, while one per-run link is not. Second, the route is addressed *per run*: a destination in
the frame has no run to name and would need an invented chooser, which is new surface design. The
Passport is already about one run, so it holds the `{source}` the address needs — exactly as
`analyses.html.j2` already links each row to its Passport.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import timedelta

from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rca.session_cookie import SESSION_COOKIE
from khepri.rca.workspace.contracts import RUN_FAILED
from khepri.runtime.shell_api import SHELL_PREFIX, add_shell_routes
from tests.w104_support import member
from tests.w104b_support import (
    RETRY_DELAY,
    BrokenHandler,
    commercial_client,
    journey,
    request_report,
    submit,
)
from tests.w106_support import HTTPS, completed_run, decisions_stub, services_over, started_run

__all__: list[str] = []

_HREF = re.compile(r'href="([^"]+)"')


@dataclass(frozen=True, slots=True)
class _Reader:
    """One member's browser onto one journey's shell.

    A value object rather than more parameters: `j` and `who` travel together everywhere below,
    and threading them plus the wiring and language flags through each helper is the argument
    count CodeScene refuses. Grouping them is also the honest shape — every helper here needs
    the same reader, not four independent inputs.
    """

    j: object
    who: object
    wired: bool = True

    @property
    def client(self) -> TestClient:
        """A shell whose decision seam is present or absent, varied with `dataclasses.replace` —
        the idiom every other optional collaborator in these fixtures uses."""
        services = services_over(self.j, self.who)
        if self.wired:
            services = replace(services, decisions=decisions_stub())
        app = FastAPI()
        add_shell_routes(app, services=services, clock=self.j.clock)
        client = TestClient(app, base_url=HTTPS)
        client.cookies.set(SESSION_COOKIE, "a-session-token")
        return client

    def passport(self, run_id: str, language: str = "en") -> str:
        address = f"{SHELL_PREFIX}/{language}/{self.who.organization_id}/analyses/{run_id}"
        return self.client.get(address).text


def _links(body: str) -> tuple[str, ...]:
    return tuple(_HREF.findall(body))


def _decision_links(body: str) -> tuple[str, ...]:
    return tuple(href for href in _links(body) if "/decisions/" in href)


def test_a_reader_reaches_the_decision_surface_without_composing_an_address() -> None:
    """The `M4` clause-3 assertion: navigate, never address.

    The reader opens Analyses, follows the rendered link to the run's Passport, and finds a
    rendered link to that run's decision surface. No address in this test is built by the test —
    each is read out of the page before it.
    """
    j = journey()
    who = member(j.w, "reader@example.test")
    run, _job, _session = completed_run(j, who)
    client = _Reader(j, who).client

    spine = client.get(f"/app/en/{who.organization_id}/analyses").text
    to_passport = [href for href in _links(spine) if href.endswith(f"/analyses/{run.run_id}")]
    assert to_passport, "Analyses does not link to the run's Passport"

    passport = client.get(to_passport[0]).text
    to_decisions = _decision_links(passport)
    assert to_decisions, "the Passport offers no way to reach the decision surface"

    reached = client.get(to_decisions[0])
    assert reached.status_code == 200
    assert run.run_id in to_decisions[0]


def test_the_entry_point_is_offered_in_both_languages() -> None:
    """`FR-164`/`FR-171`: neither language drops the way in."""
    j = journey()
    who = member(j.w, "bilingual@example.test")
    run, _job, _session = completed_run(j, who)
    for language in ("en", "ar"):
        body = _Reader(j, who).passport(run.run_id, language)
        assert _decision_links(body), f"{language} drops the decision entry point"


def test_no_link_is_rendered_when_the_surface_is_unwired() -> None:
    """`FR-049`/`#382`: a link to a capability absent from the image is a dangling address.

    The decision routes are declared only when the seam is wired, so an unwired deployment must
    offer no way in rather than a link that 404s. This is the check `#382` and `#448` introduced
    after a capability passed every route test while being absent from the deployed image.
    """
    j = journey()
    who = member(j.w, "unwired@example.test")
    run, _job, _session = completed_run(j, who)
    body = _Reader(j, who, wired=False).passport(run.run_id)
    assert not _decision_links(body)


def test_an_unsettled_run_offers_no_entry_point() -> None:
    """The decision surface's `{source}` is a *completed* run (`D1-12`).

    A run the worker has not settled has no projections, so the surface could only refuse;
    offering the way in would promise a page that cannot answer. **This test exists because a
    mutant proved the guard untested**: dropping the `completed` check from
    `DetailView.source_id` left all 39 detail and entry-point tests passing, since every other
    case builds a settled run.
    """
    j = journey()
    who = member(j.w, "unsettled@example.test")
    run, _job, _session = started_run(j, who)
    assert run.completed_at is None, "this case needs a run the worker has not settled"
    body = _Reader(j, who).passport(run.run_id)
    assert not _decision_links(body)


def test_a_failed_run_offers_no_entry_point() -> None:
    """A settled run is not necessarily a *succeeded* one (`D1-12`).

    **Review on `#472` found this, and it is a real defect rather than a hypothetical.**
    `workspace_recording.fail_run` writes `RunOutcome(state=RUN_FAILED, completed_at=now)`, so a
    dead-lettered run has a non-`None` `completed_at`. Gating `source_id` on `completed is not
    None` therefore offered the way in for a run that produced no report and has no provenance —
    a link to a surface that could only refuse. The guard reads the *state*, and this test drives
    the real failure path rather than constructing the state directly.
    """
    j = journey()
    who = member(j.w, "failed@example.test")
    client, _session = commercial_client(j, who)
    submit(client)
    job_id = request_report(client)
    broken = BrokenHandler()
    for _attempt in range(3):
        j.run_job(job_id, handler=broken)
        j.clock.advance(RETRY_DELAY * 2)
    (run,) = j.w.store.analysis_runs_for_scope(who.owner_id)
    assert run.state == RUN_FAILED, "this case needs the dead-letter path to have failed the run"
    assert run.completed_at is not None, "the defect only exists because a failed run is settled"

    body = _Reader(j, who).passport(run.run_id)
    assert not _decision_links(body)


def test_the_frame_destination_set_is_unchanged() -> None:
    """The entry point adds no fifth destination (`RCA-008` §Exclusions).

    `U1` owns the navigation programme, and the settled set is Overview · Data · Analyses · Team.
    A slice that grew this set would be taking `U1`'s authority, so the guard is here rather than
    in a reviewer's memory.
    """
    j = journey()
    who = member(j.w, "frame@example.test")
    run, _job, _session = completed_run(j, who)
    body = _Reader(j, who).passport(run.run_id)
    frame = body[: body.find("</nav>")] if "</nav>" in body else body
    assert "/decisions/" not in frame, "the entry point leaked into the frame's destination set"


def test_the_entry_point_names_this_runs_own_source() -> None:
    """`FR-042`: the link carries the run the Passport is about, never another."""
    j = journey()
    one = member(j.w, "scoped-one@example.test")
    first, _job, _session = completed_run(j, one)
    j.clock.advance(timedelta(hours=1))
    # A second member in a second organization, because `completed_run` reads the scope's runs
    # expecting exactly one. Two scopes give two distinct runs without teaching the helper to
    # return a list, and they also prove the link carries *this* Passport's run rather than the
    # newest run anywhere.
    two = member(j.w, "scoped-two@example.test")
    second, _job2, _session2 = completed_run(j, two)
    assert first.run_id != second.run_id
    for who, run in ((one, first), (two, second)):
        body = _Reader(j, who).passport(run.run_id)
        links = _decision_links(body)
        assert links, "no entry point on this Passport"
        # The segment is compared **exactly**, not by containment. A mutant returning
        # `"mut_" + run_id` survives `run_id in href` — the corrupted identifier still contains
        # the real one — and the decision route answers `200` for an unknown source by design
        # (it renders the governed empty page), so status cannot catch it either.
        assert [href.rsplit("/decisions/", 1)[1] for href in links] == [run.run_id] * len(links)
