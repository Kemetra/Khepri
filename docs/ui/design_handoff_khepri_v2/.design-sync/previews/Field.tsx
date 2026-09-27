import * as React from "react";
import { Field } from "@khepri/ds";

export const WrappingCustomControl = () => (
  <div style={{ maxWidth: 360 }}>
    <Field label="نطاق الألوان" required hint="اختر لون السلسلة الأساسية">
      <div className="k-row">
        {["var(--k-chart-1)", "var(--k-chart-2)", "var(--k-chart-3)", "var(--k-chart-4)"].map((c) => (
          <span key={c} style={{ width: 28, height: 28, borderRadius: 8, background: c }} />
        ))}
      </div>
    </Field>
  </div>
);

export const WithError = () => (
  <div style={{ maxWidth: 360 }}>
    <Field label="فترة التقرير" required error="يجب أن تكون سنة البداية قبل سنة النهاية">
      <div className="k-input"><input defaultValue="2024 - 2020" /></div>
    </Field>
  </div>
);
