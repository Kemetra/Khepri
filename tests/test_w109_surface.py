"""`W1-09`'s Overview sections (`RCA-005` `FR-128`/`FR-129`, `KHEPRI-DEC-034` §1).

Two regions on the surface `W1-05` built: Pinned, then Recent. Both render whether or not they
hold rows, unlike attention -- an empty "Pinned" tells a reader the capability exists, where an
empty "no issues" panel would be reassurance nobody asked for (blueprint §7.1).

The assertions that matter are the ones about what is *absent*: no count, no expiry claim, and a
deployment without pins rendering Overview exactly as before.
"""

from __future__ import annotations

import re

from khepri.rca.workspace.persistence import RETENTION_TOMBSTONED
from tests.test_w109_routes import shell_with_pins
from tests.w104_support import member
from tests.w104b_support import journey
from tests.w107_support import NOW, sealed_version

OVERVIEW = "/app/{language}/{organization}/overview"


def _overview(client, who, *, language: str = "en") -> str:
    response = client.get(
        OVERVIEW.format(language=language, organization=who.organization_id)
    )
    assert response.status_code == 200, response.status_code
    return response.text


class TestTheRegionsRender:
    def test_a_pinned_version_appears_under_pinned(self) -> None:
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        client = shell_with_pins(j, who)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        page = _overview(client, who)

        assert "Pinned" in page
        assert "pinned-item" in page
        assert "Nothing is pinned yet" not in page

    def test_recent_activity_appears_without_anything_being_pinned(self) -> None:
        """The two halves are independent: `FR-129`'s view reads the workspace records, so it has
        rows the moment work exists, whether or not anything was ever pinned."""
        j = journey()
        who = member(j.w)
        sealed_version(j, who, with_run=True)

        page = _overview(shell_with_pins(j, who), who)

        assert "recent-item" in page
        assert "Nothing is pinned yet" in page, "pinned is empty and says so"

    def test_both_regions_state_their_emptiness(self) -> None:
        """Rendered when empty, unlike attention. A reader who has pinned nothing should learn
        that pinning exists rather than meeting a surface that omits it."""
        j = journey()
        who = member(j.w)

        page = _overview(shell_with_pins(j, who), who)

        assert "Nothing is pinned yet" in page
        assert "No recent activity yet" in page

    def test_both_regions_render_in_arabic(self) -> None:
        """Bilingual parity (`FR-050`), asserted on the rendered page rather than on the copy
        table: a key can exist in both languages and reach no code path."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        client = shell_with_pins(j, who)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        page = _overview(client, who, language="ar")

        assert "مثبَّت" in page
        assert "الأحدث" in page

    def test_a_deleted_versions_pin_leaves_the_region(self) -> None:
        """The cascade, seen from the surface. A pin whose object ended must not keep pointing at
        it -- which is what `KHEPRI-DEC-034` §1's "the object ends" clause buys the reader."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        client = shell_with_pins(j, who)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)
        assert "pinned-item" in _overview(client, who)

        j.w.store.set_retention_state(
            version.version_id, RETENTION_TOMBSTONED, now=NOW, owner_id=who.owner_id
        )

        assert "Nothing is pinned yet" in _overview(client, who)


class TestWhatTheRegionsNeverSay:
    def test_neither_region_renders_a_count(self) -> None:
        """`KHEPRI-DEC-034` §2 refuses counting and ranking.

        Overview's own `test_overview_carries_no_figure` already asserts no digit outside a
        `<time>` across the whole page, which covers these regions too. This states the property
        for the regions specifically, so a reader of this module sees the refusal.
        """
        j = journey()
        who = member(j.w)
        version, run = sealed_version(j, who, with_run=True)
        client = shell_with_pins(j, who)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)
        j.w.store.pin(run.run_id, "analysis_run", owner_id=who.owner_id, now=NOW)

        page = _overview(client, who)

        without_time = re.sub(r"<time[^>]*>.*?</time>", "", page, flags=re.S)
        without_attrs = re.sub(r"<[^>]+>", "", without_time)
        assert not re.search(r"\d", without_attrs), "a figure reached the rendered text"

    def test_neither_region_claims_content_expires(self) -> None:
        """`KHEPRI-DEC-033` §5's caution. `W1-07b` shipped the sweep with a caller, so horizons
        are enforced -- but this slice adds no expiry claim, and the guard stays because these are
        the regions a later slice would put one in."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        client = shell_with_pins(j, who)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        page = _overview(client, who)

        for claim in ("expires", "expiry", "automatically deleted", "will be removed"):
            assert claim not in page.lower(), claim

    def test_a_deployment_without_pins_renders_overview_unchanged(self) -> None:
        """`FR-046`: a capability nobody wired is absent, not broken.

        The regions come from `services.pins`, so a shell without one must render the surface it
        rendered before this slice rather than raising on a missing field -- which is why both
        view fields default to empty tuples.
        """
        j = journey()
        who = member(j.w)
        sealed_version(j, who, with_run=True)

        page = _overview(shell_with_pins(j, who, wired=False), who)

        assert "pinned-item" not in page
        assert "recent-item" not in page

    def test_no_inline_script_or_style_reaches_the_page(self) -> None:
        """CSP unweakened, as every shell surface requires. Asserted here because two new regions
        are two new opportunities to add one."""
        j = journey()
        who = member(j.w)
        version, _ = sealed_version(j, who)
        client = shell_with_pins(j, who)
        j.w.store.pin(version.version_id, "dataset_version", owner_id=who.owner_id, now=NOW)

        page = _overview(client, who)

        assert "<script" not in page.lower()
        assert "style=" not in page.lower()
