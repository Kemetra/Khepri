import * as React from "react";
import { ChartLegend } from "./ChartLegend";
import { SERIES_COLORS, fmt, niceMax, niceTicks, type ChartSeries } from "./chartUtils";
import { useChartWidth } from "./useChartWidth";

export interface LineChartProps {
  /** X-axis labels, oldest first (drawn left to right, as in the mockups). */
  labels: string[];
  series: ChartSeries[];
  /** Fill a soft gradient under each line. */
  area?: boolean;
  /** Dots on each data point. Default true. */
  showPoints?: boolean;
  /** Print the value above each point (single-series trend charts). */
  showValues?: boolean;
  /** Suffix for axis ticks and values, e.g. "%". */
  valueSuffix?: string;
  /** Fixed y-axis maximum; default is a clean ceiling above the data. */
  yMax?: number;
  /** Chart height in px (width is fluid). Default 220. */
  height?: number;
  /** Legend above the chart. Default: shown when there are 2+ series. */
  showLegend?: boolean;
}


/** Multi-series line / area chart in hand-drawn SVG - trends, run resource usage, GDP contribution. */
export function LineChart({ labels, series, area, showPoints = true, showValues, valueSuffix = "", yMax, height = 220, showLegend }: LineChartProps) {
  const [ref, W] = useChartWidth();
  const uid = React.useId().replace(/:/g, "");
  const pad = { top: 16, right: 12, bottom: 28, left: 40 };
  const all = series.flatMap((s) => s.data.filter((v): v is number => v != null));
  const max = yMax ?? niceMax(Math.max(...all, 0) * 1.1);
  const iw = W - pad.left - pad.right;
  const ih = height - pad.top - pad.bottom;
  const x = (i: number) => pad.left + (labels.length <= 1 ? iw / 2 : (i * iw) / (labels.length - 1));
  const y = (v: number) => pad.top + ih - (v / max) * ih;
  const ticks = niceTicks(max);
  const colored = series.map((s, i) => ({ ...s, color: s.color ?? SERIES_COLORS[i % SERIES_COLORS.length] }));
  const legend = showLegend ?? series.length > 1;
  return (
    <div className="k-chart" ref={ref}>
      {legend ? <ChartLegend items={colored.map((s) => ({ label: s.name, color: s.color }))} /> : null}
      <svg viewBox={`0 0 ${W} ${height}`} width="100%" className="k-chart__svg" role="img" aria-label={series.map((s) => s.name).join("، ")}>
        <defs>
          {colored.map((s, i) => (
            <linearGradient key={i} id={`${uid}-g${i}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.28" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0.02" />
            </linearGradient>
          ))}
        </defs>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={pad.left} x2={W - pad.right} y1={y(t)} y2={y(t)} className="k-chart__grid" />
            <text x={pad.left - 8} y={y(t) + 4} textAnchor="end" className="k-chart__tick">{fmt(t)}{valueSuffix}</text>
          </g>
        ))}
        {labels.map((l, i) => (
          <text key={l + i} x={x(i)} y={height - 8} textAnchor="middle" className="k-chart__tick">{l}</text>
        ))}
        {colored.map((s, si) => {
          const pts = s.data.map((v, i) => (v == null ? null : [x(i), y(v)] as const)).filter(Boolean) as Array<readonly [number, number]>;
          if (!pts.length) return null;
          const d = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
          const areaD = `${d} L${pts[pts.length - 1][0]},${y(0)} L${pts[0][0]},${y(0)} Z`;
          return (
            <g key={si}>
              {area ? <path d={areaD} fill={`url(#${uid}-g${si})`} /> : null}
              <path d={d} fill="none" stroke={s.color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
              {showPoints ? pts.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r="4" fill={s.color} stroke="#fff" strokeWidth="1.5" />) : null}
              {showValues
                ? s.data.map((v, i) => (v == null ? null : (
                    <text key={i} x={x(i)} y={y(v) - 10} textAnchor="middle" className="k-chart__value">{fmt(v)}{valueSuffix}</text>
                  )))
                : null}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
