import * as React from "react";
import { cx } from "../lib/cx";
import { Icon, renderIcon, type IconName } from "./Icon";
import { Field } from "./Field";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "size"> {
  options: SelectOption[];
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  /** Leading icon (e.g. "calendar", "globe", "database"). */
  icon?: IconName;
  /** Small caption above the value inside the box - the filter-bar style ("الفترة الزمنية" / "الكل"). */
  caption?: React.ReactNode;
  size?: "sm" | "md";
}

/** Native select styled as a Khepri dropdown (chevron at inline-end). Used for forms and filter bars. */
export function Select({ options, label, hint, error, icon, caption, required, id, size = "md", className, ...rest }: SelectProps) {
  const autoId = React.useId();
  const fid = id ?? autoId;
  const control = (
    <span className={cx("k-select", `k-select--${size}`, caption ? "k-select--captioned" : undefined, className)}>
      {icon ? <span className="k-select__icon">{renderIcon(icon, 17)}</span> : null}
      {caption ? <span className="k-select__caption">{caption}</span> : null}
      <select id={fid} required={required} aria-invalid={!!error || undefined} {...rest}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
      <span className="k-select__chevron"><Icon name="chevron-down" size={16} /></span>
    </span>
  );
  if (!label && !hint && !error) return control;
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={fid}>
      {control}
    </Field>
  );
}
