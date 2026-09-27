import * as React from "react";
import type { Tone } from "../lib/tone";
import type { IconName } from "./Icon";
import { IconBadge } from "./IconBadge";
import { IconButton } from "./IconButton";
import { Tag } from "./Tag";
import { Avatar } from "./Avatar";
import { ProgressRing } from "./ProgressRing";
import { StatusPill, type AnalysisStatus } from "./StatusPill";

export interface AnalysisCardProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: IconName;
  /** Tint of the icon badge. */
  tone?: Tone;
  /** Category chips, e.g. [{label:"تحليل السوق", tone:"red"}, {label:"العقارات"}]. */
  tags?: Array<{ label: string; tone?: Tone }>;
  /** Owner shown with avatar. */
  owner?: { name: string; avatarUrl?: string };
  /** Evidence coverage percentage (0-100) for the ring. */
  coverage?: number;
  status?: AnalysisStatus;
  /** Last-run line, e.g. "2025/04/21 ، 10:32 ص". */
  lastRun?: React.ReactNode;
  onMenu?: () => void;
}

/** Analysis-library card: icon, title, description, category tags, owner, evidence-coverage ring, status and last run. */
export function AnalysisCard({ title, description, icon = "analyses", tone = "gold", tags, owner, coverage, status, lastRun, onMenu }: AnalysisCardProps) {
  return (
    <article className="k-analysis">
      <header className="k-analysis__head">
        <div className="k-analysis__titles">
          <h4 className="k-analysis__title">{title}</h4>
          {description ? <p className="k-analysis__desc">{description}</p> : null}
        </div>
        <IconBadge icon={icon} tone={tone} size="lg" />
        <span className="k-analysis__menu"><IconButton icon="more" label="خيارات" size="sm" onClick={onMenu} /></span>
      </header>
      {tags && tags.length ? (
        <div className="k-analysis__tags">
          {tags.map((t) => (
            <Tag key={t.label} tone={t.tone ?? "neutral"}>{t.label}</Tag>
          ))}
        </div>
      ) : null}
      <div className="k-analysis__meta">
        {owner ? (
          <span className="k-analysis__owner">
            <Avatar name={owner.name} src={owner.avatarUrl} size={28} />
            <span>{owner.name}</span>
          </span>
        ) : <span />}
        {coverage != null ? (
          <span className="k-analysis__coverage">
            <span className="k-analysis__coverage-label">تغطية الأدلة</span>
            <ProgressRing value={coverage} size={40} thickness={4} />
          </span>
        ) : null}
      </div>
      <footer className="k-analysis__foot">
        {status ? <StatusPill status={status} size="sm" /> : <span />}
        {lastRun ? <span className="k-analysis__run">آخر تنفيذ: {lastRun}</span> : null}
      </footer>
    </article>
  );
}
