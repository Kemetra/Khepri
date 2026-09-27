import * as React from "react";
import { cx } from "../lib/cx";
import type { Tone } from "../lib/tone";
import { Icon, type IconName } from "./Icon";
import { IconBadge } from "./IconBadge";

export interface StatTileProps {
  /** Headline figure, pre-formatted ("87%", "12", "4.2 جيجاوات", "$ 12.4B"). */
  value: React.ReactNode;
  /** What the figure measures ("تغطية الأدلة"). */
  label: React.ReactNode;
  /** Small caption under the label ("من المصادر الموثوقة"). */
  caption?: React.ReactNode;
  /** Change indicator text ("+12%", "+3", "-2.1%"). */
  delta?: React.ReactNode;
  /** Direction of the delta; "up" is green, "down" red unless `deltaTone` overrides. */
  trend?: "up" | "down" | "flat";
  /** Force the delta colour, e.g. a falling error rate is good news ("green"). */
  deltaTone?: "green" | "red" | "neutral";
  icon?: IconName | React.ReactNode;
  /** Tint of the icon badge. */
  tone?: Tone;
  /** Extra content under the figure (a mini legend, a link). */
  children?: React.ReactNode;
}

/** KPI tile: tinted icon badge, big figure, label, caption and a coloured up/down delta. */
export function StatTile({ value, label, caption, delta, trend = "up", deltaTone, icon, tone = "gold", children }: StatTileProps) {
  const dt = deltaTone ?? (trend === "down" ? "red" : trend === "flat" ? "neutral" : "green");
  return (
    <div className="k-stat">
      <div className="k-stat__main">
        <div className="k-stat__text">
          <div className="k-stat__value">{value}</div>
          <div className="k-stat__label">{label}</div>
        </div>
        {icon ? <IconBadge icon={icon} tone={tone} size="lg" /> : null}
      </div>
      {children}
      {delta != null || caption != null ? (
        <div className="k-stat__foot">
          {caption != null ? <span className="k-stat__caption">{caption}</span> : <span />}
          {delta != null ? (
            <span className={cx("k-stat__delta", `k-stat__delta--${dt}`)}>
              {trend !== "flat" ? <Icon name={trend === "down" ? "arrow-down" : "arrow-up"} size={14} /> : null}
              <bdi>{delta}</bdi>
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
