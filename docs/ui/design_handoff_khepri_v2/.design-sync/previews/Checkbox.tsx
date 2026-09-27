import * as React from "react";
import { Checkbox } from "@khepri/ds";

export const EvidenceSelection = () => (
  <div className="k-stack">
    <Checkbox defaultChecked label="سياسة الطاقة المتجددة 2030" />
    <Checkbox label="بيانات هيئة الطاقة المتجددة" />
    <Checkbox label="تقرير الوكالة الدولية للطاقة" />
    <Checkbox defaultChecked disabled label="مصدر معتمد (مقفل)" />
  </div>
);
