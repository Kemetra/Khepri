import * as React from "react";
import { cx } from "../lib/cx";
import { Icon } from "./Icon";

export interface TaskItemProps {
  /** Task text, e.g. "مراجعة نتائج تحليل جودة الهواء". */
  title: React.ReactNode;
  /** Due text, e.g. "مستحق اليوم", "خلال 3 أيام". */
  due?: React.ReactNode;
  /** "overdue"/"today" renders the due text red. */
  urgency?: "today" | "soon" | "later";
  done?: boolean;
  onToggle?: (done: boolean) => void;
}

/** Upcoming-task row with a round checkbox and a due label (red when due today). */
export function TaskItem({ title, due, urgency = "later", done, onToggle }: TaskItemProps) {
  return (
    <div className={cx("k-task", done && "is-done")}>
      <button type="button" className="k-task__check" aria-pressed={!!done} aria-label="إنجاز" onClick={() => onToggle?.(!done)}>
        {done ? <Icon name="check" size={13} /> : null}
      </button>
      <span className="k-task__title">{title}</span>
      {due ? <span className={cx("k-task__due", urgency === "today" && "k-task__due--today")}>{due}</span> : null}
    </div>
  );
}
