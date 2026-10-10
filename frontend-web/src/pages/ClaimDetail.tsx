// Claim detail: status, line decisions, amounts, the explanation rendered by the API from the
// decision record (§8.7), and the audit trail as a timeline.

import { Link, useParams } from "react-router";

import { useAudit, useClaim, useExplanation, useProcess } from "../api/hooks";
import type { AuditEvent } from "../api/types";
import { AuditTimeline } from "../components/AuditTimeline";
import { DecisionChip, StatusChip } from "../components/Chip";
import { PageTitle, Section } from "../components/Layout";
import { AmountsTable } from "../components/Record";
import { ErrorNotice, Skeleton } from "../components/States";
import { button, table, td, th } from "../components/ui";
import { reason, SOURCE } from "../lib/labels";
import { useSession } from "../lib/session";

export function ChangedAmounts({ events }: { events: AuditEvent[] }) {
  const finalized = [...events].reverse().find((e) => e.event_type === "FINALIZED");
  if (!finalized?.payload.amounts_changed_since_review) return null;
  const totals = (finalized.payload.changed_totals as string[] | undefined) ?? [];
  return (
    <p role="note" className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
      The final amounts differ from those shown at review ({totals.join(", ")}): they were
      recomputed at finalization from the final line decisions and the member's accumulators at
      that time.
    </p>
  );
}

export function ClaimDetail() {
  const { claimId = "" } = useParams();
  const claim = useClaim(claimId);
  const audit = useAudit(claimId);
  const record = claim.data?.record ?? null;
  const explanation = useExplanation(claimId, record !== null);
  const process = useProcess();
  const { role } = useSession();

  if (claim.isPending) return <Skeleton lines={8} />;
  if (claim.error) return <ErrorNotice error={claim.error} onRetry={() => void claim.refetch()} />;
  const view = claim.data;
  return (
    <>
      <PageTitle title={`Claim ${view.claim_id}`} />
      <div className="mb-8 flex flex-wrap items-center gap-4">
        <StatusChip status={view.status} showHint />
        {view.status === "RECEIVED" && (
          <button
            type="button"
            className={button.primary}
            disabled={process.isPending}
            onClick={() => process.mutate(view.claim_id)}
          >
            {process.isPending ? "Processing…" : "Process claim"}
          </button>
        )}
        {view.status === "AWAITING_REVIEW" && role !== "provider" && (
          <Link className={button.primary} to={`/review/${encodeURIComponent(view.claim_id)}`}>
            Review this claim
          </Link>
        )}
      </div>
      {process.error && (
        <div className="mb-6">
          <ErrorNotice error={process.error} />
        </div>
      )}
      {audit.data && <ChangedAmounts events={audit.data} />}
      {record && (
        <>
          <Section title="Line decisions">
            {record.line_decisions.length === 0 ? (
              <p className="text-gray-600">No line decisions: the rules decided the whole claim.</p>
            ) : (
              <div className="overflow-auto rounded-md border border-gray-200">
                <table className={table}>
                  <thead>
                    <tr>
                      <th scope="col" className={th}>Line</th>
                      <th scope="col" className={th}>Decision</th>
                      <th scope="col" className={th}>Decided by</th>
                      <th scope="col" className={th}>Reasons</th>
                    </tr>
                  </thead>
                  <tbody>
                    {record.line_decisions.map((line) => (
                      <tr key={line.line_no}>
                        <td className={td}>{line.line_no}</td>
                        <td className={td}>
                          <DecisionChip decision={line.decision} />
                        </td>
                        <td className={td}>{SOURCE[line.source] ?? line.source}</td>
                        <td className={td}>{line.reason_codes.map(reason).join("; ")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Section>
          <Section title="Amounts">
            <AmountsTable record={record} />
          </Section>
          <Section title="Explanation">
            {explanation.isPending ? (
              <Skeleton lines={6} />
            ) : explanation.error ? (
              <ErrorNotice error={explanation.error} onRetry={() => void explanation.refetch()} />
            ) : (
              <div
                data-testid="explanation"
                className="explanation rounded-lg border border-gray-200 p-5"
                // The API renders this fragment from the decision record with autoescaping (§8.7).
                dangerouslySetInnerHTML={{ __html: explanation.data }}
              />
            )}
          </Section>
        </>
      )}
      <Section title="Audit trail">
        {audit.isPending ? (
          <Skeleton lines={4} />
        ) : audit.error ? (
          <ErrorNotice error={audit.error} onRetry={() => void audit.refetch()} />
        ) : (
          <div data-testid="audit-trail">
            <AuditTimeline events={audit.data} />
          </div>
        )}
      </Section>
    </>
  );
}
