import * as React from "react";
import type { Tone } from "../lib/tone";

const TONE_VAR: Record<Tone, string> = {
  gold: "var(--k-gold-500)", teal: "var(--k-teal)", green: "var(--k-green)", blue: "var(--k-blue)",
  sky: "var(--k-sky)", amber: "var(--k-amber)", red: "var(--k-red)", purple: "var(--k-purple)", neutral: "var(--k-subtle)",
};

export interface ProgressRingProps {
  /** 0-100. */
  value: number;
  /** Diameter in px. Default 64 (use 140+ for hero gauges like "87% جاهز للمراجعة"). */
  size?: number;
  /** Ring thickness in px. Default size/9. */
  thickness?: number;
  /** Ring colour. Default: green >= 70, amber >= 50, else red. */
  tone?: Tone;
  /** Caption under the percentage inside the ring (large rings only). */
  caption?: React.ReactNode;
}

function autoTone(v: number): Tone {
  return v >= 70 ? "green" : v >= 50 ? "amber" : "red";
}

/** Circular percentage gauge - evidence coverage on cards, data quality and report readiness. */
export function ProgressRing({ value, size = 64, thickness, tone, caption }: ProgressRingProps) {
  const v = Math.max(0, Math.min(100, value));
  const t = thickness ?? Math.max(4, Math.round(size / 9));
  const r = (size - t) / 2;
  const c = 2 * Math.PI * r;
  const color = TONE_VAR[tone ?? autoTone(v)];
  return (
    <span className="k-ring" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--k-sunken)" strokeWidth={t} />
        <circle
          cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={t} strokeLinecap="round"
          strokeDasharray={`${(v / 100) * c} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <span className="k-ring__label">
        <strong style={{ fontSize: Math.max(11, Math.round(size * 0.24)) }}>{Math.round(v)}%</strong>
        {caption && size >= 100 ? <small>{caption}</small> : null}
      </span>
    </span>
  );
}
