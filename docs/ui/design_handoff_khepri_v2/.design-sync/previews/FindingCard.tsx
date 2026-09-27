import * as React from "react";
import { FindingCard } from "@khepri/ds";

export const KeyFindings = () => (
  <div className="k-grid-2" style={{ maxWidth: 620 }}>
    <FindingCard
      rank={1} tone="green" icon="users" title="تحسن جودة الهواء في المناطق الحضرية"
      description="انخفاض ملحوظ في ملوثات الهواء بنسبة 28% خلال العام الماضي."
      confidence={92} sources="6 مصادر بيانات"
    />
    <FindingCard
      rank={2} tone="blue" icon="globe" title="زيادة فعالية السياسات المائية"
      description="تحسن كفاءة استخدام المياه بنسبة 24% في المحافظات المستهدفة."
      confidence={88} sources="4 مصادر بيانات"
    />
  </div>
);

export const AmberAndPurple = () => (
  <div className="k-grid-2" style={{ maxWidth: 620 }}>
    <FindingCard
      rank={3} tone="amber" icon="coins" title="فرص اقتصادية خضراء واعدة"
      description="إمكانية خلق 45 ألف فرصة عمل جديدة في قطاع الطاقة المتجددة."
      confidence={81} sources="5 مصادر بيانات"
    />
    <FindingCard
      rank={4} tone="purple" icon="alert" title="تفاوت إقليمي في النتائج"
      description="وجود فجوات في الأداء بين المحافظات تتطلب تدخلات موجهة."
      confidence={76} sources="6 مصادر بيانات"
    />
  </div>
);
