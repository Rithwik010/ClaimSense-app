// Claim result (a provider's own claim, D-AUTH-1). Until it is final: "In review" and how far it
// went (the stage strip), nothing of the recommendation. Once final: each line's outcome in plain
// words with its standard reason codes, the amounts, then the explanation built from the record.

import { useParams } from "react-router";
import { toast } from "sonner";

import { useExplanation, useMyClaim, useProcess } from "@/api/hooks";
import type { Adjustment, DecisionRecord, ProviderClaimView } from "@/api/types";
import { AdjustmentCodes } from "@/components/AdjustmentCodes";
import { Chip, DecisionChip } from "@/components/Chip";
import { PageTitle, Panel, Section } from "@/components/Layout";
import { AmountSummary } from "@/components/Record";
import { providerStages, StageStrip } from "@/components/StageStrip";
import { ErrorNotice, Note, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { money } from "@/lib/format";
import { lineReason, providerStatus, reason } from "@/lib/labels";

function procedureCode(view: ProviderClaimView, lineNo: number): string {
  const lines = (view.received.service_lines as { line_no?: number; procedure_code?: string }[] | undefined) ?? [];
  return lines.find((line) => line.line_no === lineNo)?.procedure_code ?? "";
}

function Lines({ view, record }: { view: ProviderClaimView; record: DecisionRecord }) {
  const byLine = (lineNo: number): Adjustment[] => view.adjustments.filter((a) => a.line_no === lineNo);
  const lineAmounts = new Map((record.amounts?.lines ?? []).map((line) => [line.line_no, line]));
  // A claim the rules decided has no line decisions: its codes (for the claim or a line) and the
  // reasons of every failed rule show together.
  const decided = new Set(record.line_decisions.map((line) => line.line_no));
  const undecided = view.adjustments.filter((a) => a.line_no === null || !decided.has(a.line_no));
  const failed = record.rules_outcome.rule_results.filter((r) => !r.passed);
  return (
    <div className="space-y-3">
      {record.line_decisions.length === 0 && failed.length > 0 && (
        <Panel className="p-4">
          <p className="font-semibold">The rules decided this claim</p>
          <ul className="mt-1 list-disc pl-5">
            {failed.map((rule, i) => (
              <li key={`${rule.rule_id}-${i}`}>
                {rule.line_no ? `Line ${rule.line_no}: ` : ""}
                {reason(rule.reason_code)}
              </li>
            ))}
          </ul>
        </Panel>
      )}
      <AdjustmentCodes title="Reason codes" items={undecided} />
      {record.line_decisions.map((line) => {
        const amounts = lineAmounts.get(line.line_no);
        return (
          <Panel key={line.line_no} className="p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-semibold">
                Line {line.line_no}
                {procedureCode(view, line.line_no) && `, procedure ${procedureCode(view, line.line_no)}`}
              </h3>
              <DecisionChip decision={line.decision} />
            </div>
            <p className="mt-1.5">{lineReason(line.decision, line.reason_codes)}.</p>
            {amounts && (
              <p className="mt-1 text-[13px] text-ink-muted tabular-nums">
                Billed {money(amounts.billed_cents)}, allowed {money(amounts.allowed_cents)}, plan pays{" "}
                {money(amounts.plan_pays_cents)}
              </p>
            )}
            {byLine(line.line_no).length > 0 && (
              <div className="mt-3">
                <AdjustmentCodes items={byLine(line.line_no)} />
              </div>
            )}
          </Panel>
        );
      })}
    </div>
  );
}

export function ClaimResult() {
  const { claimId = "" } = useParams();
  const claim = useMyClaim(claimId);
  const final = claim.data?.final ?? false;
  const explanation = useExplanation(claimId, final);
  const process = useProcess();

  if (claim.isPending) return <Skeleton lines={8} />;
  if (claim.error) return <ErrorNotice error={claim.error} onRetry={() => void claim.refetch()} />;
  const view = claim.data;
  const record = view.record;
  return (
    <>
      <PageTitle
        title={`Claim ${view.claim_id}`}
        actions={
          <>
            <Chip label={providerStatus(view.status)} showHint />
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
      {!final || !record ? (
        <Note tone="neutral">
          {view.status === "IN_REVIEW"
            ? "In review. A reviewer is checking the recommendation; the decision shows here once it is final."
            : "Not processed yet. Process the claim to run the rules, the model and the calculator."}
        </Note>
      ) : (
        <>
          {record.amounts && (
            <Section title="Amounts">
              <AmountSummary totals={record.amounts.totals} glass />
            </Section>
          )}
          <Section title="Lines">
            <Lines view={view} record={record} />
          </Section>
          <Section title="Explanation">
            {explanation.isPending ? (
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
            )}
          </Section>
        </>
      )}
    </>
  );
}
