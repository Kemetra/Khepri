import * as React from "react";
import { FileTypeIcon, type FileKind } from "./FileTypeIcon";
import { IconButton } from "./IconButton";

export interface FileRowProps {
  /** File or dataset name. */
  name: React.ReactNode;
  kind: FileKind;
  /** Size text, e.g. "245 MB". */
  size?: string;
  /** Date text, e.g. "2025/04/20". */
  date?: string;
  /** Extra trailing content (a `StatusPill`, `ConfidenceBadge`). */
  trailing?: React.ReactNode;
  onMenu?: () => void;
}

/** Compact dataset / attachment row: file-type glyph, name, "XLSX • 128 MB • 2025/04/18" meta, overflow menu. */
export function FileRow({ name, kind, size, date, trailing, onMenu }: FileRowProps) {
  const meta = [kind.toUpperCase(), size, date].filter(Boolean).join(" • ");
  return (
    <div className="k-filerow">
      <FileTypeIcon kind={kind} />
      <div className="k-filerow__text">
        <div className="k-filerow__name">{name}</div>
        <div className="k-filerow__meta"><bdi>{meta}</bdi></div>
      </div>
      {trailing}
      <IconButton icon="more" label="خيارات" size="sm" onClick={onMenu} />
    </div>
  );
}
