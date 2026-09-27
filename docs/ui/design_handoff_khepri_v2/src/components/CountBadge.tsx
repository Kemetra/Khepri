import * as React from "react";
import { cx } from "../lib/cx";
import type { Tone } from "../lib/tone";

export interface CountBadgeProps {
  /** Number to show (e.g. step index, section count, tasks due). */
  value: number | string;
  /** Colour. Default "gold" (sand circle with gold numeral). */
  tone?: Tone;
  /** "soft" = tinted circle; "solid" = filled circle with white numeral. */
  variant?: "soft" | "solid";
}

/** Small round numeric badge used beside card titles, in numbered lists and ranked findings. */
export function CountBadge({ value, tone = "gold", variant = "soft" }: CountBadgeProps) {
  return <span className={cx("k-count", `k-tone-${tone}`, variant === "solid" && "k-count--solid")}>{value}</span>;
}
