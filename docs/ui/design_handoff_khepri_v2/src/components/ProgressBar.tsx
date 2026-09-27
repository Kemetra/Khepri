import * as React from "react";
import { cx } from "../lib/cx";
import type { Tone } from "../lib/tone";

export interface ProgressBarProps {
  /** 0-100. */
  value: number;
  /** Bar colour. "gradient" is the gold-to-teal run-progress fill. Default "green". */
  tone?: Tone | "gradient";
  /** Label shown above the bar at inline-start ("مستوى الثقة"). */
  label?: React.ReactNode;
  /** Show the percentage at inline-end. */
  showValue?: boolean;
  /** Track height: sm 6px, md 8px, lg 14px. */
  size?: "sm" | "md" | "lg";
}

/** Horizontal progress / confidence bar with optional label and percentage. */
export function ProgressBar({ value, tone = "green", label, showValue, size = "md" }: ProgressBarProps) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className="k-progress">
      {label != null || showValue ? (
        <div className="k-progress__head">
          <span>{label}</span>
          {showValue ? <strong className={cx("k-progress__value", tone !== "gradient" && `k-text-${tone}`)}>{Math.round(v)}%</strong> : null}
        </div>
      ) : null}
      <div className={cx("k-progress__track", `k-progress__track--${size}`)} role="progressbar" aria-valuenow={v} aria-valuemin={0} aria-valuemax={100}>
        <div className={cx("k-progress__fill", tone === "gradient" ? "k-progress__fill--gradient" : `k-bg-${tone}`)} style={{ inlineSize: `${v}%` }} />
      </div>
    </div>
  );
}
