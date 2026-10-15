// Claim result (a provider's own claim, D-AUTH-1). Not processed yet: the check before processing
// and the boxes read, with corrections (D-CHK-1, D-FIX-1). Until it is final: "In review" and how
// far it went (the stage strip), nothing of the recommendation. Once final (D-UI-6): the outcome;
// for a claim not fully paid, why in plain words, what to check on the claim and the standard
// reason codes; for a paid claim (or the paid lines of a partly approved one), the billing with a
// sentence for each reduction; and, once the plan decided it, the patient's EOB (D-EOB-1). All of
// it is built by the API from the decision record; the page shows no rule IDs, internal codes,
// criterion IDs, model output or versions.

import { FileText } from "lucide-react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { useMyClaim, useProcess } from "@/api/hooks";
import { Billing } from "@/components/Billing";
import { OutcomeChip } from "@/components/Chip";
import { ClaimPrep } from "@/components/ClaimPrep";
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
              Not processed yet. Check the claim and correct any box read wrong, then process it to run the rules,
              the model and the calculator.
            </Note>
          </div>
          <ClaimPrep claimId={view.claim_id} sourceFormat={view.source_format} claim={view.received} />
        </>
      ) : !explanation ? (
        <Note tone="neutral">
          In review. A reviewer is checking the recommendation; the decision shows here once it is final.
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
