import * as React from "react";
import { cx } from "../lib/cx";
import type { Tone } from "../lib/tone";
import type { IconName } from "./Icon";
import { Icon } from "./Icon";
import { IconBadge } from "./IconBadge";
import { CountBadge } from "./CountBadge";
import { ProgressBar } from "./ProgressBar";
import { LinkButton } from "./LinkButton";

export interface FindingCardProps {
  /** Rank shown in the numbered badge. */
  rank: number;
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: IconName;
  /** Card tint: the whole card takes this tone's pale surface. */
  tone?: Tone;
  /** Confidence 0-100, drawn as a bar. */
  confidence?: number;
  /** Supporting-sources line, e.g. "6 مصادر بيانات". */
  sources?: React.ReactNode;
  /** Label of the footer link. Default "عرض التفاصيل". */
  actionLabel?: string;
  onAction?: () => void;
}

/** Ranked key-finding card: tinted panel with number, title, summary, confidence bar and sources. */
export function FindingCard({ rank, title, description, icon = "lightbulb", tone = "green", confidence, sources, actionLabel = "عرض التفاصيل", onAction }: FindingCardProps) {
  return (
    <article className={cx("k-finding", `k-tone-${tone}`)}>
      <header className="k-finding__head">
        <CountBadge value={rank} tone={tone} variant="solid" />
        <IconBadge icon={icon} tone={tone} size="sm" />
      </header>
      <h4 className="k-finding__title">{title}</h4>
      {description ? <p className="k-finding__desc">{description}</p> : null}
      {confidence != null ? <ProgressBar value={confidence} tone={tone} label="مستوى الثقة" showValue /> : null}
      {sources ? (
        <p className="k-finding__sources">
          <Icon name="database" size={15} />
          <span>{sources}</span>
        </p>
      ) : null}
      <div className="k-finding__foot">
        <LinkButton onClick={(e) => { e.preventDefault(); onAction?.(); }}>{actionLabel}</LinkButton>
      </div>
    </article>
  );
}
