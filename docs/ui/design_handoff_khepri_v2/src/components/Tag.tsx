import * as React from "react";
import { cx } from "../lib/cx";
import type { Tone } from "../lib/tone";
import { Icon } from "./Icon";

export interface TagProps {
  children: React.ReactNode;
  /** Colour family. Default "neutral". */
  tone?: Tone;
  /** Show an × button; called when it is clicked. */
  onRemove?: () => void;
  /** "soft" tinted chip (default) or "outline". */
  variant?: "soft" | "outline";
}

/** Small category chip ("الطاقة المتجددة", "تحليل السوق"), optionally removable (selected variables). */
export function Tag({ children, tone = "neutral", onRemove, variant = "soft" }: TagProps) {
  return (
    <span className={cx("k-tag", `k-tone-${tone}`, variant === "outline" && "k-tag--outline", onRemove && "k-tag--removable")}>
      <span>{children}</span>
      {onRemove ? (
        <button type="button" className="k-tag__remove" onClick={onRemove} aria-label="إزالة">
          <Icon name="x" size={13} />
        </button>
      ) : null}
    </span>
  );
}
