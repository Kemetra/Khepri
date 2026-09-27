<!-- Generated: 2026-09-27 | Files scanned: 310 | Token estimate: ~600 -->
# Frontend (server-rendered, no SPA)

Jinja2 templates + static CSS/vanilla JS served by FastAPI. Every page exists in `ar` (RTL) and `en`.
State lives on the server (session cookies + DB); JS only drives step progress in the beta journey.
UI work → load the `khepri-ui` skill.

## Surfaces
```
/landing/{lang}         runtime/landing_templates/landing.html.j2   + landing_assets/landing.css
/legal/{lang}/{page}    runtime/legal_templates/{legal,legal_page}.html.j2   (copy: legal_copy.py)
/beta/{lang}/{step}     rra/journey/templates/  base → upload → review → processing → report | expired
                        assets: journey.css, common.js, upload.js, review.js, processing.js, report.js
/app/{lang}/{org}/…     runtime/shell_templates/  shell.html.j2 (frame) + switcher.html.j2
                          overview · data · analyses · analysis · compare · decision (+decision_print)
                          team · invitation_issued · no_membership · unavailable
                          partials: _decision_cards, _decision_sections
                        assets: shell.css, shell-components.css (in rra/journey/assets), workspace.css
Report surfaces         rra/rendering/templates/  report.html.j2 (web) · report.evidence.html.j2
                          report.pdf.html.j2 (+report.print.css) · _components · _evidence · _chart.svg.j2
                          fonts: rendering/typefaces/NotoSansArabic-*.woff2 (fonts.py inlines them)
```

## Copy / i18n
```
runtime/shell_copy.py     shell strings (ar/en)       runtime/landing_copy.py, legal_copy.py
rra/journey/copy.py       journey strings             rra/rendering/wording.py  report wording (1972 LOC)
```

## Render pipeline (report)
```
FactPackage → rra/bundle.ReportBundle → rendering/html.py (Jinja) → web / evidence HTML
                                      → rendering/pdf.py + chromium.py (Playwright print) → PDF
                                      → rendering/excel*.py (xlsxwriter) → XLSX
Charts: rendering/charts.py → _chart.svg.j2 (inline SVG, no JS chart lib)
```

## Shell view-model flow
`shell_api.py` dispatch → `shell_frame.py` (nav destinations) → `shell_workspace.py` / `shell_analysis.py`
/ `shell_decisions.py` / `shell_comparison.py` / `shell_provenance.py` → template context.
Refusals render via `shell_refusals.py` (refusal is a result, not an error page).
