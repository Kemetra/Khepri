import * as React from "react";
import { KeyValueList, StatusPill } from "@khepri/ds";

export const ReportInfo = () => (
  <div style={{ maxWidth: 300 }}>
    <KeyValueList
      items={[
        { icon: "calendar", label: "تاريخ النشر", value: "2025/04/21 10:32 م" },
        { icon: "layers", label: "النسخة", value: "v1.0 (النهائي)" },
        { icon: "shield", label: "تصنيف التقرير", value: "عام - قابل للمشاركة" },
        { icon: "leaf", label: "المجال", value: "البيئة والسياسات العامة" },
        { icon: "file", label: "عدد الصفحات", value: "48 صفحة" },
        { icon: "database", label: "المجموعات البيانية", value: "12 مجموعة بيانات" },
      ]}
    />
  </div>
);

export const RunInfo = () => (
  <div style={{ maxWidth: 280 }}>
    <KeyValueList
      layout="stacked"
      items={[
        { icon: "hash", label: "معرف التنفيذ", value: <bdi>#RUN-2025-0421-001</bdi> },
        { icon: "analyses", label: "نوع التحليل", value: "تحليل أثر السياسات" },
        { icon: "database", label: "البيانات المستخدمة", value: "5 مجموعات بيانات" },
        { icon: "clock", label: "الوقت المنقضي", value: "28 دقيقة" },
        { icon: "gauge", label: "الحالة", value: <StatusPill status="running" size="sm" /> },
      ]}
    />
  </div>
);
