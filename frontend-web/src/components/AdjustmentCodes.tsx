// External reason codes (CARC/RARC) of a DENY or REJECT reason with their official descriptions
// (D-CARC-2). The API looks them up by reason code; the UI only shows them.

import type { Adjustment } from "@/api/types";

export function AdjustmentCodes({ items, title = "Adjustment codes" }: { items: Adjustment[]; title?: string }) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-md border border-rules bg-canvas/60 px-3 py-2.5">
      <p className="text-[13px] font-semibold text-ink-muted">{title}</p>
      <ul className="mt-1 space-y-2">
        {items.map((a, i) => (
          <li key={`${a.line_no ?? "claim"}-${a.reason_code}-${i}`} className="text-[14px]">
            <span className="text-[13px] text-ink-muted">
              {a.line_no ? `Line ${a.line_no}, ` : ""}
              group {a.group_code}
            </span>
            {a.codes.map((c) => (
              <span key={c.kind + c.code} className="block">
                <span className="font-semibold">
                  {c.kind} {c.code}
                </span>
                {c.description && <span className="text-ink-muted">: {c.description}</span>}
              </span>
            ))}
            {a.billing_article && (
              <span className="block text-[13px] text-ink-muted">
                Billing article {a.billing_article}
                {a.lcds.length ? `, related LCD ${a.lcds.join(", ")}` : ", no related LCD"}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
