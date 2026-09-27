import * as React from "react";
import { PageHeader, Button, Stepper, Tabs } from "@khepri/ds";

export const Welcome = () => (
  <div style={{ maxWidth: 1000 }}>
    <PageHeader
      title="مرحباً سارة"
      subtitle="هنا نظرة عامة على تقدم أعمال التحليل في مساحة العمل الحالية."
      actions={<Button icon="plus">تحليل جديد</Button>}
    />
  </div>
);

export const WithStepper = () => (
  <div style={{ maxWidth: 1000 }}>
    <PageHeader
      size="compact"
      icon="upload-cloud"
      title="رفع البيانات"
      subtitle="ارفع بياناتك لبدء تحليل جديد وتحويلها إلى رؤى قابلة للتنفيذ."
    >
      <Stepper current={0} steps={[{ label: "رفع البيانات" }, { label: "تهيئة البيانات" }, { label: "إعداد التحليل" }, { label: "مراجعة" }]} />
    </PageHeader>
  </div>
);

export const WithTabs = () => (
  <div style={{ maxWidth: 1000 }}>
    <PageHeader
      icon="trend-up"
      title="النتائج الرئيسية"
      subtitle="ملخص تنفيذي لأهم النتائج المستخلصة من التحليلات."
      actions={<Button icon="download">تصدير التقرير</Button>}
    >
      <Tabs activeId="top" items={[{ id: "top", label: "أهم النتائج", icon: "lightbulb" }, { id: "t", label: "الاتجاهات", icon: "list" }, { id: "a", label: "الشذوذات", icon: "alert" }]} />
    </PageHeader>
  </div>
);

export const Plain = () => (
  <div style={{ maxWidth: 1000 }}>
    <PageHeader image={null} icon="file" title="بناء التقرير" subtitle="أنشئ تقريراً احترافياً مدعوماً بالبيانات والتحليلات والأدلة." size="compact" />
  </div>
);
