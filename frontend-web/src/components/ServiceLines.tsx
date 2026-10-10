// The claim's service lines, each expanding to its criteria with their status and quote (motion
// moment 2: the line opens and closes). Selecting a criterion with a quote shows it in the note.

import { ChevronDown, CircleCheck, CircleDashed, CircleMinus, CircleX } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useState, type ReactNode } from "react";

import type { DecisionRecord, FinalLineDecision } from "@/api/types";
import { DecisionChip } from "@/components/Chip";
import { money } from "@/lib/format";
import { evidenceChecks, reason, SOURCE } from "@/lib/labels";

const sentence = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

const CRITERION: Record<string, { label: string; Icon: typeof CircleCheck }> = {
  MET: { label: "Met", Icon: CircleCheck },
  NOT_MET: { label: "Not met", Icon: CircleX },
  NOT_DOCUMENTED: { label: "Not documented", Icon: CircleDashed },
  NOT_APPLICABLE: { label: "Does not apply", Icon: CircleMinus },
};

export function quoteKey(lineNo: number, criterionId: string): string {
  return `${lineNo}:${criterionId}`;
}

function LinePanel({
  record,
  line,
  open,
  onToggle,
  onQuote,
  activeKey,
  actions,
  status,
}: {
  record: DecisionRecord;
  line: FinalLineDecision;
  open: boolean;
  onToggle: () => void;
  onQuote: (key: string) => void;
  activeKey: string | null;
  actions?: ReactNode;
  status?: ReactNode;
}) {
  const reduce = useReducedMotion();
  const context = record.context_refs?.lines.find((c) => c.line_no === line.line_no);
  const answer = record.slm_output?.lines.find((l) => l.line_no === line.line_no);
  const cited = new Map((context?.criteria ?? []).map((c) => [c.criterion_id, c]));
  const amounts = record.amounts?.lines.find((a) => a.line_no === line.line_no);
  const unquoted = new Set(
    evidenceChecks(record.output_errors)
      .filter((c) => c.lineNo === line.line_no)
      .map((c) => c.criterionId),
  );
  const criteria = line.source === "RULE" ? [] : (answer?.criteria ?? []);
  const id = `line-${line.line_no}-body`;
  return (
    <div className="rounded-lg border border-rules bg-paper">
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2 p-4">
        <button
          type="button"
          aria-expanded={open}
          aria-controls={id}
          onClick={onToggle}
          className="-m-1 flex min-w-0 flex-1 items-start gap-2 rounded-md p-1 text-left"
        >
          <ChevronDown
            aria-hidden
            className={`mt-0.5 size-5 shrink-0 text-ink-muted ${open ? "" : "-rotate-90"}`}
          />
          <span className="min-w-0">
            <span className="block font-semibold">
              Line {line.line_no}
              {context && <span className="ml-2 font-normal text-ink-muted">Procedure {context.procedure_code}</span>}
            </span>
            <span className="block text-[13px] text-ink-muted">
              {SOURCE[line.source] ?? line.source}
              {line.benefit_category && `, ${line.benefit_category.replaceAll("_", " ").toLowerCase()}`}
            </span>
          </span>
        </button>
        <div className="flex flex-wrap items-center gap-2">
          <DecisionChip decision={line.decision} />
          {status}
        </div>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            key="body"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduce ? 0 : 0.18, ease: "easeOut" }}
            className="overflow-hidden"
          >
            <div className="space-y-4 border-t border-rules px-4 pt-3 pb-4">
              {line.reason_codes.length > 0 && (
                <ul className="space-y-1 text-[14px]">
                  {line.reason_codes.map((code) => (
                    <li key={code}>{sentence(reason(code))}</li>
                  ))}
                </ul>
              )}
              {line.source === "RULE" && (
                <p className="text-[14px] text-ink-muted">
                  Decided by a rule. Rule outcomes are automatic and cannot be overridden.
                </p>
              )}
              {criteria.length > 0 && (
                <ul className="divide-y divide-rules">
                  {criteria.map((c) => {
                    const source = cited.get(c.criterion_id);
                    const key = quoteKey(line.line_no, c.criterion_id);
                    const guarded = unquoted.has(c.criterion_id);
                    const shown = guarded ? CRITERION.NOT_DOCUMENTED! : (CRITERION[c.status] ?? CRITERION.NOT_APPLICABLE!);
                    const quotable = (c.status === "MET" || c.status === "NOT_MET") && !guarded && c.evidence;
                    const body = (
                      <>
                        <span className="flex flex-wrap items-center gap-x-3 gap-y-1">
                          <span className="inline-flex items-center gap-1.5 font-semibold">
                            <shown.Icon aria-hidden className="size-4 shrink-0" strokeWidth={2.25} />
                            {shown.label}
                          </span>
                          <span className="text-[13px] text-ink-muted">
                            {source ? `${source.policy_title}, ${c.criterion_id}` : c.criterion_id}
                          </span>
                        </span>
                        {source && <span className="mt-1 block text-[14px]">{source.text}</span>}
                        {guarded ? (
                          <span className="mt-1 block text-[13px] text-pend">
                            The model said met, but its quote is not in the note.
                          </span>
                        ) : (
                          c.evidence && (
                            <span className="mt-1 block text-[14px] text-ink-muted">
                              {quotable ? <q className="rounded-sm bg-highlight/60 px-0.5 text-ink">{c.evidence}</q> : c.evidence}
                            </span>
                          )
                        )}
                      </>
                    );
                    return (
                      <li key={c.criterion_id} className="py-3 first:pt-0 last:pb-0">
                        {quotable ? (
                          <button
                            type="button"
                            onClick={() => onQuote(key)}
                            aria-pressed={activeKey === key}
                            className="-m-1 block w-full rounded-md p-1 text-left hover:bg-canvas"
                          >
                            {body}
                            <span className="sr-only">Show the quote in the clinical note</span>
                          </button>
                        ) : (
                          body
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
              {line.decision === "PEND" && line.source !== "RULE" && (
                <p className="text-[14px]">
                  Awaiting documentation for{" "}
                  {criteria
                    .filter((c) => c.status === "NOT_DOCUMENTED" || unquoted.has(c.criterion_id))
                    .map((c) => c.criterion_id)
                    .join(", ") || "documentation that supports the service"}
                  .
                </p>
              )}
              {amounts && (
                <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-[14px] sm:grid-cols-4">
                  {(
                    [
                      ["Billed", amounts.billed_cents],
                      ["Allowed", amounts.allowed_cents],
                      ["Plan pays", amounts.plan_pays_cents],
                      ["Member pays", amounts.member_pays_cents],
                    ] as const
                  ).map(([label, cents]) => (
                    <div key={label}>
                      <dt className="text-[13px] text-ink-muted">{label}</dt>
                      <dd className="tabular-nums">{money(cents)}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {actions}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function ServiceLines({
  record,
  onQuote,
  activeKey,
  actions,
  status,
}: {
  record: DecisionRecord;
  onQuote: (key: string) => void;
  activeKey: string | null;
  actions?: (line: FinalLineDecision) => ReactNode;
  status?: (line: FinalLineDecision) => ReactNode;
}) {
  const lines = [...record.line_decisions].sort((a, b) => a.line_no - b.line_no);
  const [open, setOpen] = useState<Set<number>>(
    () => new Set(lines.slice(0, lines.length <= 3 ? lines.length : 1).map((l) => l.line_no)),
  );
  if (lines.length === 0) {
    return (
      <p className="rounded-lg border border-rules bg-paper p-4 text-ink-muted">
        No line decisions: the rules decided the whole claim. The rule checks and the explanation say why.
      </p>
    );
  }
  return (
    <div className="space-y-3">
      {lines.map((line) => (
        <LinePanel
          key={line.line_no}
          record={record}
          line={line}
          open={open.has(line.line_no)}
          onToggle={() =>
            setOpen((now) => {
              const next = new Set(now);
              if (next.has(line.line_no)) next.delete(line.line_no);
              else next.add(line.line_no);
              return next;
            })
          }
          onQuote={onQuote}
          activeKey={activeKey}
          actions={actions?.(line)}
          status={status?.(line)}
        />
      ))}
    </div>
  );
}
