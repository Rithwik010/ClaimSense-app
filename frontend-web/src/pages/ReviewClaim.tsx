// Review claim (§8.8; the demo's main screen, DESIGN.md): the stage strip, the service lines with
// their criteria and quotes, and the clinical note. "Override line" opens a side sheet with the
// new decision, a required reason code for Deny or Pend (D-REV-9; the provider sees it), only when
// needed the benefit category, and a required note for the audit trail. One primary action:
// "Accept recommendation", or "Finalize claim" once a line is overridden; both are confirmed.
// Reviewers never enter amounts: the calculator recomputes them. The page says when another
// reviewer opened the claim in the last 30 minutes (D-REV-10) and, for an appeal, who filed it and
// why; the reviewer who made the decision under appeal cannot decide it (D-APL-1). Keys: A accepts
// or finalizes, N opens the next claim, Q goes back to the queue. Once final, the reviewer can
// correct the model's criteria for the next fine-tune (D-FBK-1).

import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { toast } from "sonner";

import { useAudit, useClaim, useOpenReview, useOthersReviewing, useQueue, useSubmitReview } from "@/api/hooks";
import type { DecisionRecord, FinalLineDecision, LineDecision } from "@/api/types";
import { Chip, OutcomeChip, StatusChip } from "@/components/Chip";
import { ClaimWorkspace } from "@/components/ClaimWorkspace";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { FeedbackForm } from "@/components/Feedback";
import { AppealHistory } from "@/components/FollowUps";
import { PageTitle } from "@/components/Layout";
import { OriginalFileButton } from "@/components/OriginalFile";
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
import { useShortcuts } from "@/hooks/use-shortcuts";
import { age } from "@/lib/format";
import { answerErrors, DECISION, reasonOption, TIER } from "@/lib/labels";
import { useUser } from "@/lib/auth";
import {
  check,
  initialLines,
  isChanged,
  needsCategory,
  needsReasonCode,
  reasonCodes,
  withDecision,
  type FormField,
  type LineState,
} from "@/review/form";
import { ChangedAmounts } from "./ClaimDetail";

const DECISIONS: LineDecision[] = ["APPROVE", "PEND", "DENY"];

/** The override form inside the side sheet; `error` is shown under its `field` once the reviewer
 *  tries to save. */
export function OverrideForm({
  line,
  error,
  field = "reason",
  onChange,
}: {
  line: LineState;
  error?: string;
  field?: FormField;
  onChange: (next: LineState) => void;
}) {
  const id = `override-${line.lineNo}`;
  const errorOn = (name: FormField) => (error && field === name ? error : undefined);
  const errorText = (name: FormField) =>
    errorOn(name) && (
      <p id={`${id}-${name}-error`} className="text-[13px] font-semibold text-deny">
        {errorOn(name)}
      </p>
    );
  return (
    <div className="grid gap-5 px-6">
      <div className="grid gap-1.5">
        <label htmlFor={`${id}-decision`} className="font-semibold">
          New decision for line {line.lineNo}
        </label>
        <Select value={line.decision} onValueChange={(value) => onChange(withDecision(line, value as LineDecision))}>
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
            <SelectTrigger
              id={`${id}-category`}
              className="w-full"
              aria-invalid={Boolean(errorOn("category"))}
              aria-describedby={errorOn("category") ? `${id}-category-error` : undefined}
            >
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
          {errorText("category")}
        </div>
      )}
      {needsReasonCode(line) && (
        <div className="grid gap-1.5">
          <label htmlFor={`${id}-code`} className="font-semibold">
            Reason (required)
          </label>
          <Select value={line.reasonCode ?? ""} onValueChange={(value) => onChange({ ...line, reasonCode: value || null })}>
            <SelectTrigger
              id={`${id}-code`}
              className="w-full"
              aria-invalid={Boolean(errorOn("reasonCode"))}
              aria-describedby={errorOn("reasonCode") ? `${id}-reasonCode-error` : `${id}-code-hint`}
            >
              <SelectValue placeholder="Choose a reason" />
            </SelectTrigger>
            <SelectContent>
              {reasonCodes(line.decision).map((code) => (
                <SelectItem key={code} value={code}>
                  {reasonOption(code)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <p id={`${id}-code-hint`} className="text-[13px] text-ink-muted">
            The provider sees this reason with its adjustment codes.
          </p>
          {errorText("reasonCode")}
        </div>
      )}
      <div className="grid gap-1.5">
        <label htmlFor={`${id}-reason`} className="font-semibold">
          Note (required)
        </label>
        <Textarea
          id={`${id}-reason`}
          rows={4}
          value={line.reason}
          aria-invalid={Boolean(errorOn("reason"))}
          aria-describedby={errorOn("reason") ? `${id}-reason-error` : `${id}-reason-hint`}
          placeholder="What in the note or the policy supports this decision"
          onChange={(event) => onChange({ ...line, reason: event.target.value })}
        />
        <p id={`${id}-reason-hint`} className="text-[13px] text-ink-muted">
          Kept in the audit trail for reviewers; the provider never sees it.
        </p>
        {errorText("reason")}
      </div>
    </div>
  );
}

/** The keys the review pages take, where the reviewer sees them. */
function Keys({ keys }: { keys: [string, string][] }) {
  return (
    <p className="hidden text-[13px] text-ink-muted md:block">
      Keys:{" "}
      {keys.map(([key, what], i) => (
        <span key={key}>
          {i > 0 && ", "}
          <kbd className="rounded border border-rules bg-subtle px-1.5 font-mono text-[12px] text-ink">{key}</kbd> {what}
        </span>
      ))}
    </p>
  );
}

function Finalized({ record }: { record: DecisionRecord }) {
  const audit = useAudit(record.claim_id);
  const claim = useClaim(record.claim_id); // the outcome every dashboard shows (D-UI-6)
  const queue = useQueue(null);
  const navigate = useNavigate();
  // The next claim in the queue's order (most work first, then the oldest).
  const next = queue.data?.find((item) => item.claim_id !== record.claim_id);
  useShortcuts({
    n: () => next && navigate(`/review/${encodeURIComponent(next.claim_id)}`),
    q: () => navigate("/queue"),
  });
  return (
    <>
    <div role="status" className="surface rounded-lg p-5">
      <div className="flex flex-wrap items-center gap-3">
        <p className="font-semibold">Claim {record.claim_id} is final</p>
        {claim.data?.status === record.status ? (
          <OutcomeChip outcome={claim.data.outcome} showHint />
        ) : (
          <StatusChip status={record.status} showHint />
        )}
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
        <Keys keys={[["N", "next claim"], ["Q", "queue"]]} />
      </div>
    </div>
    <FeedbackForm record={record} />
    </>
  );
}

function Review({
  view,
  record,
  submit,
  fill,
  blocked = false,
}: {
  view: Parameters<typeof ClaimWorkspace>[0]["view"];
  record: DecisionRecord;
  submit: ReturnType<typeof useSubmitReview>;
  fill: boolean;
  /** This reviewer made the decision under appeal: they cannot decide it (D-APL-1). */
  blocked?: boolean;
}) {
  const reviewerId = useUser().username;
  const navigate = useNavigate();
  const audit = useAudit(record.claim_id);
  const [lines, setLines] = useState(() => initialLines(record));
  const [editing, setEditing] = useState<LineState | null>(null);
  const [showError, setShowError] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const checked = check(lines);
  const overridden = checked.changed.length;
  const byLine = new Map(lines.map((l) => [l.lineNo, l]));
  const draftCheck = editing ? check([editing]) : undefined;
  const draftError = editing
    ? isChanged(editing)
      ? draftCheck?.errors[editing.lineNo]
      : "Choose a different decision or category to override the line."
    : undefined;
  const draftField: FormField | undefined = editing ? draftCheck?.fields[editing.lineNo] : undefined;
  useShortcuts(
    {
      a: () => !blocked && !submit.isPending && setConfirming(true),
      q: () => navigate("/queue"),
    },
    editing === null && !confirming,
  );

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
                    ? { ...l, decision: l.original.decision, category: l.original.category, reasonCode: null, reason: "" }
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
      <div className="sticky bottom-0 z-10 mt-6 -mx-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-rules bg-white px-4 py-3 shadow-[0_-8px_16px_-12px_rgb(16_24_40/0.18)] md:-mx-8 md:px-8">
        <Button
          size="lg"
          disabled={submit.isPending || blocked}
          onClick={() => setConfirming(true)}
        >
          {overridden ? "Finalize claim" : "Accept all lines"}
        </Button>
        <span className="min-w-0 flex-1 text-[13px] text-ink-muted">
          {blocked
            ? "You made the decision under appeal, so another reviewer decides it."
            : overridden
              ? `${overridden} line${overridden === 1 ? "" : "s"} overridden. The calculator recomputes the amounts.`
              : "Accepts every line as recommended. Reviewers never enter amounts."}
        </span>
        <Keys keys={[["A", overridden ? "finalize" : "accept"], ["Q", "queue"]]} />
      </div>
      <Sheet open={editing !== null} onOpenChange={(open) => !open && setEditing(null)}>
        <SheetContent className="w-full sm:max-w-md">
          {editing && (
            <>
              <SheetHeader className="px-6 pt-6">
                <SheetTitle className="text-[18px] font-semibold">Override line {editing.lineNo}</SheetTitle>
                <SheetDescription className="text-ink-muted">
                  Recommended: {DECISION[editing.original.decision].label.toLowerCase()}. The provider sees the
                  reason; the note stays in the audit trail.
                </SheetDescription>
              </SheetHeader>
              <OverrideForm
                line={editing}
                error={showError ? draftError : undefined}
                field={draftField}
                onChange={setEditing}
              />
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
  const others = useOthersReviewing(claimId, status === "AWAITING_REVIEW" && !submit.data);

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
  const appeal = view.appeals?.find((a) => a.status === "OPEN");
  return (
    <>
      <PageTitle
        title={`Review claim ${view.claim_id}`}
        actions={
          <>
            <OutcomeChip outcome={view.outcome} />
            {record?.review_tier && (
              <span className="text-[13px] text-ink-muted">{TIER[record.review_tier].label} review tier</span>
            )}
            <OriginalFileButton claimId={view.claim_id} documents={view.documents} />
          </>
        }
      />
      {open.error && (
        <div className="mb-6">
          <ErrorNotice error={open.error} />
        </div>
      )}
      {view.status === "AWAITING_REVIEW" && (others.data ?? []).length > 0 && (
        <div className="mb-6">
          <Note>
            <p className="font-semibold">
              {(others.data ?? [])
                .map((o) => `${o.reviewer_id} opened this claim ${age(o.opened)} ago`)
                .join("; ")}
              .
            </p>
            <p className="mt-1">
              Check with them before you review it: the first reviewer to finalize decides the claim, and the other
              review is refused.
            </p>
          </Note>
        </div>
      )}
      {view.status === "AWAITING_REVIEW" && appeal && (
        <div className="mb-6">
          <Note>
            <p className="font-semibold">
              Appeal: the {appeal.filed_role} asks for this denied claim to be decided again
              {appeal.previous_reviewer ? `. ${appeal.previous_reviewer} made the decision under appeal` : ""}.
            </p>
            {appeal.reason && <p className="mt-1 break-words whitespace-pre-line">“{appeal.reason}”</p>}
            <p className="mt-1 text-[14px] text-ink-muted">
              The lines show the decision under appeal. Accept it to uphold it, or override lines to change it.
            </p>
          </Note>
        </div>
      )}
      {!record || view.status !== "AWAITING_REVIEW" ? (
        <EmptyState title="This claim is not awaiting review">
          <Link className="font-semibold text-link underline underline-offset-4" to={`/claims/${encodeURIComponent(view.claim_id)}`}>
            Open the claim
          </Link>{" "}
          to see its decision and explanation.
        </EmptyState>
      ) : (
        <Review
          view={view}
          record={record}
          submit={submit}
          fill={fill}
          blocked={appeal?.previous_reviewer === reviewerId}
        />
      )}
      {view.status !== "AWAITING_REVIEW" && <AppealHistory appeals={view.appeals} staff />}
    </>
  );
}
