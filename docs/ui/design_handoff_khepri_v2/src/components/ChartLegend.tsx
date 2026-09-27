import * as React from "react";

export interface ChartLegendProps {
  items: Array<{ label: React.ReactNode; color: string; value?: React.ReactNode }>;
  /** "row" wraps horizontally (above charts); "column" stacks (beside donuts). */
  layout?: "row" | "column";
}

/** Dot + label legend used by the Khepri charts; also usable on its own. */
export function ChartLegend({ items, layout = "row" }: ChartLegendProps) {
  return (
    <ul className={`k-legend k-legend--${layout}`}>
      {items.map((it, i) => (
        <li key={i}>
          <span className="k-legend__dot" style={{ background: it.color }} />
          <span className="k-legend__label">{it.label}</span>
          {it.value != null ? <strong className="k-legend__value"><bdi>{it.value}</bdi></strong> : null}
        </li>
      ))}
    </ul>
  );
}
