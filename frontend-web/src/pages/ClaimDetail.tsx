// Claim detail: the review layout, read-only, plus the explanation rendered by the API from the
// decision record (§8.7); the summary, clinical note and audit trail as tabs on the right (D-UI-6),
// the original file the claim was filed from (D-DOC-1) and, once decided, the patient's EOB
// (D-EOB-1). Its appeals (D-APL-1), and for the reviewer who finalized it, the form to correct the
// model's criteria (D-FBK-1).

import { FileText } from "lucide-react";
import { Link, useLocation, useParams } from "react-router";

import { useAudit, useClaim, useExplanation } from "@/api/hooks";
import type { AuditEvent } from "@/api/types";
import { AuditTimeline } from "@/components/AuditTimeline";
import { OutcomeChip } from "@/components/Chip";
import { ClaimWorkspace } from "@/components/ClaimWorkspace";
import { FeedbackForm } from "@/components/Feedback";
import { AppealHistory } from "@/components/FollowUps";
import { PageTitle } from "@/components/Layout";
import { OriginalFileButton } from "@/components/OriginalFile";
import { ErrorNotice, Note, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { useUser } from "@/lib/auth";

/** The totals' names in words (fix 6): never the record's field names. */
const TOTAL_NAMES: Record<string, string> = {
  billed_cents: "billed",
  allowed_cents: "allowed",
  contractual_adjustment_cents: "contractual adjustment",
  deductible_cents: "deductible",
  copay_cents: "copay",
  coinsurance_cents: "coinsurance",
  plan_pays_cents: "plan pays",
  member_pays_cents: "member pays",
  cob_primary_paid_cents: "paid by the primary plan",
  balance_bill_exposure_cents: "balance bill",
};

export function totalNames(fields: string[]): string {
  const words = fields.map((f) => TOTAL_NAMES[f] ?? f.replace(/_cents$/, "").replaceAll("_", " "));
  if (words.length <= 1) return words.join("");
  return `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

export function ChangedAmounts({ events }: { events: AuditEvent[] }) {
  const finalized = [...events].reverse().find((e) => e.event_type === "FINALIZED");
  if (!finalized?.payload.amounts_changed_since_review) return null;
  const totals = (finalized.payload.changed_totals as string[] | undefined) ?? [];
  return (
    <Note>
      The final amounts differ from those shown at review{totals.length ? ` (${totalNames(totals)})` : ""}. They were
      recomputed at finalization from the final line decisions and the member's accumulators at that time.
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
  const { role, username } = useUser();
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
            <OriginalFileButton claimId={view.claim_id} documents={view.documents} />
            {view.eob && (
              <Button asChild variant="outline">
                <Link to={`/claims/${encodeURIComponent(view.claim_id)}/eob`}>
                  <FileText aria-hidden /> Patient EOB
                </Link>
              </Button>
            )}
            {action}
          </>
        }
      />
      {audit.data && (
        <div className="mb-6 empty:hidden">
          <ChangedAmounts events={audit.data} />
        </div>
      )}
      <AppealHistory appeals={view.appeals} staff />
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
      {role === "reviewer" && record?.review?.reviewer_id === username && view.status.startsWith("FINAL_") && (
        <FeedbackForm record={record} />
      )}
    </>
  );
}
