// Tools the claim lists share (D-UI-12): a column to sort by, kept in the URL (?sort=, ?dir=) so a
// refresh keeps it, and a CSV download of the rows shown. Formatting only: the CSV writes amounts
// in dollars from the API's cents with the same integer arithmetic as the page (src/lib/format.ts).

import { ArrowDown, ArrowUp, ArrowUpDown, Download } from "lucide-react";
import type { ReactNode } from "react";
import { useSearchParams } from "react-router";

import { Button } from "@/components/ui/button";
import { TableHead } from "@/components/ui/table";

export type SortDir = "asc" | "desc";
type Value = string | number | null | undefined;

export interface Sort<K extends string> {
  key: K;
  dir: SortDir;
  toggle: (key: K) => void;
  /** The rows sorted by the column; a row without a value goes last either way. */
  apply: <T>(rows: T[], value: (row: T, key: K) => Value) => T[];
}

export function useSort<K extends string>(keys: readonly K[], fallback: K, fallbackDir: SortDir = "desc"): Sort<K> {
  const [params, setParams] = useSearchParams();
  const asked = params.get("sort") as K | null;
  const key = asked && keys.includes(asked) ? asked : fallback;
  const dir: SortDir = params.get("dir") === "asc" ? "asc" : params.get("dir") === "desc" ? "desc" : fallbackDir;
  return {
    key,
    dir,
    toggle: (next) =>
      setParams(
        (now) => {
          const edited = new URLSearchParams(now);
          edited.set("sort", next);
          edited.set("dir", next === key && dir === "desc" ? "asc" : "desc");
          return edited;
        },
        { replace: true },
      ),
    apply: (rows, value) =>
      [...rows].sort((a, b) => {
        const x = value(a, key);
        const y = value(b, key);
        if (x === y) return 0;
        if (x === null || x === undefined || x === "") return 1;
        if (y === null || y === undefined || y === "") return -1;
        const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
        return dir === "asc" ? order : -order;
      }),
  };
}

/** A column header that sorts the list: a button, with the order said in words for screen readers. */
export function SortHead<K extends string>({
  sort,
  column,
  children,
  className = "",
}: {
  sort: Sort<K>;
  column: K;
  children: ReactNode;
  className?: string;
}) {
  const active = sort.key === column;
  const Icon = !active ? ArrowUpDown : sort.dir === "asc" ? ArrowUp : ArrowDown;
  return (
    <TableHead
      className={className}
      aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : undefined}
    >
      <button
        type="button"
        onClick={() => sort.toggle(column)}
        className={`inline-flex items-center gap-1 rounded font-semibold whitespace-nowrap hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-glow-cyan ${className.includes("text-right") ? "flex-row-reverse" : ""}`}
      >
        {children}
        <Icon aria-hidden className={`size-3.5 ${active ? "text-primary" : "text-ink-muted"}`} />
      </button>
    </TableHead>
  );
}

/** Dollars for a CSV cell from integer cents: 123456 -> "1234.56" (empty when there is none). */
export function csvMoney(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return "";
  const sign = cents < 0 ? "-" : "";
  const whole = Math.abs(cents);
  return `${sign}${(whole - (whole % 100)) / 100}.${String(whole % 100).padStart(2, "0")}`;
}

function cell(value: Value): string {
  const text = value === null || value === undefined ? "" : String(value);
  return /[",\n\r]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

/** The CSV text of the rows: a header row, then one row each (RFC 4180 quoting). */
export function toCsv<T>(rows: T[], columns: { header: string; value: (row: T) => Value }[]): string {
  const lines = [columns.map((c) => cell(c.header)).join(",")];
  for (const row of rows) lines.push(columns.map((c) => cell(c.value(row))).join(","));
  return `${lines.join("\r\n")}\r\n`;
}

export function CsvButton<T>({
  rows,
  columns,
  fileName,
}: {
  rows: T[];
  columns: { header: string; value: (row: T) => Value }[];
  fileName: string;
}) {
  return (
    <Button
      variant="outline"
      disabled={rows.length === 0}
      onClick={() => {
        const url = URL.createObjectURL(new Blob([toCsv(rows, columns)], { type: "text/csv;charset=utf-8" }));
        const link = document.createElement("a");
        link.href = url;
        link.download = fileName;
        link.click();
        URL.revokeObjectURL(url);
      }}
    >
      <Download aria-hidden /> Download CSV
    </Button>
  );
}
