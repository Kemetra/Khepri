import * as React from "react";
import type { Tone } from "../lib/tone";
import type { IconName } from "./Icon";
import { IconBadge } from "./IconBadge";
import { Button } from "./Button";
import { LinkButton } from "./LinkButton";

export interface SuggestionCardProps {
  title: React.ReactNode;
  description: React.ReactNode;
  icon?: IconName;
  tone?: Tone;
  /** Primary action label. Default "تطبيق الاقتراح". */
  applyLabel?: string;
  onApply?: () => void;
  onDetails?: () => void;
}

/** AI suggestion panel (اقتراحات الذكاء الاصطناعي): icon, title, explanation, "تطبيق الاقتراح" and "عرض التفاصيل". */
export function SuggestionCard({ title, description, icon = "lightbulb", tone = "amber", applyLabel = "تطبيق الاقتراح", onApply, onDetails }: SuggestionCardProps) {
  return (
    <article className="k-suggestion">
      <header className="k-suggestion__head">
        <h4 className="k-suggestion__title">{title}</h4>
        <IconBadge icon={icon} tone={tone} size="sm" />
      </header>
      <p className="k-suggestion__desc">{description}</p>
      <div className="k-suggestion__foot">
        <LinkButton onClick={(e) => { e.preventDefault(); onDetails?.(); }}>عرض التفاصيل</LinkButton>
        <Button size="sm" onClick={onApply}>{applyLabel}</Button>
      </div>
    </article>
  );
}
