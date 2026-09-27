import * as React from "react";
import { ProgressRing } from "@khepri/ds";

export const Coverage = () => (
  <div className="k-row" style={{ gap: 20 }}>
    <ProgressRing value={87} size={48} />
    <ProgressRing value={68} size={48} />
    <ProgressRing value={55} size={48} />
    <ProgressRing value={42} size={48} />
  </div>
);

export const HeroGauge = () => (
  <div className="k-row" style={{ gap: 32 }}>
    <ProgressRing value={87} size={150} caption="جاهز للمراجعة" />
    <ProgressRing value={92} size={120} tone="teal" caption="جودة البيانات" />
  </div>
);
