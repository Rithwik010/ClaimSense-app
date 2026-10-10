import type { AuditEvent } from "../api/types";
import { dateTime } from "../lib/format";

const EVENTS: Record<string, string> = {
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
  REVIEW_ACCEPTED: "Review: accepted",
  REVIEW_OVERRIDDEN: "Review: lines changed",
  FINALIZED: "Finalized",
};

export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  return (
    <ol className="relative ml-2 border-l border-gray-200">
      {events.map((event) => (
        <li key={event.id} className="mb-5 ml-5">
          <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full bg-accent" aria-hidden />
          <p className="font-medium">{EVENTS[event.event_type] ?? event.event_type}</p>
          <p className="text-sm text-gray-600">
            {dateTime(event.created_at)} · {event.actor}
          </p>
        </li>
      ))}
    </ol>
  );
}
