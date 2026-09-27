import * as React from "react";
import { TextField } from "@khepri/ds";

export const AnalysisName = () => (
  <div style={{ maxWidth: 360 }}>
    <TextField label="اسم التحليل" required defaultValue="تحليل أثر سياسات الطاقة المتجددة" maxLength={100} showCount />
  </div>
);

export const WithIconAndHint = () => (
  <div style={{ maxWidth: 360 }}>
    <TextField label="فترة التقرير" required icon="calendar" defaultValue="2020 - 2024" hint="حدد السنوات المشمولة بالتحليل" />
  </div>
);

export const Error = () => (
  <div style={{ maxWidth: 360 }}>
    <TextField label="البريد الإلكتروني" required defaultValue="sara@" error="أدخل بريداً إلكترونياً صالحاً" />
  </div>
);

export const Empty = () => (
  <div style={{ maxWidth: 360 }}>
    <TextField label="اسم المشروع" placeholder="مثال: أثر السياسات على جودة الهواء" />
  </div>
);
