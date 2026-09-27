import * as React from "react";
import { cx } from "../lib/cx";

export interface LogLine {
  /** Timestamp, e.g. "10:59:12". */
  time: string;
  message: React.ReactNode;
  /** Dot colour. Default "success". */
  level?: "success" | "info" | "warning" | "error";
}

export interface LogConsoleProps {
  lines: LogLine[];
  /** Max height before scrolling. Default 220. */
  maxHeight?: number;
}

/** Dark live-log panel for a running analysis: timestamp, message and a level dot per line. */
export function LogConsole({ lines, maxHeight = 220 }: LogConsoleProps) {
  return (
    <div className="k-console" style={{ maxHeight }} role="log" aria-live="polite">
      {lines.map((l, i) => (
        <div className="k-console__line" key={i}>
          <span className={cx("k-console__dot", `k-console__dot--${l.level ?? "success"}`)} />
          <span className="k-console__msg">{l.message}</span>
          <span className="k-console__time">{l.time}</span>
        </div>
      ))}
    </div>
  );
}
