import * as React from "react";
import { cx } from "../lib/cx";

export interface ConfidenceBadgeProps {
  /** Confidence percentage, 0-100. */
  value: number;
  /** Override the level; otherwise >= 80 high, >= 60 medium, else low. */
  level?: "high" | "medium" | "low";
}

const LABEL = { high: "ثقة عالية", medium: "ثقة متوسطة", low: "ثقة منخفضة" } as const;

/** Evidence-confidence chip: "ثقة عالية 92%" (green), "ثقة متوسطة" (amber), "ثقة منخفضة" (red). */
export function ConfidenceBadge({ value, level }: ConfidenceBadgeProps) {
  const l = level ?? (value >= 80 ? "high" : value >= 60 ? "medium" : "low");
  return (
    <span className={cx("k-confidence", `k-confidence--${l}`)}>
      <span className="k-confidence__dot" />
      <span>{LABEL[l]}</span>
      <strong><bdi>{Math.round(value)}%</bdi></strong>
    </span>
  );
}
