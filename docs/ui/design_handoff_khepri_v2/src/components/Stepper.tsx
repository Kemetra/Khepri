import * as React from "react";
import { cx } from "../lib/cx";
import { Icon, renderIcon, type IconName } from "./Icon";

export interface StepperStep {
  /** Step name, e.g. "رفع البيانات". */
  label: React.ReactNode;
  /** Small caption under the label ("إضافة الملفات والمصادر"). */
  description?: React.ReactNode;
  /** Icon shown inside the node for the "icon" variant instead of the number. */
  icon?: IconName;
  /** Extra lines under the label in the "icon" variant (status pill, "5/5 مجموعات", "6 دقائق"). */
  meta?: React.ReactNode;
}

export interface StepperProps {
  steps: StepperStep[];
  /** Zero-based index of the current step. Earlier steps render done (green tick), later ones pending. */
  current: number;
  /**
   * "numbered": numbered circles, current in gold (upload / setup wizards).
   * "icon": large icon nodes with a green completed connector (run progress).
   */
  variant?: "numbered" | "icon";
}

/** Horizontal wizard / pipeline progress. Flows inline-start to inline-end (right to left in RTL). */
export function Stepper({ steps, current, variant = "numbered" }: StepperProps) {
  return (
    <ol className={cx("k-stepper", `k-stepper--${variant}`)}>
      {steps.map((s, i) => {
        const state = i < current ? "done" : i === current ? "current" : "todo";
        return (
          <li key={i} className={cx("k-stepper__step", `is-${state}`)} aria-current={state === "current" ? "step" : undefined}>
            <span className="k-stepper__node">
              {state === "done" ? <Icon name="check" size={variant === "icon" ? 22 : 16} strokeWidth={2.6} />
                : variant === "icon" && s.icon ? renderIcon(s.icon, 22)
                : i + 1}
            </span>
            <span className="k-stepper__text">
              {variant === "icon" ? <span className="k-stepper__index">{i + 1}</span> : null}
              <span className="k-stepper__label">{s.label}</span>
              {s.description ? <span className="k-stepper__desc">{s.description}</span> : null}
              {s.meta ? <span className="k-stepper__meta">{s.meta}</span> : null}
            </span>
            {i < steps.length - 1 ? <span className="k-stepper__line" aria-hidden="true" /> : null}
          </li>
        );
      })}
    </ol>
  );
}
