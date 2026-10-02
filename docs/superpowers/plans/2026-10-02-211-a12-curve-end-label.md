# #211 slice: the concentration curve's last label stays inside the canvas (A12)

> Plan and RED evidence for one slice. A12 was found during SCRUM-25 (#629) and recorded on #211.
> SCRUM-26 kept it there, so this slice is GitHub-only.

## Authority

`RRA-015` FR-183 (registry `state: active`). The requirement is that no chart word is clipped by its
canvas. §Scope names `charts.py` label geometry, `_chart.svg.j2` and the chart rules in
`report.css`.

## Cause

`charts._rank` places the curve's kth point at the rank fraction `(k + 1) / n` on purpose, so the
last point, which is the whole set, sits on the inline-end edge. `_label` centred that point's label
there, and half of the word left the canvas: the right edge in English, and the left once the
Arabic axis mirrors.

## Change

- `ChartLabel.anchor_end` is set only on a label whose centre sits on the inline-end edge:
  `CHART_WIDTH`, or `0` when mirrored.
- `_chart.svg.j2` gives that label the `chart__label--end` class, and `report.css` anchors it with
  `text-anchor: end`.
- `end` is relative to the text's direction, which reaches the SVG from `dir`. One rule therefore
  serves both languages, with no physical property.
- No point moves, so the curve still states every percentile where `_rank` puts it.

## Tests (RED at `43e886d`)

- `test_rra015_chart_label_band.py` now measures the category labels' inline edges on the web
  report (1440 px; 390 px at 200% text) and on the printed document, in both languages. It
  reproduced `clipped by the canvas: 3`.
- A view-model case pins that only the label on the inline-end edge is end-anchored, in each
  direction, and that a bar label never is.
- Mutant: `chart__label--end { text-anchor: middle }` turns 3 browser tests red.

## Recorded, not fixed

The axis unit is start-anchored at the start edge. In the printed Arabic report its glyph ink
reaches 0.6 px past the canvas edge (`نصيب`, `عملة`). That is sub-pixel and is not the curve
label, so it is added to #211.
