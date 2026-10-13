// The Reason column (D-UI-6): one line of plain words from the API's reason table for a claim not
// paid as billed, the first reason plus "+N more"; the tooltip lists every reason with its internal
// code and rule, which reviewers and admins may see. "—" when there is none (approved, in review,
// not processed). The text is cut with an ellipsis rather than wrapping the row.

import type { Reason } from "@/api/types";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function words(reason: Reason): string {
  return `${reason.line_no ? `Line ${reason.line_no}: ` : ""}${reason.short}`;
}

function codes(reason: Reason): string {
  return [reason.code, reason.rule_id].filter(Boolean).join(", ");
}

export function ReasonCell({ reasons }: { reasons: Reason[] }) {
  const [first, ...rest] = reasons;
  if (!first) return <span className="text-ink-muted">—</span>;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          className="flex w-full max-w-[18rem] min-w-0 items-baseline gap-2 rounded-sm text-left"
          data-testid="reason"
        >
          <span className="min-w-0 truncate">{words(first)}</span>
          {rest.length > 0 && <span className="shrink-0 text-[13px] text-ink-muted">+{rest.length} more</span>}
        </button>
      </TooltipTrigger>
      <TooltipContent side="top" align="start" className="max-w-sm">
        <ul className="space-y-1">
          {reasons.map((reason) => (
            <li key={`${reason.line_no ?? "claim"}-${reason.code}`}>
              {words(reason)} <span className="text-ink-muted">({codes(reason)})</span>
            </li>
          ))}
        </ul>
      </TooltipContent>
    </Tooltip>
  );
}
