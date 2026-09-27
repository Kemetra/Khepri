/** Default series colours, in order (token-backed). */
export const SERIES_COLORS = [
  "var(--k-chart-1)", "var(--k-chart-2)", "var(--k-chart-3)",
  "var(--k-chart-4)", "var(--k-chart-5)", "var(--k-chart-6)",
];

export interface ChartSeries {
  /** Legend name, e.g. "التحليلات المنفذة". */
  name: string;
  /** One value per label. `null` leaves a gap. */
  data: Array<number | null>;
  /** CSS colour; defaults to the next `--k-chart-*` token. */
  color?: string;
}

/** Rounds a max value up to a clean axis ceiling. */
export function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return step * p;
}

export function fmt(v: number): string {
  return Number.isInteger(v) ? v.toLocaleString("en-US") : v.toLocaleString("en-US", { maximumFractionDigits: 1 });
}

/** Evenly spaced axis ticks with a "nice" step (1, 2, 2.5, 5 x 10^k) that divides `max`. */
export function niceTicks(max: number): number[] {
  const isNice = (s: number) => {
    const p = Math.pow(10, Math.floor(Math.log10(s)));
    return [1, 2, 2.5, 5, 10].some((m) => Math.abs(s / p - m) < 1e-9);
  };
  const n = [4, 5, 3, 6, 2].find((k) => isNice(max / k)) ?? 4;
  return Array.from({ length: n + 1 }, (_, i) => (max / n) * i);
}
