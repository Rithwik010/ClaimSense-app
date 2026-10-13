// The audit trail as a simple timeline (§8.9): when, what happened, who did it, and the versions
// the step ran with. Read from GET /v1/claims/{id}/audit; insert-only on the server.

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

function versions(event: AuditEvent): string {
  const parts = [
    event.rules_version && `rules ${event.rules_version}`,
    event.model_name && `model ${event.model_name}`,
    event.prompt_version && `prompt ${event.prompt_version}`,
  ].filter(Boolean);
  const policies = Object.keys(event.policy_versions ?? {}).length;
  if (policies) parts.push(`${policies} polic${policies === 1 ? "y" : "ies"}`);
  return parts.join(", ");
}

export function AuditTimeline({ events }: { events: AuditEvent[] }) {
  return (
    <ol aria-label="Audit trail" className="surface rounded-lg px-5 py-4">
      {events.map((event, i) => (
        <li key={event.id} className="relative grid grid-cols-[16px_1fr] gap-x-3 pb-4 last:pb-0">
          <span aria-hidden className="relative flex justify-center">
            <span className="mt-2 size-2.5 rounded-full bg-glow-blue shadow-[0_0_0_4px_rgb(111_140_255/0.16)]" />
            {i < events.length - 1 && <span className="absolute top-5 bottom-[-6px] w-px bg-[linear-gradient(var(--color-glow-blue),rgb(103_232_249/0.25))] opacity-60" />}
          </span>
          <div className="min-w-0">
            <p className="font-semibold">{EVENTS[event.event_type] ?? event.event_type}</p>
            <p className="text-[13px] text-ink-muted">
              <time dateTime={event.created_at}>{dateTime(event.created_at)}</time>, by {event.actor}
            </p>
            {versions(event) && <p className="text-[13px] break-words text-ink-muted">{versions(event)}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
