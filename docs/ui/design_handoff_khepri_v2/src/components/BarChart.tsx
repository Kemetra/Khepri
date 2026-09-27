import * as React from "react";
import { ChartLegend } from "./ChartLegend";
import { SERIES_COLORS, fmt, niceMax, niceTicks, type ChartSeries } from "./chartUtils";
import { useChartWidth } from "./useChartWidth";

export interface BarChartProps {
  /** Category labels (years, governorates, columns). */
  labels: string[];
  series: ChartSeries[];
  /** Stack series on top of each other instead of grouping side by side. */
  stacked?: boolean;
  /** Per-category colours for a single-series chart (e.g. severity-coloured missing-value bars). */
  barColors?: string[];
  /** Print values above bars (the stack total when stacked). */
  showValues?: boolean;
  valueSuffix?: string;
  yMax?: number;
  /** Height in px (width is fluid). Default 220. */
  height?: number;
  /** Default: shown when there are 2+ series. */
  showLegend?: boolean;
}


/** Grouped or stacked vertical bar chart in SVG - capacity by source, governorate comparison, missing values. */
export function BarChart({ labels, series, stacked, barColors, showValues, valueSuffix = "", yMax, height = 220, showLegend }: BarChartProps) {
  const [ref, W] = useChartWidth();
  const pad = { top: 20, right: 12, bottom: 28, left: 44 };
  const colored = series.map((s, i) => ({ ...s, color: s.color ?? SERIES_COLORS[i % SERIES_COLORS.length] }));
  const totals = labels.map((_, i) => colored.reduce((a, s) => a + (s.data[i] ?? 0), 0));
  const peak = stacked ? Math.max(...totals, 0) : Math.max(...colored.flatMap((s) => s.data.map((v) => v ?? 0)), 0);
  const max = yMax ?? niceMax(peak * 1.12);
  const iw = W - pad.left - pad.right;
  const ih = height - pad.top - pad.bottom;
  const band = iw / Math.max(1, labels.length);
  const groupW = band * 0.62;
  const barW = stacked ? groupW : groupW / colored.length;
  const y = (v: number) => pad.top + ih - (v / max) * ih;
  const ticks = niceTicks(max);
  const legend = showLegend ?? series.length > 1;
  return (
    <div className="k-chart" ref={ref}>
      {legend ? <ChartLegend items={colored.map((s) => ({ label: s.name, color: s.color }))} /> : null}
      <svg viewBox={`0 0 ${W} ${height}`} width="100%" className="k-chart__svg" role="img" aria-label={series.map((s) => s.name).join("، ")}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} className="k-chart__grid" />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end" className="k-chart__tick">{fmt(t)}{valueSuffix}</text>
          </g>
        ))}
        {labels.map((l, i) => {
          const gx = pad.left + band * i + (band - groupW) / 2;
          let acc = 0;
          return (
            <g key={l + i}>
              {colored.map((s, si) => {
                const v = s.data[i] ?? 0;
                const color = barColors && colored.length === 1 ? barColors[i % barColors.length] : s.color;
                const bx = stacked ? gx : gx + si * barW;
                const top = stacked ? y(acc + v) : y(v);
                const h = stacked ? y(acc) - y(acc + v) : y(0) - y(v);
                acc += v;
                const isTop = stacked && si === colored.length - 1;
                return (
                  <g key={si}>
                    <rect x={bx + (stacked ? 0 : 1)} y={top} width={Math.max(2, barW - (stacked ? 0 : 2))} height={Math.max(0, h)} rx={isTop || !stacked ? 3 : 0} fill={color} />
                    {showValues && !stacked && v ? (
                      <text x={bx + barW / 2} y={top - 6} textAnchor="middle" className="k-chart__value" fill={color}>{fmt(v)}{valueSuffix}</text>
                    ) : null}
                  </g>
                );
              })}
              {showValues && stacked ? (
                <text x={gx + groupW / 2} y={y(totals[i]) - 6} textAnchor="middle" className="k-chart__value">{fmt(totals[i])}{valueSuffix}</text>
              ) : null}
              <text x={pad.left + band * i + band / 2} y={height - 8} textAnchor="middle" className="k-chart__tick">{l}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
