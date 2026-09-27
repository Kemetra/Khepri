import * as React from "react";
import { TaskItem } from "@khepri/ds";

export const UpcomingTasks = () => (
  <div style={{ maxWidth: 380 }}>
    <TaskItem title="مراجعة نتائج تحليل جودة الهواء" due="مستحق اليوم" urgency="today" />
    <TaskItem title="إضافة مجموعة بيانات جديدة" due="مستحق غداً" urgency="soon" />
    <TaskItem title="مراجعة مسودة التقرير الشهري" due="خلال 3 أيام" />
    <TaskItem title="تحديث مصادر الأدلة" due="خلال 5 أيام" />
  </div>
);

export const Completed = () => (
  <div style={{ maxWidth: 380 }}>
    <TaskItem title="رفع بيانات الطاقة 2024" due="أمس" done />
    <TaskItem title="اعتماد مواءمة الحقول" due="قبل يومين" done />
  </div>
);
