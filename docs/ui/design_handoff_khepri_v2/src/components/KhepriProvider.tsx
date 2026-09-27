import * as React from "react";
import { cx } from "../lib/cx";

export interface KhepriProviderProps {
  /** Text direction. Khepri is Arabic-first, so the default is "rtl". */
  dir?: "rtl" | "ltr";
  /** Document language for the subtree. Default "ar". */
  lang?: string;
  className?: string;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}

/**
 * Root wrapper for every Khepri screen. Sets `dir`/`lang`, the Noto Sans Arabic font stack,
 * the canvas background and base text colour. Components rely on its `dir` for their
 * logical (inline-start/end) layout - without it an Arabic layout mirrors incorrectly.
 */
export function KhepriProvider({ dir = "rtl", lang = "ar", className, style, children }: KhepriProviderProps) {
  return (
    <div className={cx("k-root", className)} dir={dir} lang={lang} style={style}>
      {children}
    </div>
  );
}
