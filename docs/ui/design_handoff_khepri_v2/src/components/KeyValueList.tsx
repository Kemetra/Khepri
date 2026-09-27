import * as React from "react";
import { renderIcon, type IconName } from "./Icon";

export interface KeyValueItem {
  label: React.ReactNode;
  value: React.ReactNode;
  icon?: IconName;
}

export interface KeyValueListProps {
  items: KeyValueItem[];
  /** "inline": label and value on one row (report info). "stacked": label above value (run info). */
  layout?: "inline" | "stacked";
}

/** Labelled facts list with gold line icons - report metadata, analysis summary, run information. */
export function KeyValueList({ items, layout = "inline" }: KeyValueListProps) {
  return (
    <dl className={`k-kv k-kv--${layout}`}>
      {items.map((it, i) => (
        <div className="k-kv__row" key={i}>
          {it.icon ? <span className="k-kv__icon">{renderIcon(it.icon, 18)}</span> : null}
          <dt>{it.label}</dt>
          <dd>{it.value}</dd>
        </div>
      ))}
    </dl>
  );
}
