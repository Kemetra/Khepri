# Khepri Product UI — interaction spec (clickable prototype)

Companion to `README.md`. Source: `design-files/Khepri Clickable Prototype.dc.html` — open it in a
browser from inside `design-files/`. It is the same six screens as `Khepri Product UI.dc.html`
with working interactions.

**Status of this file.** It says how each control *behaves visually*. It does not grant product
functionality. README §3 still applies: wire a behavior only if the product already has it (a
route, a form post, a job status, a read model field). If a control here has no backing in the
product, style its resting state and leave it inert, or omit it, and list it in the final report.
The prototype fakes all data and timing. Never port its timers, sample files or figures.

Stack reminder: server-rendered Jinja2 + hand-authored CSS + the existing small JS files
(`common.js`, `upload.js`, `review.js`, `processing.js`, `report.js`). Do not add a framework.
Progressive enhancement: every screen must render correctly with JS off.

---

## 0. Global

| Control | Behavior | Implementation note |
|---|---|---|
| Side nav items | Navigate. Active rule: Upload + Review → *New Analysis*; Insights + Report → *Insights* (README §10) | Real `<a>` links from `shell_frame.organization_frame()`; never hardcode the list |
| EN / عربي switch | Switches `dir` + `lang` on the app root. Active item: weight 600, fill `#F4EEE4`, `aria-pressed="true"` | Use the existing language routing (the language is a path segment). A link to the other-language URL, not a JS toggle |
| Screen change | Scroll to top | Default for full-page navigation |
| Prototype nav strip | Scaffolding only | **Omit** |

## 1. Home / Overview

| Control | Behavior |
|---|---|
| Range segmented control 7D / 30D / 3M / 12M | Selected chip `#E8D6B0`, ink `#4A3712`, weight 600; others transparent, ink `#6B7580`. Changing range redraws line, area and dots, and replaces the 5 x-axis labels. Y-axis stays 0–40 |
| Recent Analyses rows | Completed → analysis detail. Running → processing. Error row → upload (re-upload), `title="Re-upload the file"` |
| Recently Generated Reports rows | Open the report. "Preparing…" row is not clickable |
| Quick action "New Analysis" | → upload. "Invite Team Members" stays disabled with its reason (README §12) |

Bind the range control only if `read_overview` can return a series per range. Otherwise render
the chart for the one range it has and leave the control out. Report which case applies.

## 2. Upload

| Control | Behavior |
|---|---|
| Dropzone | Click opens the file picker. Drag-over: 2px solid `#C9A45C` outline. Drop adds each file to the queue at 0% |
| Upload queue row | Three states. **Uploading**: `NN% · speed` in `#6B7580`, gold gradient bar. **Done**: `✓ Uploaded` `#27724F`, bar `#46875F` at 100%. **Failed**: name + reason `#B0392F`, track `#F7E2DF`, bar `#C0433A` frozen at stop point, plus *Retry* (gold-link) and *Remove* (`#6B7580`) |
| Queue header | `N files · X MB`, live |
| Empty queue | "No files yet. Drop files above or click the upload area." `#6B7580` |
| Analysis Objective | Custom select. Closed: 40px, border `#E6E0D6` (`#C9A45C` while open). Open: list below, border `#DED7CC`, radius 9, options 38px, hover `#F7F3EC`, selected `#F6EBD6` + 600. No shadow (the system has three shadows only). Helper under it: "Required before you can continue." `#B0392F` until set, then "✓ Objective set" `#27724F` |
| Dataset Context textarea | `maxlength=500`; counter `N / 500` updates on input |
| Tags | Chip click removes it. "+ Add tag" becomes an inline input (border `#C9A45C`); Enter adds, Escape or blur cancels, duplicates ignored |
| Save as draft | Label becomes "Draft saved ✓" |
| Continue to Review | **Enabled only when** an objective is set, at least one file is done, and none are uploading. Otherwise disabled tokens (`#FAF8F5` / `#F0ECE5` / `#B2B7BC`, `cursor: not-allowed`) with `title` = the hint. Hint line left of the buttons: "Select an objective to continue." → "Waiting for uploads to finish…" → "Add at least one file to continue." → "N files ready · {objective}" |

Use a native `<select>` if the existing `upload.html.j2` uses one; restyle it to match. The
custom listbox is a visual reference, not a requirement. Objective options, validation and the
250 MB limit come from the product (`copy.py`, `upload.js`, server validation). Do not invent them.

## 3. Review & Map

| Control | Behavior |
|---|---|
| Transformation Suggestions → Apply | Button becomes "Applied ✓" (`#EFEAE2` / `#6B7580`), row fill `#FAF8F5`, secondary line changes to the applied result. Clicking again undoes |
| Map To selector | Each click moves to the next candidate; status, confidence, row tint and note update together from the one `status` enum (README §11) |
| Auto-Map | Resolves every row to its best candidate |
| Reset mappings | Returns every row to the suggested state |
| Back to Upload / Continue to Analysis | Navigate |

Status mapping used by the table:

| status | row tint | badge | meter | selector border / fill / ink |
|---|---|---|---|---|
| mapped | none | `#E7F2EB` / `#27724F` "Mapped" | `#46875F` | `#E6E0D6` / `#FDFBF8` / ink |
| review | `#FDF9F0` | `#FAEEDA` / `#7A5A17` "Needs Review" | `#D9922E` | `#E3CE9F` / `#FFFCF5` / ink |
| unmapped | `#FEF8F7` | `#FBE9E7` / `#B0392F` "Unmapped" | `#C0433A` | `#EBC7C2` / `#FFFBFA` / `#6B7580` |
| excluded | none | `#F1ECE4` / `#6B7580` "Excluded" | `#CBD4DC`, confidence shown as "—" | `#E6E0D6` / `#FAF8F5` / `#6B7580` |

Map these onto the class names `test_r808` already enforces. Rows with one candidate are not
clickable (`cursor: default`). Candidate lists come from the review read model.

## 4. Analysis in Progress

Read-only. The prototype steps through the six tasks on a timer; production polls the real job
status the way `processing.js` does today.

| Element | Behavior |
|---|---|
| Stepper (5) | Upload, Parse always done. Validate is done when task 3 is done, Analyze when task 5 is done, Report when task 6 is done. Current step = first not done: gold ring node, label `#7A5A17`, sub-line is the running text. Connector gold (`#E3CE9F`) only behind done steps |
| Task list (6) | Done: green ✓ + "Completed · time". Running: tinted row `#FDF7EA` / `#F0E1C2`, `khSpin` ring, indeterminate `khBar` with `role="progressbar" aria-busy="true"`. Pending: `#EFE9E0` dot, ink `#8A929B` |
| Header count | "N of 6 completed" (count of done tasks, not of started tasks) |
| ETA panel | Running: "Estimated completion / ~ N min / Elapsed Xm YYs". Complete: "Completed in / Xm YYs / All tasks finished" |
| Live region | `aria-live="polite"`, visually hidden: "In progress: {task}" → "Analysis complete" |
| AI Insights header | "Generating…" + spinner → "✓ Ready" `#27724F` |
| Bottom banner | Running: info banner "You can safely leave this page" + secondary "Preview results". Complete: success banner (`#E9F3EC` / `#D5E5DA`), "Analysis complete", and the screen's single primary button **View insights** (46px, gold gradient, primary shadow) |

Error: the failed task keeps its bar at the stop point in `#C0433A`, states the cause, and offers
Retry plus dismissal (README §12). Only if the job model can fail that way.

## 5. Insights

| Control | Behavior |
|---|---|
| Tabs Overview / Findings / Charts / Recommendations | `role="tab"`, `aria-selected`. Active: 2px `#B98C39` underline, ink `#16212B`, 600; inactive transparent underline, `#6B7580`. **Overview** = KPI strip + both chart rows. **Findings** = KPI strip + Key Findings list (text + status badge). **Charts** = chart rows only. **Recommendations** = numbered list (24px gold-tint number, title .88rem 600, body .8rem `#55616C`) |
| Open Report / View full report | → report |
| "Review mapping" in the excluded-columns callout | → review |

Tabs map onto the existing `analyses` / `analysis` / `decision` surfaces (README §4). If the
product has no source for a tab's content, drop that tab. Do not fill it with prototype copy.
Prefer server-side tab URLs or anchors over JS-only panels.

## 6. Executive Report

| Control | Behavior |
|---|---|
| Page rail | Selected: border `#C9A45C`, 600, ink `#16212B`. Click smooth-scrolls the sheet to that section (offset about 150px for the sticky toolbar) and updates the footer "Page N / 14" |
| Zoom − / + | 70–130% in steps of 10, readout `NN%` in a `dir="ltr"` span. Scales the sheet only, not the rail or toolbar |
| Export PDF | Spinner + "Exporting…" → "PDF ready ✓". Production: the existing print / export path (`report.print.css`) |
| Send to stakeholders | Becomes disabled "Sent ✓" with `title`. Success banner reappears: "**Report sent.** Shared with 4 stakeholders…" |
| Success banner | `role="status"`; Dismiss hides it |
| Back to insights | Navigate |

Send and Export only if those actions exist. Otherwise leave them out and report it.

---

## Accessibility for these interactions

* Clickable spans in the prototype are shorthand. Use real `<a>` for navigation and `<button>` for
  actions. Selects, tabs and listboxes need their ARIA roles and full keyboard support (arrows,
  Enter, Escape, focus return).
* Every progress bar: `role="progressbar"` + `aria-valuenow/min/max`; `aria-busy` when indeterminate.
* Disabled controls keep their shape and say why (`title` or helper line). No opacity for disabling.
* Focus ring per README §15 on every interactive element, including queue Retry/Remove, tag chips and
  table selectors.
* `prefers-reduced-motion` freezes `khSpin`, `khBar`, `khPulse` and the smooth scroll.

## Motion

Only `khSpin` 900ms linear, `khBar` 1.6s ease-in-out, `khPulse` 1.5s ease-in-out. Transitions
140ms, background and color only. No width transitions on progress bars; set the width directly.
