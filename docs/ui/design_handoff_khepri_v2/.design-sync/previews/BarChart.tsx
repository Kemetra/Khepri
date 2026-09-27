import * as React from "react";
import { BarChart } from "@khepri/ds";

export const CapacityStacked = () => (
  <div style={{ maxWidth: 520 }}>
    <BarChart
      stacked
      showValues
      labels={["2020", "2021", "2022", "2023", "2024"]}
      series={[
        { name: "الطاقة الشمسية", data: [0.9, 1.2, 1.4, 1.6, 1.8], color: "var(--k-chart-2)" },
        { name: "الطاقة الكهرومائية", data: [0.7, 0.9, 1.1, 1.2, 1.3], color: "var(--k-chart-1)" },
        { name: "طاقة الرياح", data: [0.5, 0.7, 0.9, 1.1, 1.1], color: "var(--k-chart-3)" },
      ]}
      yMax={5}
    />
  </div>
);

export const GovernorateComparison = () => (
  <div style={{ maxWidth: 560 }}>
    <BarChart
      labels={["القاهرة", "الجيزة", "الإسكندرية", "الدقهلية", "أسوان", "الأقصر"]}
      series={[
        { name: "جودة الهواء", data: [72, 65, 60, 58, 70, 76] },
        { name: "كفاءة المياه", data: [62, 55, 45, 68, 55, 74] },
        { name: "مؤشر الاستدامة", data: [80, 58, 50, 85, 62, 70] },
      ]}
      yMax={100}
    />
  </div>
);

export const MissingValues = () => (
  <div style={{ maxWidth: 480 }}>
    <BarChart
      showValues
      valueSuffix="%"
      labels={["PM2_5", "PM10", "NO2", "SO2", "O3", "الحرارة"]}
      series={[{ name: "القيم المفقودة", data: [25, 12, 4, 3, 2, 1] }]}
      barColors={["#f2a0a0", "#f0b36a", "#9cc0f0", "#9cc0f0", "#9cc0f0", "#9cc0f0"]}
      yMax={30}
    />
  </div>
);
