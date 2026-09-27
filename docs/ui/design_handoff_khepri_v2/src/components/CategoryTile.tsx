import * as React from "react";
import { cx } from "../lib/cx";
import type { Tone } from "../lib/tone";
import { renderIcon, type IconName } from "./Icon";

export interface CategoryTileProps {
  label: React.ReactNode;
  /** Count line, e.g. "6 تحليلات". */
  count?: React.ReactNode;
  icon?: IconName | React.ReactNode;
  /** Icon colour. */
  tone?: Tone;
  active?: boolean;
  onClick?: () => void;
}

/** Filter tile for the analyses library ("تحليل السوق · 6 تحليلات"); active tile gets the sand fill and gold border. */
export function CategoryTile({ label, count, icon, tone = "gold", active, onClick }: CategoryTileProps) {
  return (
    <button type="button" className={cx("k-category", active && "is-active")} aria-pressed={!!active} onClick={onClick}>
      <span className="k-category__text">
        <span className="k-category__label">{label}</span>
        {count != null ? <span className="k-category__count">{count}</span> : null}
      </span>
      {icon ? <span className={cx("k-category__icon", `k-text-${tone}`)}>{renderIcon(icon, 28)}</span> : null}
    </button>
  );
}
