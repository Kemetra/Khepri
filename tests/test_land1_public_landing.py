"""The public product landing surface (`LAND1-01`, RCA-004).

Each test names the requirement it holds. The landing's risk is not that it renders badly — it is
that it quietly claims authority it does not have: a CTA to a destination nobody authorized, a
second copy of governed vocabulary, a link to an unpublished legal page, or a second marketing
surface appearing without a specification.
"""

from __future__ import annotations

import re
from importlib.resources import files

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from khepri.rra.rendering.fonts import load_report_fonts
from khepri.rra.rendering.wording import (
    caveat_message,
    metric_business_name,
    refusal_message,
)
from khepri.runtime.landing_api import (
    LANDING_PAGES,
    LANDING_PREFIX,
    SPECIMEN_AVERAGE_ORDER_VALUE,
    SPECIMEN_REVENUE,
    SPECIMEN_ROWS,
    SPECIMEN_TRANSACTIONS,
    add_landing_routes,
    legal_links,
    specimen,
    specimen_caveat,
    specimen_refusal,
)
from khepri.runtime.landing_copy import LANDING_COPY, LANDING_DIRECTIONS
from khepri.runtime.legal_api import LEGAL_PAGES, add_legal_routes, published_pages

LANGUAGES = ("en", "ar")


def build_client() -> TestClient:
    """The landing beside the legal surface it links into, and nothing else."""
    app = FastAPI()
    add_legal_routes(app)
    add_landing_routes(app)
    return TestClient(app)


@pytest.fixture(name="client")
def client_fixture() -> TestClient:
    return build_client()


# ---- FR-081: exactly one public marketing surface ------------------------------------------


def test_the_landing_inventory_is_limited_to_the_one_authorized_surface() -> None:
    """`FR-081` authorizes exactly one marketing surface; a second is a specification change.

    Nothing else enforces this. `RCA-003`'s closed-set guard is scoped to `LEGAL_PAGES`, which
    `FR-086` forbids the landing from joining, and the runtime wiring test asserts a subset, so
    an extra public page would pass both.
    """
    assert frozenset({"index"}) == LANDING_PAGES


def test_the_landing_serves_one_page_per_language_and_nothing_else(client: TestClient) -> None:
    """The route set is the language set — no second marketing destination hides behind it."""
    paths = {
        route.path
        for route in client.app.routes
        if getattr(route, "path", "").startswith(LANDING_PREFIX)
    }
    assert paths == {f"{LANDING_PREFIX}/{{language}}", f"{LANDING_PREFIX}/assets/{{name}}"}


# ---- FR-082: bilingual, first-class, server-computed ---------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_language_answers_publicly_without_authentication(
    client: TestClient, language: str
) -> None:
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert response.status_code == 200


@pytest.mark.parametrize(("language", "direction"), sorted(LANDING_DIRECTIONS.items()))
def test_language_and_direction_are_server_computed(
    client: TestClient, language: str, direction: str
) -> None:
    """`lang` and `dir` are rendered by the server, never inferred by the document."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert f'<html lang="{language}" dir="{direction}">' in response.text


def test_an_unsupported_language_is_refused_rather_than_partly_rendered(
    client: TestClient,
) -> None:
    """Ambiguity fails closed: a language with no copy never renders a half-translated page."""
    assert client.get(f"{LANDING_PREFIX}/fr").status_code == 404


@pytest.mark.parametrize("language", LANGUAGES)
def test_each_language_reaches_the_other(client: TestClient, language: str) -> None:
    """Neither language is a dead end, so neither is the secondary one."""
    alternate = "ar" if language == "en" else "en"
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert f'href="{LANDING_PREFIX}/{alternate}"' in response.text


def test_the_two_languages_carry_the_same_marketing_keys() -> None:
    """Copy parity, asserted here as well as at import so the failure names this surface."""
    assert set(LANDING_COPY["en"]) == set(LANDING_COPY["ar"])


def test_the_template_and_the_copy_module_agree() -> None:
    """Every key the template reads exists, and every key that exists is read.

    `StrictUndefined` already turns a missing key into a render failure, but only for the branch
    that renders it. This states the whole relationship at once, and catches the opposite drift —
    copy kept alive after the markup that used it was removed, which is how a page ends up
    maintaining prose no visitor ever sees.
    """
    template = (
        files("khepri.runtime")
        .joinpath("landing_templates", "landing.html.j2")
        .read_text(encoding="utf-8")
    )
    used = set(re.findall(r"copy\.([a-z_0-9]+)", template))
    assert used - set(LANDING_COPY["en"]) == set(), "template reads a key the copy lacks"
    assert set(LANDING_COPY["en"]) - used == set(), "copy carries a key no template renders"


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_marketing_string_is_blank_in_either_language(language: str) -> None:
    """A key present in both languages but empty in one is a gap parity alone cannot see."""
    blank = sorted(key for key, value in LANDING_COPY[language].items() if not value.strip())
    assert blank == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_stylesheet_uses_no_physical_directional_property(language: str) -> None:
    """Zero physical directional properties is a verified property of every shipped sheet."""
    css = build_client().get(f"{LANDING_PREFIX}/assets/landing.css").text
    body = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    physical = re.findall(
        r"(?<![-\w])(?:margin|padding|border)-(?:left|right)\b"
        r"|(?<![-\w])text-align\s*:\s*(?:left|right)\b"
        r"|(?<![-\w])float\s*:\s*(?:left|right)\b",
        body,
    )
    assert physical == []


# ---- FR-084: synthetic data, labelled ------------------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_specimen_is_labelled_synthetic(client: TestClient, language: str) -> None:
    """`FR-084`: demonstration data must never read as customer evidence."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert LANDING_COPY[language]["specimen_caption"] in response.text


def test_the_specimen_satisfies_the_products_own_arithmetic() -> None:
    """A synthetic specimen must be producible, not merely plausible.

    `facts` counts transactions distinct over eligible rows, so the count cannot exceed the row
    count, and average order value is revenue over that count. An earlier draft showed 61,244
    sales from a 41,905-row export: every figure was individually believable and the set was
    arithmetically impossible. No vocabulary guard could catch it, because each value is only
    wrong in relation to the others.
    """
    assert SPECIMEN_TRANSACTIONS <= SPECIMEN_ROWS
    assert pytest.approx(SPECIMEN_AVERAGE_ORDER_VALUE, abs=0.01) == (
        SPECIMEN_REVENUE / SPECIMEN_TRANSACTIONS
    )


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_rendered_specimen_shows_those_numbers(client: TestClient, language: str) -> None:
    """The checked constants are the ones the page prints, not a parallel set beside them."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    digits = "٠١٢٣٤٥٦٧٨٩" if language == "ar" else "0123456789"

    def localized(value: int) -> str:
        grouping = "٬" if language == "ar" else ","
        return f"{value:,}".replace(",", grouping).translate(
            str.maketrans("0123456789", digits)
        )

    assert localized(SPECIMEN_TRANSACTIONS) in response.text
    assert localized(SPECIMEN_ROWS) in response.text


def test_the_print_ground_resets_every_ink_it_inverts() -> None:
    """Flipping to a white ground inverts every contrast, so every ink must be re-stated.

    `--papyrus-dim` computes to about 2.65:1 on white and gold to about 2.22:1. Resetting only
    the brightest three left the caveat detail, the verdict names and the synthetic note below
    the floor on paper while they looked correct on screen.
    """
    body = _without_comments(_stylesheet())
    start = body.index("@media print")
    depth, index = 0, body.index("{", start)
    open_at = index
    while index < len(body):
        depth += (body[index] == "{") - (body[index] == "}")
        index += 1
        if depth == 0:
            break
    block = body[open_at + 1 : index - 1]

    # Every ink is redefined at the token, so no selector can be forgotten and none can be
    # outranked. Listing selectors by hand left seventeen failures behind: a print block gets no
    # specificity bonus, so `.verdict--withheld .verdict-claim` beat a flat `.verdict-claim`.
    for token in ("--papyrus", "--papyrus-dim", "--withheld", "--gold", "--egyptian-blue"):
        assert re.search(rf"{token}\s*:", block), f"{token} keeps its screen value on paper"

    # And every painted ground is cleared, including the header's literal colour.
    assert ".site-header" in block


# ---- FR-085: one source for governed vocabulary --------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_specimen_names_metrics_from_the_governed_catalog(
    client: TestClient, language: str
) -> None:
    """The metric names rendered are the catalog's, so a rename reaches the page."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    for course in specimen(language):
        assert course["term"] in response.text


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_specimen_metric_names_are_not_retyped(language: str) -> None:
    """Each rendered term equals `metric_business_name`, not a landing-authored string."""
    rendered = {course["term"] for course in specimen(language)}
    governed = {
        metric_business_name(code, language)
        for code in ("revenue", "transactions", "average_order_value")
    }
    assert rendered == governed


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_refusal_is_the_governed_wording(client: TestClient, language: str) -> None:
    """`FR-085`: the landing may not state a refusal the product would not state."""
    governed = refusal_message("prior_window_absent", context="section", language=language)
    assert specimen_refusal(language) == governed
    assert governed in client.get(f"{LANDING_PREFIX}/{language}").text


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_caveat_is_the_governed_wording(client: TestClient, language: str) -> None:
    """A caveat the landing shows must be one the product can actually emit.

    An earlier draft narrated a missing-category caveat. The runtime refuses an incomplete
    dimension with `dimension_values_incomplete` rather than caveating it, and no such caveat
    code exists — so the page advertised behavior the product does not have and defined a caveat
    meaning of its own. Reading the text from the catalog makes both failures impossible.
    """
    governed = caveat_message("rows_without_time_field_excluded", language)
    assert specimen_caveat(language) == governed
    assert governed in client.get(f"{LANDING_PREFIX}/{language}").text


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_bilingual_panel_names_the_metric_from_the_catalog(
    client: TestClient, language: str
) -> None:
    """Both panels label a displayed figure, so both names come from the catalog.

    The panels render in both scripts on both pages, so each is checked in its own script rather
    than in the page's language.
    """
    response = client.get(f"{LANDING_PREFIX}/{language}")
    for script in LANGUAGES:
        assert metric_business_name("revenue", script) in response.text


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_landing_copy_holds_no_second_copy_of_the_governed_caveat(language: str) -> None:
    """The caveat, like the refusal, has exactly one source."""
    governed = caveat_message("rows_without_time_field_excluded", language)
    assert governed not in "\n".join(LANDING_COPY[language].values())


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_landing_copy_holds_no_second_copy_of_the_governed_refusal(language: str) -> None:
    """A duplicate manually maintained truth is what `FR-085` forbids; this is its shape."""
    governed = refusal_message("prior_window_absent", context="section", language=language)
    assert governed not in "\n".join(LANDING_COPY[language].values())


# ---- FR-086: link only to legal destinations that publish ----------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_footer_legal_link_answers_successfully(
    client: TestClient, language: str
) -> None:
    """Liveness, asserted against the runtime rather than against a second hardcoded list.

    Comparing two lists to each other passes when a page is absent from both. Requesting each
    rendered link fails loudly if a destination regresses to unpublished, and stays correct when
    a currently unpublished page later publishes.
    """
    links = legal_links(language)
    assert links, "the landing renders no legal link at all"
    for link in links:
        assert client.get(link["href"]).status_code == 200


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_landing_links_no_unpublished_legal_destination(
    client: TestClient, language: str
) -> None:
    """An unpublished page answers 503; linking one would publish a dead destination."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    published = {page for page, _ in published_pages(language)}
    for page in LEGAL_PAGES - published:
        assert f"/legal/{language}/{page}" not in response.text


def test_the_landing_did_not_join_the_closed_legal_inventory() -> None:
    """`FR-086`: the landing must not enter `RCA-003`'s closed legal/trust inventory."""
    assert "index" not in LEGAL_PAGES
    assert LANDING_PAGES.isdisjoint(LEGAL_PAGES)


# ---- FR-087 / FR-088: no CTA without an authorized destination -----------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_call_to_action_renders(client: TestClient, language: str) -> None:
    """`FR-087` permits a CTA only where its destination already exists. None does.

    `contact-us` is unpublished, `/beta` is the invitation-gated private journey, and RCA-001
    and RCA-002 both exclude public self-serve signup. `FR-088` forbids a dead, disabled, or
    invented destination, so the page closes on its thesis instead.
    """
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert "<button" not in response.text
    assert 'class="button' not in response.text


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_landing_offers_no_signup_or_beta_destination(
    client: TestClient, language: str
) -> None:
    """No public signup, and no hand-off into the private beta from a public page."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert "/beta" not in response.text
    assert "mailto:" not in response.text
    for forbidden in ("sign up", "signup", "register now", "free trial", "coming soon"):
        assert forbidden not in response.text.lower()


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_link_is_a_destination_that_answers(client: TestClient, language: str) -> None:
    """No dead or invented href reaches the visitor, whatever its label."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    for href in set(re.findall(r'href="([^"]+)"', response.text)):
        if href.startswith("#"):
            assert href == "#main"
            assert f'id="{href[1:]}"' in response.text
            continue
        assert href.startswith("/"), f"external destination on a public page: {href}"
        assert client.get(href).status_code == 200


# ---- FR-089 / FR-090: presentation and security ---------------------------------------------


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_reaches_content_by_keyboard(client: TestClient, language: str) -> None:
    """A skip link is the first tab stop and reaches the main landmark."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert LANDING_COPY[language]["skip"] in response.text
    assert 'href="#main"' in response.text
    assert 'id="main"' in response.text


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_carries_one_first_level_heading(client: TestClient, language: str) -> None:
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert len(re.findall(r"<h1\b", response.text)) == 1


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_declares_its_landmarks(client: TestClient, language: str) -> None:
    response = client.get(f"{LANDING_PREFIX}/{language}")
    for landmark in ("<header", "<main", "<footer", "<nav"):
        assert landmark in response.text


def _stylesheet() -> str:
    return build_client().get(f"{LANDING_PREFIX}/assets/landing.css").text


def _without_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _keyframes(css: str) -> dict[str, str]:
    """Every `@keyframes` body, matched by counting braces rather than by a regex.

    A non-greedy `\\{(.+?)\\}` stops at the first inner `}` — the end of the first step — so the
    captured body never contains a complete step block and any search inside it finds nothing.
    That silently turns a guard into a test that cannot fail, which is how the first version of
    `test_no_animation_starts_from_invisible_content` passed against a deliberately broken
    stylesheet.
    """
    blocks: dict[str, str] = {}
    for match in re.finditer(r"@keyframes\s+([\w-]+)\s*\{", css):
        depth, index = 1, match.end()
        while index < len(css) and depth:
            depth += (css[index] == "{") - (css[index] == "}")
            index += 1
        blocks[match.group(1)] = css[match.end() : index - 1]
    return blocks


def test_the_keyframe_reader_sees_whole_blocks() -> None:
    """The helper the motion guards depend on must actually parse a step.

    Without this, a parsing bug makes every motion assertion below vacuously true.
    """
    blocks = _keyframes(_without_comments(_stylesheet()))
    assert blocks, "no keyframes parsed at all"
    assert "opacity" in blocks["value-arrives"]
    assert re.search(r"(?:from|0%)\s*\{[^}]*\}", blocks["value-arrives"])


def _relative_luminance(value: str) -> float:
    channels = (int(value[index : index + 2], 16) / 255 for index in (1, 3, 5))
    linear = [
        channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(foreground: str, background: str) -> float:
    first, second = _relative_luminance(foreground), _relative_luminance(background)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


def _tokens() -> dict[str, str]:
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\s*;", _stylesheet()))


@pytest.mark.parametrize(
    "token",
    (
        "--papyrus",
        "--papyrus-dim",
        "--withheld",
        "--gold",
        "--egyptian-blue",
        "--egyptian-blue-dim",
    ),
)
def test_every_ink_clears_wcag_on_every_ground_it_is_drawn_on(token: str) -> None:
    """Contrast is computed here, not asserted in a comment.

    `--egyptian-blue-dim` shipped at #2c6a87 in the concept and cleared 3:1 on none of the three
    grounds while carrying 11.2px numerals. A colour judged against the page ground and then set
    on a lifted register is the recurring failure in this palette, so every ink is checked against
    every ground rather than against the one it was designed on.
    """
    tokens = _tokens()
    for ground in ("--stone-900", "--stone-800", "--stone-700"):
        ratio = _contrast(tokens[token], tokens[ground])
        assert ratio >= 4.5, f"{token} on {ground} is {ratio:.2f}:1"


def test_the_stylesheet_honours_reduced_motion() -> None:
    """Motion is gated by a real block, not by the phrase appearing in a comment.

    The concept's grammar is double-gated — `@supports` and `prefers-reduced-motion` — and the
    un-animated state is the finished one. This asserts the guard block exists in the cascade and
    carries declarations, so a future edit cannot leave the comment while dropping the rule.
    """
    body = _without_comments(_stylesheet())
    blocks = re.findall(
        r"@media[^{]*prefers-reduced-motion:\s*reduce[^{]*\{(.+?\})\s*\}", body, flags=re.DOTALL
    )
    assert blocks, "no prefers-reduced-motion block survives outside comments"
    assert any("animation" in block or "scroll-behavior" in block for block in blocks)


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_admission_sequence_covers_every_course_it_staggers(language: str) -> None:
    """The load animation's stagger is written per course; the courses come from Python.

    `.specimen .course:nth-of-type(n)` carries one delay per value-bearing course. The specimen's
    length is now data — a metric added to `_SPECIMEN_COURSES` would render a course with no
    delay, which animates at 0ms and breaks the one sequence the page's argument depends on. This
    ties the two together so the omission fails here rather than on the page.
    """
    html = build_client().get(f"{LANDING_PREFIX}/{language}").text
    value_courses = len(re.findall(r'class="course"', html))
    delays = set(
        int(index)
        for index in re.findall(
            r"\.specimen \.course:nth-of-type\((\d+)\) \.course-value", _stylesheet()
        )
    )
    assert delays == set(range(1, value_courses + 1))


def test_the_withheld_course_is_the_last_course_rendered() -> None:
    """The refusal settles last because it is the considered outcome, not the quick one.

    Its animation delay (1700ms) assumes it follows every resolving figure. If the withheld course
    stopped being last, the refusal would land mid-sequence and the argument would misread.
    """
    html = build_client().get(f"{LANDING_PREFIX}/en").text
    courses = re.findall(r'class="(course(?: course--withheld)?)"', html)
    assert courses[-1] == "course course--withheld"
    assert courses.count("course course--withheld") == 1


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_reads_correctly_with_no_animation(language: str) -> None:
    """Content is correct at frame zero: no meaning is carried only by motion.

    Every animated rule animates `transform`, `opacity`, or `color`. Nothing is hidden waiting for
    a scroll or a timeline that may never fire, so a client with no view-timeline support, no
    animation, or reduced motion sees the finished page.
    """
    body = _without_comments(_stylesheet())

    # Nothing is hidden while waiting to be animated in. A decorative rule may still be dropped
    # for print, which is why this looks inside the motion blocks rather than the whole sheet.
    for block in re.findall(
        r"@media[^{]*prefers-reduced-motion:\s*no-preference[^{]*\{(.+?\})\s*\}",
        body,
        flags=re.DOTALL,
    ):
        assert "display: none" not in block
        assert "visibility: hidden" not in block

    # Every keyframe moves only compositable, non-layout properties.
    for frames in _keyframes(body).values():
        animated = set(re.findall(r"([a-z-]+)\s*:", frames))
        assert animated <= {"opacity", "transform", "color", "content"}


def test_no_animation_starts_from_invisible_content() -> None:
    """Content is legible in every frame, including frame zero — the delayed ones especially.

    The sequence staggers courses by up to 1.7s, and `animation-fill-mode: both` pins an element
    to its opening keyframe for the whole delay. A keyframe opening at `opacity: 0` therefore
    blanks that content for over a second on the animated path — invisible to a reduced-motion
    check (no animation runs) and to a contrast check (the computed colour is set). It shipped in
    the concept behind a comment asserting the opposite, and a screenshot is what found it.

    A decorative pseudo-element may still start at zero: it carries no content.
    """
    offenders = []
    for name, frames in _keyframes(_without_comments(_stylesheet())).items():
        if name in {"rule-open", "claim-underlines"}:
            continue  # decorative rules that draw themselves open; they carry no state
        # A transform-only keyframe that carries a STATE shape is checked too. The withheld
        # rule replaces a border the motion block sets transparent, so opening it at zero
        # removes the disclosure shape entirely for the length of its delay.
        if name == "withheld-rule-cuts":
            opening = re.search(r"(?:from|0%)\s*\{([^}]*)\}", frames)
            assert opening, "withheld-rule-cuts: no opening step parsed"
            scale = re.search(r"scaleY\(([\d.]+)\)", opening.group(1))
            assert scale and float(scale.group(1)) >= 0.3, (
                "the withheld state carrier opens invisible: " + opening.group(1).strip()
            )
            continue
        opening = re.search(r"(?:from|0%)\s*\{([^}]*)\}", frames)
        assert opening, f"{name}: no opening step parsed — the guard would be vacuous"
        opacity = re.search(r"opacity\s*:\s*([\d.]+)", opening.group(1))
        if opacity and float(opacity.group(1)) < 0.4:
            offenders.append(f"{name} opens at opacity {opacity.group(1)}")
    assert offenders == []


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_class_the_page_renders_is_styled(language: str) -> None:
    """No rendered element falls back to unstyled default text.

    The stylesheet began as a concept for a page whose markup differed from the shipped template.
    Nothing else asserts the two still agree, so a class renamed in the template — or a new one
    added without a rule — would silently ship as unstyled prose. That matters most for the
    refusal, which is the page's whole argument and must not read as plain body copy.

    The reverse direction is deliberately not asserted: an unused selector is a lint concern, and
    several rules exist only inside a media query.
    """
    response = build_client().get(f"{LANDING_PREFIX}/{language}")
    rendered = {
        name
        for attribute in re.findall(r'class="([^"]+)"', response.text)
        for name in attribute.split()
    }
    styled = set(re.findall(r"\.([A-Za-z][\w-]*)", _without_comments(_stylesheet())))
    assert rendered - styled == set()


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_page_introduces_no_third_party_or_inline_asset(
    client: TestClient, language: str
) -> None:
    """`FR-090`: bundled assets only, and nothing the public CSP would refuse to load."""
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert "<script" not in response.text
    assert "<style" not in response.text
    assert "style=" not in response.text
    assert "http://" not in response.text
    assert "https://" not in response.text


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_public_response_carries_the_security_headers(
    client: TestClient, language: str
) -> None:
    response = client.get(f"{LANDING_PREFIX}/{language}")
    assert response.headers["Content-Security-Policy"].startswith("default-src 'none'")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_landing_holds_no_customer_context(client: TestClient, language: str) -> None:
    """A public surface sets no cookie and returns the same bytes to everyone."""
    client.cookies.set("khepri_session", "a-session-that-must-not-matter")
    first = client.get(f"{LANDING_PREFIX}/{language}")
    client.cookies.clear()
    second = client.get(f"{LANDING_PREFIX}/{language}")
    assert first.text == second.text
    assert "set-cookie" not in {header.lower() for header in first.headers}


# ---- Assets ---------------------------------------------------------------------------------


def test_the_stylesheet_is_served(client: TestClient) -> None:
    response = client.get(f"{LANDING_PREFIX}/assets/landing.css")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/css")


@pytest.mark.parametrize("face", [face.file_name for face in load_report_fonts()])
def test_each_bundled_face_is_served_from_the_audited_loader(
    client: TestClient, face: str
) -> None:
    """The landing serves the audited bytes rather than a second copy of the faces."""
    expected = {item.file_name: item.payload for item in load_report_fonts()}[face]
    response = client.get(f"{LANDING_PREFIX}/assets/{face}")
    assert response.status_code == 200
    assert response.content == expected


def test_an_unknown_asset_is_refused(client: TestClient) -> None:
    """The asset route is an exact allowlist, not a directory."""
    assert client.get(f"{LANDING_PREFIX}/assets/unknown.css").status_code == 404


@pytest.mark.parametrize("path", ("../legal_copy.py", "..%2Flegal_copy.py"))
def test_the_asset_route_does_not_traverse(client: TestClient, path: str) -> None:
    assert client.get(f"{LANDING_PREFIX}/assets/{path}").status_code in {307, 404}
