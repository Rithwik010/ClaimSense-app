// Claim result (a provider's own claim, D-AUTH-1). Until it is final: "In review" and how far it
// went (the stage strip), nothing of the recommendation. Once final (D-UI-6): the outcome; for a
// claim not fully paid, why in plain words, what to check on the claim and the standard reason
// codes; for a paid claim (or the paid lines of a partly approved one), the billing with a sentence
// for each reduction. All of it is built by the API from the decision record; the page shows no
// rule IDs, internal codes, criterion IDs, model output, confidence scores or versions.

import { useParams } from "react-router";
import { toast } from "sonner";

import { useMyClaim, useProcess } from "@/api/hooks";
import { Billing } from "@/components/Billing";
import { OutcomeChip } from "@/components/Chip";
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
            <OutcomeChip outcome={view.outcome} provider showHint />
            <OriginalFileButton claimId={view.claim_id} document={view.document} />
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
      {!explanation ? (
        <Note tone="neutral">
          {view.status === "IN_REVIEW"
            ? "In review. A reviewer is checking the recommendation; the decision shows here once it is final."
            : "Not processed yet. Process the claim to run the rules, the model and the calculator."}
        </Note>
      ) : (
        <>
          <ProviderOutcome explanation={explanation} />
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
