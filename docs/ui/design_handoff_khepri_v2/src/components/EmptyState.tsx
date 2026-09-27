import * as React from "react";
import { renderIcon, type IconName } from "./Icon";

export interface EmptyStateProps {
  /** Illustration icon. Default "folder". */
  icon?: IconName | React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Call to action, normally a small `Button`. */
  action?: React.ReactNode;
}

/** Centered empty state: gold outline icon, title, hint and an optional action ("لا توجد تحليلات مثبتة بعد"). */
export function EmptyState({ icon = "folder", title, description, action }: EmptyStateProps) {
  return (
    <div className="k-empty">
      <span className="k-empty__icon">{renderIcon(icon, 40)}</span>
      <p className="k-empty__title">{title}</p>
      {description ? <p className="k-empty__desc">{description}</p> : null}
      {action ? <div className="k-empty__action">{action}</div> : null}
    </div>
  );
}
