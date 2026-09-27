import * as React from "react";
import { cx } from "../lib/cx";

export interface ToggleProps {
  checked?: boolean;
  defaultChecked?: boolean;
  onChange?: (checked: boolean) => void;
  /** Label text beside the switch ("تطبيق تلقائي للاقتراحات"). */
  label?: React.ReactNode;
  disabled?: boolean;
}

/** On/off switch - gold track when on. */
export function Toggle({ checked, defaultChecked, onChange, label, disabled }: ToggleProps) {
  const [inner, setInner] = React.useState(!!defaultChecked);
  const on = checked ?? inner;
  return (
    <label className={cx("k-toggle", disabled && "is-disabled")}>
      <button
        type="button" role="switch" aria-checked={on} disabled={disabled}
        className={cx("k-toggle__track", on && "is-on")}
        onClick={() => { setInner(!on); onChange?.(!on); }}
      >
        <span className="k-toggle__thumb" />
      </button>
      {label ? <span className="k-toggle__label">{label}</span> : null}
    </label>
  );
}
