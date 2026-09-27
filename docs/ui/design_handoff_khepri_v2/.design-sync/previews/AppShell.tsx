import * as React from "react";
import { AppShell, Sidebar, TopBar, PageHeader, Button, StatTile, Card, DonutChart } from "@khepri/ds";

export const HomeDashboard = () => (
  <div style={{ width: 1280, height: 820, overflow: "hidden" }}>
    <AppShell
      sidebar={<Sidebar activeId="home" />}
      topbar={
        <TopBar
          workspace={{ name: "البيئة والسياسات العامة", subtitle: "Environment & Public Policy" }}
          user={{ name: "سارة أحمد", role: "مدير التحليلات" }}
          hasNotifications
        />
      }
    >
      <PageHeader title="مرحباً سارة" subtitle="هنا نظرة عامة على تقدم أعمال التحليل في مساحة العمل الحالية." actions={<Button icon="plus">تحليل جديد</Button>} />
      <div className="k-grid-4">
        <StatTile value="87%" label="تغطية الأدلة" caption="من المصادر الموثوقة" delta="+12%" icon="pie-chart" tone="amber" />
        <StatTile value="12" label="تحليلاً منفذاً" caption="7 مكتملة بنجاح" delta="+3" icon="check-circle" tone="green" />
        <StatTile value="5" label="مجموعات بيانات" caption="تم رفعها ومعالجتها" delta="+1" icon="database" tone="blue" />
        <StatTile value="24" label="نتيجة رئيسية" caption="عبر جميع التحليلات" delta="+6" icon="lightbulb" tone="amber" />
      </div>
      <div className="k-grid-2">
        <Card title="حالة التحليلات">
          <DonutChart centerLabel="إجمالي التحليلات" segments={[
            { label: "مكتملة بنجاح", value: 7, color: "var(--k-green)" },
            { label: "قيد التنفيذ", value: 2, color: "var(--k-blue)" },
            { label: "مراجعة النتائج", value: 2, color: "var(--k-amber)" },
            { label: "متوقفة", value: 1, color: "var(--k-red)" },
          ]} />
        </Card>
        <Card title="أحدث تقرير منشور" icon="report">
          <p className="k-muted">تقرير: أثر سياسات الطاقة المتجددة على النمو الاقتصادي في مصر.</p>
        </Card>
      </div>
    </AppShell>
  </div>
);
