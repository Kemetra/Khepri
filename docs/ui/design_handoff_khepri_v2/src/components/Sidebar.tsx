import * as React from "react";
import { cx } from "../lib/cx";
import { renderIcon, type IconName } from "./Icon";
import { KhepriLogo } from "./KhepriLogo";

export interface SidebarItem {
  /** Stable key, compared with `activeId`. */
  id: string;
  /** Visible label, e.g. "التحليلات". */
  label: string;
  icon?: IconName;
  href?: string;
}

export interface SidebarProps {
  /** Navigation entries, top to bottom. Defaults to `defaultNavItems`. */
  items?: SidebarItem[];
  /** `id` of the current page's entry. */
  activeId?: string;
  /** Called with the item id when an entry is clicked. */
  onNavigate?: (id: string) => void;
  /** Brand block at the top. Defaults to `<KhepriLogo />`. */
  brand?: React.ReactNode;
  /** Tagline shown in the illustrated footer panel. */
  tagline?: React.ReactNode;
  /** Small caption below the tagline. */
  taglineCaption?: React.ReactNode;
  /** Hide the illustrated footer panel. */
  hideFooter?: boolean;
}

/** Khepri's default primary navigation, in mockup order. */
export const defaultNavItems: SidebarItem[] = [
  { id: "home", label: "الرئيسية", icon: "home" },
  { id: "analyses", label: "التحليلات", icon: "analyses" },
  { id: "data", label: "البيانات", icon: "database" },
  { id: "findings", label: "النتائج", icon: "lightbulb" },
  { id: "evidence", label: "الأدلة", icon: "file" },
  { id: "report", label: "التقرير", icon: "report" },
  { id: "history", label: "السجل", icon: "history" },
  { id: "settings", label: "الإعدادات", icon: "settings" },
];

/**
 * Vertical navigation rail with the Khepri brand, icon+label entries (the active entry gets
 * a sand fill, gold icon and a gold edge marker) and an illustrated tagline panel at the bottom.
 */
export function Sidebar({
  items = defaultNavItems, activeId, onNavigate, brand, tagline = "من البيانات.. إلى أثر حقيقي",
  taglineCaption = "رؤى موثوقة لقرارات أفضل", hideFooter,
}: SidebarProps) {
  return (
    <nav className="k-sidebar" aria-label="التنقل الرئيسي">
      <div className="k-sidebar__brand">{brand ?? <KhepriLogo />}</div>
      <ul className="k-sidebar__list">
        {items.map((item) => {
          const active = item.id === activeId;
          return (
            <li key={item.id}>
              <a
                href={item.href ?? "#"}
                className={cx("k-sidebar__item", active && "is-active")}
                aria-current={active ? "page" : undefined}
                onClick={(e) => {
                  if (onNavigate) {
                    e.preventDefault();
                    onNavigate(item.id);
                  }
                }}
              >
                <span className="k-sidebar__icon">{renderIcon(item.icon, 20)}</span>
                <span>{item.label}</span>
              </a>
            </li>
          );
        })}
      </ul>
      {hideFooter ? null : (
        <div className="k-sidebar__footer">
          <div className="k-sidebar__art" aria-hidden="true">
            <svg viewBox="0 0 200 110" preserveAspectRatio="xMidYMax slice" width="100%" height="100%">
              <circle cx="150" cy="28" r="13" fill="#f2cf92" />
              <path d="M18 110 L84 26 L150 110 Z" fill="#e7c48f" />
              <path d="M84 26 L150 110 L112 110 Z" fill="#d4a86a" />
              <path d="M112 110 L152 58 L194 110 Z" fill="#edd2a6" />
              <path d="M152 58 L194 110 L174 110 Z" fill="#dcb67e" />
              <rect x="0" y="104" width="200" height="6" fill="#e9d3ae" />
            </svg>
          </div>
          <p className="k-sidebar__tagline">{tagline}</p>
          {taglineCaption ? <p className="k-sidebar__caption">{taglineCaption}</p> : null}
        </div>
      )}
    </nav>
  );
}
