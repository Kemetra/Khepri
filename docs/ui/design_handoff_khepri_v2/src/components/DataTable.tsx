import * as React from "react";
import { cx } from "../lib/cx";

export interface DataTableColumn<Row> {
  /** Unique key; also the row property read when `render` is omitted. */
  key: string;
  /** Header text. */
  header: React.ReactNode;
  /** Custom cell renderer. */
  render?: (row: Row, index: number) => React.ReactNode;
  /** Text alignment in logical terms. Default "start". */
  align?: "start" | "center" | "end";
  /** Fixed width (CSS length). */
  width?: string | number;
  /** Render cell in the tabular / monospace numeric style. */
  numeric?: boolean;
}

export interface DataTableProps<Row> {
  columns: Array<DataTableColumn<Row>>;
  rows: Row[];
  /** Row key accessor. Default: the row index. */
  rowKey?: (row: Row, index: number) => string | number;
  /** Tighter rows for dense previews (data preview grids). */
  dense?: boolean;
  /** Zebra striping. */
  striped?: boolean;
  /** Shown when `rows` is empty. */
  empty?: React.ReactNode;
  /** Called when a row is clicked. */
  onRowClick?: (row: Row, index: number) => void;
}

/**
 * Light-ruled data table with a sand header row. Compose cells with `StatusPill`, `Tag`,
 * `FileTypeIcon`, `ProgressBar` and a trailing `IconButton icon="more"` via `render`.
 */
export function DataTable<Row extends Record<string, unknown>>({
  columns, rows, rowKey, dense, striped, empty = "لا توجد بيانات", onRowClick,
}: DataTableProps<Row>) {
  return (
    <div className="k-table-wrap">
      <table className={cx("k-table", dense && "k-table--dense", striped && "k-table--striped", onRowClick && "k-table--clickable")}>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} style={{ width: c.width, textAlign: c.align ?? "start" }}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="k-table__empty">{empty}</td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={rowKey ? rowKey(row, i) : i} onClick={onRowClick ? () => onRowClick(row, i) : undefined}>
                {columns.map((c) => (
                  <td key={c.key} className={cx(c.numeric && "k-num")} style={{ textAlign: c.align ?? "start" }}>
                    {c.render ? c.render(row, i) : c.numeric ? <bdi>{row[c.key] as React.ReactNode}</bdi> : (row[c.key] as React.ReactNode)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
