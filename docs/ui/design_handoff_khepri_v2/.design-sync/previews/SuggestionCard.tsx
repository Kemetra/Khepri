import * as React from "react";
import { SuggestionCard } from "@khepri/ds";

export const AiSuggestions = () => (
  <div className="k-stack" style={{ maxWidth: 340 }}>
    <SuggestionCard
      icon="lightbulb" tone="amber" title="معالجة القيم المفقودة"
      description="يوجد 8,421 قيمة مفقودة في حقل PM2_5. أقترح استخدام القيم المتوسطة حسب المنطقة الجغرافية."
    />
    <SuggestionCard
      icon="calendar" tone="amber" title="توحيد تنسيق التواريخ"
      description="يوصى بتوحيد تنسيق حقل &quot;التاريخ&quot; إلى YYYY-MM-DD لضمان التوافق."
    />
  </div>
);
