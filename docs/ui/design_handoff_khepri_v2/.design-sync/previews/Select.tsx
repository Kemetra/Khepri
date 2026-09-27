import * as React from "react";
import { Select } from "@khepri/ds";

export const FormSelects = () => (
  <div className="k-stack" style={{ maxWidth: 360 }}>
    <Select label="فترة التقرير" required icon="calendar" options={[{ value: "a", label: "2020 - 2024" }, { value: "b", label: "2015 - 2019" }]} />
    <Select label="لغة التحليل" required icon="globe" hint="سيتم إنشاء النتائج والتقارير باللغة العربية." options={[{ value: "ar", label: "العربية" }, { value: "en", label: "English" }]} />
  </div>
);

export const FilterBar = () => (
  <div className="k-row" style={{ maxWidth: 760 }}>
    <Select caption="الفترة الزمنية" options={[{ value: "all", label: "الكل" }]} style={{ minWidth: 140 }} />
    <Select caption="النطاق الجغرافي" options={[{ value: "all", label: "الكل" }]} />
    <Select caption="نوع المصدر" options={[{ value: "all", label: "الكل" }]} />
    <Select caption="جودة المصدر" options={[{ value: "all", label: "الكل" }]} />
  </div>
);

export const CompactFilters = () => (
  <div className="k-row">
    <Select size="sm" icon="database" options={[{ value: "all", label: "جميع البيانات" }]} />
    <Select size="sm" icon="retry" options={[{ value: "all", label: "جميع حالات التحليل" }]} />
    <Select size="sm" options={[{ value: "6m", label: "آخر 6 أشهر" }, { value: "12m", label: "آخر 12 شهر" }]} />
  </div>
);
