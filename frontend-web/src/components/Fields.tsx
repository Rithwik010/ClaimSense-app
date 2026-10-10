// The claim's fields as read at intake, each with its confidence; a field read below the
// extraction threshold is highlighted (§8.2, H5). A JSON claim lists no confidences (all 1.0).

import { fieldLabel, money } from "../lib/format";
import { LOW_CONFIDENCE } from "../lib/labels";
import type { Claim } from "../api/types";
import { table, td, th } from "./ui";

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
      <p className="mb-3 text-sm text-gray-600">
        {jsonClaim
          ? "A JSON claim is read exactly: every field has full confidence."
          : low
            ? `${low} field${low === 1 ? "" : "s"} read with low confidence (below ${LOW_CONFIDENCE}). A rule that fails on one rejects the claim instead of denying it.`
            : "Every field was read with high confidence."}
      </p>
      <div className="max-h-[28rem] overflow-auto rounded-md border border-gray-200">
        <table className={table}>
          <thead className="sticky top-0 bg-white">
            <tr>
              <th scope="col" className={th}>Field</th>
              <th scope="col" className={th}>Value</th>
              <th scope="col" className={th}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const found = jsonClaim ? 1 : confidenceOf(row.path, confidences);
              const isLow = found !== null && found < LOW_CONFIDENCE;
              return (
                <tr key={row.path} className={isLow ? "bg-amber-50" : undefined}>
                  <td className={`${td} whitespace-nowrap text-gray-700`}>{fieldLabel(row.path)}</td>
                  <td className={`${td} max-w-xl whitespace-pre-wrap break-words`}>{row.value}</td>
                  <td className={`${td} whitespace-nowrap`}>
                    {found === null ? "—" : `${Math.round(found * 100)}%`}
                    {isLow && (
                      <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-900">
                        Low
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
