# Handoff: Khepri — data-to-report product UI (Arabic-first, RTL)

## Overview

Khepri turns an uploaded Excel/CSV file into a reviewable executive report. The design covers the full
operator journey through the product in Arabic (RTL):

`Home → Upload → Column & quality review → Report configuration → Generating → Final report`

Plus a second, separate flow — the **client journey** (English + Arabic, light theme) — for the
self-serve external user who uploads one file and receives a Retail Revenue Assessment.

Two distinct visual environments exist on purpose:

| Environment | Where | Meaning |
| --- | --- | --- |
| **Dark app chrome** | Home, Upload, Config, Generating | You are operating the product. |
| **Light document surface** | Quality review, Final report | You are looking at data / a deliverable. |

The light surface is achieved by re-declaring the same CSS variables locally on the screen root — not
by a second stylesheet. Implement it the same way (a theme scope / `data-surface="doc"` wrapper), so
every component inside inherits the light values with no per-component overrides.

## About the design files

The files in `design-files/` are **design references created in HTML**. They are prototypes showing
intended look and behaviour — not production code to lift directly.

The task is to **recreate these designs in the target codebase's existing environment** (React, Vue,
Next, SwiftUI, native — whatever the app already uses), following its established component patterns,
routing, state management and styling approach. If no environment exists yet, choose the framework
most appropriate for the project and implement the designs there.

Concretely:
- Keep the tokens, layout, spacing, typography and copy exactly.
- Replace the prototype's runtime (a small template + logic-class harness in `support.js`) with the
  codebase's own component model. Do not port `support.js`.
- Replace the `.dc.html` screen-switching (`sc-if` blocks driven by a `screen` state string) with real
  routes or a real wizard state machine.

## Fidelity

**High-fidelity.** Colors, typography, spacing, radii, shadows, iconography, table structure and all
Arabic copy are final. Recreate the UI pixel-accurately using the codebase's libraries. Nothing here
is a placeholder except the numeric data (see *Content & data*).

---

## Foundations

### Direction and language

- Root direction is **RTL** (`dir="rtl"`) on the app shell. This is not a mirrored afterthought — it
  is the default.
- Use **logical CSS properties everywhere**: `margin-inline-start/end`, `padding-inline-*`,
  `inset-inline-start`, `text-align: start/end`. No `left`/`right` in layout code.
- Latin and numeric runs are wrapped in `dir="ltr"` islands so bidi doesn't scramble them. Apply this
  to: filenames (`مبيعات_الربع_الثاني.xlsx`), currency codes (`SAR`, `USD`), formats
  (`PDF`, `Excel`, `.xlsx`, `.csv`), ISO dates (`2024-04-01`), version numbers (`1.3`), percentages
  and all numeric table cells, and the wordmark `Khepri`.
- Percent-change deltas are written `↑ 13.7%` and live inside an LTR island so the arrow stays on the
  numeric side.

### Typography

| Role | Value |
| --- | --- |
| Font family (both heading and body) | `IBM Plex Sans Arabic`, fallback `Inter`, `system-ui`, `sans-serif` |
| Weights loaded | 400, 500, 600 |
| Heading weight | 500 (600 for the wordmark and the client-journey H1s) — never bolder |
| Heading `line-height` | 1.35 |
| Heading `letter-spacing` | 0 (Arabic must not be tracked) |
| Body / paragraph `line-height` | 1.75 |
| Table cell `line-height` | 1.7 |

The design system's own font is Inter; Arabic support required overriding `--font-heading` and
`--font-body` to IBM Plex Sans Arabic. Keep that override — it is deliberate, not drift.

Type sizes actually used (px):

| Size | Use |
| --- | --- |
| 46 | Home hero H1 |
| 34 | Generating progress percentage; client-journey H1 (desktop) |
| 30 | Upload stat values; estimated-time value; client-journey section H1 |
| 26 | Report KPI values; wide-screen client H1 |
| 24 | Home KPI values; live-preview KPI values |
| 20 | Quality-summary values |
| 19 | Wordmark; rail icons |
| 17 | Card titles in the hero report card |
| 15–16 | Card titles, drop-zone headline, primary buttons |
| 14 | Nav items, list rows, screen label |
| 13 | Table body, chips, secondary rows, most muted labels |
| 12 | Meta lines, breadcrumbs, footnotes, small buttons |
| 11 | Card kickers, unit labels, delta lines, timestamps |
| 10 | Chart axis labels, avatar timestamps |

Never go below 10px. 11–13px carries most of the interface; it is dense on purpose.

### Design tokens (Nocturne)

Dark theme — the app default (`:root`):

```
--color-bg:       #161826      /* card / panel ground */
--color-surface:  #232532
--color-text:     #e9e9ed
--color-accent:   #9184d9      /* blurple; a line and a glow, never a flood */
--color-divider:  color-mix(in srgb, #e9e9ed 16%, transparent)

neutral-100 #f3f5fe  200 #e4e7f5  300 #cfd3e5  400 #b2b6ca  500 #9397ab
        600 #75798c  700 #595d6c  800 #3f424d  900 #292b31

accent-100  #f5f4ff  200 #e7e5fe  300 #d2cefd  400 #b5abfc  500 #968ae0
        600 #796cbf  700 #5d5294  800 #423a6a  900 #2b2741

--shadow-sm: 0 0 0 1px #3f424d
--shadow-md: 0 0 0 1px #595d6c, 0 6px 18px rgba(0,0,0,0.55)
--shadow-lg: 0 0 0 1px #9397ab, 0 16px 40px rgba(0,0,0,0.65)
```

The page behind the app window is **#101220** (one step darker than `--color-bg`) so the app window
reads as a lifted object.

Light document surface — declared on the Quality-review and Final-report screen roots:

```
--color-bg:      #e4e7f5      /* the page of the document */
--color-surface: #f3f5fe      /* cards on it */
--color-text:    #292b31
--color-divider: color-mix(in srgb, #292b31 16%, transparent)
--color-neutral-100 #595d6c   --color-neutral-200 #3f424d
--color-neutral-400 #75798c   --color-neutral-600 #75798c
--color-neutral-800 #e4e7f5   --color-neutral-900 #f3f5fe
--color-accent      #796cbf   --color-accent-100 #5d5294
--color-accent-200  #423a6a   --color-accent-300 #796cbf
--color-accent-400  #796cbf   --color-accent-800 #e7e5fe
--shadow-sm: 0 0 0 1px #cfd3e5
--shadow-md: 0 0 0 1px #cfd3e5, 0 6px 18px rgba(41,43,49,0.10)
--shadow-lg: 0 0 0 1px #b2b6ca, 0 16px 40px rgba(41,43,49,0.14)
```

Note the ramps invert on the light surface (100 becomes the *dark* step) so a component styled once
works on both grounds. Muted text on the light surface resolves to `--color-neutral-700` (#595d6c) —
a real ramp step, not an opacity mix of the ink.

Spacing scale (density 0.7×) — use the variable, not the raw px:

```
--space-1 2.8   --space-2 5.6   --space-3 8.4
--space-4 11.2  --space-6 16.8  --space-8 22.4
```

Radii: `--radius-sm 4px`, `--radius-md 8px`, `--radius-lg 14px`.

### Icons

**Phosphor Icons**, regular weight for most, fill weight for status/confirmation glyphs. Icon sizes
in use: 13, 17, 18, 19, 20, 22, 24, 26, 42px. Brand mark is `ph-fill ph-bug-beetle` in the accent
(the scarab — Khepri). The ornate logo render in `docs/assets/khepri-logo.png` in the repo is *not*
used at product scale.

### Interaction states (from the design system, do not restyle per-screen)

- Primary button = **1px accent outline on transparent**, never a solid accent fill.
- Hover: accent tint from the ramp. Pressed: one step past base — `--color-accent-400` on the dark
  ground, `--color-accent-600` on the light one.
- Keyboard focus: `outline: 2px solid var(--color-accent); outline-offset: 2px` on `:focus-visible`.
  Never the browser default.
- Disabled: 45% opacity.
- Selected/active option cards: 1px accent border + `color-mix(in srgb, var(--color-accent) 10%, transparent)` fill.
- Active nav item: accent text + `box-shadow: inset 0 -2px 0 var(--color-accent)` (an underline that
  doesn't shift layout).
- Active rail icon: accent text + `color-mix(in srgb, var(--color-accent) 14%, transparent)` on
  `--radius-sm`.

---

## App shell

Wraps every operator screen.

- Outer page: `dir="rtl"`, background `#101220`, padding `clamp(16px, 2.2vw, 40px)` with `96px` bottom.
- App window: `width: min(1520px, 100%)`, `border-radius: var(--radius-lg)`, `overflow: hidden`,
  `box-shadow: var(--shadow-lg)`, `background: var(--color-bg)`.
- **Top bar**: height 60px, `background: var(--color-neutral-900)`, `padding: 0 var(--space-6)`.
  - Right (start in RTL): scarab icon 22px accent + wordmark `Khepri` 19px/600, `dir="ltr"`.
  - Nav, 14px, `gap: var(--space-6)`: الرئيسية · التقارير · مصادر البيانات · التنبيهات · الإعدادات.
    Inactive items are `color-mix(in srgb, var(--color-text) 62%, transparent)`.
  - Left (end): help + bell icons 19px muted, then a user chip — 1px divider border,
    `--radius-md`, containing a caret, the name `أحمد`, and a 24px round avatar
    (`--color-accent-800` ground, `--color-accent-100` initial).
- **Icon rail**: 60px wide, on the **left** (visual end in RTL), `background: var(--color-neutral-900)`,
  column, `gap: var(--space-4)`, `padding: var(--space-4) 0`. Scarab at top, then six nav icons:
  `chart-line-up`, `table`, `database`, `file-text`, `shield-check`, `clock-counter-clockwise`.
- **Content area**: `flex: 1`, `padding: var(--space-8)`, `min-height: 880px`. The light-surface
  screens cancel that padding with `margin: calc(var(--space-8) * -1)` and re-apply their own, so the
  document ground bleeds to the shell edges.
- **Caption strip** below the window: accent screen label + muted one-line description. This is a
  *mockup annotation*, not product UI — **do not implement it**.

---

## Screens

### 1. Home — `الرئيسية`

**Purpose.** First screen after sign-in: orient the user, show a live glimpse of their latest report,
and give them the next action.

**Layout.** Column, `gap: var(--space-8)`.

1. **Hero row** — `grid-template-columns: 1fr 1fr`, `gap: var(--space-8)`, `align-items: center`.
   - Left cell (`padding-inline-start: var(--space-4)`):
     - H1 46px: `مرحبًا بك في Khepri` — `Khepri` in `--color-accent`, `dir="ltr"`.
     - H4 500 weight in `--color-accent-300`:
       `حوّل ملفات Excel و CSV إلى تقارير تنفيذية واضحة وقابلة للمراجعة`
     - Body 15px muted, `max-width: 54ch`, `text-wrap: pretty`:
       `يساعد Khepri فرق الأعمال على تحويل بياناتهم إلى رؤى موثوقة وتقارير جاهزة للمشاركة، مع تتبع كامل للمصدر، وسجل تدقيق لا يمكن تغييره، وبيئة آمنة تُلبي أعلى معايير حوكمة البيانات.`
     - Buttons, `gap: var(--space-3)`, `padding: 11px 22px`, 15px:
       primary `ابدأ برفع ملف` (`ph-cloud-arrow-up`) → Upload;
       secondary `شاهد مثال تقرير` (`ph-file-text`) → Final report.
     - Reassurance line 12px muted with `ph-lock-simple`:
       `بياناتك آمنة ومشفرة ولا تُستخدم لأي تدريب أو مشاركة.`
   - Right cell — **report preview card** (`.card .elev-md`, `padding: 0`, `overflow: hidden`):
     - Header row: title `تقرير الأداء التنفيذي` 17px + `مايو 2024` 12px muted; on the end side an
       accent tag `تم التحديث 10:30 ص` and a 12px secondary `تصدير` button.
     - KPI strip: `grid-template-columns: repeat(4, 1fr)`, `gap: 1px`, container background
       `--color-divider` so the 1px gap *is* the rule; each cell `background: var(--color-surface)`,
       `padding: var(--space-4)`. Per cell: 11px muted label, 24px value, 10px muted unit, 11px
       `--color-accent-300` delta.
       `إجمالي الإيرادات 12.84 مليون ر.س ↑13.7%` · `صافي الربح 2.31 مليون ر.س ↑16.4%` ·
       `هامش الربح 18.0% من الإيرادات ↑1.8 نقطة مئوية` · `عدد العملاء الجدد 1,248 عميل ↑11.2%`
       (all compared `عن الشهر السابق`).
     - Body: `grid-template-columns: 1.15fr 1fr`, `gap: var(--space-6)`, `padding: var(--space-6)`.
       Left = revenue line chart (see *Charts*). Right = top-products table, 12px, five rows, cell
       padding `5px var(--space-2)`, amounts and deltas `text-align: end`.
2. **Three cards** — `repeat(3, 1fr)`, `gap: var(--space-6)`, all `.card .elev-sm`,
   `padding: var(--space-6)`:
   - `موثوق من فرق الأعمال` (`ph-shield-check`) — three icon+text rows; row title 14px in
     `--color-accent-300`, body 12px muted `line-height: 1.6`.
   - `ثلاث خطوات من البيانات إلى تقرير تنفيذي` (`ph-sparkle`) — three centred steps; step 1's numeral
     ring is a 30px circle with a 1px accent border in accent, steps 2–3 use a divider border and
     70%-mixed text.
   - `خطواتك للانطلاق` (`ph-flag`) — checklist. Done row: accent 10% tint on `--radius-sm`,
     `ph-fill ph-check-circle`, title in `--color-accent-300`. Pending rows: `ph-circle` in
     `--color-neutral-700`, no fill.
3. **Trust bar** (toggleable, see *Props*) — `repeat(5, 1fr)`, `gap/padding: var(--space-6)`,
   `--radius-md`, `box-shadow: var(--shadow-sm)`. Five icon + two-line items: immutable audit log,
   secure hosting, PDPL compliance, AES-256 encryption, ISO 27001. Standards names are `dir="ltr"`.

### 2. Upload — `رفع البيانات`

**Purpose.** Bring a file in, state the limits before the user hits them, and show recent history.

- Page head: `ph-cloud-arrow-up` 26px accent + H2 `رفع البيانات` + 14px muted
  `استورد ملفات Excel و CSV بأمان لبدء التحليل والتقارير.`
- **Three stat cards** — `repeat(3, 1fr)`. Each: 12px muted label + 18px accent-400 icon on the row
  end, 30px value, 11px muted delta.
  `الملفات قيد الفحص 8 ↑14.3%` · `عمليات الاستيراد الناجحة 104 ↑16.7%` ·
  `اجمالي عمليات الرفع 128 ↑18.2%` (all `عن الشهر الماضي`).
- **New-upload card** (`padding: var(--space-8)`) — `grid-template-columns: 1fr 1px 1.35fr` with the
  middle column a literal `background: var(--color-divider)` divider.
  - Left: `اختر نوع الملف المراد استيراده`, then two type cards (`1fr 1fr`). Excel is selected
    (accent border + 10% tint, `ph-file-xls` 26px accent, `Excel` / `.xlsx, .xls`); CSV unselected
    (divider border, `ph-file-csv` in `--color-neutral-400`, `CSV` / `.csv`). Below, a security note
    row with `ph-shield-check`: `جميع الملفات تعالج بشكل آمن ولا يتم تخزينها خارج بيئة Khepri.`
  - Right: **drop zone** — `1px dashed color-mix(in srgb, var(--color-accent) 55%, transparent)`,
    `--radius-lg`, `padding: var(--space-8)`, ground `color-mix(in srgb, var(--color-accent) 5%, transparent)`,
    centred column: `ph-cloud-arrow-up` 42px accent, `اسحب الملف هنا وأفلته للرفع` 16px,
    `أو اختر ملفًا من جهازك أو من OneDrive` 13px muted, then primary `اختيار ملف`
    (`ph-file-arrow-up`) → Quality review, and secondary `استيراد من OneDrive` (`ph-cloud`).
    Under it, 12px muted with `ph-info`:
    `الحد الأقصى لحجم الملف: 50 ميجابايت · ملف Excel بورقة واحدة`.
    **These limits are real product constraints** (50 MB; CSV or single-sheet XLSX) — enforce them
    client-side and surface the same wording.
- **Recent files** card — `.table`, columns: اسم الملف · المصدر · حجم الملف · تاريخ الرفع · الحالة ·
  رفع بواسطة · (row menu, `ph-dots-three`, `text-align: end`). Filenames, source, and size are LTR
  islands. Status uses tags: `.tag-accent` = تم الرفع, `.tag-neutral` = قيد الفحص,
  `.tag-outline` + `ph-warning` = فشل الاستيراد. Ghost buttons `عرض الكل` (header) and
  `عرض كل السجلات` (centred footer).

### 3. Column & quality review — `مراجعة الأعمدة والتحقق من الجودة`

**Light document surface.** Purpose: prove what was read and let the user fix the mapping before any
computation. This is the trust gate of the product.

- Head row: H2 + 14px muted subtitle on the start side; on the end side a compact file card
  (`min-width: 240px`) — `ph-file-xls` 20px accent, `مبيعات_أبريل_2024`, meta
  `Excel · 2.4 MB · تم الرفع قبل 3 دقائق`, ghost `عرض تفاصيل الملف`.
- **Stepper** — one row, `padding: var(--space-4) var(--space-6)`, `--radius-md`,
  `box-shadow: var(--shadow-sm)`, 13px. Five steps separated by `flex: 1` 1px divider lines.
  Completed (1–2) = accent `ph-fill ph-check-circle` + accent label. Current (3) = a 20px accent
  filled circle with the numeral in `--color-bg`. Upcoming (4–5) = 20px 1px-divider ring, muted.
  Steps: `رفع الملف · التحقق من الجودة · ربط الأعمدة · إعداد التقرير · التسليم`.
- Body grid: `grid-template-columns: 1.6fr 1fr`, `gap: var(--space-6)`, `align-items: start`.
  - **Left column:**
    - *Data preview card* (`padding: 0`, `overflow: hidden`):
      - Tab strip: `معاينة البيانات` (active — accent + inset 2px underline) / `ملخص الجودة`, both
        `padding: var(--space-4) 0`, strip `border-bottom: 1px solid var(--color-divider)`.
      - Toolbar: `ph-eye` + `عرض أول` + a 100 input chip + `من أصل 7,542 صف`; on the end a 190px
        search field placeholder `بحث في البيانات...` (placeholder color
        `color-mix(in srgb, var(--color-text) 45%, transparent)`) and a 12px secondary
        `خيارات المعاينة` (`ph-sliders-horizontal`).
      - Table, 13px, `min-width: 780px` inside `overflow-x: auto`. Columns: رقم الفاتورة ·
        تاريخ الفاتورة · اسم العميل · إجمالي المبلغ · العملة · المنتج · الكمية · سعر الوحدة ·
        (status). Eight rows of real-looking dirty data. **Row-level status glyph in the last cell**
        and **inline highlighting of the offending cell**: inconsistent dates
        (`01/04/2024`, `2024/04/02`, `03/04/2024`) are rendered in `--color-accent-300`; missing
        values are an em dash `—`; a foreign currency (`USD`) is wrapped in `.tag-neutral`.
        Glyphs: `ph-fill ph-check-circle` accent = valid, `ph-warning` accent-300 = warning,
        `ph-fill ph-x-circle` neutral-200 = error, `ph-info` neutral-400 = informational.
      - Footer: ghost `عرض جميع المشاكل (18)` on the start; on the end a 12px muted legend
        `مفتاح الحالة:` with all four glyphs labelled صحيح / تحذير / خطأ / معلومة.
    - *Two cards* — `grid-template-columns: 1.25fr 1fr`:
      - `أبرز المشاكل` (`ph-warning-circle`): count in accent-300 with `min-width: 34px` so the
        numbers align, then the muted description. Rows:
        `118 قيمة مفقودة في «إجمالي المبلغ»` · `94 تاريخ غير متسق (سيتم التوحيد إلى YYYY-MM-DD)` ·
        `56 سعر وحدة مفقود أو غير صالح`. Ghost `عرض جميع المشاكل ←`.
      - `ملخص الجودة`: 2×2 grid, 11px muted label + 20px value with an 11px inline percentage.
        `إجمالي الصفوف 7,542` · `صفوف صالحة 6,812 90.3%` (accent-300) · `تحذيرات 612 8.1%` ·
        `مشكلات حرجة 118 1.6%`.
  - **Right column — column mapping card.** Header: `ربط الأعمدة بالمجالات المستهدفة` + 11px muted
    `سحب مستوى الثقة ⌄`. Eight rows, each `grid-template-columns: 1fr 1fr auto`,
    `gap: var(--space-3)`, `padding: var(--space-3)`, `--radius-sm`, `box-shadow: var(--shadow-sm)`:
    target field (13px, required fields marked with an accent `*`, 11px muted description) →
    detected source column (13px + 11px muted type) → confidence tag.
    `.tag-accent` at ≥90%, `.tag-outline` below: رقم الفاتورة 99% · تاريخ الفاتورة 98% ·
    اسم العميل 99% · إجمالي المبلغ 97% · العملة 96% · المنتج 82% · الكمية 78% · سعر الوحدة 75%.
    Footer: ghost `+ إضافة مجال مخصص` and 12px muted `8 من 12 مجال مكتملة`.
- **Action bar**: secondary `الرجوع` on the start; on the end secondary `حفظ كمسودة`
  (`ph-floppy-disk`) and primary `اعتماد الربط` (`ph-check-circle`) → Config.

### 4. Report configuration — `إعداد التقرير التنفيذي`

- Head: breadcrumb 12px muted `التقارير › إعداد تقرير جديد`, H2, 14px muted intro
  (`max-width: 72ch`); on the end secondary `إعادة تعيين` (`ph-arrow-counter-clockwise`) and
  `معاينة تعيينة` (`ph-eye`).
- Grid `1.75fr 1fr`, `gap: var(--space-6)`, `align-items: start`.
  - **Left, card 1** — two halves (`1fr 1fr`, `gap: var(--space-8)`):
    - `نوع التقرير`: 2×2 option cards, `padding: var(--space-3)`, `--radius-md`. `تنفيذي`
      (`ph-briefcase`) selected; `تحليلي` (`ph-chart-line`), `تشغيلي` (`ph-gear`), `مخصص`
      (`ph-sliders`) unselected. Each: 14px title row + 11px muted description.
    - `نطاق التاريخ`: two `.field` date inputs (`من` 01 مايو 2024 / `إلى` 31 مايو 2024) with a
      trailing `ph-calendar-blank`; a `الفترة المسبقة للمقارنة` select set to `نفس الفترة السابقة`;
      and a radio for including the comparison period.
    - `المقاييس (KPIs)`: a wrapping chip row, `gap: var(--space-3)`. Chip = `padding: 8px 12px`,
      `--radius-md`, 13px, `white-space: nowrap` (labels must never break mid-phrase). Selected
      chips carry a 1px accent border, 10% accent tint, `--color-accent-200` text and a `ph-check`;
      unselected carry a divider border, muted text and their own icon. Selected: إجمالي الإيرادات ·
      هامش الربح · صافي الربح · معدل دوران المخزون. Unselected: النمو على أساس سنوي (`ph-trend-up`) ·
      متوسط قيمة الطلب (`ph-shopping-cart`) · تكلفة اكتساب العميل (`ph-user-plus`) ·
      رضا العملاء (`ph-smiley`).
    - `المرشحات`: three selects (المنطقة / القناة / فئة المنتج, all `الكل`) + ghost `+ إضافة مرشح`.
    - Bottom strip above a `border-top: 1px solid var(--color-divider)`: three selects with icon
      labels — تنسيق الإخراج (`PDF و Excel`), اللغة (`العربية والإنجليزية`), التجميع (`الشهر`).
  - **Left, card 2 — `اختيار القالب`**: `repeat(5, 1fr)`. Each item is a `4 / 3` thumbnail +
    caption. Selected thumbnail: 1px accent border, 12% accent tint, 26px accent icon, caption in
    `--color-accent-200` with `ph-fill ph-check-circle`. Others: `box-shadow: var(--shadow-sm)`,
    26px `--color-neutral-500` icon, muted caption. The fifth is a dashed-border `+` for a custom
    template. Names: قالب تنفيذي كلاسيكي · قالب تحليلي حديث · قالب ملخص مرئي · قالب أداء الأقسام ·
    قالب مخصص.
  - **Right rail:**
    - `ملخص الإعدادات`: four icon + three-line rows — مصدر البيانات (مستودع البيانات الرئيسي /
      تحديث يومي · آخر تحديث اليوم 10:30 ص), الأقسام المختارة (4 أقسام), الجمهور المستهدف
      (الإدارة التنفيذية / 15 مستخدم), وقت التسليم المتوقع (05 يونيو 2024 · 08:00 ص / حسب منطقتك الزمنية).
    - Info note: `color-mix(in srgb, var(--color-accent) 9%, transparent)`, `--radius-md`,
      `ph-info`, title `معلومات مهمة` in `--color-accent-200`, body 12px muted.
    - `.btn-block` primary `إنشاء التقرير` (`ph-file-plus`, `padding: 12px`) → Generating, then
      `.btn-block` secondary `حفظ كمسودة` (`ph-bookmark-simple`).

### 5. Generating — `جاري إنشاء التقرير`

**Purpose.** Make a two-minute wait legible and interruptible.

- Head: breadcrumb, H2 with a `ph-file-text` accent glyph, 14px
  `جارٍ إنشاء تقرير الأداء التنفيذي لشهر مايو 2024`, 12px muted
  `بناءً على البيانات المحدثة في 19 مايو 2024، 10:30 ص`; on the end secondary
  `إشعار عند الاكتمال` (`ph-bell`) and primary `متابعة في الخلفية` (`ph-arrow-square-out`).
- **Progress card** (`padding: var(--space-8)`), `grid-template-columns: auto 1fr`,
  `gap: var(--space-8)`, `align-items: center`:
  - Left block (`min-width: 150px`): 11px muted `الوقت المتبقي المقدر`, 30px `2 دقيقة`, 11px muted
    `حتى الاكتمال`, a six-segment 4px-tall bar (`gap: 4px`; four accent, two `--color-neutral-800`),
    then 11px muted `تم الانتهاء من 4 من 6`.
  - Right block: baseline row of 34px accent `78%` and 12px muted
    `الخطوة الحالية: مراجعة الجودة الداخلية · جاري إنشاء التقرير...`; a 6px `--radius: 3px` track on
    `--color-neutral-900` with a 78% accent fill **plus a 12%-wide travelling sheen**
    (`linear-gradient(to left, transparent, color-mix(in srgb, var(--color-accent-100) 55%, transparent), transparent)`,
    `animation: khepri-sheen 2.4s linear infinite`, keyframes `translateX(120%) → translateX(-820%)`
    — RTL-directed). Below, `repeat(6, 1fr)` steps: تحقق البيانات (`ph-database`) · حساب المؤشرات
    (`ph-calculator`) · إنشاء الرسوم البيانية (`ph-chart-bar`) · توليد السرد (`ph-text-align-left`)
    all `اكتمل`; مراجعة الجودة (`ph-shield-check`) `جاري التنفيذ` — highlighted with a 12% accent
    tint on `--radius-sm`; حزمة التصدير (`ph-package`) `في الانتظار`, fully muted.
- Lower grid `1fr 1.6fr`:
  - `الأنشطة في الخلفية`: six labelled 4px progress bars — 8 مصادر 100% · 23 مؤشر 100% ·
    18 رسم بياني 87% · 12 قسم 64% · تحقق تلقائي 22% · `PDF, Excel, PPT` 0%. Track
    `--color-neutral-900`, fill accent. Footnote 11px muted
    `ستبقى هذه الصفحة مفتوحة حتى اكتمال التقرير.`
  - `معاينة حية (مبدئية)` (`ph-eye`): a `1fr 1fr 1.2fr` row of two KPI tiles (هامش الربح 18.0%,
    إجمالي الإيرادات 12.84) and a `ملخص تنفيذي` paragraph; then a `1fr 1fr` row with a six-month
    revenue sparkline and a segment bar `توزيع الإيرادات حسب القطاع` (50 / 26 / 17 / 7 % across
    accent, accent-600, accent-700, neutral-700) with a legend beneath. Tiles use
    `box-shadow: var(--shadow-sm)` on `--radius-sm`, no card fill.

### 6. Final report — `التقرير التنفيذي النهائي`

**Light document surface.** Purpose: the deliverable plus the governance layer that makes it
defensible.

- Head: `ph-fill ph-seal-check` 24px accent + H2 + `.tag-outline` `جاهز للتسليم`; meta row 12px
  muted — `تقرير الأداء التنفيذي — 2024`, `آخر تحديث: 10 يونيو 2024، 10:30 ص`,
  `.tag-neutral` `الإصدار 1.3`. Actions on the end (wrapping): secondary `Excel` (`ph-file-xls`),
  `تصدير PDF` (`ph-file-pdf`), `طلب مراجعة` (`ph-users-three`), primary `مشاركة آمنة`
  (`ph-lock-simple`).
- **KPI row** — `repeat(5, 1fr)`, `gap: var(--space-4)`. Each card `padding: var(--space-4)`,
  `gap: 2px`: label 11px muted + accent-400 icon on the row end, 26px value, 10px muted unit, 11px
  accent-300 delta. إجمالي الإيرادات 12.84 ↑13.7% · صافي الربح 2.31 ↑16.4% · هامش الربح 18.0%
  ↑1.8 نقطة مئوية · عدد العملاء النشطين 1,248 ↑11.2% · التدفق النقدي التشغيلي 4.56 ↑24.3%
  (all `عن النصف السابق`).
- Body grid `1.65fr 1fr`:
  - **Left:**
    - Row `1.1fr 1fr`: revenue-trend line chart with dot markers and half-year axis labels; and an
      `أداء المؤشرات الرئيسية` table (المؤشر / القيمة / التغير, values and deltas `text-align: end`).
    - `تفاصيل الأداء حسب خط الأعمال` table — خط الأعمال / إجمالي الإيرادات / % من الإجمالي / التغير /
      هامش الربح, five rows with a total row whose label and first value use `--font-heading`.
    - `الرؤى التنفيذية` (`ph-sparkle`): a 13px `line-height: 1.8` paragraph, three
      `ph-fill ph-check-circle` bullet rows, and a secondary `عرض المنهجية وملاحظات التقرير`.
  - **Right rail — governance:**
    - Tabbed card `التعاون والحوكمة` / `معلومات التقرير`. Comments list: 30px round avatar
      (`flex: none`; reviewer = accent-800 ground + accent-100 initial, commenter = neutral-800 +
      neutral-100), name 12px, role tag (`.tag-accent` مراجع / `.tag-neutral` تعليق), timestamp 10px
      muted pushed with `margin-inline-start: auto`, body 12px muted `line-height: 1.6`. Ghost
      `عرض جميع التعليقات (3) ←`.
    - `سجل الإصدارات`: version number (`dir="ltr"`, `min-width: 26px`), `.tag-accent` الحالي on the
      current one, author, timestamp on the end. Ghost `عرض كل الإصدارات ←`.
    - `الأذونات`: `ph-globe` + `تمت مشاركة التقرير مع 6 أشخاص و 3 مجموعات`.
    - `سجل التدقيق`: three rows, timestamp column `min-width: 92px`, then the event. This log is
      **append-only** on the backend — the UI must never offer edit or delete.

### Client journey (separate flow) — `Khepri Client Journey.dc.html`

A light-theme, self-serve flow for the external client, drawn in both English and Arabic and at two
widths (desktop and narrow). Screens: **Upload your sales data → This is what we read → Working
through your data → Retail Revenue Assessment**, plus an edge-case state board.

Behavioural facts baked into this flow, all from the repo's governance specs — carry them across:
- Intake limit **50 MB**, CSV or **single-sheet** XLSX.
- Nothing is computed until the user confirms the detected columns.
- Sessions expire after **7 days**; the copy promises the link stays live that long, so the backend
  TTL and this string must not drift.
- The result identifies itself by filename, row count analysed, and a timestamp with timezone
  (`sales_2024.csv · 48,207 rows analysed · 12 Aug 2026, 14:22 AST`).
- Body font `IBM Plex Sans Arabic`; monospace meta lines use `IBM Plex Mono`; muted ink `#55606d`;
  the ready state's kicker green is `#1d6b45`.

---

## Charts

All charts are **hand-authored inline SVG with a `viewBox` and `width: 100%; height: auto`** — no
chart library, no fixed pixel sizes. Replace with the codebase's charting library if it can match
this restraint; otherwise keep them as SVG.

Recipe, used identically in all four charts:

```html
<svg viewBox="0 0 320 130" style="width:100%;height:auto;display:block" aria-label="…">
  <polyline points="…" fill="none" stroke="var(--color-accent-500)"
            stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
  <polyline points="… closed back along the baseline …"
            fill="var(--color-accent-500)" fill-opacity="0.10" stroke="none"/>
  <line x1="10" y1="126" x2="310" y2="126"
        stroke="var(--color-neutral-400)" stroke-width="1"/>
</svg>
```

- Stroke 2px `--color-accent-500`; area fill the same colour at **0.10** opacity; a single 1px
  `--color-neutral-400` baseline. No gridlines, no axis ticks, no legend box.
- The report trend chart adds 3px dot markers (3.5px on the latest point).
- Axis labels are a separate `dir="ltr"` flex row with `justify-content: space-between`, 10px muted —
  **one label per data point**, in the same order as the points.
- Charts read **left → right in time** even inside the RTL page. That is intentional for numeric
  series; do not mirror them.
- Give every chart an `aria-label`, and expose the underlying series as a table for screen readers
  (the top-products and KPI tables already do this for two of them).

---

## Interactions & behaviour

**Implemented in the prototype:**
- Screen switching via the mockup tab bar and via in-screen CTAs: home→upload (`ابدأ برفع ملف`),
  home→report (`شاهد مثال تقرير`), upload→quality (`اختيار ملف`), quality→upload (`الرجوع`),
  quality→config (`اعتماد الربط`), config→running (`إنشاء التقرير`), running→report
  (`متابعة في الخلفية`).
- Top-bar nav and icon rail highlight derived from the current screen, not clicked independently:
  الرئيسية is active on home *and* quality; التقارير on config/running/report; مصادر البيانات on upload.
- The progress-bar sheen animation (2.4s linear, infinite).

**To build for real (shown as static states in the prototype):**
- Drag-and-drop upload with dragover styling, file-type and size validation, and per-file progress.
- Type selector, KPI chips, filters, template picker, and date range as real controls with the
  selected styling above.
- Column mapping: each detected column editable via a dropdown of target fields; confidence
  recomputed on change; the `8 من 12 مجال مكتملة` counter and the `اعتماد الربط` button's enabled
  state both derived from required-field completeness.
- Data preview: horizontal scroll, `عرض أول N` selector, search filter, and a problems view behind
  `عرض جميع المشاكل (18)`.
- Generation: poll or stream job progress; the six step states, the percentage, the segment bar, the
  background-activity bars and the ETA all read from one job object. `متابعة في الخلفية` must not
  cancel the job. `إشعار عند الاكتمال` registers a notification.
- Report: real export (PDF / Excel), share dialog with permission scoping, review request, comment
  posting, version switching.
- Error/empty states: failed import (the `فشل الاستيراد` row), multi-sheet XLSX rejection,
  over-limit file, zero valid rows, expired session. The client-journey file's edge-case board is the
  reference for these.

**Accessibility.** Set `lang="ar"` `dir="rtl"` on the document. Status is never colour-only — every
glyph has a legend entry and needs an accessible name. Keep the `:focus-visible` ring. Body copy must
not use `--color-accent` directly on either ground (the accent pair is tuned to ~3:1, enough for
icons, large text and chrome only) — use `--color-accent-300` on the dark ground.

## Responsive behaviour

The prototype is authored at a **1520px** app window. The spec below is the agreed adaptation — build
to it; nothing here is left to interpretation.

### Breakpoints

| Name | Range | Target |
| --- | --- | --- |
| `xl` | ≥ 1520px | The design as drawn. Window capped at `min(1520px, 100%)`; the surplus is page margin. |
| `lg` | 1280–1519px | Same structure, fluid width. No column counts change. |
| `md` | 1024–1279px | Two-column reflow. |
| `sm` | 768–1023px | Single-column reflow; rail collapses. |
| `xs` | < 768px | Mobile. Operator screens are **not supported** below 768px — see below. |

Use `min-width` (mobile-first) media queries, or container queries on the app-content element if the
codebase supports them. Container queries are the better fit here: the rail and top bar make the
content column narrower than the viewport, and every grid below reflows off the *content* width, not
the window width.

### Shell

| Element | `lg`+ | `md` | `sm` | `xs` |
| --- | --- | --- | --- | --- |
| Page padding | `clamp(16px, 2.2vw, 40px)` | 24px | 16px | 12px |
| Window radius | `--radius-lg` | `--radius-lg` | `--radius-md` | 0 (full-bleed) |
| Window shadow | `--shadow-lg` | `--shadow-lg` | `--shadow-md` | none |
| Top bar height | 60px | 60px | 56px | 52px |
| Top-bar nav | all 5 items | all 5 items | first 3 + overflow `⋯` | hamburger drawer only |
| User chip | avatar + name + caret | avatar + name + caret | avatar only | avatar only |
| Icon rail | 60px, visible | 60px, visible | hidden; folded into the drawer | hidden |
| Content padding | `var(--space-8)` | `var(--space-8)` | `var(--space-6)` | `var(--space-4)` |
| Content `min-height` | 880px | 880px | none | none |

The rail and the top-bar nav are the same navigation. At `sm` and below they merge into one drawer
that opens from the **inline-start (right) edge** in RTL, 280px wide, over a
`rgba(0,0,0,0.55)` backdrop. Close on backdrop click, `Esc`, and route change. Trap focus while open.

### Grid reflow — the full table

Every multi-column grid in the design, and what it becomes:

| Screen | Grid | `lg`+ | `md` | `sm` and below |
| --- | --- | --- | --- | --- |
| Home | hero row | `1fr 1fr` | 1 col (copy above card) | 1 col |
| Home | report-card KPI strip | `repeat(4,1fr)` | `repeat(2,1fr)` | `repeat(2,1fr)` |
| Home | report-card body | `1.15fr 1fr` | 1 col (chart above table) | 1 col |
| Home | three feature cards | `repeat(3,1fr)` | `repeat(2,1fr)`, third spans both | 1 col |
| Home | steps inside card 2 | `repeat(3,1fr)` | `repeat(3,1fr)` | 1 col, left-aligned rows |
| Home | trust bar | `repeat(5,1fr)` | `repeat(3,1fr)` | `repeat(2,1fr)` |
| Upload | stat cards | `repeat(3,1fr)` | `repeat(3,1fr)` | 1 col |
| Upload | new-upload card | `1fr 1px 1.35fr` | 1 col; **drop the 1px divider column**, use a `border-top` between the halves; drop zone first | same |
| Upload | file-type cards | `1fr 1fr` | `1fr 1fr` | `1fr 1fr` (keep — they are short) |
| Quality | body | `1.6fr 1fr` | 1 col (preview above mapping) | 1 col |
| Quality | stepper | one row, 5 steps | one row, labels hidden below the numerals | current step + `3 / 5` counter only |
| Quality | issues + summary | `1.25fr 1fr` | `1.25fr 1fr` | 1 col |
| Quality | quality-summary tiles | `1fr 1fr` | `1fr 1fr` | `1fr 1fr` |
| Quality | mapping rows | `1fr 1fr auto` | `1fr 1fr auto` | 2 rows: target over source, confidence tag on the first row's end |
| Config | body | `1.75fr 1fr` | 1 col (rail moves **below** the form) | 1 col |
| Config | type + date halves | `1fr 1fr` | `1fr 1fr` | 1 col |
| Config | report-type cards | `1fr 1fr` | `1fr 1fr` | `1fr 1fr` |
| Config | output strip | `repeat(3,1fr)` | `repeat(3,1fr)` | 1 col |
| Config | template picker | `repeat(5,1fr)` | `repeat(3,1fr)` | `repeat(2,1fr)` |
| Generating | progress card | `auto 1fr` | 1 col (ETA block above the bar) | 1 col |
| Generating | six step icons | `repeat(6,1fr)` | `repeat(3,1fr)` | `repeat(2,1fr)` |
| Generating | lower row | `1fr 1.6fr` | 1 col (preview above activities) | 1 col |
| Generating | live-preview tiles | `1fr 1fr 1.2fr` | `1fr 1fr`, summary spans both | 1 col |
| Generating | chart + segment row | `1fr 1fr` | 1 col | 1 col |
| Report | KPI row | `repeat(5,1fr)` | `repeat(3,1fr)` | `repeat(2,1fr)` |
| Report | body | `1.65fr 1fr` | 1 col (governance rail **below** the report) | 1 col |
| Report | chart + KPI table | `1.1fr 1fr` | 1 col | 1 col |

Rule for every collapse: **content order in the DOM is already the correct reading order**, so a
grid → single column change needs no reordering. The three exceptions are called out above (upload
drop zone first; config and report side rails move below).

### Tables

The data-preview table already sits in `overflow-x: auto` with `min-width: 780px` — keep that at every
width; horizontal scroll is correct for a spreadsheet preview. Add a fading edge shadow on the
scrollable side so the cut is legible, and keep `رقم الفاتورة` as a sticky inline-start column at `md`
and below.

The other tables (recent files, KPI performance, business lines) are **narrative** tables, not
spreadsheets. Below `md` convert each row to a stacked label/value card rather than scrolling:
filename as the card title, remaining fields as `label · value` rows, the status tag on the title row's
end.

### Type and spacing scaling

Only the display sizes move; the 10–14px interface sizes stay fixed at every width.

| Element | `lg`+ | `md` | `sm` | `xs` |
| --- | --- | --- | --- | --- |
| Home hero H1 | 46px | 38px | 32px | 28px |
| Screen H2 | 28px (system) | 26px | 24px | 22px |
| Generating `78%` | 34px | 34px | 30px | 28px |
| KPI values (report) | 26px | 26px | 24px | 22px |
| Stat values (upload) | 30px | 30px | 26px | 24px |

Spacing: at `sm` and below, step every `var(--space-8)` gap down to `var(--space-6)`, and every
`var(--space-6)` down to `var(--space-4)`. Do not touch `--space-1..3`.

### Touch targets

Below `md`, every interactive element gets a **minimum 44×44px** hit area: the row menus
(`ph-dots-three`), the top-bar icon buttons, the tab-strip tabs, the KPI chips, and the mapping-row
confidence controls. Grow the padding, not the font size.

### Mobile scope (`xs`)

The operator screens are dense analytical surfaces; below 768px they are **out of scope** rather than
squeezed. At `xs` show, per screen:

- **Home** — full support (hero, KPI strip 2-up, cards stacked).
- **Upload** — full support; the drop zone becomes a file picker button.
- **Generating** — full support (progress, steps 2-up, activity bars).
- **Report** — read-only support: KPIs, insights, and the governance rail. The business-lines table
  becomes stacked cards. Export and share stay available.
- **Quality review** and **Config** — **not supported.** Show a full-panel message directing the user
  to a wider screen (`يتطلب هذا الإجراء شاشة أوسع`, with the reason and a link back to the report
  list). Column mapping and report configuration are precision tasks; a bad small-screen version of
  them causes wrong reports, which is worse than not offering them.

The **client journey** is the opposite case: it is a public, self-serve flow and must work fully at
every width down to 360px. Its narrow-width layouts are already drawn in
`Khepri Client Journey.dc.html` — use those, not an interpolation of the desktop ones.

### RTL and responsive together

Because every offset is a logical property, no breakpoint needs an RTL-specific rule. Two things to
watch: the drawer opens from the inline-**start** edge (visually right), and the table's sticky column
and scroll-fade shadow must both follow `direction`, not a hard-coded side.

## State management

```
screen:        'home' | 'upload' | 'quality' | 'config' | 'running' | 'report'
upload:        { file, type: 'excel'|'csv', progress, error }
qualityReport: { totalRows, validRows, warnings, criticalIssues, issues[] }
mapping:       [{ targetField, required, sourceColumn, sourceType, confidence }]
reportConfig:  { type, dateRange:{from,to}, comparison, kpis[], filters{}, outputFormat,
                 language, grouping, template }
job:           { percent, etaMinutes, steps[6]{name,status}, activities[]{label,percent,status} }
report:        { version, updatedAt, kpis[], series[], lines[], insights[],
                 comments[], versions[], permissions, auditLog[] }
```

In the prototype `screen` is the only live state (a `useState`-equivalent on the logic class, falling
back to the `startScreen` prop). Everything else is literal markup.

## Props exposed by the prototype (mockup controls, not product features)

| Prop | Type | Default | Effect |
| --- | --- | --- | --- |
| `startScreen` | enum of the six screen keys | `home` | Which screen renders first |
| `showTrustBar` | boolean | `true` | Shows the five-item compliance strip on Home |

## Content & data

All Arabic copy in these files is **final and must be carried across verbatim** — headings, button
labels, helper text, legends, footnotes and the executive-insight paragraphs.

All numbers are **illustrative sample data**, chosen to be plausible: revenue 12.84M SAR, margin
18.0%, 7,542 rows with 6,812 valid / 612 warnings / 118 critical, 48,207 rows in the client journey.
Replace with real values; keep the formats — Latin numerals, thousands separators, one decimal for
percentages, two for currency, ISO `YYYY-MM-DD` after normalisation.

## Assets

- **No image assets.** Every visual is CSS, inline SVG, or a Phosphor icon.
- **Phosphor Icons** — https://phosphoricons.com — loaded from
  `https://unpkg.com/@phosphor-icons/web@2.1.1/src/{regular,fill}/style.css`. Bundle the icon set
  locally in production rather than hotlinking a CDN.
- **IBM Plex Sans Arabic** (400/500/600) from Google Fonts; **IBM Plex Mono** for meta lines in the
  client journey. Self-host both.
- `docs/assets/khepri-logo.png` in the source repo is an ornate render and is deliberately **not**
  used in the product UI; the scarab icon glyph stands in for the brand at interface scale.

## Design system

Nocturne — the stylesheet is included at
`design-files/_ds/nocturne-3819359e-e402-4ee9-a5e9-8d624afd2a9b/styles.css`, with the system's own
guide alongside it as `readme.md`. Read that guide before implementing: it defines the button
philosophy (outlined, not filled), the ramp discipline, the no-pure-black/white rule, and the
"accent as a line and a glow, never a flood" constraint. Every value in this handoff traces back to a
token in that file. If the target codebase already has a design system, map the tokens onto it rather
than importing this stylesheet — but keep the ramp relationships.

## Files

| File | What it is |
| --- | --- |
| `design-files/Khepri App.dc.html` | The six operator screens (this document's main subject) |
| `design-files/Khepri Client Journey.dc.html` | The external-client flow, EN + AR, two widths, plus the edge-case state board |
| `design-files/_ds/nocturne-…/styles.css` | Nocturne token sheet + component layer |
| `design-files/_ds/nocturne-…/readme.md` | Nocturne's own usage guide |
| `design-files/_ds/nocturne-…/_ds_bundle.js` | Nocturne component bundle (needed only to open the prototypes) |
| `design-files/support.js` | Prototype runtime. **Do not port.** Present only so the HTML opens in a browser. |
| `screenshots/` | Rendered PNGs of every screen at design width (see below) |

### Screenshots

Captured at the design width, 1:1, no scaling. Use them for visual diffing while implementing.

| File | Screen |
| --- | --- |
| `01-home.png` | Home — 1520px |
| `02-upload.png` | Upload — 1520px |
| `03-quality.png` | Column & quality review (light surface) — 1520px |
| `04-config.png` | Report configuration — 1520px |
| `05-generating.png` | Generating — 1520px |
| `06-final-report.png` | Final report (light surface) — 1520px |
| `07-client-A1-upload.png` | Client journey, direction A (document), step 1, EN — 1180px |
| `08-client-A2-review.png` | Client journey, direction A, step 2 (column confirmation), EN |
| `09-client-A3-analysing.png` | Client journey, direction A, step 3 (processing), EN |
| `10-client-A4-report.png` | Client journey, direction A, step 4 (assessment), EN |
| `11-client-A1-upload-AR.png` | Client journey, direction A, step 1, **AR** — the RTL counterpart |
| `12-client-B-console-report.png` | Client journey, direction B (console) — the alternative direction |

Direction A (document) is the recommended client-journey direction; B is kept for reference.

To view a prototype: open the `.dc.html` file directly in a browser (it needs its sibling
`support.js` and `_ds/` folder in place).

## Source repository

`Kemetra/Khepri` (branch `main`). The designs were grounded in that repo's RRA governance
specifications, `src/khepri/rra/intake.py` (intake limits), `api.py` / `sessions.py` (job and session
handling), and `rendering/templates/report.css` (report palette). See `github.md` at the project root
for the screen-to-source map.
