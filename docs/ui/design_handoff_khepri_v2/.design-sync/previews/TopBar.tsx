import * as React from "react";
import { TopBar } from "@khepri/ds";

export const Full = () => (
  <div style={{ maxWidth: 1100, border: "1px solid var(--k-line)", background: "var(--k-surface)" }}>
    <TopBar
      workspace={{ name: "البيئة والسياسات العامة", subtitle: "Environment & Public Policy" }}
      user={{ name: "سارة أحمد", role: "مدير التحليلات" }}
      hasNotifications
    />
  </div>
);

export const SearchOnly = () => (
  <div style={{ maxWidth: 1100, border: "1px solid var(--k-line)", background: "var(--k-surface)" }}>
    <TopBar searchPlaceholder="البحث في التحليلات، القوالب، المالكين..." user={{ name: "محمد علي", role: "محلل بيانات" }} />
  </div>
);
