import * as React from "react";

export interface PrimaryCellProps {
  /** Main (Arabic) text, bold. */
  title: React.ReactNode;
  /** Secondary line - usually the English name or a timestamp. */
  subtitle?: React.ReactNode;
  /** Leading visual (a `FileTypeIcon`, `Avatar` or `IconBadge`). */
  leading?: React.ReactNode;
}

/** Two-line table cell: bold title with a muted second line, optional leading visual. */
export function PrimaryCell({ title, subtitle, leading }: PrimaryCellProps) {
  return (
    <span className="k-cell">
      {leading ? <span className="k-cell__leading">{leading}</span> : null}
      <span className="k-cell__text">
        <span className="k-cell__title">{title}</span>
        {subtitle ? <span className="k-cell__subtitle">{subtitle}</span> : null}
      </span>
    </span>
  );
}
