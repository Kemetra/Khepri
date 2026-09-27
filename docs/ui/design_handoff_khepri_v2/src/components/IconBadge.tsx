import * as React from "react";
import { cx } from "../lib/cx";
import type { Tone } from "../lib/tone";
import { renderIcon, type IconName } from "./Icon";

export interface IconBadgeProps {
  icon: IconName | React.ReactNode;
  /** Tint of the rounded square and the icon. */
  tone?: Tone;
  /** Square edge: sm 32, md 44, lg 56. */
  size?: "sm" | "md" | "lg";
}

/** Tinted rounded square holding an icon - the leading visual of stat tiles, cards and list rows. */
export function IconBadge({ icon, tone = "gold", size = "md" }: IconBadgeProps) {
  const px = size === "sm" ? 16 : size === "lg" ? 26 : 22;
  return <span className={cx("k-icon-badge", `k-tone-${tone}`, `k-icon-badge--${size}`)}>{renderIcon(icon, px)}</span>;
}
