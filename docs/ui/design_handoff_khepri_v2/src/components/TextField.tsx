import * as React from "react";
import { renderIcon, type IconName } from "./Icon";
import { Field } from "./Field";

export interface TextFieldProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size"> {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  /** Show "length / maxLength" under the field (needs `maxLength`). */
  showCount?: boolean;
  /** Leading icon inside the input. */
  icon?: IconName;
}

/** Single-line text input with label, required marker, hint/error and optional character counter. */
export function TextField({ label, hint, error, showCount, icon, required, id, value, defaultValue, maxLength, ...rest }: TextFieldProps) {
  const autoId = React.useId();
  const fid = id ?? autoId;
  const len = String(value ?? defaultValue ?? "").length;
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={fid} counter={showCount && maxLength ? `${len} / ${maxLength}` : undefined}>
      <span className="k-input">
        {icon ? <span className="k-input__icon">{renderIcon(icon, 18)}</span> : null}
        <input id={fid} required={required} value={value} defaultValue={defaultValue} maxLength={maxLength} aria-invalid={!!error || undefined} {...rest} />
      </span>
    </Field>
  );
}
