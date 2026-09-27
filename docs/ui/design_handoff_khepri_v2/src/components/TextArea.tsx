import * as React from "react";
import { Field } from "./Field";

export interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  /** Show "length / maxLength" under the field (needs `maxLength`). */
  showCount?: boolean;
}

/** Multi-line text input ("الهدف من التحليل") with label, hint and character counter. */
export function TextArea({ label, hint, error, showCount, required, id, value, defaultValue, maxLength, rows = 3, ...rest }: TextAreaProps) {
  const autoId = React.useId();
  const fid = id ?? autoId;
  const len = String(value ?? defaultValue ?? "").length;
  return (
    <Field label={label} required={required} hint={hint} error={error} htmlFor={fid} counter={showCount && maxLength ? `${len} / ${maxLength}` : undefined}>
      <textarea
        id={fid} className="k-textarea" rows={rows} required={required} value={value} defaultValue={defaultValue}
        maxLength={maxLength} aria-invalid={!!error || undefined} {...rest}
      />
    </Field>
  );
}
