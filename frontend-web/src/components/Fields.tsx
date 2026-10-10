// The claim's fields as read at intake, each with its confidence; a field read below the
// extraction threshold is highlighted (§8.2, H5). A JSON claim lists no confidences (all 1.0).

import type { Claim } from "@/api/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fieldLabel, money } from "@/lib/format";
import { LOW_CONFIDENCE } from "@/lib/labels";

const JOINED = new Set(["modifiers", "diagnosis_pointers"]);

interface Row {
  path: string;
  value: string;
}

export function flatten(value: unknown, path = ""): Row[] {
  if (value === null || value === undefined || value === "") return [];
  const name = path.split(".").pop() ?? "";
  if (Array.isArray(value)) {
    if (JOINED.has(name)) return value.length ? [{ path, value: value.join(" ") }] : [];
    return value.flatMap((item, i) => flatten(item, `${path}.${i}`));
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, item]) =>
      flatten(item, path ? `${path}.${key}` : key),
    );
  }
  if (typeof value === "boolean") return [{ path, value: value ? "Yes" : "No" }];
  if (name.endsWith("_cents") && typeof value === "number") return [{ path, value: money(value) }];
  return [{ path, value: String(value) }];
}

/** A field's confidence: its own, or that of the box it was read from (an enclosing path). */
export function confidenceOf(path: string, confidences: Record<string, number>): number | null {
  let probe = path;
  for (;;) {
    if (probe in confidences) return confidences[probe] ?? null;
    const cut = probe.lastIndexOf(".");
    if (cut < 0) return null;
    probe = probe.slice(0, cut);
  }
}

export function FieldsTable({
  claim,
  confidences,
  jsonClaim,
}: {
  claim: Claim;
  confidences: Record<string, number>;
  jsonClaim: boolean;
}) {
  const read = flatten(claim);
  // A field with a confidence but no value was unreadable (its text failed its format check).
  const unreadable = Object.keys(confidences)
    .filter((key) => !read.some((row) => row.path === key || row.path.startsWith(`${key}.`)))
    .map((key) => ({ path: key, value: "(could not be read)" }));
  const rows = [...read, ...unreadable];
  const low = rows.filter((row) => {
    const found = confidenceOf(row.path, confidences);
    return found !== null && found < LOW_CONFIDENCE;
  }).length;
  return (
    <div>
      <p className="mb-3 max-w-[72ch] text-[13px] text-ink-muted">
        {jsonClaim
          ? "A JSON claim is read exactly, so every field has full confidence."
          : low
            ? `${low} field${low === 1 ? "" : "s"} read with low confidence (below ${LOW_CONFIDENCE}). A rule that fails on one of them rejects the claim instead of denying it.`
            : "Every field was read with high confidence."}
      </p>
      <div className="max-h-[28rem] overflow-auto rounded-lg border border-rules bg-paper">
        <Table>
          <TableHeader className="sticky top-0 bg-paper">
            <TableRow>
              <TableHead>Field</TableHead>
              <TableHead>Value</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => {
              const found = jsonClaim ? 1 : confidenceOf(row.path, confidences);
              const isLow = found !== null && found < LOW_CONFIDENCE;
              return (
                <TableRow key={row.path} className={isLow ? "bg-pend-tint hover:bg-pend-tint" : undefined}>
                  <TableCell className="whitespace-nowrap text-ink-muted">{fieldLabel(row.path)}</TableCell>
                  <TableCell className="max-w-xl break-words whitespace-pre-wrap">{row.value}</TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {isLow && <span className="mr-2 text-[13px] font-semibold text-pend">Low</span>}
                    {found === null ? "—" : `${Math.round(found * 100)}%`}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
