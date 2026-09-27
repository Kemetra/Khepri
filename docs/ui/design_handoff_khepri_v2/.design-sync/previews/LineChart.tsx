import * as React from "react";
import { LineChart } from "@khepri/ds";

export const AnalysesTrend = () => (
  <div style={{ maxWidth: 560 }}>
    <LineChart
      area
      labels={["نوفمبر", "ديسمبر", "يناير", "فبراير", "مارس", "أبريل"]}
      series={[
        { name: "التحليلات المنفذة", data: [5, 8, 12, 17, 20, 27] },
        { name: "النتائج المستخلصة", data: [10, 14, 20, 24, 28, 36] },
      ]}
      yMax={40}
    />
  </div>
);

export const GdpContribution = () => (
  <div style={{ maxWidth: 560 }}>
    <LineChart
      area
      showValues
      valueSuffix="%"
      labels={["2020", "2021", "2022", "2023", "2024"]}
      series={[{ name: "مساهمة الطاقة المتجددة في الناتج المحلي", data: [0.8, 1.0, 1.3, 1.6, 1.8], color: "var(--k-chart-2)" }]}
      yMax={2.5}
    />
  </div>
);

export const ResourceUsage = () => (
  <div className="k-grid-3" style={{ maxWidth: 640 }}>
    <LineChart height={140} area showPoints={false} valueSuffix="%" yMax={100} labels={["", "", "", "", "", "", ""]}
      series={[{ name: "المعالج", data: [52, 60, 55, 68, 62, 70, 68], color: "var(--k-chart-2)" }]} />
    <LineChart height={140} area showPoints={false} valueSuffix="%" yMax={100} labels={["", "", "", "", "", "", ""]}
      series={[{ name: "الذاكرة", data: [30, 38, 45, 52, 58, 66, 72], color: "var(--k-chart-3)" }]} />
    <LineChart height={140} area showPoints={false} valueSuffix="%" yMax={100} labels={["", "", "", "", "", "", ""]}
      series={[{ name: "التخزين", data: [12, 15, 14, 20, 22, 25, 28], color: "var(--k-chart-4)" }]} />
  </div>
);
