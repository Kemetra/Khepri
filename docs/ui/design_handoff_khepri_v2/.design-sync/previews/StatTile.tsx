import * as React from "react";
import { StatTile } from "@khepri/ds";

export const DashboardRow = () => (
  <div className="k-grid-3" style={{ maxWidth: 820 }}>
    <StatTile value="87%" label="تغطية الأدلة" caption="من المصادر الموثوقة" delta="+12%" icon="pie-chart" tone="amber" />
    <StatTile value="12" label="تحليلاً منفذاً" caption="7 مكتملة بنجاح" delta="+3" icon="check-circle" tone="green" />
    <StatTile value="5" label="مجموعات بيانات" caption="تم رفعها ومعالجتها" delta="+1" icon="database" tone="blue" />
  </div>
);

export const ReportFigures = () => (
  <div className="k-grid-2" style={{ maxWidth: 560 }}>
    <StatTile value="4.2 جيجاوات" label="قدرة مضافة من الطاقة المتجددة" caption="2020 - 2024" delta="+28%" icon="zap" tone="amber" />
    <StatTile value="120 ألف" label="فرصة عمل جديدة" caption="خلال الفترة محل الدراسة" icon="users" tone="blue" />
  </div>
);

export const NegativeDelta = () => (
  <div className="k-grid-2" style={{ maxWidth: 560 }}>
    <StatTile value="4.8%" label="القيم المفقودة إجمالاً" caption="مقارنة بالرفع السابق" delta="-2.1%" trend="down" deltaTone="green" icon="database" tone="blue" />
    <StatTile value="12" label="تنبيهات التحقق" caption="2 حرجة" delta="+4" trend="up" deltaTone="red" icon="alert" tone="red" />
  </div>
);
