import * as React from "react";
import { Sidebar } from "@khepri/ds";

export const Default = () => (
  <div style={{ width: 240, height: 640, border: "1px solid var(--k-line)" }}>
    <Sidebar activeId="home" />
  </div>
);

export const ReportActive = () => (
  <div style={{ width: 240, height: 640, border: "1px solid var(--k-line)" }}>
    <Sidebar activeId="report" />
  </div>
);

export const NoFooter = () => (
  <div style={{ width: 240, border: "1px solid var(--k-line)" }}>
    <Sidebar activeId="analyses" hideFooter />
  </div>
);
