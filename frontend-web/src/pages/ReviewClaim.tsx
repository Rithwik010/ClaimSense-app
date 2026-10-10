// Review claim (§8.8): the fields, the rule checks and each line's recommendation with criteria,
// evidence, citations and amounts; per line a decision, a required reason when changed and a
// category only when needed. One "Accept all" or one "Submit changes", confirmed before the claim
// is finalized. Reviewers never enter amounts: the calculator recomputes them.

import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";

import { useAudit, useClaim, useOpenReview, useSubmitReview } from "../api/hooks";
import type { DecisionRecord, LineDecision } from "../api/types";
import { StatusChip } from "../components/Chip";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { FieldsTable } from "../components/Fields";
import { PageTitle, Section } from "../components/Layout";
import { AmountsTable, LineDetails, RuleChecks } from "../components/Record";
import { EmptyState, ErrorNotice, Skeleton } from "../components/States";
import { button, card, input } from "../components/ui";
import { answerErrors, DECISION, reason, TIER } from "../lib/labels";
import { useSession } from "../lib/session";
import { check, initialLines, isChanged, needsCategory, type LineState } from "../review/form";
import { ChangedAmounts } from "./ClaimDetail";

const DECISIONS: LineDecision[] = ["APPROVE", "DENY", "PEND"];

export function LineControls({
  line,
  error,
  onChange,
}: {
  line: LineState;
  error?: string;
  onChange: (next: LineState) => void;
}) {
  const changed = isChanged(line);
  const id = `line-${line.lineNo}`;
  return (
    <div className="mt-4 grid gap-4 border-t border-gray-100 pt-4 md:grid-cols-3">
      <label className="text-sm font-medium text-gray-700" htmlFor={`${id}-decision`}>
        Your decision for line {line.lineNo}
        <select
          id={`${id}-decision`}
          className={`${input} mt-1 font-normal`}
          value={line.decision}
          onChange={(event) => onChange({ ...line, decision: event.target.value as LineDecision })}
        >
          {DECISIONS.map((d) => (
            <option key={d} value={d}>
              {DECISION[d].label} ({d})
            </option>
          ))}
        </select>
      </label>
      {needsCategory(line) && (
        <label className="text-sm font-medium text-gray-700" htmlFor={`${id}-category`}>
          Benefit category
          <select
            id={`${id}-category`}
            className={`${input} mt-1 font-normal`}
            value={line.category ?? ""}
            onChange={(event) => onChange({ ...line, category: event.target.value || null })}
          >
            <option value="">Choose one</option>
            {line.candidates.map((c) => (
              <option key={c} value={c}>
                {c.replaceAll("_", " ").toLowerCase()}
              </option>
            ))}
          </select>
        </label>
      )}
      <label
        className={`text-sm font-medium text-gray-700 ${needsCategory(line) ? "" : "md:col-span-2"}`}
        htmlFor={`${id}-reason`}
      >
        Reason {changed ? "(required)" : "(only when you change the line)"}
        <textarea
          id={`${id}-reason`}
          rows={2}
          className={`${input} mt-1 font-normal ${error ? "border-red-400" : ""}`}
          value={line.reason}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? `${id}-error` : undefined}
          onChange={(event) => onChange({ ...line, reason: event.target.value })}
        />
        {error && (
          <span id={`${id}-error`} className="mt-1 block font-normal text-red-700">
            {error}
          </span>
        )}
      </label>
    </div>
  );
}

function Finalized({ record }: { record: DecisionRecord }) {
  const audit = useAudit(record.claim_id);
  return (
    <div className={card} role="status">
      <div className="flex flex-wrap items-center gap-3">
        <p className="font-medium">Claim {record.claim_id} is final:</p>
        <StatusChip status={record.status} showHint />
      </div>
      <div className="mt-4">
        {audit.data && <ChangedAmounts events={audit.data} />}
        <AmountsTable record={record} />
      </div>
      <Link className={`${button.primary} mt-5`} to={`/claims/${encodeURIComponent(record.claim_id)}`}>
        See the claim and its explanation
      </Link>
    </div>
  );
}

function ReviewForm({
  record,
  submit,
}: {
  record: DecisionRecord;
  submit: ReturnType<typeof useSubmitReview>;
}) {
  const { reviewerId } = useSession();
  const [lines, setLines] = useState(() => initialLines(record));
  const [showErrors, setShowErrors] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const checked = check(lines);
  const changes = checked.changed.length;
  const hasErrors = Object.keys(checked.errors).length > 0;

  const byLine = new Map(record.line_decisions.map((l) => [l.line_no, l]));
  return (
    <>
      <Section title="Lines">
        <div className="space-y-5">
          {lines.map((line) => {
            const decided = byLine.get(line.lineNo);
            return (
              <div key={line.lineNo} className={card}>
                {decided && <LineDetails record={record} line={decided} />}
                {line.editable ? (
                  <LineControls
                    line={line}
                    error={showErrors ? checked.errors[line.lineNo] : undefined}
                    onChange={(next) =>
                      setLines((all) => all.map((l) => (l.lineNo === next.lineNo ? next : l)))
                    }
                  />
                ) : (
                  <p className="mt-4 border-t border-gray-100 pt-4 text-sm text-gray-600">
                    Decided by a rule ({decided?.reason_codes.map(reason).join("; ")}); rule outcomes
                    are automatic and cannot be changed.
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </Section>
      <Section title="Amounts at review">
        <AmountsTable record={record} />
        <p className="mt-2 text-sm text-gray-600">
          Reviewers do not enter amounts; the calculator recomputes them from the final decisions.
        </p>
      </Section>
      {submit.error && (
        <div className="mb-4">
          <ErrorNotice error={submit.error} />
        </div>
      )}
      <div className="sticky bottom-0 flex flex-wrap items-center gap-3 border-t border-gray-200 bg-white py-4">
        <button
          type="button"
          className={changes ? button.secondary : button.primary}
          disabled={changes > 0 || !reviewerId.trim() || submit.isPending}
          onClick={() => setConfirming(true)}
        >
          Accept all
        </button>
        <button
          type="button"
          className={changes ? button.primary : button.secondary}
          disabled={changes === 0 || !reviewerId.trim() || submit.isPending}
          onClick={() => {
            setShowErrors(true);
            if (!hasErrors) setConfirming(true);
          }}
        >
          Submit changes{changes ? ` (${changes})` : ""}
        </button>
        <span className="text-sm text-gray-600">
          {!reviewerId.trim()
            ? "Enter your reviewer ID in the top bar first."
            : changes
              ? "Undo your changes to accept every line as recommended."
              : "Change a line's decision to submit changes instead."}
        </span>
      </div>
      <ConfirmDialog
        open={confirming}
        title={changes ? `Submit ${changes} changed line${changes === 1 ? "" : "s"}?` : "Accept all lines?"}
        confirmLabel={changes ? "Submit and finalize" : "Accept and finalize"}
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          submit.mutate({ claimId: record.claim_id, overrides: checked.overrides });
        }}
      >
        Claim {record.claim_id} will be finalized as reviewer {reviewerId}. This cannot be undone.
      </ConfirmDialog>
    </>
  );
}

export function ReviewClaim() {
  const { claimId = "" } = useParams();
  const { role, reviewerId } = useSession();
  const claim = useClaim(claimId);
  const open = useOpenReview();
  const submit = useSubmitReview();
  const opened = useRef<string | null>(null);
  const status = claim.data?.status;

  // REVIEW_OPENED once per claim and reviewer: the start of the review time (D-REV-6).
  useEffect(() => {
    const who = reviewerId.trim();
    const key = `${claimId}/${who}`;
    if (status === "AWAITING_REVIEW" && who && role !== "provider" && opened.current !== key) {
      opened.current = key;
      open.mutate({ claimId, reviewerId: who });
    }
  }, [claimId, reviewerId, role, status, open]);

  if (role === "provider") {
    return (
      <EmptyState title="Reviewing is for reviewers">
        Switch the role in the top bar to Reviewer or Admin.
      </EmptyState>
    );
  }
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
      <PageTitle title={`Review claim ${view.claim_id}`} />
      <div className="mb-8 flex flex-wrap items-center gap-4">
        <StatusChip status={view.status} showHint />
        {record?.review_tier && (
          <span className="text-gray-700">
            {TIER[record.review_tier].label} review: {TIER[record.review_tier].hint}
          </span>
        )}
      </div>
      {open.error && (
        <div className="mb-6">
          <ErrorNotice error={open.error} />
        </div>
      )}
      {!record || view.status !== "AWAITING_REVIEW" ? (
        <EmptyState title="This claim is not awaiting review">
          <Link className="text-accent underline" to={`/claims/${encodeURIComponent(view.claim_id)}`}>
            See the claim
          </Link>
        </EmptyState>
      ) : (
        <>
          {answerErrors(record.output_errors).length > 0 && (
            <p role="note" className="mb-6 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-amber-900">
              The model's answer could not be used ({answerErrors(record.output_errors).join("; ")}),
              so every model line needs your decision.
            </p>
          )}
          <Section title="Fields">
            <FieldsTable
              claim={view.intake?.claim ?? view.received}
              confidences={view.field_confidences}
              jsonClaim={view.source_format === "JSON"}
            />
          </Section>
          <Section title="Rule checks">
            <RuleChecks record={record} />
          </Section>
          <ReviewForm record={record} submit={submit} />
        </>
      )}
    </>
  );
}
