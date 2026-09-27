import * as React from "react";
import { ChartLegend } from "./ChartLegend";
import { SERIES_COLORS } from "./chartUtils";

export interface DonutSegment {
  label: string;
  value: number;
  /** CSS colour; defaults to the `--k-chart-*` sequence. */
  color?: string;
}

export interface DonutChartProps {
  segments: DonutSegment[];
  /** Big figure in the hole (e.g. "12", "19.2 GW"). Default: the total. */
  centerValue?: React.ReactNode;
  /** Caption under the figure ("إجمالي التحليلات"). */
  centerLabel?: React.ReactNode;
  /** Diameter in px. Default 160. */
  size?: number;
  /** Legend placement. Default "side". */
  legend?: "side" | "bottom" | "none";
  /** Legend value column: raw values or percentages. Default "value". */
  legendValue?: "value" | "percent";
}

/** Donut chart with centre total and a dot legend - analysis status breakdown, energy mix. */
export function DonutChart({ segments, centerValue, centerLabel, size = 160, legend = "side", legendValue = "value" }: DonutChartProps) {
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  const stroke = Math.round(size * 0.13);
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const gap = segments.length > 1 ? 2 : 0;
  let offset = 0;
  const colored = segments.map((s, i) => ({ ...s, color: s.color ?? SERIES_COLORS[i % SERIES_COLORS.length] }));
  return (
    <div className={`k-donut k-donut--${legend}`}>
      <span className="k-donut__chart" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={segments.map((s) => `${s.label} ${s.value}`).join("، ")}>
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            {colored.map((s, i) => {
              const len = (s.value / total) * c;
              const el = (
                <circle
                  key={i} cx={size / 2} cy={size / 2} r={r} fill="none" stroke={s.color} strokeWidth={stroke}
                  strokeDasharray={`${Math.max(0, len - gap)} ${c}`} strokeDashoffset={-offset}
                />
              );
              offset += len;
              return el;
            })}
          </g>
        </svg>
        <span className="k-donut__center">
          <strong style={{ fontSize: Math.round(size * 0.17) }}><bdi>{centerValue ?? total}</bdi></strong>
          {centerLabel ? <small>{centerLabel}</small> : null}
        </span>
      </span>
      {legend !== "none" ? (
        <ChartLegend
          layout={legend === "side" ? "column" : "row"}
          items={colored.map((s) => ({
            label: s.label, color: s.color,
            value: legendValue === "percent" ? `${Math.round((s.value / total) * 100)}%` : s.value,
          }))}
        />
      ) : null}
    </div>
  );
}
