import * as React from "react";
import { cx } from "../lib/cx";
import { renderIcon, type IconName } from "./Icon";
import { CountBadge } from "./CountBadge";

export interface CardProps {
  /** Section heading, e.g. "التحليلات الحديثة". */
  title?: React.ReactNode;
  /** Small gold icon beside the title. */
  icon?: IconName | React.ReactNode;
  /** Numeric badge beside the title (e.g. a task count). */
  count?: number;
  /** One-line description under the title. */
  description?: React.ReactNode;
  /** Header controls at the inline-end edge (a `LinkButton` "عرض الكل", a `Select`, a menu). */
  actions?: React.ReactNode;
  /** Remove body padding (for edge-to-edge tables). */
  flush?: boolean;
  /** Sand background with a gold border (selected / featured). */
  highlighted?: boolean;
  className?: string;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}

/** White rounded panel - the basic container for every dashboard section. */
export function Card({ title, icon, count, description, actions, flush, highlighted, className, style, children }: CardProps) {
  const hasHeader = title != null || actions != null;
  return (
    <section className={cx("k-card", flush && "k-card--flush", highlighted && "k-card--highlighted", className)} style={style}>
      {hasHeader ? (
        <header className="k-card__header">
          <div className="k-card__heading">
            {title != null ? (
              <h3 className="k-card__title">
                {icon ? <span className="k-card__icon">{renderIcon(icon, 20)}</span> : null}
                <span>{title}</span>
                {count != null ? <CountBadge value={count} /> : null}
              </h3>
            ) : null}
            {description ? <p className="k-card__description">{description}</p> : null}
          </div>
          {actions ? <div className="k-card__actions">{actions}</div> : null}
        </header>
      ) : null}
      <div className="k-card__body">{children}</div>
    </section>
  );
}
