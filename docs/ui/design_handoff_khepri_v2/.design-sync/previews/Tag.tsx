import * as React from "react";
import { Tag } from "@khepri/ds";

export const CategoryTags = () => (
  <div className="k-row">
    <Tag tone="red">تحليل السوق</Tag>
    <Tag>العقارات</Tag>
    <Tag tone="amber">التسعير والتعرفة</Tag>
    <Tag tone="blue">مقارنة السيناريوهات</Tag>
    <Tag tone="green">الطاقة المتجددة</Tag>
    <Tag tone="purple">السياسات والأثر</Tag>
  </div>
);

export const SelectedVariables = () => (
  <div className="k-row" style={{ maxWidth: 360 }}>
    <Tag tone="green" onRemove={() => {}}>جودة الهواء (PM2.5)</Tag>
    <Tag tone="blue" onRemove={() => {}}>الطاقة المتجددة</Tag>
    <Tag tone="amber" onRemove={() => {}}>انبعاثات CO2</Tag>
    <Tag tone="blue" onRemove={() => {}}>النمو السكاني</Tag>
    <Tag tone="red" onRemove={() => {}}>الناتج المحلي الإجمالي</Tag>
  </div>
);

export const Outline = () => (
  <div className="k-row">
    <Tag variant="outline" tone="blue">تقرير دولي</Tag>
    <Tag variant="outline" tone="green">وثيقة حكومية</Tag>
    <Tag variant="outline">مجموعة بيانات</Tag>
  </div>
);
