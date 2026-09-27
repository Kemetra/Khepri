import * as React from "react";
import { cx } from "../lib/cx";
import { renderIcon, type IconName } from "./Icon";

export interface ButtonProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /**
   * Visual weight. "primary" = gold gradient (one per view: "تحليل جديد", "بدء التنفيذ");
   * "secondary" = cream with a gold outline ("تحميل PDF", "استخدام القالب"); "ghost" = borderless;
   * "danger" = red outline ("إيقاف التنفيذ").
   */
  variant?: "primary" | "secondary" | "ghost" | "danger";
  /** Height: sm 32px, md 40px, lg 52px (full-width page CTAs). */
  size?: "sm" | "md" | "lg";
  /** Icon placed before the label (inline-start). */
  icon?: IconName | React.ReactNode;
  /** Icon placed after the label (inline-end), e.g. "arrow-left" for "متابعة". */
  trailingIcon?: IconName | React.ReactNode;
  /** Stretch to the container width. */
  block?: boolean;
  /** Show a spinner and disable. */
  loading?: boolean;
  children?: React.ReactNode;
}

/** Khepri button. Use one gold `primary` per view; everything else is `secondary` or `ghost`. */
export function Button({
  variant = "primary", size = "md", icon, trailingIcon, block, loading, disabled, className, children, type = "button", ...rest
}: ButtonProps) {
  const iconSize = size === "lg" ? 20 : size === "sm" ? 15 : 18;
  return (
    <button
      type={type}
      className={cx("k-btn", `k-btn--${variant}`, `k-btn--${size}`, block && "k-btn--block", className)}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...rest}
    >
      {loading ? <span className="k-spin">{renderIcon("loader", iconSize)}</span> : renderIcon(icon, iconSize)}
      {children != null ? <span>{children}</span> : null}
      {renderIcon(trailingIcon, iconSize)}
    </button>
  );
}
