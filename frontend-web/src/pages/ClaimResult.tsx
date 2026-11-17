// Claim result (a provider's own claim, D-AUTH-1). Not processed yet: the check before processing
// and the boxes read, with corrections (D-CHK-1, D-FIX-1). Until it is final: "In review" and how
// far it went (the stage strip), nothing of the recommendation. Once final (D-UI-6): the outcome;
// for a claim not fully paid, why in plain words, what to check on the claim and the standard
// reason codes; for a paid claim (or the paid lines of a partly approved one), the billing with a
// sentence for each reduction; and, once the plan decided it, the patient's EOB (D-EOB-1). A decided
// claim offers what can be done next (D-FUP-1, D-APL-1): correct and resubmit, send documentation,
// or appeal; a claim sent back is "Not processed" again, its boxes correctable. All of it is built
// by the API from the decision record; the page shows no rule IDs, internal codes, criterion IDs,
// model output or versions.

import { FileText } from "lucide-react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { useMyClaim, useProcess } from "@/api/hooks";
import { Billing } from "@/components/Billing";
import { OutcomeChip } from "@/components/Chip";
import { ClaimPrep } from "@/components/ClaimPrep";
import { AppealHistory, FollowUpActions } from "@/components/FollowUps";
import { PageTitle, Section } from "@/components/Layout";
import { OriginalFileButton } from "@/components/OriginalFile";
import { ProviderOutcome } from "@/components/ProviderOutcome";
import { providerStages, StageStrip } from "@/components/StageStrip";
import { ErrorNotice, Note, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";

export function ClaimResult() {
  const { claimId = "" } = useParams();
  const claim = useMyClaim(claimId);
  const process = useProcess();

  if (claim.isPending) return <Skeleton lines={8} />;
  if (claim.error) return <ErrorNotice error={claim.error} onRetry={() => void claim.refetch()} />;
  const view = claim.data;
  const explanation = view.final ? view.explanation : null;
  return (
    <>
      <PageTitle
        title={`Claim ${view.claim_id}`}
        actions={
          <>
            <OutcomeChip outcome={view.outcome} provider status={view.status} showHint />
            <OriginalFileButton claimId={view.claim_id} documents={view.documents} />
            {view.eob && (
              <Button asChild variant="outline">
                <Link to={`/my-claims/${encodeURIComponent(view.claim_id)}/eob`}>
                  <FileText aria-hidden /> Patient EOB
                </Link>
              </Button>
            )}
            {view.status === "RECEIVED" && (
              <Button
                size="lg"
                disabled={process.isPending}
                onClick={() => process.mutate(view.claim_id, { onSuccess: () => toast.success("Claim processed") })}
              >
                {process.isPending ? "Processing" : "Process claim"}
              </Button>
            )}
          </>
        }
      />
      {process.error && (
        <div className="mb-6">
          <ErrorNotice error={process.error} />
        </div>
      )}
      <StageStrip list={providerStages(view)} />
      {view.status === "RECEIVED" ? (
        <>
          <div className="mb-6">
            <Note tone="neutral">
              {view.follow_ups?.reopened
                ? "Sent back to you. Correct any box that needs it (and add documentation if the plan asked for it), check the claim, then process it to run the rules, the model and the review again."
                : "Not processed yet. Check the claim and correct any box read wrong, then process it to run the rules, the model and the calculator."}
            </Note>
          </div>
          <ClaimPrep
            claimId={view.claim_id}
            sourceFormat={view.source_format}
            claim={view.received}
            reopened={view.follow_ups?.reopened}
          />
        </>
      ) : !explanation ? (
        <>
          <Note tone="neutral">
            {view.appeals?.some((a) => a.status === "OPEN")
              ? "Appealed. A reviewer who did not deny the claim is deciding it again; the decision shows here once it is final."
              : "In review. A reviewer is checking the recommendation; the decision shows here once it is final."}
          </Note>
          <div className="mt-8">
            <AppealHistory appeals={view.appeals} />
          </div>
        </>
      ) : (
        <>
          <ProviderOutcome explanation={explanation} />
          <FollowUpActions claimId={view.claim_id} followUps={view.follow_ups} />
          <AppealHistory appeals={view.appeals} />
          {explanation.billing && (
            <Section title="Billing">
              <Billing lines={explanation.billing.lines} totals={explanation.billing.totals} />
            </Section>
          )}
        </>
      )}
    </>
  );
}
