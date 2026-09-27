import * as React from "react";
import { cx } from "../lib/cx";
import { renderIcon, type IconName } from "./Icon";
import { khepriHero } from "../assets";

export interface PageHeaderProps {
  /** Page title, e.g. "مكتبة التحليلات". */
  title: React.ReactNode;
  /** One-line description under the title. */
  subtitle?: React.ReactNode;
  /** Gold icon shown beside the title. */
  icon?: IconName | React.ReactNode;
  /** Primary action(s), normally one gold `Button`. */
  actions?: React.ReactNode;
  /** Hero artwork URL faded in at the inline-end side. Defaults to the Khepri hero art; pass `null` for none. */
  image?: string | null;
  /** Content below the title row (e.g. a `Stepper` or `Tabs`). */
  children?: React.ReactNode;
  /** "compact" is shorter, for inner pages. */
  size?: "default" | "compact";
}

/**
 * Page hero: large title with a gold icon, subtitle, primary action and landscape artwork that
 * fades into the canvas. Optional children (stepper, tabs) sit under the title row.
 */
export function PageHeader({ title, subtitle, icon, actions, image = khepriHero, children, size = "default" }: PageHeaderProps) {
  return (
    <section className={cx("k-page-header", size === "compact" && "k-page-header--compact", !image && "k-page-header--plain")}>
      {image ? (
        <div className="k-page-header__art" aria-hidden="true" style={{ backgroundImage: `url(${image})` }} />
      ) : null}
      <div className="k-page-header__content">
        <div className="k-page-header__row">
          <div className="k-page-header__titles">
            <h1 className="k-page-header__title">
              {icon ? <span className="k-page-header__icon">{renderIcon(icon, 30)}</span> : null}
              <span>{title}</span>
            </h1>
            {subtitle ? <p className="k-page-header__subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="k-page-header__actions">{actions}</div> : null}
        </div>
        {children ? <div className="k-page-header__extra">{children}</div> : null}
      </div>
    </section>
  );
}
