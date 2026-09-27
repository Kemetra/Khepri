import * as React from "react";

export interface FieldProps {
  /** Field label, e.g. "اسم التحليل". */
  label?: React.ReactNode;
  /** Adds the red asterisk. */
  required?: boolean;
  /** Helper text under the control. */
  hint?: React.ReactNode;
  /** Error message; replaces the hint and turns the border red. */
  error?: React.ReactNode;
  /** Character counter text at the inline-end under the control, e.g. "32 / 100". */
  counter?: React.ReactNode;
  htmlFor?: string;
  children: React.ReactNode;
}

/** Label + control + hint/counter wrapper shared by `TextField`, `TextArea` and `Select`. */
export function Field({ label, required, hint, error, counter, htmlFor, children }: FieldProps) {
  return (
    <div className={error ? "k-field is-invalid" : "k-field"}>
      {label ? (
        <label className="k-field__label" htmlFor={htmlFor}>
          {label}
          {required ? <span className="k-field__req">*</span> : null}
        </label>
      ) : null}
      {children}
      {error || hint || counter ? (
        <div className="k-field__foot">
          <span className={error ? "k-field__error" : "k-field__hint"}>{error ?? hint}</span>
          {counter ? <span className="k-field__counter"><bdi>{counter}</bdi></span> : null}
        </div>
      ) : null}
    </div>
  );
}
