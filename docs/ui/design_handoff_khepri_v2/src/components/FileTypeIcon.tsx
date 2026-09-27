import * as React from "react";
import { cx } from "../lib/cx";
import { Icon } from "./Icon";

export type FileKind = "csv" | "xlsx" | "pdf" | "zip" | "doc" | "link";

const KIND: Record<FileKind, { icon: "file" | "file-sheet" | "file-zip" | "link"; label: string }> = {
  csv: { icon: "file", label: "CSV" },
  xlsx: { icon: "file-sheet", label: "XLSX" },
  pdf: { icon: "file", label: "PDF" },
  zip: { icon: "file-zip", label: "ZIP" },
  doc: { icon: "file", label: "DOC" },
  link: { icon: "link", label: "LINK" },
};

export interface FileTypeIconProps {
  kind: FileKind;
  /** "icon" = coloured file glyph; "chip" = small coloured format label ("CSV"). */
  variant?: "icon" | "chip";
  size?: number;
}

/** File-format marker: CSV blue, XLSX green, PDF red, ZIP purple - as glyph or text chip. */
export function FileTypeIcon({ kind, variant = "icon", size = 22 }: FileTypeIconProps) {
  const def = KIND[kind];
  if (variant === "chip") return <span className={cx("k-filechip", `k-file-${kind}`)}>{def.label}</span>;
  return (
    <span className={cx("k-fileicon", `k-file-${kind}`)} title={def.label}>
      <Icon name={def.icon} size={size} />
    </span>
  );
}
