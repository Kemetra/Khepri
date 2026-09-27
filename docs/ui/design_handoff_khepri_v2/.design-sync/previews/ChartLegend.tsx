import * as React from "react";
import { ChartLegend } from "@khepri/ds";

export const Row = () => (
  <ChartLegend items={[
    { label: "التحليلات المنفذة", color: "var(--k-chart-1)" },
    { label: "النتائج المستخلصة", color: "var(--k-chart-2)" },
  ]} />
);

export const ColumnWithValues = () => (
  <ChartLegend layout="column" items={[
    { label: "مكتملة بنجاح", color: "var(--k-green)", value: 7 },
    { label: "قيد التنفيذ", color: "var(--k-blue)", value: 2 },
    { label: "مراجعة النتائج", color: "var(--k-amber)", value: 2 },
    { label: "متوقفة", color: "var(--k-red)", value: 1 },
  ]} />
);
