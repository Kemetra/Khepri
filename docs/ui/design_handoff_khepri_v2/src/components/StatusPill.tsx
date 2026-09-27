import * as React from "react";
import { cx } from "../lib/cx";
import type { Tone } from "../lib/tone";

/** Workflow states with fixed Arabic labels and colours. */
export type AnalysisStatus =
  | "complete"
  | "running"
  | "review"
  | "stopped"
  | "draft"
  | "queued"
  | "waiting"
  | "warning"
  | "ready"
  | "published"
  | "compatible";

const STATUS: Record<AnalysisStatus, { label: string; tone: Tone }> = {
  complete: { label: "مكتمل", tone: "green" },
  running: { label: "قيد التنفيذ", tone: "blue" },
  review: { label: "مراجعة النتائج", tone: "amber" },
  stopped: { label: "متوقف", tone: "red" },
  draft: { label: "مسودة", tone: "neutral" },
  queued: { label: "في الطابور", tone: "amber" },
  waiting: { label: "بالانتظار", tone: "neutral" },
  warning: { label: "تحذير", tone: "amber" },
  ready: { label: "جاهز", tone: "green" },
  published: { label: "منشور", tone: "green" },
  compatible: { label: "متوافق", tone: "green" },
};

export interface StatusPillProps {
  /** Workflow state; sets the colour and the default Arabic label. */
  status?: AnalysisStatus;
  /** Override the label (e.g. "قيد المعالجة"). */
  label?: React.ReactNode;
  /** Override the colour, or colour a free-form pill when `status` is omitted. */
  tone?: Tone;
  /** Hide the leading dot. */
  noDot?: boolean;
  size?: "sm" | "md";
}

/** Rounded status label with a coloured dot: "مكتمل" (green), "قيد التنفيذ" (blue), "مراجعة النتائج" (amber)… */
export function StatusPill({ status, label, tone, noDot, size = "md" }: StatusPillProps) {
  const def = status ? STATUS[status] : undefined;
  const t = tone ?? def?.tone ?? "neutral";
  return (
    <span className={cx("k-pill", `k-tone-${t}`, size === "sm" && "k-pill--sm")}>
      {noDot ? null : <span className="k-pill__dot" />}
      {label ?? def?.label}
    </span>
  );
}
