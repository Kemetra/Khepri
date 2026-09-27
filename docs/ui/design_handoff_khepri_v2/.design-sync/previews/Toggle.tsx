import * as React from "react";
import { Toggle } from "@khepri/ds";

export const States = () => (
  <div className="k-stack">
    <Toggle defaultChecked label="تطبيق تلقائي للاقتراحات" />
    <Toggle label="إظهار في جدول المحتويات" />
    <Toggle defaultChecked disabled label="حفظ تلقائي" />
  </div>
);
