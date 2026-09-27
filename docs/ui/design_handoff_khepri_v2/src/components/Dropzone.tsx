import * as React from "react";
import { cx } from "../lib/cx";
import { Icon } from "./Icon";
import { FileTypeIcon, type FileKind } from "./FileTypeIcon";

export interface DropzoneProps {
  /** Accepted formats shown as tiles, with their size limits. */
  formats?: Array<{ kind: FileKind; limit: string }>;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  /** Footer note under the tiles. */
  note?: React.ReactNode;
  onFiles?: (files: FileList) => void;
}

/** Dashed file drop area with a gold cloud icon and accepted-format tiles (CSV / XLSX / PDF / ZIP). */
export function Dropzone({
  formats = [
    { kind: "csv", limit: "حتى 500 ميجابايت" },
    { kind: "xlsx", limit: "حتى 500 ميجابايت" },
    { kind: "pdf", limit: "حتى 500 ميجابايت" },
    { kind: "zip", limit: "حتى 1 جيجابايت" },
  ],
  title = "اسحب وأفلت الملفات هنا", subtitle = "أو اضغط لاختيار الملفات",
  note = "يمكنك رفع ملف واحد أو عدة ملفات في نفس الوقت", onFiles,
}: DropzoneProps) {
  const [over, setOver] = React.useState(false);
  const input = React.useRef<HTMLInputElement>(null);
  return (
    <div
      className={cx("k-dropzone", over && "is-over")}
      onDragOver={(e) => { e.preventDefault(); setOver(true); }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => { e.preventDefault(); setOver(false); if (e.dataTransfer.files.length) onFiles?.(e.dataTransfer.files); }}
      onClick={() => input.current?.click()}
      role="button"
      tabIndex={0}
    >
      <input ref={input} type="file" multiple hidden onChange={(e) => e.target.files && onFiles?.(e.target.files)} />
      <span className="k-dropzone__icon"><Icon name="upload-cloud" size={52} strokeWidth={1.4} /></span>
      <p className="k-dropzone__title">{title}</p>
      <p className="k-dropzone__subtitle">{subtitle}</p>
      <div className="k-dropzone__formats">
        {formats.map((f) => (
          <div key={f.kind} className={cx("k-dropzone__format", `k-file-${f.kind}`)}>
            <FileTypeIcon kind={f.kind} size={30} />
            <strong>{f.kind.toUpperCase()}</strong>
            <small>{f.limit}</small>
          </div>
        ))}
      </div>
      {note ? <p className="k-dropzone__note">{note}</p> : null}
    </div>
  );
}
