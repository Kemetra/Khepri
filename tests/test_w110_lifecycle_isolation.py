"""`W1-10` -- the lifecycle and isolation cases (`RCA-005` `FR-127`, re-verifying `FR-109`).

`FR-127` names seven case classes -- cross-organization, expired, deleted, partial, corrupt,
restore and concurrent -- and `RCA-005`:180-181 says how each must be driven: *real requests across
two organizations*, asserting *the uniform denial byte-for-byte*.

**Why this module exists rather than more of the same.** Both halves of that sentence were already
present in the repository and had never met. The two-org HTTP tests compare a substring
(`test_w106_analysis_detail.py:349`) or only status codes (`test_w107_deletion_route.py:35`); the
one byte-for-byte comparison (`test_r802_shell_unavailable_surface.py:239`) drives stub resolvers
raising `ScopeAccessDenied` with no workspace rows beneath them. A substring assertion passes on a
refusal that has grown a distinguishing detail, and that detail is the disclosure `FR-051` forbids.

**Every case here drives a real route.** `G3-04` §2 records the risk this slice was most likely to
ship: *"testing the guard rather than the caller. A test that calls the isolation check directly
survives deletion of its call site -- drive the real route."* The four workspace entry points are
the catch-all `GET /app/{path}`, `POST .../data/{version}/delete`, `POST .../analyses`, and
`POST .../analyses/{run}/artifacts/{kind}`.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import text

from tests.w104_support import member
from tests.w104b_support import journey
from tests.w106_support import completed_run, started_run, submitted
from tests.w107_support import (
    NOW,
    delete_address,
    deletion_service,
    sealed_version,
    shell_with_deletion,
)
from tests.w110_support import (
    Denials,
    analyses_address,
    assert_uniform_denial,
    data_address,
    detail_address,
    handoff_address,
    overview_address,
    shell_across,
    shell_mis_composed,
    two_members,
)

#: Comfortably past `KHEPRI-DEC-015` §2a's twelve months, as a day offset so the fixture does
#: not restate the calendar arithmetic under test.
_THIRTEEN_MONTHS_ON = NOW + timedelta(days=396)


class TestCrossOrganization:
    """One scope may not read or act inside another, and the refusal is one refusal.

    `test_w106_analysis_detail.py:349` already drives the *detail* read across two real
    organizations, and `test_w107_deletion_route.py` drives *delete*. The surfaces and verbs
    below had no two-organization HTTP test at all, and none of the existing ones compared the
    refusal byte-for-byte.
    """

    def test_every_read_surface_refuses_another_organization_identically(self) -> None:
        """`FR-109`, `FR-127`. Overview, Data and Analyses answer one refusal.

        Byte-for-byte across all three, because a refusal that differs *per surface* tells a
        caller which surfaces exist for a scope they cannot read -- and a per-surface substring
        assertion cannot see that happen.
        """
        j = journey()
        who, other = two_members(j)
        submitted(j, who)
        shell = shell_across(j, other)

        responses = tuple(
            shell.get(address(who))
            for address in (overview_address, data_address, analyses_address)
        )

        assert_uniform_denial(
            Denials(responses, ("overview", "data", "analyses")), forbidden=(who.owner_id,)
        )

    def test_starting_an_analysis_inside_another_organization_is_the_same_refusal(self) -> None:
        """The `analyses` POST (`shell_journey_entry.py:66`) had no cross-organization test.

        A read that refuses while the *write* admits is the worse half of the pair: it does not
        disclose, it acts. Driven through the route, so dropping the check fails this test.
        """
        j = journey()
        who, other = two_members(j)
        submitted(j, who)
        shell = shell_across(j, other)

        started = shell.post(analyses_address(who), follow_redirects=False)
        read = shell.get(analyses_address(who))

        assert_uniform_denial(
            Denials((started, read), ("analyses POST", "analyses GET")),
            forbidden=(who.owner_id,),
        )
        assert j.w.store.analysis_runs_for_scope(who.owner_id) == (), (
            "the refused POST still opened a run in the scope it was refused"
        )

    def test_handing_off_another_organizations_artifact_refuses_and_sets_no_cookie(self) -> None:
        """The artifact handoff is where a refusal that leaks is most costly: the response
        carries a cookie in the success case, so a refusal that still sets one hands over the
        capability it was refusing."""
        j = journey()
        who, other = two_members(j)
        run, _job, _session = completed_run(j, who)
        shell = shell_across(j, other)

        handoff = shell.post(handoff_address(who, run.run_id, "web"), follow_redirects=False)
        read = shell.get(detail_address(who, run.run_id))

        assert_uniform_denial(
            Denials((handoff, read), ("handoff POST", "detail GET")),
            forbidden=(who.owner_id, run.run_id),
        )
        assert "set-cookie" not in handoff.headers


class TestDeletedAndRestored:
    """An ended object stays ended, and a row put back beneath the ORM does not resurrect it.

    `test_w107_restore_and_copy.py` proves this at the *store*, and says at its head that it
    writes beneath the ORM deliberately. But `FR-126`'s promise is that a restored version is not
    **readable**, and readability is a property of the surface: a store that answers `None` while
    the surface still renders the row would satisfy every existing test and break the promise.
    """

    def test_a_deleted_version_is_absent_from_the_surface_that_listed_it(self) -> None:
        """The Data surface is where a customer sees their versions; ending one must remove it
        from there, not only from a store read no customer makes."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        before = shell_across(j, who).get(data_address(who))
        assert version.version_id in before.text, "the version never reached the surface"

        deletion_service(j).delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )

        after = shell_across(j, who).get(data_address(who))
        assert after.status_code == 200
        assert version.version_id not in after.text

    def test_a_restored_version_is_still_absent_from_the_surface(self) -> None:
        """`FR-126` at the entry point. A whole-row restore from a backup is the case the
        revocation ledger exists for, and the customer-visible half of that promise is this one:
        the surface does not show it again."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        deletion_service(j).delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )

        _restore_beneath_the_orm(j, version.version_id)

        surface = shell_across(j, who).get(data_address(who))
        assert surface.status_code == 200
        assert version.version_id not in surface.text, (
            "a restored row reappeared on the surface; `FR-126` promises it is not readable"
        )

    def test_a_restored_version_is_not_readable_through_the_single_row_read(self) -> None:
        """The same promise on the path the revocation ledger actually guards.

        The listing above and this read are **different code paths**: the Data surface renders
        from `history_for_scope`, which filters on the tombstone, while `FR-126`'s ledger check
        lives in `_live_in` and decides the single-row read. Dropping the ledger half of that
        guard leaves the listing correct and makes this read resurrect the version -- measured,
        not assumed: the mutant was written and the listing assertion survived it.

        `test_w107_restore_and_copy.py:37` asserts this same read. It is repeated here because a
        promise proven only where the guard is absent is not proven, and because these two
        assertions together are what say *which* path each half of the guard covers.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        deletion_service(j).delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )

        _restore_beneath_the_orm(j, version.version_id)

        assert j.w.store.get_dataset_version(version.version_id, who.owner_id) is None, (
            "a restored row read back as live; the revocation ledger is what refuses it (`FR-126`)"
        )

    def test_deleting_a_version_this_scope_does_not_hold_is_the_uniform_refusal(self) -> None:
        """Replaces the `in (200, 303, 404)` assertion in `test_w107_deletion_route.py:87`.

        That range admits a success *and* a redirect *and* a refusal, so it passes whatever the
        route does and cannot detect a regression to a response that discloses.

        The uniform answer here is the `303` back to Data that a successful delete also gets, not
        a `404`: `shell_deletion.py:105-110` records that distinguishing the two would be the
        enumeration oracle. So this pins the redirect *and its destination*, and asserts the
        refused delete left the other organization's version intact -- a route that answered
        uniformly while still deleting would satisfy every byte comparison.
        """
        j = journey()
        who, other = two_members(j)
        theirs, _ = sealed_version(j, other)
        shell = shell_with_deletion(j, who)

        never_existed = shell.post(delete_address(who, "dsv-nobody"), follow_redirects=False)
        someone_elses = shell.post(delete_address(who, theirs.version_id), follow_redirects=False)

        assert_uniform_denial(
            Denials((never_existed, someone_elses), ("unknown version", "another scope's version")),
            forbidden=(theirs.version_id, other.owner_id),
            status=303,
        )
        assert never_existed.headers["location"] == someone_elses.headers["location"], (
            "the two causes redirect to different places, which distinguishes them"
        )
        assert j.w.store.get_dataset_version(theirs.version_id, other.owner_id) is not None, (
            "the refused delete ended another organization's version"
        )


class TestExpired:
    """A horizon that has elapsed removes the object from the surface, not only from a counter.

    `test_w107b_retention_horizons.py` proves the sweeper's counts and has no `TestClient` at all.
    A sweeper that purged rows while the surface still rendered them from a cache or a second
    table would pass every one of those tests.
    """

    def test_a_swept_audit_trail_leaves_the_surface_answering_without_it(self) -> None:
        """The sweep runs through its production verb, then the surface is read.

        Asserts the surface still *answers* -- a purge that emptied a table the surface joins
        against could turn a successful read into an error, which is a worse outcome than the
        unbounded growth the horizon exists to stop.
        """
        from khepri.rca.workspace.audit_retention import WorkspaceAuditSweeper

        j = journey()
        who = member(j.w)
        sealed_version(j, who)
        aged = _THIRTEEN_MONTHS_ON

        purged = WorkspaceAuditSweeper(j.w.audit).sweep(now=aged)

        assert purged.purged_events > 0, "nothing was aged past the horizon, so nothing is proven"
        surface = shell_across(j, who).get(overview_address(who))
        assert surface.status_code == 200


def _restore_beneath_the_orm(j, version_id: str) -> None:
    """Put a deleted row back the way a database restore would: raw, past every guard.

    The same manoeuvre `test_w107_restore_and_copy.py` uses, for the same reason -- a restore does
    not come through the application, so a test that reinstated the row through a production verb
    would be proving something no operator does.
    """
    with j.w.factory() as database:
        database.execute(
            text(
                "UPDATE rca_workspace_dataset_versions "
                "SET retention_state='active' WHERE version_id=:v"
            ),
            {"v": version_id},
        )
        database.commit()


class TestPartialAndCorrupt:
    """Incomplete and unreadable state fails closed at the surface, not at a helper.

    `test_w105_analyses_spine.py:366` covers a completed run missing a binding, and
    `test_w105_overview_and_data.py:641` covers an unknown admission outcome -- both over stub
    records. A stub proves the renderer refuses a bad value; it cannot prove the value can *reach*
    the renderer from the database, which is the path a corrupt row actually takes.
    """

    def test_a_run_that_never_settled_renders_without_claiming_a_result(self) -> None:
        """A started, unsettled run is the ordinary partial state -- the worker has not finished.

        The surface must answer and must not offer artifacts it does not have: a detail page that
        linked a report for a run with no bindings would hand the customer a dead end, and one
        that refused outright would hide a run that is legitimately in progress.
        """
        j = journey()
        who = member(j.w)
        run, _job, _session = started_run(j, who)

        detail = shell_across(j, who).get(detail_address(who, run.run_id))

        assert detail.status_code == 200, "an in-progress run is not an error"
        assert j.w.store.artifact_bindings_for_scope(who.owner_id) == ()

    def test_a_corrupt_admission_outcome_in_the_database_refuses_the_surface(self) -> None:
        """`test_w105_overview_and_data.py:641` proves the renderer refuses a bad outcome from a
        stub. This writes the bad value into the real column and drives the real read, so the
        refusal covers the whole path rather than the last step of it.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        _corrupt_admission_outcome(j, version.version_id)

        surface = shell_across(j, who).get(data_address(who))

        assert surface.status_code == 404, (
            "a corrupt row rendered instead of refusing; the surface read a value W1-04 never wrote"
        )
        assert "application/vnd.ms-excel" not in surface.text


class TestConcurrent:
    """Two operations racing on one object leave one outcome, and the loser fails closed.

    `test_w102_workspace_locks.py` asserts `"FOR UPDATE" in compiled` and
    `"run_for_update" in source` -- that the code *mentions* a lock, which survives the lock being
    taken on the wrong row or released too early. **SQLite cannot exhibit the row-lock race**, as
    that file concedes; what is asserted here is the property that holds regardless of engine:
    the second operation through the real route neither succeeds twice nor corrupts the first.
    """

    def test_deleting_the_same_version_twice_ends_it_once(self) -> None:
        """The repeat is the reachable concurrency case: a customer double-submits, or a retry
        arrives after the first completed. Both answer identically, and the second writes no
        second ending -- a cascade run twice could double-count in any evidence built on it.
        """
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        shell = shell_with_deletion(j, who)
        address = delete_address(who, version.version_id)

        first = shell.post(address, follow_redirects=False)
        second = shell.post(address, follow_redirects=False)

        assert_uniform_denial(
            Denials((first, second), ("first delete", "repeat delete")), status=303
        )
        tombstones = j.w.store.tombstones_for_scope(who.owner_id)
        for_version = [
            stone
            for stone in tombstones
            if getattr(stone, "version_id", None) == version.version_id
        ]
        assert len(for_version) == 1, "the repeat wrote a second tombstone for one ending"

    def test_a_handoff_racing_a_deletion_does_not_hand_over_ended_content(self) -> None:
        """The order that matters: content ends while a handoff is in flight. The handoff must
        not succeed on an object whose ending has been recorded -- an artifact cookie issued after
        the tombstone hands out exactly what the deletion was for.
        """
        j = journey()
        who = member(j.w)
        run, _job, _session = completed_run(j, who)
        (version,) = j.w.store.dataset_versions_for_scope(who.owner_id)
        deletion_service(j).delete_version(
            who.owner_id, version.version_id, actor_account_id=who.account_id, now=NOW
        )

        handoff = shell_across(j, who).post(
            handoff_address(who, run.run_id, "web"), follow_redirects=False
        )

        assert handoff.status_code == 404, "handed off an artifact of ended content"
        assert "set-cookie" not in handoff.headers


def _corrupt_admission_outcome(j, version_id: str) -> None:
    """Write an outcome `W1-04` never writes into the real column, past every guard.

    The column accepts any string, so a foreign or half-migrated row can hold one; raw SQL is how
    such a row comes to exist, and shaping it through a production verb would prove only that the
    verb refuses it.
    """
    with j.w.factory() as database:
        database.execute(
            text(
                "UPDATE rca_workspace_dataset_versions "
                "SET admission_outcome='not_a_real_outcome' WHERE version_id=:v"
            ),
            {"v": version_id},
        )
        database.commit()


class TestTheRoutesOwnComparison:
    """Each route's `{organization}` comparison, on the code path alone.

    Every other test here runs behind a resolver that already refuses a mismatch, so the route's
    own check never decides the outcome -- deleting it leaves all of them green. That is the
    "redundant guards need separate evidence" shape: one outcome test passes with either guard
    alone, and neither is then covered. `shell_deletion.py:88-95` states the route may not assume
    its resolver compares, so the comparison is a real guard and needs real evidence.
    """

    def test_the_deletion_route_refuses_a_foreign_organization_segment_by_itself(self) -> None:
        """`FR-042` scenario 3, with the resolver deliberately not helping.

        A permissive resolver is exactly `w105_support.StubResolver`'s behaviour, so this is the
        composition the route is actually deployed behind in most of this suite.
        """
        j = journey()
        who, other = two_members(j)
        theirs, _ = sealed_version(j, other)
        shell = shell_mis_composed(j, who)

        refused = shell.post(
            delete_address(who, theirs.version_id, organization=other.organization_id),
            follow_redirects=False,
        )

        assert refused.status_code == 404, (
            "the route deleted under an organization segment its session does not resolve to"
        )
        assert j.w.store.get_dataset_version(theirs.version_id, other.owner_id) is not None, (
            "another organization's version was ended through a foreign address segment"
        )
