import * as React from "react";
import { Icon, iconNames } from "@khepri/ds";

export const Navigation = () => (
  <div className="k-row" style={{ gap: 18, color: "var(--k-muted)" }}>
    <Icon name="home" size={22} />
    <Icon name="analyses" size={22} />
    <Icon name="database" size={22} />
    <Icon name="lightbulb" size={22} />
    <Icon name="file" size={22} />
    <Icon name="report" size={22} />
    <Icon name="history" size={22} />
    <Icon name="settings" size={22} />
  </div>
);

export const FullSet = () => (
  <div style={{ display: "grid", gridTemplateColumns: "repeat(6, 1fr)", gap: 12, maxWidth: 620 }}>
    {iconNames.map((n) => (
      <div key={n} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4, color: "var(--k-gold-600)" }}>
        <Icon name={n} size={20} />
        <span style={{ fontSize: 10, color: "var(--k-muted)", direction: "ltr" }}>{n}</span>
      </div>
    ))}
  </div>
);
