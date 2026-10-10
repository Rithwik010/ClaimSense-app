import type { AuditEvent } from "@/api/types";
import { dateTime } from "@/lib/format";

export const EVENTS: Record<string, string> = {
  INTAKE_COMPLETED: "Claim received",
  RULES_EVALUATED: "Rules checked",
  AUTO_OUTCOME: "Decided by the rules",
  CONTEXT_ASSEMBLED: "Coverage criteria gathered",
  SLM_RECOMMENDED: "Model recommendation",
  OUTPUT_INVALID: "Model answer could not be used",
  VALIDATION: "Recommendation checked",
  CALCULATED: "Amounts calculated",
  CALCULATION_FAILED: "Amounts could not be calculated",
  EXPLANATION_BUILT: "Explanation built",
  REVIEW_OPENED: "Opened for review",
  REVIEW_ACCEPTED: "Recommendation accepted",
  REVIEW_OVERRIDDEN: "Lines overridden",
  FINALIZED: "Finalized",
};

export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  return (
    <ol className="rounded-lg border border-rules bg-paper px-5 py-4">
      {events.map((event, i) => (
        <li key={event.id} className="relative grid grid-cols-[16px_1fr] gap-x-3 pb-4 last:pb-0">
          <span aria-hidden className="relative flex justify-center">
            <span className="mt-2 size-2 rounded-full bg-ink" />
            {i < events.length - 1 && <span className="absolute top-4 bottom-[-8px] w-px bg-rules" />}
          </span>
          <div>
            <p className="font-semibold">{EVENTS[event.event_type] ?? event.event_type}</p>
            <p className="text-[13px] text-ink-muted">
              {dateTime(event.created_at)}, by {event.actor}
            </p>
          </div>
        </li>
      ))}
    </ol>
  );
}
