// The audit trail as a simple timeline (§8.9): when (to the second), what happened, who did it, the
// versions the step ran with and the request that wrote it (D-OBS-1). A provider's corrections
// before processing name the boxes and, for all but the patient's, the text before and after
// (D-FIX-1); an override names each line's decision before and after, its reason code and the
// reviewer's note (fix 4); follow-ups, appeals and feedback say what they did (D-FUP-1, D-APL-1,
// D-FBK-1). Read from GET /v1/claims/{id}/audit (staff only); insert-only on the server.

import type { AuditEvent, ClaimStatus } from "@/api/types";
import { dateTimeSeconds, fieldLabel } from "@/lib/format";
import { APPEAL_OUTCOME, CRITERION_STATUS, DECISION, STATUS } from "@/lib/labels";

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
  FIELD_CORRECTED: "Boxes corrected by the provider",
  CLAIM_REOPENED: "Sent back to the provider",
  DOCUMENTATION_ADDED: "Documentation added",
  APPEAL_FILED: "Appeal filed",
  APPEAL_DECIDED: "Appeal decided",
  REVIEWER_FEEDBACK: "Reviewer corrected the model's criteria",
};

interface Change {
  line_no: number;
  reason?: string | null;
  reason_code?: string | null;
  before?: { decision?: string; benefit_category?: string | null };
  after?: { decision?: string; benefit_category?: string | null };
}

function decision(value: string | undefined): string {
  return value ? (DECISION[value as keyof typeof DECISION]?.label ?? value) : "—";
}

function statusLabel(value: unknown): string {
  return typeof value === "string" ? (STATUS[value as ClaimStatus]?.label ?? value) : "";
}

/** What an event did, in a line or two each: overrides line by line, follow-ups, appeals and
 * feedback. The payloads hold IDs, codes and counts only (§8.9). */
export function details(event: AuditEvent): string[] {
  const p = event.payload;
  switch (event.event_type) {
    case "REVIEW_OVERRIDDEN":
      return ((p.changes as Change[] | undefined) ?? []).map((c) => {
        const code = c.reason_code ? ` (${c.reason_code})` : "";
        const note = c.reason ? `. Note: ${c.reason}` : "";
        return `Line ${c.line_no}: ${decision(c.before?.decision)} → ${decision(c.after?.decision)}${code}${note}`;
      });
    case "AUTO_OUTCOME":
    case "FINALIZED":
      return p.status ? [statusLabel(p.status)] : [];
    case "CLAIM_REOPENED":
      return [
        `${p.purpose === "documentation" ? "To add documentation" : "To correct and resubmit"}; it was ${statusLabel(p.previous_status).toLowerCase()}`,
      ];
    case "DOCUMENTATION_ADDED":
      return [`${Number(p.characters ?? 0).toLocaleString("en-US")} characters added to the clinical notes`];
    case "APPEAL_FILED":
      return [
        `By the ${p.filed_role === "member" ? "member" : "provider"}${p.previous_reviewer ? `; first decided by ${String(p.previous_reviewer)}, who cannot decide the appeal` : ""}`,
      ];
    case "APPEAL_DECIDED":
      return [APPEAL_OUTCOME[String(p.outcome)] ?? String(p.outcome ?? "")];
    case "REVIEWER_FEEDBACK":
      return (
        (p.lines as { line_no: number; criteria: { criterion_id: string; model_status: string; status: string }[] }[]) ??
        []
      ).flatMap((line) =>
        line.criteria.map(
          (c) =>
            `Line ${line.line_no}, ${c.criterion_id}: ${CRITERION_STATUS[c.model_status] ?? c.model_status} → ${CRITERION_STATUS[c.status] ?? c.status}`,
        ),
      );
    default:
      return [];
  }
}

interface Corrected {
  field: string;
  before?: string | null;
  after?: string | null;
}

/** What a FIELD_CORRECTED event changed, one box per item. */
export function corrections(event: AuditEvent): string[] {
  if (event.event_type !== "FIELD_CORRECTED") return [];
  const fields = (event.payload.fields as Corrected[] | undefined) ?? [];
  return fields.map((f) =>
    "after" in f
      ? `${fieldLabel(f.field)}: ${f.before ?? "(blank)"} → ${f.after ?? "(blank)"}`
      : `${fieldLabel(f.field)} (patient detail, not shown)`,
  );
}

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
            <span className="mt-2 size-2.5 rounded-full bg-primary shadow-[0_0_0_4px_#e6ebff]" />
            {i < events.length - 1 && <span className="absolute top-5 bottom-[-6px] w-px bg-rules" />}
          </span>
          <div className="min-w-0">
            <p className="font-semibold">{EVENTS[event.event_type] ?? event.event_type}</p>
            <p className="text-[13px] text-ink-muted">
              <time dateTime={event.created_at}>{dateTimeSeconds(event.created_at)}</time>, by {event.actor}
            </p>
            {[...corrections(event), ...details(event)].length > 0 && (
              <ul className="text-[13px] break-words text-ink">
                {[...corrections(event), ...details(event)].map((text) => (
                  <li key={text}>{text}</li>
                ))}
              </ul>
            )}
            {versions(event) && <p className="text-[13px] break-words text-ink-muted">{versions(event)}</p>}
            {event.request_id && (
              <p className="text-[13px] text-ink-muted">
                Request <span className="tabular-nums">{event.request_id.slice(0, 12)}</span>
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
