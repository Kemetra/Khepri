import * as React from "react";
import { cx } from "../lib/cx";
import { Icon } from "./Icon";

export interface CheckboxProps {
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: (checked: boolean) => void;
  label?: React.ReactNode;
  disabled?: boolean;
}

/** Square checkbox - gold fill with a white tick when checked (evidence selection). */
export function Checkbox({ checked, defaultChecked, onChange, label, disabled }: CheckboxProps) {
  const [inner, setInner] = React.useState(!!defaultChecked);
  const on = checked ?? inner;
  return (
    <label className={cx("k-checkbox", disabled && "is-disabled")}>
      <button
        type="button" role="checkbox" aria-checked={on} disabled={disabled}
        className={cx("k-checkbox__box", on && "is-on")}
        onClick={() => { setInner(!on); onChange?.(!on); }}
      >
        {on ? <Icon name="check" size={14} strokeWidth={2.5} /> : null}
      </button>
      {label ? <span>{label}</span> : null}
    </label>
  );
}
