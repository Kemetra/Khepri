import * as React from "react";
import { Button } from "@khepri/ds";

export const Variants = () => (
  <div className="k-row">
    <Button icon="plus">تحليل جديد</Button>
    <Button variant="secondary" icon="download">تحميل PDF</Button>
    <Button variant="ghost" icon="share">مشاركة</Button>
    <Button variant="danger" icon="stop">إيقاف التنفيذ</Button>
  </div>
);

export const Sizes = () => (
  <div className="k-row">
    <Button size="sm">تطبيق الاقتراح</Button>
    <Button size="md" icon="check">اعتماد التهيئة</Button>
    <Button size="lg" icon="play">بدء التنفيذ</Button>
  </div>
);

export const FullWidthCta = () => (
  <div style={{ maxWidth: 360 }}>
    <Button size="lg" block trailingIcon="arrow-left">متابعة التهيئة</Button>
  </div>
);

export const States = () => (
  <div className="k-row">
    <Button loading>جاري الحفظ</Button>
    <Button disabled icon="report">عرض التقرير</Button>
    <Button variant="secondary" size="sm">استخدام القالب</Button>
  </div>
);
