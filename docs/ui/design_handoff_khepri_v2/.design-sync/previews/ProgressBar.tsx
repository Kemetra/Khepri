import * as React from "react";
import { ProgressBar } from "@khepri/ds";

export const Confidence = () => (
  <div className="k-stack" style={{ maxWidth: 320 }}>
    <ProgressBar value={92} tone="green" label="مستوى الثقة" showValue />
    <ProgressBar value={88} tone="blue" label="مستوى الثقة" showValue />
    <ProgressBar value={81} tone="amber" label="مستوى الثقة" showValue />
    <ProgressBar value={76} tone="purple" label="مستوى الثقة" showValue />
  </div>
);

export const RunProgress = () => (
  <div style={{ maxWidth: 560 }}>
    <ProgressBar value={48} tone="gradient" size="lg" label="التقدم الإجمالي" showValue />
  </div>
);

export const Compact = () => (
  <div className="k-stack" style={{ maxWidth: 200 }}>
    <ProgressBar value={91} tone="green" size="sm" />
    <ProgressBar value={79} tone="amber" size="sm" />
    <ProgressBar value={35} tone="red" size="sm" />
  </div>
);
