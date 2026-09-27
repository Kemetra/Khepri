import * as React from "react";
import { Card, LinkButton, TaskItem, Select, FileRow } from "@khepri/ds";

export const WithCountAndLink = () => (
  <div style={{ maxWidth: 400 }}>
    <Card title="المهام القادمة" count={4} actions={<LinkButton>عرض جميع المهام</LinkButton>}>
      <TaskItem title="مراجعة نتائج تحليل جودة الهواء" due="مستحق اليوم" urgency="today" />
      <TaskItem title="إضافة مجموعة بيانات جديدة" due="مستحق غداً" />
      <TaskItem title="مراجعة مسودة التقرير الشهري" due="خلال 3 أيام" />
    </Card>
  </div>
);

export const IconAndDescription = () => (
  <div style={{ maxWidth: 400 }}>
    <Card title="المجموعات البيانية المرفوعة" icon="database" description="آخر الملفات التي تمت معالجتها" actions={<Select size="sm" options={[{ value: "all", label: "الكل" }]} />}>
      <FileRow name="بيانات جودة الهواء 2020-2024" kind="csv" size="245 MB" date="2025/04/20" />
      <FileRow name="مؤشرات الطاقة المتجددة" kind="xlsx" size="128 MB" date="2025/04/18" />
    </Card>
  </div>
);

export const Highlighted = () => (
  <div style={{ maxWidth: 400 }}>
    <Card highlighted title="ملخص التحليل" icon="file">
      <p className="k-muted">تحليل أثر التوسع في الطاقة المتجددة على جودة الهواء في القاهرة الكبرى.</p>
    </Card>
  </div>
);
