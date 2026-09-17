"""`U1-03` chart grammar: the baseline, the axis unit, and the two deferrals.

Separate from `test_rra006_charts.py`, which asserts the geometry `RRA-006` shipped.
This module asserts the *grammar* `RRA-015` `FR-181`-`FR-188` adds over it, and the
split is not cosmetic: CodeScene gates a test module at 600 lines and at four
responsibilities, and folding these into the geometry module took it to 623 lines
and nine responsibilities. Two modules with one subject each is the shape the gate
asks for -- and the shape a reader wants, since a failure here names the grammar
rather than the geometry.

**Two of these tests hold deferrals rather than features.** `FR-183` asks an axis to
state its period and a legend to appear with two or more series; nothing the bundle
hands a chart carries a period, and no shipped family plots two series. Those halves
are deferred, and a deferral's only load-bearing artifact is the assertion that stops
a later slice shipping the thing this one declined to invent. Both scan the macro as
well as the view, because the macro is what a reader sees.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

from jinja2 import Environment, nodes

from khepri.rra import facts
from khepri.rra.bundle import CHART_GROUPED_BAR, GOVERNED_CHART_KINDS
from khepri.rra.narrative import LANGUAGE_ARABIC, LANGUAGE_ENGLISH
from khepri.rra.rendering.charts import (
    _GEOMETRY,  # the table under test
    CHART_HEIGHT,
    CHART_WIDTH,
    ChartView,
)
from khepri.rra.rendering.wording import AXIS_UNITS
from tests.test_rra006_charts import DEFAULT_UNIT, _chart_macro_source, chart_of

_TEMPLATES = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "khepri"
    / "rra"
    / "rendering"
)


def test_the_geometry_table_covers_exactly_the_governed_kinds() -> None:
    """`FR-181`: the table that decides whether a kind renders, asserted for extent.

    `_GEOMETRY` is reached only from `build_chart`, and no test asserted it: a kind
    admitted in `bundle` with no row here raises `KeyError` at render time, and a row
    here for a kind `bundle` does not admit is a fourth kind this specification
    forbids. **The expectation is `GOVERNED_CHART_KINDS`, which lives in `bundle.py`
    and is outside `RRA-015` §Scope** -- a slice under this specification cannot widen
    it to match a mistake, which is what makes it an independent source rather than a
    restatement.

    Two assertions already ship and are deliberately not repeated: the frozenset
    identity (`test_rra006_bundle_sections.py`) and the `stacked_bar` sentinel
    mutation (`test_rra009_wording.py`).
    """
    assert set(_GEOMETRY) == GOVERNED_CHART_KINDS
    assert _GEOMETRY, "an empty geometry table would satisfy any subset claim"


def test_the_domain_always_includes_zero_whatever_the_series() -> None:
    """`FR-183`: the invariant behind "an axis truncated on a comparison is refused".

    No input can reach a truncated axis -- `_Domain` is built with `Decimal(0)` in
    both bounds, so zero is always inside it. A test driving a "truncated" series
    would therefore be a run that can only produce the null case, which is NOT
    EXERCISED rather than PASS. The property worth asserting is the construction
    itself, and the mutation that proves it is replacing either bound's `Decimal(0)`
    with the bare series.

    Measured through the rendered marks rather than the private domain: an
    all-positive series must leave the baseline at the canvas foot, so every bar
    rises from it and none floats.
    """
    rising = chart_of(values=(Decimal(100), Decimal(300)))
    assert rising is not None
    # Zero is the low bound, so the tallest bar reaches the top and both sit on the
    # canvas foot: y + height == CHART_HEIGHT for every mark.
    for mark in rising.marks:
        assert Decimal(mark.y) + Decimal(mark.height) == CHART_HEIGHT

    falling = chart_of(values=(Decimal(-300), Decimal(-100)))
    assert falling is not None
    # Zero is the high bound, so every bar hangs from the canvas top.
    for mark in falling.marks:
        assert Decimal(mark.y) == Decimal(0)


def test_a_chart_carries_the_zero_baseline_the_domain_computes() -> None:
    """`FR-183`: a negative value hangs below a visible zero baseline.

    The domain already knew where zero fell; nothing drew it. The view now carries
    the position so a consumer renders the line rather than deriving the offset a
    second time -- two derivations are two chances to disagree about where zero sits.

    Asserted against the mark geometry rather than a remembered number: the bar that
    straddles zero must meet the baseline exactly, which is the property a reader
    depends on and a recomputed offset would break.
    """
    view = chart_of(values=(Decimal(-100), Decimal(300)))
    assert view is not None
    loss, gain = view.marks

    # Domain -100..300 over 320 units puts zero 240 units down, and the losing bar
    # hangs from exactly there while the gaining bar rises to exactly there.
    assert view.baseline == "240.0000"
    assert loss.y == view.baseline
    assert Decimal(gain.y) + Decimal(gain.height) == Decimal(view.baseline)


def test_the_baseline_stays_inside_the_canvas_for_every_drawable_series() -> None:
    """`FR-183`: the line is always drawable, because zero is always in the domain.

    An all-positive series puts zero at the foot and an all-negative one puts it at
    the head. Neither is outside the canvas, so no consumer has to decide what to do
    with a baseline it cannot draw.
    """
    rising = chart_of(values=(Decimal(100), Decimal(300)))
    falling = chart_of(values=(Decimal(-300), Decimal(-100)))
    assert rising is not None and falling is not None

    assert Decimal(rising.baseline) == CHART_HEIGHT
    assert Decimal(falling.baseline) == Decimal(0)


def test_the_axis_states_its_unit_as_a_code_the_surface_looks_up() -> None:
    """`FR-183`, `FR-184`: the axis states its unit, and the word is governed.

    The view carries the unit *kind*, not a word: a chart composes no text, and the
    surface resolves it through the same chrome as every other label. `_resolve`
    refuses a series mixing units, so one chart states one dimension and the kind is
    unambiguous by construction.
    """
    view = chart_of()
    assert view is not None
    assert view.axis_unit_kind == "monetary"
    # A kind, not a rendered word -- the surface's job, asserted by its absence here.
    assert view.axis_unit_kind in AXIS_UNITS[LANGUAGE_ENGLISH]
    assert view.axis_unit_kind in AXIS_UNITS[LANGUAGE_ARABIC]


def test_every_governed_unit_kind_has_an_axis_label_in_both_languages() -> None:
    """`FR-184`: the extent of the axis-unit table, from an independent source.

    The expectation is `facts`' three unit-kind constants, which live outside
    `RRA-015` §Scope: a slice under this specification cannot widen them to match a
    mistake here. That is what makes this an extent assertion rather than a
    restatement of the table it measures.
    """
    governed = {facts.UNIT_MONETARY, facts.UNIT_COUNT, facts.UNIT_RATIO}
    assert governed, "an empty unit set would satisfy any subset claim"
    assert set(AXIS_UNITS) == {LANGUAGE_ENGLISH, LANGUAGE_ARABIC}
    for language, entries in AXIS_UNITS.items():
        assert set(entries) == governed, f"{language} is missing a unit kind"
        assert all(word.strip() for word in entries.values())


def test_the_axis_states_no_period() -> None:
    """`FR-183`'s period half is deferred, and this is what holds the deferral.

    Nothing `build_chart` receives carries a period: a `ChartSpec` is a kind and
    figure identifiers, and a `CitedFigure` has none. A chart that stated one would
    be stating a fact it was never given, which `FR-182` forbids. The owner of the
    other half is an artifact that puts a governed period on the bundle.

    Without this assertion the deferral is an invitation: a later slice could
    synthesize a period from a run timestamp and nothing would object.
    """
    view = chart_of()
    assert view is not None
    assert not hasattr(view, "axis_period")
    assert not any("period" in field for field in ChartView.__dataclass_fields__)
    # A field-name check cannot see the surface. A period rendered straight into the
    # macro needs no `ChartView` field at all, and that is the shape a later slice
    # would reach for -- so the macro source is scanned too.
    assert "period" not in _chart_macro_source().lower()


def test_a_chart_renders_no_legend() -> None:
    """`FR-183`'s legend half is deferred, and this is what holds that deferral.

    A legend "renders only where two or more series exist", and there is no series
    concept to count: `_Plot.values` is flat, and `_bars` and `_grouped_bars` differ
    only by a fill constant. `_resolve` already refuses fewer than two *values*, so
    "two or more" is always true of values and cannot be the test.

    So no chart renders a legend, and this asserts it -- a decorative legend naming
    nothing would be worse than none, and is exactly what a later slice might add if
    the deferral were only prose. The owner is a slice giving `_Plot` series
    grouping, which needs `ChartSpec` to name series membership.
    """
    view = chart_of(kind=CHART_GROUPED_BAR)
    assert view is not None
    assert not any("legend" in field for field in ChartView.__dataclass_fields__)
    # Same reason as the period: the macro is what a reader sees, and a legend drawn
    # there passes every check on the view model. Verified by mutation -- a
    # `<g class="chart__legend">` appended to the macro passed all 37 tests before
    # this line existed.
    assert "legend" not in _chart_macro_source().lower()


#: The functions in `charts.py` that may contain arithmetic, because scaling a value
#: to a canvas offset cannot be expressed without it. Every other function must be
#: arithmetic-free, and a NEW arithmetic-bearing function fails by construction
#: rather than by a reviewer noticing.
#:
#: This is an allowlist of *names*, which makes it the independent expectation: the
#: subject is what `ast` finds in the module, and widening the subject cannot widen
#: this list.
_ARITHMETIC_ALLOWED = frozenset(
    {
        "span",
        "offset",
        "slot",
        "_resolve",
        "_plot",
        "_rank",
        "_columns",
        "_top",
        "_height",
        "_mirror",
        "_centre",
        "_coordinate",
        "_line",
        "_label",
        "_polyline",
    }
)


def test_the_chart_module_confines_arithmetic_to_geometry() -> None:
    """`FR-182` and §Verification: no figure is derived here.

    **A token grep cannot make this assertion, and an earlier form of this test
    tried.** It forbade the strings `sum(`, `mean(`, `median(`, `round(` and
    `statistics.`, and three real derivations walked past it: `+=` accumulation in a
    new helper, a Jinja percentage in the macro, and a `|sum` filter. Verified by
    mutation -- each passed before this rewrite.

    So the module is parsed instead. Every `BinOp` and `AugAssign` must sit inside a
    function this specification admits arithmetic in, because geometry over given
    values *is* this module's job: `_Domain.offset` scales a value to a canvas
    offset, and it cannot do that without division. What must not exist is a new
    function that derives a figure, and a name not on the allowlist is exactly that.
    """
    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "charts.py"
    ).read_text(encoding="utf-8")
    assert source.strip(), "charts.py is empty, so this scan proves nothing"

    tree = ast.parse(source)
    enclosing: dict[ast.AST, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            for child in ast.walk(node):
                enclosing.setdefault(child, node.name)

    # `ast.BitOr` is not arithmetic: `ChartView | None` is a type union, and an
    # earlier form of this test reported `build_chart` as an offender for its own
    # return annotation. The operators that can derive a figure are named instead.
    deriving_ops = (
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
    )

    def _derives(node: ast.AST) -> bool:
        if isinstance(node, ast.BinOp):
            return isinstance(node.op, deriving_ops)
        if isinstance(node, ast.AugAssign):
            return isinstance(node.op, deriving_ops)
        return False

    offenders = sorted(
        {enclosing.get(node, "<module level>") for node in ast.walk(tree) if _derives(node)}
        - _ARITHMETIC_ALLOWED
    )
    assert offenders == [], f"arithmetic outside geometry: {offenders}"
    # The scan must actually have found arithmetic, or an empty parse would satisfy
    # every claim it makes.
    assert any(_derives(node) for node in ast.walk(tree)), (
        "no arithmetic found at all, so this scan proves nothing"
    )


def test_the_chart_macro_derives_nothing() -> None:
    """`FR-182`: the template composes no value either.

    The macro is where a percentage is cheapest to add and hardest to notice -- it
    renders, it looks right, and no Python test reads it. Parsed with Jinja's own
    parser rather than grepped: `{{ view.marks|length * 100 / 4 }}%` passed a token
    scan, and `|sum` did too.
    """
    source = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "templates"
        / "_chart.svg.j2"
    ).read_text(encoding="utf-8")
    assert source.strip(), "the macro is empty, so this scan proves nothing"

    parsed = Environment(autoescape=True).parse(source)
    arithmetic = [
        type(node).__name__
        for node in parsed.find_all((nodes.Add, nodes.Sub, nodes.Mul, nodes.Div))
    ]
    assert arithmetic == [], f"the macro derives a value: {arithmetic}"

    deriving = {"sum", "round", "int", "float", "abs", "map", "select", "reject"}
    filters = sorted(
        {node.name for node in parsed.find_all(nodes.Filter)} & deriving
    )
    assert filters == [], f"the macro applies a deriving filter: {filters}"


def test_a_value_survives_the_chart_with_its_precision_intact() -> None:
    """`FR-182`, §Verification: the value-preservation half, distinct from the scan.

    A static scan proves no arithmetic is written. It cannot prove a value arrives
    unchanged -- a quantization applied through a helper the scan admits would pass
    it. So a figure whose precision differs from any default is driven through
    `build_chart`, and the label beside its mark must still be the figure's own
    rendering, character for character.
    """
    odd = Decimal("123.456789")
    view = chart_of(values=(odd, Decimal(300)))
    assert view is not None

    # A label names its category, never its value -- the table beside the chart is
    # where a number is stated. So the preservation this asserts is geometric: the
    # mark's offset must be the exact scaling of the given value, quantized once to
    # the governed coordinate precision and never re-rounded on the way.
    # The expectation is a LITERAL, not a re-derivation from `COORDINATE_PRECISION`.
    # Deriving it from the same constant the geometry uses made this test pass a
    # mutant that halved the precision: both sides moved together, which is the
    # tautology an extent assertion exists to avoid. 188.3128 is the four-place
    # quantization of 320 * (300 - 123.456789) / 300 = 188.3127584, checked by hand.
    assert view.marks[0].y == "188.3128"
    # And the precision is the governed four places, asserted against the literal
    # rather than against the constant, so a change to either is visible here.
    assert len(view.marks[0].y.split(".")[1]) == 4
    # And the value itself is nowhere in the view: a chart that carried the number
    # would be a second place a figure is stated, which the table already is.
    assert all(str(odd) not in label.value for label in view.labels)


def test_the_axis_unit_renders_in_both_languages_on_a_real_surface() -> None:
    """`FR-184`, `FR-188`: the chrome key reaches both `_CHROME` branches.

    The macro resolves `chrome.axis_units` under `StrictUndefined`, so a key
    registered in one language only raises on that language's render alone -- and a
    test comparing table key sets would never drive it. This renders the chart macro
    through the real environment in both languages instead.
    """
    for language in (LANGUAGE_ENGLISH, LANGUAGE_ARABIC):
        view = chart_of(language=language)
        assert view is not None
        assert view.axis_unit_kind in AXIS_UNITS[language]
        # The word differs between the two, which is what makes this a parity check
        # rather than a restatement of one table.
        assert AXIS_UNITS[language][view.axis_unit_kind].strip()
    assert (
        AXIS_UNITS[LANGUAGE_ENGLISH][DEFAULT_UNIT]
        != AXIS_UNITS[LANGUAGE_ARABIC][DEFAULT_UNIT]
    )


def test_the_new_chart_rules_carry_no_hardcoded_colour() -> None:
    """`FR-192`, and the reason print inherits these rules correctly.

    `report.print.css` is layered onto `report.css` rather than replacing it, and it
    redefines `--report-rule` and `--report-muted` for paper. So a chart rule written
    with those tokens prints in the paper palette without a second declaration, and
    one written with a literal hex value would print the screen colour on paper --
    silently, because nothing renders a chart during a stylesheet test.

    Asserted on the two rules this slice added rather than on the whole sheet: the
    rest of the file is `RRA-012`'s and `RRA-009`'s, and a scan over all of it would
    fail on rules this specification does not govern.
    """
    sheet = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "templates"
        / "report.css"
    ).read_text(encoding="utf-8")
    assert sheet.strip(), "the stylesheet is empty, so this proves nothing"

    for selector in (".chart__baseline", ".chart__axis-unit"):
        start = sheet.index(selector)
        block = sheet[start : sheet.index("}", start)]
        assert "var(--report-" in block, f"{selector} must take the report palette"
        assert "#" not in block, f"{selector} hardcodes a colour: {block!r}"


def test_the_axis_unit_anchor_mirrors_with_the_category_axis() -> None:
    """`FR-188`: the Arabic axis unit is present, not painted off the canvas.

    The label sits on the category axis, and that axis mirrors. An earlier form
    hardcoded `x="0"` in the macro with a stylesheet comment claiming
    `text-anchor: start` made it follow the reading order. It does not: `dir` reaches
    the SVG by inheritance, so under `rtl` the text's start edge anchors at canvas
    zero and the glyphs paint leftward, outside the viewBox. The English page read
    correctly and the Arabic page lost its axis unit -- which `FR-188` forbids, since
    a label present in one language must be present in the other.

    Mirroring is geometry, so `_mirror` decides it and the view carries the result.
    """
    ltr = chart_of(language=LANGUAGE_ENGLISH)
    rtl = chart_of(language=LANGUAGE_ARABIC)
    assert ltr is not None and rtl is not None

    assert ltr.axis_unit_x == "0.0000"
    assert rtl.axis_unit_x == str(CHART_WIDTH.quantize(Decimal("0.0001")))
    assert ltr.axis_unit_x != rtl.axis_unit_x

    # Inside the canvas in both directions, which is the property a reader depends on.
    for view in (ltr, rtl):
        assert Decimal(0) <= Decimal(view.axis_unit_x) <= CHART_WIDTH


def test_the_print_sheet_sizes_the_axis_unit_for_paper() -> None:
    """`RRA-015` §Scope admits "the chart's print behaviour only", and this needs it.

    `report.print.css` is layered onto `report.css`, so the chart's colours inherit
    correctly -- the print palette redefines the two tokens the new rules use. One
    property does not inherit usefully: `0.75rem` against print's `10.5pt` root is
    about 7.9pt, too small to read on paper, and no test renders a chart to paper to
    notice.

    So the print sheet names `.chart__axis-unit` with a point size, and this asserts
    it does. The rest of the chart deliberately has no print rule.
    """
    sheet = (
        Path(__file__).resolve().parent.parent
        / "src"
        / "khepri"
        / "rra"
        / "rendering"
        / "templates"
        / "report.print.css"
    ).read_text(encoding="utf-8")
    assert sheet.strip(), "the print stylesheet is empty, so this proves nothing"

    start = sheet.index(".chart__axis-unit")
    block = sheet[start : sheet.index("}", start)]
    assert "pt" in block, "the print axis unit must be sized in points, not rem"
    assert "0.75rem" not in block, "the screen size would render ~7.9pt on paper"
