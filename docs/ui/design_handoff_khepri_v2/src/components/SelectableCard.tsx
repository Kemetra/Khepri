import * as React from "react";
import { cx } from "../lib/cx";
import { Icon, renderIcon, type IconName } from "./Icon";

export interface SelectableCardProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Icon shown above (layout "tile") or beside (layout "row") the title. */
  icon?: IconName | React.ReactNode;
  selected?: boolean;
  onSelect?: () => void;
  /** "check" = multi-select tick (dimensions); "radio" = single choice (comparison groups). */
  mode?: "check" | "radio";
  /** "tile" = centred vertical card; "row" = full-width option row. */
  layout?: "tile" | "row";
}

/** Choice card for analysis setup - green border and tick when selected. Multi (check) or single (radio). */
export function SelectableCard({ title, description, icon, selected, onSelect, mode = "check", layout = "tile" }: SelectableCardProps) {
  return (
    <button
      type="button"
      role={mode === "radio" ? "radio" : "checkbox"}
      aria-checked={!!selected}
      onClick={onSelect}
      className={cx("k-choice", `k-choice--${layout}`, `k-choice--${mode}`, selected && "is-selected")}
    >
      <span className="k-choice__mark">{selected ? <Icon name="check" size={13} strokeWidth={2.6} /> : null}</span>
      {icon ? <span className="k-choice__icon">{renderIcon(icon, layout === "tile" ? 28 : 20)}</span> : null}
      <span className="k-choice__text">
        <span className="k-choice__title">{title}</span>
        {description ? <span className="k-choice__desc">{description}</span> : null}
      </span>
    </button>
  );
}
