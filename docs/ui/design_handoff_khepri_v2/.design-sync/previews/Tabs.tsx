import * as React from "react";
import { Tabs } from "@khepri/ds";

export const FindingsTabs = () => (
  <div style={{ maxWidth: 700 }}>
    <Tabs
      activeId="top"
      items={[
        { id: "top", label: "أهم النتائج", icon: "lightbulb" },
        { id: "trends", label: "الاتجاهات", icon: "list" },
        { id: "anomalies", label: "الشذوذات", icon: "alert" },
        { id: "recs", label: "التوصيات", icon: "file" },
      ]}
    />
  </div>
);

export const PanelTabs = () => (
  <div style={{ maxWidth: 320 }}>
    <Tabs
      variant="underline"
      activeId="outline"
      items={[
        { id: "outline", label: "المخطط", icon: "list" },
        { id: "components", label: "المكونات", icon: "grid" },
        { id: "settings", label: "الإعدادات", icon: "settings" },
      ]}
    />
  </div>
);
