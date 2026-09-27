import * as React from "react";
import { cx } from "../lib/cx";
import { Icon, type IconName } from "./Icon";

export interface IconButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Icon to show. "more" is the row / card overflow menu. */
  icon: IconName;
  /** Accessible label (required - the button has no visible text). */
  label: string;
  /** "plain" is borderless (table rows, card corners); "outlined" has a white box with a border. */
  variant?: "plain" | "outlined";
  size?: "sm" | "md";
}

/** Square icon-only button for overflow menus, close buttons and toolbar actions. */
export function IconButton({ icon, label, variant = "plain", size = "md", className, type = "button", ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      title={label}
      className={cx("k-icon-btn", `k-icon-btn--${variant}`, `k-icon-btn--${size}`, className)}
      {...rest}
    >
      <Icon name={icon} size={size === "sm" ? 16 : 18} />
    </button>
  );
}
