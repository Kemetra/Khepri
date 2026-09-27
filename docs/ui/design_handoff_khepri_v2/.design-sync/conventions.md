# Khepri v2 — how to build with this design system

Khepri is an **Arabic-first, right-to-left** analytics product: warm sand canvas, white rounded cards, brand gold for primary actions, teal/green/blue/amber/red for data and status. Every screen text is Arabic unless the user asks otherwise.

## 1. Always wrap in `KhepriProvider`

`KhepriProvider` sets `dir="rtl"`, `lang="ar"`, the Noto Sans Arabic font, base text colour and canvas background. Without it the layout mirrors wrong and text falls back to a system font.

```jsx
const { KhepriProvider, AppShell, Sidebar, TopBar, PageHeader, Button } = window.KhepriDS;
<KhepriProvider>
  <AppShell
    sidebar={<Sidebar activeId="analyses" />}
    topbar={<TopBar workspace={{ name: "البيئة والسياسات العامة", subtitle: "Environment & Public Policy" }}
                    user={{ name: "سارة أحمد", role: "مدير التحليلات" }} hasNotifications />}>
    <PageHeader title="مكتبة التحليلات" subtitle="استعرض التحليلات الجاهزة..." actions={<Button icon="plus">إنشاء تحليل</Button>} />
    {/* page sections */}
  </AppShell>
</KhepriProvider>
```

For an English screen use `<KhepriProvider dir="ltr" lang="en">`. Layout uses logical properties, so components flip automatically.

## 2. Styling idiom: components first, then `k-` helpers and `--k-*` tokens

- Build with the components: `Card` for every section, `StatTile` for KPIs, `StatusPill` for workflow state, `DataTable` with `PrimaryCell` / `StatusPill` / `IconButton icon="more"` cells, `LineChart` / `BarChart` / `DonutChart` / `ProgressRing` for data.
- Icons: every `icon` prop takes a name from `Icon`'s curated set (`home`, `analyses`, `database`, `lightbulb`, `file`, `report`, `history`, `settings`, `plus`, `search`, `download`, `upload-cloud`, `calendar`, `check-circle`, `alert`, `trend-up`, `users`, `leaf`, `zap`, `coins`, `more` …). Do not import other icon sets.
- Colour props take a `Tone`: `gold | teal | green | blue | sky | amber | red | purple | neutral`.
- Layout glue classes (these exist in the CSS): `k-stack` (vertical, 16px gap), `k-row` (horizontal wrap, 12px gap), `k-grid-2`, `k-grid-3`, `k-grid-4`, `k-grid-5` (equal columns), `k-muted`, `k-subtle`. Do not invent other `k-` class names.
- Custom styling uses tokens only: `var(--k-gold-600)`, `--k-gold-100`, `--k-gold-50`, `--k-ink`, `--k-muted`, `--k-subtle`, `--k-canvas`, `--k-surface`, `--k-border`, `--k-line`, `--k-teal`, `--k-green`, `--k-blue`, `--k-amber`, `--k-red`, `--k-purple` (each tone also has `-surface`), `--k-chart-1` … `--k-chart-6`, `--k-space-1`–`--k-space-6`, `--k-space-8`, `--k-radius-md` / `-lg` / `-xl`, `--k-shadow-card`, `--k-text-xs` … `--k-text-display`.

Rules the mockups follow:
- **One gold `primary` Button per view** (e.g. "تحليل جديد", "بدء التنفيذ"). Everything else is `secondary` (cream + gold outline) or `ghost`. Use `danger` only to stop or delete.
- Card headers: title plus an optional `icon`, `count`, and `actions={<LinkButton>عرض الكل</LinkButton>}`.
- Status labels come from `StatusPill status=…` (`complete` مكتمل, `running` قيد التنفيذ, `review` مراجعة النتائج, `stopped`, `draft`, `queued`, `waiting`, `warning`, `ready`, `published`, `compatible`). Do not hand-roll pills.
- Wrap mixed Latin and number values in `<bdi>` (e.g. `<bdi>245 MB</bdi>`) so they don't reorder in RTL.
- Charts draw time left→right (oldest first), even in RTL, as the mockups do.

## 3. Where the truth lives

- `styles.css` → `_ds_bundle.css`: every `k-` class and all `--k-*` tokens (read the `:root` block first).
- `components/<group>/<Name>/<Name>.d.ts`: exact props. `<Name>.prompt.md`: usage and examples.
- Groups: Foundations, Layout, Actions, Data Display, Cards, Forms, Navigation, Charts.

## 4. Example: a dashboard section

```jsx
const { Card, StatTile, DataTable, PrimaryCell, StatusPill, IconButton, LinkButton } = window.KhepriDS;
<div className="k-stack">
  <div className="k-grid-4">
    <StatTile value="87%" label="تغطية الأدلة" caption="من المصادر الموثوقة" delta="+12%" icon="pie-chart" tone="amber" />
    <StatTile value="12" label="تحليلاً منفذاً" caption="7 مكتملة بنجاح" delta="+3" icon="check-circle" tone="green" />
    <StatTile value="5" label="مجموعات بيانات" delta="+1" icon="database" tone="blue" />
    <StatTile value="24" label="نتيجة رئيسية" delta="+6" icon="lightbulb" tone="amber" />
  </div>
  <Card title="التحليلات الحديثة" actions={<LinkButton>عرض الكل</LinkButton>} flush>
    <DataTable rows={rows} columns={[
      { key: "name", header: "الاسم", render: (r) => <PrimaryCell title={r.name} subtitle={r.en} /> },
      { key: "status", header: "الحالة", render: (r) => <StatusPill status={r.status} size="sm" /> },
      { key: "date", header: "تاريخ التنفيذ", numeric: true },
      { key: "menu", header: "", render: () => <IconButton icon="more" label="خيارات" size="sm" /> },
    ]} />
  </Card>
</div>
```
