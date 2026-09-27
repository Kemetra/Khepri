import * as React from "react";
import { SelectableCard } from "@khepri/ds";

export const Dimensions = () => (
  <div className="k-grid-3" style={{ maxWidth: 520 }}>
    <SelectableCard selected icon="leaf" title="البيئة" description="جودة الهواء، الانبعاثات، الموارد الطبيعية" />
    <SelectableCard selected icon="analyses" title="الاقتصاد" description="التكلفة، الفوائد الاقتصادية، فرص العمل" />
    <SelectableCard icon="users" title="المجتمع" description="الصحة العامة، الرفاهة، جودة الحياة" />
  </div>
);

export const ComparisonGroups = () => (
  <div className="k-stack" style={{ maxWidth: 480, gap: 8 }}>
    <SelectableCard mode="radio" layout="row" selected title="مناطق ذات تطبيق مقابل مناطق دون تطبيق" description="مقارنة بين المناطق التي طبقت التوسع في الطاقة المتجددة والمناطق التي لم تطبق" />
    <SelectableCard mode="radio" layout="row" title="قبل وبعد التطبيق" description="مقارنة لنفس المنطقة عبر فترات زمنية مختلفة" />
    <SelectableCard mode="radio" layout="row" title="مقارنة بين محافظات" description="مقارنة بين محافظات مختلفة" />
  </div>
);
