import * as React from "react";
import { AnalysisCard } from "@khepri/ds";

export const LibraryGrid = () => (
  <div className="k-grid-2" style={{ maxWidth: 640 }}>
    <AnalysisCard
      title="مقارنة سيناريوهات استخدام المياه"
      description="تحليل بدائل استخدام المياه وأثرها الاقتصادي والبيئي."
      icon="file" tone="sky"
      tags={[{ label: "مقارنة السيناريوهات", tone: "blue" }, { label: "الموارد المائية" }]}
      owner={{ name: "أحمد خالد" }} coverage={82} status="complete" lastRun="2025/04/18 ، 09:40 ص"
    />
    <AnalysisCard
      title="تحليل السوق السكني في القاهرة"
      description="دراسة اتجاهات العرض والطلب في سوق العقارات السكنية."
      icon="scenario" tone="red"
      tags={[{ label: "تحليل السوق", tone: "red" }, { label: "العقارات" }]}
      owner={{ name: "د. نادية حسن" }} coverage={68} status="complete" lastRun="2025/04/19 ، 11:20 ص"
    />
  </div>
);

export const Running = () => (
  <div style={{ maxWidth: 320 }}>
    <AnalysisCard
      title="نمذجة سيناريوهات التسعير"
      description="مقارنة تأثير سيناريوهات التعرفة المختلفة على الإيرادات والطلب."
      icon="database" tone="amber"
      tags={[{ label: "التسعير والتعرفة", tone: "amber" }, { label: "السيناريوهات" }]}
      owner={{ name: "محمد علي" }} coverage={72} status="running" lastRun="2025/04/20 ، 03:15 م"
    />
  </div>
);

export const Draft = () => (
  <div style={{ maxWidth: 320 }}>
    <AnalysisCard
      title="تحليل الأثر البيئي للمشاريع"
      description="تقييم الأثر البيئي والاجتماعي لمشاريع البنية التحتية المقترحة."
      icon="leaf" tone="green"
      tags={[{ label: "السياسات والأثر", tone: "red" }, { label: "البيئة", tone: "blue" }]}
      owner={{ name: "سارة أحمد" }} coverage={55} status="draft" lastRun="2025/04/17 ، 02:18 م"
    />
  </div>
);
