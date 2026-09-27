import * as React from "react";
import { TextArea } from "@khepri/ds";

export const AnalysisGoal = () => (
  <div style={{ maxWidth: 420 }}>
    <TextArea
      label="الهدف من التحليل" required maxLength={500} showCount
      defaultValue="تقييم أثر سياسات الطاقة المتجددة على الاستهلاك الوطني وتحديد الفرص المستقبلية للنمو."
    />
  </div>
);

export const Placeholder = () => (
  <div style={{ maxWidth: 420 }}>
    <TextArea label="ملاحظات" placeholder="أضف ملاحظات للمراجعين..." rows={4} hint="اختياري" />
  </div>
);
