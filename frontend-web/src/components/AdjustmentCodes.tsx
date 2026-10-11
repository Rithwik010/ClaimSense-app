// The standard reason codes of a denied or rejected line or claim (CARC, with any RARC) and their
// official descriptions (D-CARC-2), plus the billing article and its LCDs for a diagnosis that does
// not support the service (R15). The API looks them up; the UI only lays them out.

import type { Adjustment } from "@/api/types";
import { PlainBadge } from "@/components/Chip";

const GROUPS: Record<string, string> = {
  CO: "contractual obligation",
  PR: "patient responsibility",
  OA: "other adjustment",
  PI: "payer initiated",
};

export function AdjustmentCodes({ items, title = "Reason codes" }: { items: Adjustment[]; title?: string }) {
  if (items.length === 0) return null;
  return (
    <section aria-label={title} className="rounded-md border border-rules bg-paper">
      <h3 className="border-b border-rules px-3 py-2 text-[13px] font-semibold">{title}</h3>
      <ul className="divide-y divide-rules">
        {items.map((a, i) => (
          <li key={`${a.line_no ?? "claim"}-${a.reason_code}-${i}`} className="px-3 py-2.5">
            <p className="text-[13px] text-ink-muted">
              {a.line_no ? `Line ${a.line_no}` : "The whole claim"}, group {a.group_code}
              {GROUPS[a.group_code] ? ` (${GROUPS[a.group_code]})` : ""}
            </p>
            <dl className="mt-1.5 space-y-1.5">
              {a.codes.map((c) => (
                <div key={c.kind + c.code} className="grid grid-cols-[auto_1fr] items-start gap-x-2.5">
                  <dt>
                    <PlainBadge>
                      {c.kind} {c.code}
                    </PlainBadge>
                  </dt>
                  <dd className="pt-0.5 text-[14px] leading-5">{c.description ?? "Description not loaded"}</dd>
                </div>
              ))}
            </dl>
            {a.billing_article && (
              <p className="mt-1.5 text-[13px] text-ink-muted">
                Billing article {a.billing_article};{" "}
                {a.lcds.length ? `related LCD ${a.lcds.join(", ")}` : "no related LCD"}
              </p>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
