import * as React from "react";
import { Stepper, StatusPill } from "@khepri/ds";

export const UploadWizard = () => (
  <div style={{ maxWidth: 980 }}>
    <Stepper
      current={0}
      steps={[
        { label: "رفع البيانات", description: "إضافة الملفات والمصادر" },
        { label: "تهيئة البيانات", description: "معاينة وربط الحقول" },
        { label: "إعداد التحليل", description: "تحديد المتغيرات والخيارات" },
        { label: "مراجعة", description: "مراجعة الإعدادات" },
        { label: "بدء التحليل", description: "معالجة البيانات وإنتاج النتائج" },
      ]}
    />
  </div>
);

export const MidWizard = () => (
  <div style={{ maxWidth: 720 }}>
    <Stepper
      current={2}
      steps={[{ label: "رفع البيانات" }, { label: "مواءمة الحقول" }, { label: "فحص الجودة" }, { label: "المراجعة والاعتماد" }]}
    />
  </div>
);

export const RunPipeline = () => (
  <div style={{ maxWidth: 900 }}>
    <Stepper
      variant="icon"
      current={2}
      steps={[
        { label: "استيعاب البيانات", meta: <><StatusPill status="complete" size="sm" /><span>5/5 مجموعات</span></> },
        { label: "التحقق من البيانات", meta: <><StatusPill status="complete" size="sm" /><span>124 قاعدة</span></> },
        { label: "تنفيذ النماذج", icon: "cog", meta: <><StatusPill status="running" size="sm" /><span>3/4 نماذج</span></> },
        { label: "تقييم الأدلة", icon: "file", meta: <><StatusPill status="waiting" size="sm" /><span>0/3 مهام</span></> },
        { label: "إعداد المسودة", icon: "edit", meta: <><StatusPill status="waiting" size="sm" /><span>0/2 مهام</span></> },
        { label: "المراجعة النهائية", icon: "search", meta: <><StatusPill status="waiting" size="sm" /><span>0/1 مهام</span></> },
      ]}
    />
  </div>
);
