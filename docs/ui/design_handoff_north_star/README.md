> ## Repository authority notice
>
> **This is supplied design and handoff material. It is reference-only and non-governing, and it is
> not implementation authority.**
>
> The owner supplied it on 2026-09-28 as `Khepri v2.zip` (folder `templates/design_handoff_north_star/`),
> tracked as Jira `SCRUM-24`. Four of its five files are imported verbatim, and the content below
> this notice is unmodified. Nothing here is built, served, tested or imported by product code.
>
> **Active specifications and their `§Scope` govern what product code may change** (Constitution
> Article IV; `governance/registry.yaml` is authoritative for artifact state). Where this package and
> an active specification, `docs/product/KHEPRI_UI_UX_MASTER_SPEC.md`, or `shell.css` disagree, the
> governed source wins and this package yields.
>
> ### Instructions in this package carry no authority here
>
> - "Goal for the developer: (a) update `@khepri/ds` … then (b) implement the Overview screen", and
>   `COMPONENT-CHANGES.md`'s "Apply in `@khepri/ds`, then re-sync with `/design-sync`", are design
>   guidance. `@khepri/ds` is not a package in this repository. Its only copy is the non-built
>   reference snapshot `docs/ui/design_handoff_khepri_v2/` (`SCRUM-23`). This import does not edit
>   that snapshot. Applying the change list to it would be new authored work, outside that folder's
>   recorded CodeScene exception.
> - The screen's controls and destinations (scope, period and comparison controls, filters, saved
>   views, the explorer, the ask field, drill-downs, next-step analyses) grant no product
>   functionality. A control with no backing in an active specification is omitted or left inert.
> - Every figure, branch and category name, finding statement and next-step question is sample data.
>   None of it may be carried into a surface. The package itself records that caveat and refusal
>   patterns do not exist yet, and says not to invent them.
>
> ### Known defects in the supplied files (recorded, not fixed)
>
> The imports stay byte-identical, so defects found in review are recorded here rather than
> corrected. None of them may be copied into an implementation.
>
> - `NorthStarFlagship.dc.html`: the next-step band's full-bleed wrapper `div` (line 198) is not
>   closed before the footer, so the footer renders inside the band's background. README §7 below
>   places the footer outside the band, at container width. The file has 274 `<div` openings and
>   273 closings.
> - `NorthStarSystem.dc.html`: `<html>` has no `lang`, and the Arabic specimens set `dir="rtl"`
>   without `lang="ar"`. In Khepri, `lang` and `dir` are computed on the server for every surface.
> - `NorthStarSystem.dc.html` links to `../north-star-flagship/NorthStarFlagship.dc.html`, and
>   `COMPONENT-CHANGES.md` cites `templates/north-star-flagship/`. Neither path exists. The
>   flagship sits beside them in this folder.
>
> ### The package's status is an open owner question
>
> The README below calls the screen "approved" and "the visual authority for Khepri v2".
> `COMPONENT-CHANGES.md` calls its change list "**proposal, awaiting owner approval**". This notice
> does not resolve that. Either way, approval inside a design tool is not a governance artifact:
> nothing here outranks the registry.
>
> ### Conflicts with governed sources (governed source wins)
>
> | Topic | This package | Governed Khepri source |
> |---|---|---|
> | Colour | ink `#16140F`, paper `#F6F2EA`, gold `#A07A3A`, gold-text `#7A5A22`, positive `#276B4E`, negative `#B03D25`; primary button in ink | Master spec §16.5, binding for colour values: `ink #16212B`, `surface-canvas #FBF9F6`, `gold-500 #C9A45C`, `gold-600 #B98C39`, success `#27724F`, error `#B0392F`; gold is "brand and primary" |
> | Typeface | Noto Naskh Arabic 500–700 and IBM Plex Sans Arabic 300–700 | Master spec §G.1: `Noto Sans Arabic`, package data, SHA-256 verified; "no second typeface" is a recorded deliberate absence, and any new face must pass the licence-plus-audited-digest process |
> | External assets | Both prototypes load `fonts.googleapis.com` | Master spec §G.1 "No `@import`, no font host"; `RCA-010 FR-206`: no external font, style, script or CDN, which the shipped `default-src 'none'` CSP forbids |
> | Elevation | Menu shadow `0 14px 36px`, tooltip shadow `0 10px 28px` | `shell.css` `--shadow: none`; "no elevation ramp" is a recorded deliberate absence |
> | Radius | 2 / 3 / 4 px | `shell.css` `--radius-sm 3px`, `--radius-md 8px`, `--radius-row 10px`, `--radius-card 12px`, `--radius-frame 16px` |
> | Glyphs | ▾ › ‹ ← ↓ ✓ as control affordances | `RCA-010 FR-206`: no Unicode glyph standing in for an icon; "no icon set" is a recorded deliberate absence |
> | Logo | Placeholder wordmark `KHEPRI` | Master spec §7 asset policy (`FR-206`); the logo is an open owner decision |
> | Token layer | One `--k-*` set proposed for every surface | `RCA-010 FR-201`: no shared token layer across the shell and the journey/report surfaces |
> | Behaviour | Metric switching, chart hover, menus and finding focus all run in script | The commercial shell does not carry script-dependent interactions (`test_r810_shell_responsive_rtl.py`; see the `design_handoff_khepri_product_ui` notice) |
> | Layout | `min-width: 1280px`; "no mobile layout in scope" | Master spec B10 "desktop-first, responsive degradation" and §10's per-surface narrow strategy |
>
> ### One file is excluded from this import: `support.js`
>
> The package contains five files, and four are imported. `support.js` is generated build output,
> not authored source. Its first line reads `// GENERATED from dc-runtime/src/*.ts — do not edit.`
> It is a 1,911-line prototype runtime, and the required CodeScene gate would score it as authored
> code. The same exclusion was made for `design_handoff_khepri_product_ui` (#512, #562). CodeScene
> does not analyse `.html`, so both prototypes are imported whole.
>
> **What this costs.** Both `.dc.html` files load `<script src="./support.js"></script>`, so they
> do not render as live pages from this directory. They remain the readable design source (markup,
> styles, sample data and chart logic).
>
> **How to render them.** Take `templates/design_handoff_north_star/support.js` from the owner's
> `Khepri v2.zip` (2026-09-28, SHA-256 `8fe7df74405f3c55f49b7249c74ea1397e65d07dea2b1bd3b4a489bec2e28cbe`)
> and drop it beside the `.dc.html` files. They also fetch Google Fonts, so they need network access.
> Do not commit it.

# Handoff: Khepri v2 — North Star (Retail Sales Analysis · Overview) + component system

## Overview
Khepri is an Arabic-first (RTL), evidence-first retail analytics product. This package contains:
1. **The North Star screen** — the approved flagship "Retail Sales Analysis — Overview/Results" workspace. It is the visual authority for Khepri v2.
2. **The North Star component system** — a review of all 49 `@khepri/ds` components (keep / refine / replace / not needed) and refined specimens derived from the screen.

Goal for the developer: (a) update `@khepri/ds` to the North Star direction per `COMPONENT-CHANGES.md`, then (b) implement the Overview screen with the updated components.

## About the design files
The `.dc.html` files are **design references built in HTML** — prototypes showing intended look and behaviour, not production code. Recreate them in the existing `@khepri/ds` React codebase using its patterns (logical CSS properties, `KhepriProvider`, component props). Do not ship the HTML. To view them, open the `.dc.html` files in a browser with `support.js` beside them (they load Google Fonts online).

## Fidelity
**High-fidelity.** Colours, type, spacing, rules, states and interactions are final for this direction, except the items under *Open decisions*. Data is sample data but internally consistent (see *Data*).

---

## Screen: Retail Sales Analysis — Overview

**Purpose:** a manager sees what changed in the period, why, where (branches, categories), and where to dig next.
**Direction:** `dir="rtl" lang="ar"`. Reading order is right → left, top → bottom. Time axes run left → right (oldest left).
**Canvas:** page background `#F6F2EA`, `min-width: 1280px`. All content sits in a centred container `max-width: 1560px; padding-inline: 48px`. The app bar and context band are full-bleed backgrounds whose inner content uses the same container.

### 1. App bar (full-bleed, ink)
- Background `#16140F`, text `#F6F2EA`, height 64px, bottom border 1px `#3D3831`.
- Inline-start (right) group, gap 36px: wordmark `KHEPRI` (15px/600, letter-spacing .34em, `dir=ltr`, placeholder — logo undecided) · 1×24px divider `#3D3831` · workspace switcher "شركة النيل للتجزئة ▾" (15px, chevron `#C9A865` 11px) · nav: الرئيسية / **التحليلات** / البيانات / التقارير (15px, padding-inline 14px, full-height items; inactive `#CFC6B6` → hover `#F6F2EA`; active 600 + inset bottom bar 3px `#C9A865`).
- Inline-end (left): search field 340×38, bg `#2A2620`, border 1px `#3D3831`, radius 3, placeholder "ابحث أو اسأل عن بياناتك…" 14px `#B3A996`, key hint `⌘K` 12px boxed; avatar 36px circle `#3D3831` initials "س أ" 14px/600.

### 2. Context band (full-bleed, `#EEE7DA`, bottom border 1px `#C9BEAA`)
Inner padding-top 28px.
- **Title row** (space-between, align end): breadcrumb "التحليلات / التجزئة" 15px `#5C554A`, gap 10; H1 "تحليل مبيعات التجزئة" Noto Naskh Arabic 34px/700 lh 1.3. Actions (gap 12): status dot 8px `#276B4E` + "محدّث 28 سبتمبر 2026، 06:00" 14px `#5C554A`; buttons **مشاركة**, **تصدير** (secondary) and **إنشاء تقرير** (primary). Buttons: height 42, padding-inline 18–20, radius 3, 15px. Secondary: transparent, border 1px `#C9BEAA`, hover border `#16140F`. Primary: bg/border `#16140F`, text `#F6F2EA`, 600, hover bg `#3D3831`. One primary per view.
- **Lintel** (margin-top 24): 3px `#16140F` rule, 2px gap, 1px `#16140F` rule.
- **Context bar** (padding 16px 0 18px, bottom border 1px `#C9BEAA`; space-between). Three groups, gap 28, separated by 1×56px `#C9BEAA` dividers. Each group has a label above (13px/700 `#5C554A`, gap 8):
  - **النطاق** — two-line control: line 1 "شركة النيل للتجزئة" 13px `#5C554A`; line 2 "جميع الفروع (12) ▾" 16px/600 (count 500 `#5C554A`). Min-width 230.
  - **الفترة والمقارنة** — (a) period stepper: box with `›` (previous, inline-start) 36px wide · two-line button [solid 18×3 ink swatch + "الفترة الحالية" / "1–30 سبتمبر 2026 ▾"] · `‹` (next; disabled `#C9BEAA`, `cursor:not-allowed`, because it would be in the future). (b) text "مقابل" 14px `#5C554A`. (c) comparison control: [dashed 18px `#9A8F7C` swatch + "فترة المقارنة" + mini switch 26×15 (on = `#16140F` track)] / "1–31 أغسطس 2026 ▾". (d) "التجميع / يومي ▾".
  - **المرشحات** — dashed button "+ إضافة مرشح" (h44, border 1px dashed `#A07A3A`, text `#7A5A22` 15/600, hover bg `#ECE3D2`) + two-line hint "لا مرشحات مطبقة / القناة، الفئة، طريقة الدفع" 14px `#5C554A`.
  - Inline-end: links "حفظ هذا العرض" (underlined `#C9BEAA`, offset 5) and "إعادة الضبط" 14px.
  - Controls: height 56, padding-inline 16, bg `#FBF9F4`, border 1px `#C9BEAA`, radius 3, hover border `#16140F`; chevron `▾` 11px `#7A5A22`. Internal segments hover `#ECE3D2`.
  - **Menus** (open below control, top 62px, inline-start aligned): bg `#FBF9F4`, border 1px `#C9BEAA`, radius 4, shadow `0 14px 36px rgba(22,20,15,.14)`, 15px rows padding 10×16, hover `#ECE3D2`, selected row bg `#ECE3D2` 600. Scope menu (320w): search field, "جميع الفروع 12" checked, regions القاهرة والجيزة 6 / الإسكندرية 2 / الدلتا 3 / الصعيد 1 (ink checkboxes 18px radius 2). Period menu (300w): الشهر الماضي كاملاً (selected) / آخر 7 أيام / آخر 30 يوماً / الربع الثالث 2026 / منذ بداية العام / نطاق مخصص… (gold-text). Comparison menu (340w): الفترة السابقة (selected) / نفس الفترة من العام الماضي / متوسط آخر 3 أشهر / toggle row "إيقاف المقارنة" ↔ "تشغيل المقارنة". Click outside closes (transparent full-screen layer).
- **Tabs** (space-between): نظرة عامة (active) / الاتجاهات / الفروع / الفئات / المنتجات / الأدلة والمنهجية — 16px `#3D3831`, gap 36, padding 16/13; active `#16140F` 600 with 3px `#A07A3A` bottom border overlapping the band border. Inline-end link "فتح في المستكشف ←" 15/600 `#7A5A22`.

### 3. Executive summary
- Grid `minmax(0,1fr) 300px`, gap 72, align end, padding-top 60.
- Eyebrow "خلاصة سبتمبر 2026" 15/600 `#7A5A22`. Headline (H2, max-width 1080) Naskh 46px/600 lh 1.45, `text-wrap: pretty`: "ارتفع صافي المبيعات 8.4% بدفع من زيادة عدد المعاملات، بينما تراجع متوسط السلة وعدد الوحدات في كل معاملة." Lede (max 860) 19px lh 1.8 `#3D3831`: "عشرة من اثني عشر فرعاً نمت مقارنة بأغسطس. تركز النمو في فئتي الألبان والمشروبات وفي فرع سموحة، وتراجع فرعا طنطا والمحلة الكبرى."
- Evidence list (`<dl>`, top rule 1px `#C9BEAA`, 15px, gap 10×20, values end-aligned 600): المعاملات المحللة 412,300 · الفروع 12 من 12 · اكتمال البيانات 99.6% (green) · المصدر نقاط البيع.

### 4. KPI register (replaces StatTile)
- padding-top 36. Grid `auto 72px auto 72px auto 1px auto`, `justify-content: space-between`, `max-width: 1240px`, top border 1px `#16140F`, bottom 1px `#C9BEAA`.
- Cells (padding 26px 20px 30px; first 26/16/30/32): label 15px/700 `#3D3831`; value Plex 300 — hero 100px (lh 1, ls −.02em) + unit "مليون ج.م" 20px `#3D3831`; others 52px; delta line 16px: signed value 700 (+ `#276B4E`, − `#B03D25`, true minus "−", `dir=ltr`) + "مقابل …" `#5C554A`.
  - صافي المبيعات 48.6 مليون ج.م · +8.4% · مقابل 44.8 مليون في أغسطس
  - `=` (Naskh 44px `#A07A3A`) · المعاملات 412,300 · +11.2% · مقابل 370,800
  - `×` (Naskh 40px) · متوسط السلة 117.9 ج.م · −2.5% · مقابل 120.9
  - 1px `#C9BEAA` divider (margin-block 22) · وحدات لكل معاملة 4.6 · −6.1% · مقابل 4.9 · سعر الوحدة +3.9%
- Each cell is clickable → sets the chart metric. Hover bg `#EFE8DA`. Selected cell: 4px `#16140F` bar over the top border.
- Caption below (14px `#5C554A`): "اختر أي مؤشر لعرض حركته اليومية في الرسم أدناه."
- Rule: operators only where the arithmetic holds (Net Sales = Transactions × Basket). UPT is separated by the divider.

### 5. Main analysis region (chart + findings)
- padding-top 80; top border 1px `#16140F`, padding-top 20.
- **Header row** (space-between, wrap): H3 "حركة {metric} اليومية" Naskh 28/600 + subtitle "{unit} · مقارنة يوماً بيوم حسب تاريخ الشهر" 15px `#5C554A`. Toolbar: segmented metric switch (track `#E6DDCC` padding 3 radius 3; segments 15px padding 7×14; selected bg `#FBF9F4` ink 600) صافي المبيعات / المعاملات / متوسط السلة / وحدات/معاملة; secondary button "عرض كجدول" (h38, 14px).
- **Body grid** `minmax(0,1fr) 1px 500px`, gap 44, margin-top 24; middle column is a `#C9BEAA` rule.
- **Chart column.** Column label "الأداء" (14/700 `#7A5A22`, bottom hairline `#DED5C5`, padding-bottom 10). Legend (15px `#3D3831`, gap 28): solid 26×3 ink "سبتمبر 2026"; dashed 26px 2px `#9A8F7C` "أغسطس 2026" (hidden when comparison off); 14px swatch `#EAE1CF` "الجمعة والسبت"; hint "مرّر فوق الرسم لقراءة أي يوم" 14px at inline-end.
  - SVG drawn at the container's measured pixel width (ResizeObserver), height 420, `dir=ltr`. Plot width `pw = width − 64`; value labels at `x = pw + 14` (visual right = inline start in RTL). Plot y from 44 (top) to 380 (baseline). x(d) = 8 + (d−1)·(pw−16)/29.
  - Layers in order: weekend bands (Fri+Sat, `#EAE1CF`); grid lines `#D6CCBA` with labels 14px `#5C554A` (≈4 "nice" ticks, 1/2/2.5/5×10ⁿ, domain padded 12%); unit label at top of the axis (13/600); area under current `#CDB98F` @ .26; comparison line `#9A8F7C` 2px dash 6 5; current line `#16140F` 2.75px round joins; event markers (dashed 1.25px `#A07A3A` vertical, circle r13 fill `#F6F2EA` stroke `#A07A3A` 1.5, number 14/700 `#7A5A22`, label 14/500 `#3D3831` with 5px paper halo via `paint-order: stroke`) — ② 7 Sep "تمديد ساعات سموحة", ③ 14 Sep "بداية تراجع طنطا"; baseline 1.25px ink; x labels 14px at y 406 for days 1, 8, 15, 22, 29 ("1 سبتمبر"…); end dot r5 + value label 15/700.
  - **Hover:** dashed 1px ink crosshair; 12px ink dot (2px paper ring) on current, 10px ring dot `#857C6E` on comparison; tooltip bg `#16140F`, text `#F6F2EA` 15px, radius 3, padding 14×16, min-w 210, shadow `0 10px 28px rgba(22,20,15,.2)`, placed 16px to the right of the crosshair, flipped left past 60% of width. Content: "الخميس، 12 سبتمبر" (600) / سبتمبر value / أغسطس value / rule `#4A443C` / الفرق signed % (700; + `#8FD1B1`, − `#F0A48E`).
  - **Daily difference strip** (margin-top 26; hidden when comparison off): header "الفرق اليومي عن أغسطس" 15/600 + "22 يوماً أعلى · 8 أيام أدنى" (computed). SVG height 88, zero line 1px ink at y 44, bars width max(4, 0.6·step), height = |Δ%|/max|Δ%|·38, + `#276B4E` above / − `#B03D25` below; labels "أعلى"/"أدنى" 14px at axis side.
- **Findings column (500px).** Column label row: "الإشارات والدلالات" (14/700 gold-text) + "4 نتائج · مرتبة حسب الأثر" 14 `#5C554A`; hairline below. Each finding (`article`): grid `32px 1fr`, gap 14, padding 20×14 (margin-inline −14 so hover bg bleeds), hairline between; hover bg `#EAE1CF`.
  - Number: Naskh 28/600 `#A07A3A`.
  - Statement H4: Naskh 21/700 lh 1.5 `#16140F`, margin-bottom 4.
  - Two rows, grid `58px 1fr`, gap 10, 16px lh 1.7: label **الإشارة** (13/700 ink) + fact (ink); label **الدلالة** (13/700 `#7A5A22`) + interpretation (`#3D3831`).
  - Link aligned under text column (margin-inline-start 68): 15/600 `#7A5A22`, 1px `#D9C9A6` underline.
  - Copy:
    1. النمو جاء من عدد الزيارات لا من حجم السلة — الإشارة: المعاملات +11.2%، ومتوسط السلة −2.5%، والوحدات لكل معاملة من 4.9 إلى 4.6. — الدلالة: النمو يعتمد على الحركة داخل الفروع وحدها؛ إذا توقفت زيادة الزيارات سيظهر أثر تراجع السلة مباشرة. — "افحص سلوك السلة ←"
    2. سموحة ينمو بأكثر من ضعف متوسط الشركة — +21.4% مقابل +8.4% للشركة، والفارق يبدأ بعد تمديد ساعات العمل في 7 سبتمبر. — الفرع وحده يفسر 2.3 نقطة من النمو، ويستحق اختبار التمديد في فروع مشابهة. — "قارن سموحة بالفروع المشابهة ←"
    3. طنطا والمحلة الفرعان الوحيدان المتراجعان — طنطا −9.6% منذ 14 سبتمبر والمحلة −3.1%، ويتركز التراجع في الأدوات المنزلية والإلكترونيات الصغيرة. — الفرعان يخصمان 0.6 نقطة من نمو الشركة، والسبب يحتاج فحصاً على مستوى المنتج. — "افحص منتجات طنطا ←"
    4. الألبان والمشروبات تفسران 61% من النمو — 5.1 نقطة من أصل 8.4، بحصة 30% فقط من المبيعات. — أي نقص في مخزون الفئتين سيظهر مباشرة في النتيجة الإجمالية. — "افحص أداء الفئتين ←"
  - **Hover focus:** hovering finding N dims everything unrelated to opacity .25 (transition .2s): 1 → shades the three driver KPI cells `#EAE1CF`; 2 → Smouha row + event ②; 3 → Mahalla, Tanta rows, household & electronics rows + event ③; 4 → dairy & beverages rows.

### 6. "أين حدث التغير؟" — comparison region
- padding-top 96; lintel (3px + 1px ink); header row: H2 Naskh 30/600 + "الفروع والفئات مقابل أغسطس 2026 · مرتبة حسب التغير" 15px `#5C554A`.
- Grid `minmax(0,1.45fr) 1px minmax(0,1fr)`, gap 48, margin-top 28 (middle = `#C9BEAA` rule).
- **Block header:** letter marker (أ / ب, 14/700 gold-text) + H3 Naskh 26/600; summary line 15px `#3D3831` (gap 22). Inline-end: sort button "ترتيب التغير ▾" (h38) and link "كل الفروع ←".
  - Branches summary: "10 من 12 نمت · الأعلى: سموحة +21.4% · الأدنى: طنطا −9.6% · الفارق 31.0 نقطة".
  - Categories summary: "فئتان تفسران 61% من النمو · فئتان متراجعتان −1.1 نقطة".
- **Column header band:** bg `#ECE3D2`, 1px ink top and bottom, padding 10×12 (bleeds −12), 14px `#3D3831`; active sort column ink 600 with "↓".
- **Group header rows:** padding 18–22/8, top+bottom 1px `#C9BEAA`; label 15/700 (green "أعلى من المتوسط" / ink "نمو دون المتوسط" / red "تراجع"); inline-end subtotal 14px "6 فروع · +7.3 نقطة".
- **Data rows:** height 54, 16px, padding-inline 12 (bleed −12), hairline `#DED5C5`, cursor pointer, hover `#ECE3D2`. Last row of table: bottom border 1px ink.
  - Branches grid: `minmax(0,1.3fr) minmax(150px,1fr) minmax(200px,1.3fr) 76px 76px 16px`, gap 20. Cells: name (600, dotted underline `#B3A996` offset 7 = drillable) + city 14 `#5C554A` on the same baseline + optional finding ring (22px, 1.5px `#A07A3A`, 12/700); sales `44px value | bar` (8px track `#DED5C5`, fill `#7C7365`, ink for the leader); dot plot (`dir=ltr`, domain −12…+24%: zero tick 1×20 `#857C6E` at 33.33%, company average dashed 1.5px `#A07A3A` at 56.67%, dot 10px `#3D3831`, outliers 14px green/red); change % end-aligned; contribution (pts) end-aligned; `‹` drill chevron `#857C6E`.
  - Axis header over dot plot: "متوسط +8.4%" (gold-text 600) top, ticks −10 / 0 / +10 / +20% bottom.
  - Outlier rows: positive bg `#E4EEE7` (hover `#D6E6DB`), negative bg `#F6E4DD` (hover `#F0D7CD`), name 700.
  - Categories grid: `minmax(0,1fr) 52px 72px minmax(120px,1fr) 52px 16px`, gap 16. Contribution bar (`dir=ltr`, domain −1…+3 pts, zero at 25%): 16px high, ink for growth drivers, `#7C7365` neutral, `#B03D25` negative. Totals row 700: الإجمالي 100% +8.4% +8.4.
  - Footer line (branches): "الفارق بين أعلى وأدنى فرع: 31.0 نقطة" / "الإجمالي 48.60 · +8.4%".

### 7. Next step band (full-bleed `#EEE7DA`, top 3px ink, bottom 1px `#C9BEAA`, margin-top 104)
- Inner padding 28/48/40. Header: eyebrow "الخطوة التالية" (14/700 gold-text) + H3 "تابع التحليل من هذه النتائج" Naskh 28/600; inline-end ask field 520×50 (bg `#FBF9F4`, border `#C9BEAA`, placeholder "اطرح سؤالاً عن مبيعات سبتمبر…" 16px `#857C6E`, ink button "اسأل").
- Four items, grid `repeat(4, minmax(0,1fr))`, margin-top 14, top border `#C9BEAA`, bg `#F6F2EA`, vertical hairlines; each padding 22/24–32/26, hover `#E4DACA`: source label (14/700 gold-text, e.g. "تحليل السلة · النتيجة 1"), question Naskh 21/600 lh 1.6, "ابدأ التحليل ←" 15/700 ink.
  1. لماذا انخفض عدد الوحدات في كل معاملة؟ 2. ما الذي تغير في سموحة بعد 7 سبتمبر؟ 3. أي المنتجات تفسر تراجع طنطا؟ 4. كيف يتوزع الأداء حسب ساعة اليوم ويوم الأسبوع؟
- Footer (container width): top 1px `#C9BEAA`, padding 20/44, 14px `#5C554A`: source line + "المنهجية والتعريفات" (underlined).

---

## Interactions & behaviour
- **Metric selection:** KPI cells and segmented control share one `metric` state (`sales | tx | basket | upt`). The chart title, unit, y-domain, ticks, paths, tooltip and difference strip all derive from it.
- **Comparison on/off:** from the context switch/menu. Off hides the comparison line, its legend entry, its hover dot and the difference strip, and recomputes the y-domain from the current series only.
- **Chart hover:** mousemove over the chart container → nearest day (1–30); mouseleave clears.
- **Finding focus:** mouseenter / mouseleave on a finding (see mapping above). Transitions: opacity/background .2s.
- **Menus:** one open at a time; outside click closes.
- **Drill-down targets** (routes in the product): row click → branch/category detail; finding links and next-step items → the named analysis; "فتح في المستكشف" → the explorer. In the prototype these are `href="#"`.
- **Not wired in the prototype (design only):** period presets, prev-period stepping, scope selection, sort, grouping, "عرض كجدول", save/reset view, ask field.
- **Keyboard/accessibility:** all controls are native `button`/`a`; add `aria-expanded` on menu triggers, `aria-pressed` on metric segments, `role="switch"` on the comparison switch, and a table fallback for the chart ("عرض كجدول"). Text contrast ≥ 4.5:1 on paper (muted `#5C554A` ≈ 6.4:1).
- **Responsive:** canvas 1280–1560px + margins; chart width is fluid; grids use `minmax(0, …)`. No mobile layout in scope.

## State
`metric`, `comparisonEnabled` (default true), `hoverDay | null`, `focusedFinding 0–4`, `openMenu 'scope'|'period'|'comp'|null`, `chartWidth` (measured). Data needs: daily current and comparison series per metric; KPI totals; branch rows (sales, change %, contribution pts, group); category rows (share, change %, contribution, group); findings (rank, statement, signal, interpretation, related entities, event day, link target); evidence basis.

## Data (sample; consistent)
Net sales 48.6M vs 44.83M (+8.4%) = transactions 412,300 (+11.2% vs 370,800) × basket 117.9 (−2.5% vs 120.9). UPT 4.6 vs 4.9 (−6.1%); unit price +3.9%. Branch contributions sum to +8.4 pts; category contributions sum to +8.4 pts. Daily arrays are in the logic block of `NorthStarFlagship.dc.html` (`SEP`, `AUG`; derived `tx`, `basket`, `upt`).

## Design tokens
Colours: paper `#F6F2EA` · raised `#FBF9F4` · band `#EEE7DA` · sand `#ECE3D2` (weekend band `#EAE1CF`, track `#E6DDCC`, hover-on-band `#E4DACA`) · ink `#16140F` · ink-2 `#3D3831` · muted `#5C554A` · faint `#857C6E` · comparison `#9A8F7C` · neutral bar `#7C7365` · rule `#C9BEAA` · hairline `#DED5C5` · grid `#D6CCBA` · positive `#276B4E` / soft `#E4EEE7` · negative `#B03D25` / soft `#F6E4DD` · gold `#A07A3A` · gold-text `#7A5A22` · gold on ink `#C9A865` · link underline `#D9C9A6` · area `#CDB98F`@.26.
Type: **Noto Naskh Arabic** (headlines 46/600, H1 34/700, section 28–30/600, block 26/600, finding 21/700, operators). **IBM Plex Sans Arabic** for everything else: hero 100/300, KPI 52/300, body/table 16, lede 19, labels 15/700, meta/axis 14, group labels 13/700. `font-variant-numeric: tabular-nums`. Western digits; wrap numbers in `<bdi>`, signed values `dir="ltr"` with true minus.
Spacing: section gaps 60–104; container padding 48; row height 54; control height 56 (context) / 42 (buttons) / 38 (toolbar).
Radius: 2 (tags, checkbox), 3 (controls/buttons), 4 (menus), 50% only for dots/avatars/rings. No gradients.
Shadow: menus `0 14px 36px rgba(22,20,15,.14)`, tooltip `0 10px 28px rgba(22,20,15,.2)`; nothing else.
Rules: lintel = 3px ink + 2px gap + 1px ink; section 1px ink; group 1px `#C9BEAA`; row 1px `#DED5C5`.

## Assets
No images. Fonts: Google Fonts (Noto Naskh Arabic, IBM Plex Sans Arabic). Glyphs: ▾ › ‹ ← ↓ ✓ = ×. Logo: placeholder wordmark (decision open; existing `KhepriLogo` unchanged).

## Component mapping
See `COMPONENT-CHANGES.md` (token changes; Keep 6 / Refine 31 / Replace 9 / Not needed 3) and the visual spec `NorthStarSystem.dc.html`. Key new/replaced: AppBar + ContextBand (AppShell/TopBar/PageHeader), ContextControl (Select variant), Section (Card), KpiRegister (StatTile), Finding (FindingCard), grouped DataTable with bar / dot-plot / contribution cells, NextStep (SuggestionCard).

## Open decisions (owner)
Primary button ink vs gold · logo · exact brand values · display face and English headline face · digit system · retire Sidebar/DonutChart/ProgressRing · status colour mapping · caveat/refusal patterns (none exist yet — do not invent).

## Files
- `NorthStarFlagship.dc.html` — the screen (template markup + logic class with data, chart maths and interactions).
- `NorthStarSystem.dc.html` — foundations, component review, refined specimens, English parity, decisions.
- `COMPONENT-CHANGES.md` — change list for `@khepri/ds`.
- `support.js` — runtime needed to open the `.dc.html` files locally.
