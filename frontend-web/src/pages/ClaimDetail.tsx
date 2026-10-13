// Claim detail: the review layout, read-only, plus the explanation rendered by the API from the
// decision record (§8.7); the summary, clinical note and audit trail as tabs on the right (D-UI-6),
// and the original file the claim was filed from (D-DOC-1).

import { Link, useLocation, useParams } from "react-router";

import { useAudit, useClaim, useExplanation } from "@/api/hooks";
import type { AuditEvent } from "@/api/types";
import { AuditTimeline } from "@/components/AuditTimeline";
import { OutcomeChip } from "@/components/Chip";
import { ClaimWorkspace } from "@/components/ClaimWorkspace";
import { PageTitle } from "@/components/Layout";
import { OriginalFileButton } from "@/components/OriginalFile";
import { ErrorNotice, Note, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/auth";

export function ChangedAmounts({ events }: { events: AuditEvent[] }) {
  const finalized = [...events].reverse().find((e) => e.event_type === "FINALIZED");
  if (!finalized?.payload.amounts_changed_since_review) return null;
  const totals = (finalized.payload.changed_totals as string[] | undefined) ?? [];
  return (
    <Note>
      The final amounts differ from those shown at review ({totals.join(", ")}). They were recomputed at
      finalization from the final line decisions and the member's accumulators at that time.
    </Note>
  );
}

export function ClaimDetail() {
  const { claimId = "" } = useParams();
  const { state } = useLocation();
  const claim = useClaim(claimId);
  const audit = useAudit(claimId);
  const record = claim.data?.record ?? null;
  const explanation = useExplanation(claimId, record !== null);
  const { role } = useUser();
  const fill = Boolean((state as { justProcessed?: boolean } | null)?.justProcessed);

  if (claim.isPending) return <Skeleton lines={8} />;
  if (claim.error) return <ErrorNotice error={claim.error} onRetry={() => void claim.refetch()} />;
  const view = claim.data;
  // Only the provider who filed a claim processes it (D-AUTH-1); a reviewer reviews it.
  const action =
    view.status === "AWAITING_REVIEW" && role === "reviewer" ? (
      <Button asChild size="lg">
        <Link to={`/review/${encodeURIComponent(view.claim_id)}`}>Review claim</Link>
      </Button>
    ) : null;
  return (
    <>
      <PageTitle
        title={`Claim ${view.claim_id}`}
        actions={
          <>
            <OutcomeChip outcome={view.outcome} showHint />
            <OriginalFileButton claimId={view.claim_id} document={view.document} />
            {action}
          </>
        }
      />
      {audit.data && (
        <div className="mb-6 empty:hidden">
          <ChangedAmounts events={audit.data} />
        </div>
      )}
      <ClaimWorkspace
        view={view}
        events={audit.data ?? []}
        fill={fill}
        audit={
          audit.isPending ? (
            <Skeleton lines={4} />
          ) : audit.error ? (
            <ErrorNotice error={audit.error} onRetry={() => void audit.refetch()} />
          ) : (
            <div data-testid="audit-trail">
              <AuditTimeline events={audit.data} />
            </div>
          )
        }
        extraTabs={[
          ...(record
            ? [
                {
                  value: "explanation",
                  label: "Explanation",
                  content: explanation.isPending ? (
                    <Skeleton lines={6} />
                  ) : explanation.error ? (
                    <ErrorNotice error={explanation.error} onRetry={() => void explanation.refetch()} />
                  ) : (
                    <div
                      data-testid="explanation"
                      className="explanation surface rounded-lg p-5"
                      // The API renders this fragment from the decision record with autoescaping (§8.7).
                      dangerouslySetInnerHTML={{ __html: explanation.data }}
                    />
                  ),
                },
              ]
            : []),
        ]}
      />
    </>
  );
}
