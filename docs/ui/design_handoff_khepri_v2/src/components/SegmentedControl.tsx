import * as React from "react";
import { cx } from "../lib/cx";
import { renderIcon, type IconName } from "./Icon";

export interface SegmentedOption {
  value: string;
  label: React.ReactNode;
  icon?: IconName;
}

export interface SegmentedControlProps {
  options: SegmentedOption[];
  value: string;
  onChange?: (value: string) => void;
}

/** Compact exclusive toggle - the "بطاقات / جدولي" view switch; the active segment is gold. */
export function SegmentedControl({ options, value, onChange }: SegmentedControlProps) {
  return (
    <div className="k-segmented" role="radiogroup">
      {options.map((o) => (
        <button
          key={o.value} type="button" role="radio" aria-checked={o.value === value}
          className={cx("k-segmented__opt", o.value === value && "is-active")}
          onClick={() => onChange?.(o.value)}
        >
          {o.icon ? renderIcon(o.icon, 16) : null}
          <span>{o.label}</span>
        </button>
      ))}
    </div>
  );
}
