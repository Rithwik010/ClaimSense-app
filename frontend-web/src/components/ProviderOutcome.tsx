// The provider's explanation of a final claim not fully paid (D-UI-6): the outcome, why (a plain
// sentence per reason, by line where it is line-level), what to check on the claim with the values
// sent, then the standard CARC/RARC codes with their descriptions. The API builds every word from
// the decision record and its reason table; no rule IDs, internal codes or model output reach here.

import { CircleCheck, CircleHelp, CircleSlash, CircleX } from "lucide-react";

import type { CodeGroup, ExplanationItem, ProviderExplanation } from "@/api/types";
import { PlainBadge } from "@/components/Chip";
import { Panel } from "@/components/Layout";

const LOOK: Record<string, { Icon: typeof CircleCheck; className: string }> = {
  APPROVED: { Icon: CircleCheck, className: "text-approve" },
  PARTLY_APPROVED: { Icon: CircleCheck, className: "text-approve" },
  PENDED: { Icon: CircleHelp, className: "text-pend" },
  DENIED: { Icon: CircleX, className: "text-deny" },
  REJECTED: { Icon: CircleSlash, className: "text-reject" },
};

function itemText(item: ExplanationItem): string {
  return item.line_no ? `Line ${item.line_no}: ${item.text}` : item.text;
}

export function CodeChips({ groups }: { groups: CodeGroup[] }) {
  if (groups.length === 0) return null;
  return (
    <section aria-label="Reason codes" className="mt-5 border-t border-rules pt-4">
      <h3 className="text-[13px] font-semibold text-ink-muted">Reason codes</h3>
      <ul className="mt-2 space-y-2">
        {groups.flatMap((group) =>
          group.codes.map((code) => (
            <li
              key={`${group.line_no ?? "claim"}-${code.kind}-${code.code}`}
              className="grid grid-cols-[auto_1fr] items-start gap-x-2.5"
            >
              <PlainBadge>
                {code.kind} {code.code}
              </PlainBadge>
              <span className="pt-0.5 text-[13px] leading-5 text-ink-muted">
                {group.line_no ? `Line ${group.line_no}: ` : ""}
                {code.description ?? "Description not loaded"}
              </span>
            </li>
          )),
        )}
        {groups
          .filter((group) => group.billing_article)
          .map((group) => (
            <li key={`${group.line_no ?? "claim"}-article`} className="text-[13px] text-ink-muted">
              Billing article {group.billing_article};{" "}
              {group.lcds.length ? `related LCD ${group.lcds.join(", ")}` : "no related LCD"}
            </li>
          ))}
      </ul>
    </section>
  );
}

export function ProviderOutcome({ explanation }: { explanation: ProviderExplanation }) {
  const look = LOOK[explanation.outcome] ?? LOOK.PENDED!;
  return (
    <Panel glass className="mb-8 p-5 md:p-6">
      <h2 className="flex items-center gap-2 text-[22px] leading-8 font-bold">
        <look.Icon aria-hidden className={`size-5 shrink-0 ${look.className}`} strokeWidth={2.25} />
        {explanation.heading}
      </h2>
      {explanation.why.length === 0 ? (
        <p className="mt-2 text-ink-muted">Every line was approved. The billing below shows what the plan pays.</p>
      ) : (
        <>
          <section aria-label="Why" className="mt-4">
            <h3 className="font-semibold">Why</h3>
            <ul className="mt-1.5 list-disc space-y-1.5 pl-5 marker:text-ink-muted">
              {explanation.why.map((item) => (
                <li key={itemText(item)}>{itemText(item)}</li>
              ))}
            </ul>
          </section>
          {explanation.review.length > 0 && (
            <section aria-label="Please review the following details" className="mt-5">
              <h3 className="font-semibold">Please review the following details</h3>
              <ul className="mt-1.5 list-disc space-y-1.5 pl-5 marker:text-ink-muted">
                {explanation.review.map((item) => (
                  <li key={item.text} className="break-words">
                    {item.text}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
      <CodeChips groups={explanation.codes} />
    </Panel>
  );
}
