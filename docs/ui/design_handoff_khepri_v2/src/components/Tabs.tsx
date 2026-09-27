import * as React from "react";
import { cx } from "../lib/cx";
import { renderIcon, type IconName } from "./Icon";

export interface TabItem {
  id: string;
  label: React.ReactNode;
  icon?: IconName;
}

export interface TabsProps {
  items: TabItem[];
  activeId: string;
  onChange?: (id: string) => void;
  /**
   * "boxed": raised white tab strip, active tab sand with a gold bottom rule (findings page).
   * "underline": plain text tabs with a gold underline (side panels: "المخطط / المكونات / الإعدادات").
   */
  variant?: "boxed" | "underline";
}

/** Tab strip with optional icons. */
export function Tabs({ items, activeId, onChange, variant = "boxed" }: TabsProps) {
  return (
    <div className={cx("k-tabs", `k-tabs--${variant}`)} role="tablist">
      {items.map((t) => {
        const active = t.id === activeId;
        return (
          <button
            key={t.id} type="button" role="tab" aria-selected={active}
            className={cx("k-tabs__tab", active && "is-active")}
            onClick={() => onChange?.(t.id)}
          >
            {t.icon ? <span className="k-tabs__icon">{renderIcon(t.icon, 18)}</span> : null}
            <span>{t.label}</span>
          </button>
        );
      })}
    </div>
  );
}
