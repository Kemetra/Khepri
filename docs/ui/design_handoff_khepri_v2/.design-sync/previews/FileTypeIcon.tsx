import * as React from "react";
import { FileTypeIcon } from "@khepri/ds";

export const Glyphs = () => (
  <div className="k-row" style={{ gap: 18 }}>
    <FileTypeIcon kind="csv" size={28} />
    <FileTypeIcon kind="xlsx" size={28} />
    <FileTypeIcon kind="pdf" size={28} />
    <FileTypeIcon kind="zip" size={28} />
    <FileTypeIcon kind="link" size={28} />
  </div>
);

export const Chips = () => (
  <div className="k-row">
    <FileTypeIcon kind="csv" variant="chip" />
    <FileTypeIcon kind="xlsx" variant="chip" />
    <FileTypeIcon kind="pdf" variant="chip" />
    <FileTypeIcon kind="zip" variant="chip" />
  </div>
);
