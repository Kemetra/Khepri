import * as React from "react";
import { EmptyState, Button } from "@khepri/ds";

export const PinnedAnalyses = () => (
  <div style={{ maxWidth: 440 }}>
    <EmptyState
      icon="folder"
      title="لا توجد تحليلات مثبتة بعد"
      description="قم بتثبيت التحليلات المهمة للوصول السريع إليها من هنا."
      action={<Button size="sm" icon="search">تصفح مكتبة التحليلات</Button>}
    />
  </div>
);

export const NoResults = () => (
  <div style={{ maxWidth: 440 }}>
    <EmptyState icon="search" title="لا توجد نتائج مطابقة" description="جرّب تعديل عوامل التصفية أو كلمات البحث." />
  </div>
);
