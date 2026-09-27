import * as React from "react";
import { cx } from "../lib/cx";
import { Icon } from "./Icon";

export interface LinkButtonProps extends Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "children"> {
  /** Link text, e.g. "عرض الكل" or "عرض التفاصيل". */
  children: React.ReactNode;
  /** Show the directional chevron after the text (points inline-end: left in RTL). Default true. */
  chevron?: boolean;
  /** "blue" (default) for card-header links; "gold" for in-card calls to action. */
  tone?: "blue" | "gold";
}

/** Small text link with a trailing chevron - the "عرض الكل ‹" pattern in card headers. */
export function LinkButton({ children, chevron = true, tone = "blue", className, href = "#", ...rest }: LinkButtonProps) {
  return (
    <a href={href} className={cx("k-link", `k-link--${tone}`, className)} {...rest}>
      <span>{children}</span>
      {chevron ? <span className="k-link__chevron"><Icon name="chevron-right" size={15} /></span> : null}
    </a>
  );
}
