import * as React from "react";
import { DonutChart } from "@khepri/ds";

export const AnalysisStatus = () => (
  <DonutChart
    centerLabel="إجمالي التحليلات"
    segments={[
      { label: "مكتملة بنجاح", value: 7, color: "var(--k-green)" },
      { label: "قيد التنفيذ", value: 2, color: "var(--k-blue)" },
      { label: "مراجعة النتائج", value: 2, color: "var(--k-amber)" },
      { label: "متوقفة", value: 1, color: "var(--k-red)" },
    ]}
  />
);

export const EnergyMix = () => (
  <DonutChart
    size={180}
    centerValue="19.2"
    centerLabel="جيجاوات إجمالي القدرة"
    legendValue="percent"
    segments={[
      { label: "الطاقة الشمسية", value: 52, color: "var(--k-chart-2)" },
      { label: "طاقة الرياح", value: 38, color: "var(--k-chart-1)" },
      { label: "الطاقة الكهرومائية", value: 7, color: "var(--k-chart-3)" },
      { label: "مصادر أخرى", value: 3, color: "var(--k-chart-5)" },
    ]}
  />
);

export const LegendBelow = () => (
  <DonutChart
    size={140}
    legend="bottom"
    centerValue="92%"
    centerLabel="متوافقة"
    segments={[
      { label: "متوافقة", value: 18, color: "var(--k-green)" },
      { label: "تحتاج مواءمة", value: 1, color: "var(--k-amber)" },
      { label: "غير معروفة", value: 1, color: "var(--k-subtle)" },
    ]}
  />
);
