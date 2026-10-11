// Review claim (§8.8; the demo's main screen, DESIGN.md): the stage strip, the service lines with
// their criteria and quotes, and the clinical note. "Override line" opens a side sheet with the
// new decision, a required reason and, only when needed, the benefit category. One primary action:
// "Accept recommendation", or "Finalize claim" once a line is overridden; both are confirmed.
// Reviewers never enter amounts: the calculator recomputes them.

import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router";
import { toast } from "sonner";

import { useAudit, useClaim, useOpenReview, useQueue, useSubmitReview } from "@/api/hooks";
import type { DecisionRecord, FinalLineDecision, LineDecision } from "@/api/types";
import { Chip, StatusChip } from "@/components/Chip";
import { ClaimWorkspace } from "@/components/ClaimWorkspace";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { PageTitle } from "@/components/Layout";
import { AmountSummary } from "@/components/Record";
import { EmptyState, ErrorNotice, Note, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Sheet, SheetContent, SheetDescription, SheetFooter, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { answerErrors, DECISION, TIER } from "@/lib/labels";
import { useUser } from "@/lib/auth";
import { check, initialLines, isChanged, needsCategory, type LineState } from "@/review/form";
import { ChangedAmounts } from "./ClaimDetail";

const DECISIONS: LineDecision[] = ["APPROVE", "PEND", "DENY"];

/** The override form inside the side sheet; `error` is shown once the reviewer tries to save. */
export function OverrideForm({
  line,
  error,
  onChange,
}: {
  line: LineState;
  error?: string;
  onChange: (next: LineState) => void;
}) {
  const id = `override-${line.lineNo}`;
  return (
    <div className="grid gap-5 px-6">
      <div className="grid gap-1.5">
        <label htmlFor={`${id}-decision`} className="font-semibold">
          New decision for line {line.lineNo}
        </label>
        <Select value={line.decision} onValueChange={(value) => onChange({ ...line, decision: value as LineDecision })}>
          <SelectTrigger id={`${id}-decision`} className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {DECISIONS.map((d) => (
              <SelectItem key={d} value={d}>
                {DECISION[d].label}: {DECISION[d].hint.toLowerCase()}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {needsCategory(line) && (
        <div className="grid gap-1.5">
          <label htmlFor={`${id}-category`} className="font-semibold">
            Benefit category
          </label>
          <Select value={line.category ?? ""} onValueChange={(value) => onChange({ ...line, category: value || null })}>
            <SelectTrigger id={`${id}-category`} className="w-full">
              <SelectValue placeholder="Choose a category" />
            </SelectTrigger>
            <SelectContent>
              {line.candidates.map((c) => (
                <SelectItem key={c} value={c}>
                  {c.replaceAll("_", " ").toLowerCase()}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )}
      <div className="grid gap-1.5">
        <label htmlFor={`${id}-reason`} className="font-semibold">
          Reason (required)
        </label>
        <Textarea
          id={`${id}-reason`}
          rows={4}
          value={line.reason}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          placeholder="What in the note or the policy supports this decision"
          onChange={(event) => onChange({ ...line, reason: event.target.value })}
        />
        {error && (
          <p id={`${id}-error`} className="text-[13px] font-semibold text-deny">
            {error}
          </p>
        )}
      </div>
    </div>
  );
}

function Finalized({ record }: { record: DecisionRecord }) {
  const audit = useAudit(record.claim_id);
  const queue = useQueue(null);
  // The next claim in the queue's order (most work first, then the oldest).
  const next = queue.data?.find((item) => item.claim_id !== record.claim_id);
  return (
    <div role="status" className="rounded-lg border border-rules bg-paper p-5">
      <div className="flex flex-wrap items-center gap-3">
        <p className="font-semibold">Claim {record.claim_id} is final</p>
        <StatusChip status={record.status} showHint />
      </div>
      <div className="mt-4 space-y-4">
        {audit.data && <ChangedAmounts events={audit.data} />}
        {record.amounts && <AmountSummary totals={record.amounts.totals} />}
      </div>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        {next ? (
          <Button asChild size="lg">
            <Link to={`/review/${encodeURIComponent(next.claim_id)}`}>Next claim</Link>
          </Button>
        ) : (
          queue.data && <p className="text-ink-muted">Nothing else is waiting for review.</p>
        )}
        <Button asChild size="lg" variant="outline">
          <Link to={`/claims/${encodeURIComponent(record.claim_id)}`}>Open claim</Link>
        </Button>
        <Button asChild size="lg" variant="outline">
          <Link to="/queue">Back to the queue</Link>
        </Button>
      </div>
    </div>
  );
}

function Review({
  view,
  record,
  submit,
  fill,
}: {
  view: Parameters<typeof ClaimWorkspace>[0]["view"];
  record: DecisionRecord;
  submit: ReturnType<typeof useSubmitReview>;
  fill: boolean;
}) {
  const reviewerId = useUser().username;
  const audit = useAudit(record.claim_id);
  const [lines, setLines] = useState(() => initialLines(record));
  const [editing, setEditing] = useState<LineState | null>(null);
  const [showError, setShowError] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const checked = check(lines);
  const overridden = checked.changed.length;
  const byLine = new Map(lines.map((l) => [l.lineNo, l]));
  const draftError = editing
    ? isChanged(editing)
      ? check([editing]).errors[editing.lineNo]
      : "Choose a different decision or category to override the line."
    : undefined;

  const lineActions = (line: FinalLineDecision) => {
    const state = byLine.get(line.line_no);
    if (!state?.editable) return null;
    const changed = isChanged(state);
    return (
      <div className="flex flex-wrap gap-3 border-t border-rules pt-3">
        <Button
          variant="outline"
          onClick={() => {
            setShowError(false);
            setEditing({ ...state });
          }}
        >
          {changed ? "Change override" : "Override line"}
        </Button>
        {changed && (
          <Button
            variant="ghost"
            onClick={() => {
              setLines((all) =>
                all.map((l) =>
                  l.lineNo === state.lineNo
                    ? { ...l, decision: l.original.decision, category: l.original.category, reason: "" }
                    : l,
                ),
              );
              toast("Override removed", { description: `Line ${state.lineNo} keeps the recommendation.` });
            }}
          >
            Undo override
          </Button>
        )}
      </div>
    );
  };
  const lineStatus = (line: FinalLineDecision) => {
    const state = byLine.get(line.line_no);
    if (!state || !isChanged(state)) return null;
    return (
      <span className="inline-flex flex-wrap items-center gap-2 text-[13px]">
        <span className="text-ink-muted">Overridden to</span>
        <Chip label={DECISION[state.decision]} />
      </span>
    );
  };

  return (
    <>
      {answerErrors(record.output_errors).length > 0 && (
        <div className="mb-6">
          <Note>
            The model's answer could not be used ({answerErrors(record.output_errors).join("; ")}), so every
            model line needs your decision.
          </Note>
        </div>
      )}
      <ClaimWorkspace view={view} events={audit.data ?? []} fill={fill} lineActions={lineActions} lineStatus={lineStatus} />
      {submit.error && (
        <div className="mt-6">
          <ErrorNotice error={submit.error} />
        </div>
      )}
      <div className="sticky bottom-0 z-10 mt-6 -mx-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-rules bg-paper px-4 py-3 md:-mx-8 md:px-8">
        <Button
          size="lg"
          disabled={submit.isPending}
          onClick={() => setConfirming(true)}
        >
          {overridden ? "Finalize claim" : "Accept all lines"}
        </Button>
        <span className="text-[13px] text-ink-muted">
          {overridden
            ? `${overridden} line${overridden === 1 ? "" : "s"} overridden. The calculator recomputes the amounts.`
            : "Accepts every line as recommended. Reviewers never enter amounts."}
        </span>
      </div>
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent className="w-full sm:max-w-md">
          {editing && (
            <>
              <SheetHeader className="px-6 pt-6">
                <SheetTitle className="text-[18px] font-semibold">Override line {editing.lineNo}</SheetTitle>
                <SheetDescription className="text-ink-muted">
                  Recommended: {DECISION[editing.original.decision].label.toLowerCase()}. The reason is kept in the
                  audit trail.
                </SheetDescription>
              </SheetHeader>
              <OverrideForm line={editing} error={showError ? draftError : undefined} onChange={setEditing} />
              <SheetFooter className="flex-row gap-3 px-6 pb-6">
                <Button
                  onClick={() => {
                    if (draftError) {
                      setShowError(true);
                      return;
                    }
                    setLines((all) => all.map((l) => (l.lineNo === editing.lineNo ? editing : l)));
                    toast.success("Line overridden", {
                      description: `Line ${editing.lineNo}: ${DECISION[editing.decision].label.toLowerCase()}.`,
                    });
                    setEditing(null);
                  }}
                >
                  Override line
                </Button>
                <Button variant="outline" onClick={() => setEditing(null)}>
                  Cancel
                </Button>
              </SheetFooter>
            </>
          )}
        </SheetContent>
      </Sheet>
      <ConfirmDialog
        open={confirming}
        title="Finalize claim?"
        confirmLabel="Finalize claim"
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          submit.mutate(
            { claimId: record.claim_id, overrides: checked.overrides },
            { onSuccess: () => toast.success("Claim finalized", { description: `Claim ${record.claim_id}.` }) },
          );
        }}
      >
        {overridden
          ? `Claim ${record.claim_id} is finalized with ${overridden} overridden line${overridden === 1 ? "" : "s"}, as reviewer ${reviewerId}. This cannot be undone.`
          : `Claim ${record.claim_id} is finalized with every line as recommended, as reviewer ${reviewerId}. This cannot be undone.`}
      </ConfirmDialog>
    </>
  );
}

export function ReviewClaim() {
  const { claimId = "" } = useParams();
  const { state } = useLocation();
  const reviewerId = useUser().username;
  const claim = useClaim(claimId);
  const open = useOpenReview();
  const submit = useSubmitReview();
  const opened = useRef<string | null>(null);
  const status = claim.data?.status;
  const fill = Boolean((state as { justProcessed?: boolean } | null)?.justProcessed);

  // REVIEW_OPENED once per claim and reviewer: the start of the review time (D-REV-6).
  useEffect(() => {
    const key = `${claimId}/${reviewerId}`;
    if (status === "AWAITING_REVIEW" && opened.current !== key) {
      opened.current = key;
      open.mutate(claimId);
    }
  }, [claimId, reviewerId, status, open]);

  if (submit.data) {
    return (
      <>
        <PageTitle title={`Review claim ${submit.data.claim_id}`} />
        <Finalized record={submit.data} />
      </>
    );
  }
  if (claim.isPending) return <Skeleton lines={8} />;
  if (claim.error) return <ErrorNotice error={claim.error} onRetry={() => void claim.refetch()} />;
  const view = claim.data;
  const record = view.record;
  return (
    <>
      <PageTitle
        title={`Review claim ${view.claim_id}`}
        actions={
          <>
            <StatusChip status={view.status} />
            {record?.review_tier && (
              <span className="text-[13px] text-ink-muted">{TIER[record.review_tier].label} review tier</span>
            )}
          </>
        }
      />
      {open.error && (
        <div className="mb-6">
          <ErrorNotice error={open.error} />
        </div>
      )}
      {!record || view.status !== "AWAITING_REVIEW" ? (
        <EmptyState title="This claim is not awaiting review">
          <Link className="font-semibold underline underline-offset-4" to={`/claims/${encodeURIComponent(view.claim_id)}`}>
            Open the claim
          </Link>{" "}
          to see its decision and explanation.
        </EmptyState>
      ) : (
        <Review view={view} record={record} submit={submit} fill={fill} />
      )}
    </>
  );
}
