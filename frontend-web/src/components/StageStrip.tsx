// The stage strip (DESIGN.md): where a claim went in the pipeline, each stage with its result;
// stages a claim never reached are shown as not reached. Right after "Process claim" it fills in
// stage by stage, in the order of the claim's audit events (motion moment 4).

import { Check, CircleDashed, Clock, X } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";

import type { AuditEvent, ClaimView } from "@/api/types";
import { money } from "@/lib/format";
import { evidenceChecks, LOW_CONFIDENCE, STATUS, TIER, answerErrors } from "@/lib/labels";

export type StageState = "done" | "problem" | "waiting" | "not-reached";

export interface Stage {
  name: string;
  state: StageState;
  result: string;
}

const SOURCE: Record<string, string> = {
  JSON: "JSON claim",
  DIGITAL_PDF: "Digital PDF",
  SCANNED: "Scanned form",
};

const RULE_OUTCOME: Record<string, string> = {
  REJECT: "Rejected",
  DENY: "Denied",
  PEND: "Pended",
};

/** The seven stages of a claim, from what the API returned (the claim view and its audit events). */
export function stages(view: ClaimView, events: AuditEvent[]): Stage[] {
  const seen = new Set(events.map((e) => e.event_type));
  const record = view.record;
  const notReached = (name: string): Stage => ({ name, state: "not-reached", result: "Not reached" });
  const low = Object.values(view.field_confidences).filter((v) => v < LOW_CONFIDENCE).length;
  const intake: Stage = {
    name: "Intake",
    state: "done",
    result: `${SOURCE[view.source_format] ?? view.source_format}${low ? `, ${low} low-confidence field${low === 1 ? "" : "s"}` : ""}`,
  };
  if (!record) {
    return [intake, ...["Rules", "Policy", "Model", "Amounts", "Explanation", "Review"].map(notReached)];
  }
  const outcome = record.rules_outcome.claim_outcome;
  const failed = record.rules_outcome.rule_results.filter((r) => !r.passed).length;
  const rules: Stage =
    outcome === "PASS"
      ? { name: "Rules", state: "done", result: failed ? `Passed, ${failed} line rule${failed === 1 ? "" : "s"} failed` : "All passed" }
      : { name: "Rules", state: "problem", result: `${RULE_OUTCOME[outcome] ?? outcome}, ${failed} rule${failed === 1 ? "" : "s"} failed` };
  const criteria = record.context_refs?.lines.reduce((n, line) => n + line.criteria.length, 0) ?? 0;
  const policy: Stage =
    record.context_refs || seen.has("CONTEXT_ASSEMBLED")
      ? { name: "Policy", state: "done", result: `${criteria} criteri${criteria === 1 ? "on" : "a"} found` }
      : notReached("Policy");
  const unusable = answerErrors(record.output_errors).filter((e) => !e.startsWith("CALCULATION_FAILED")).length > 0;
  const unquoted = evidenceChecks(record.output_errors).length;
  const model: Stage =
    seen.has("SLM_RECOMMENDED") || seen.has("OUTPUT_INVALID") || record.slm_output
      ? unusable
        ? { name: "Model", state: "problem", result: "Answer could not be used" }
        : {
            name: "Model",
            state: "done",
            result: unquoted ? `Recommended, ${unquoted} quote${unquoted === 1 ? "" : "s"} not in the note` : "Recommended",
          }
      : notReached("Model");
  const amounts: Stage = record.amounts
    ? { name: "Amounts", state: "done", result: `${money(record.amounts.totals.allowed_cents)} allowed` }
    : seen.has("CALCULATION_FAILED")
      ? { name: "Amounts", state: "problem", result: "Could not be calculated" }
      : notReached("Amounts");
  const explanation: Stage = { name: "Explanation", state: "done", result: "Ready" };
  const final = view.status.startsWith("FINAL_");
  const review: Stage = final
    ? { name: "Review", state: "done", result: STATUS[view.status].label }
    : view.status === "AWAITING_REVIEW"
      ? {
          name: "Review",
          state: "waiting",
          result: record.review_tier ? `Waiting, ${TIER[record.review_tier].label.toLowerCase()} tier` : "Waiting",
        }
      : { name: "Review", state: "not-reached", result: "Not reached: rule outcomes are final" };
  return [intake, rules, policy, model, amounts, explanation, review];
}

const LOOK: Record<StageState, { bar: string; Icon: typeof Check; icon: string }> = {
  done: { bar: "bg-ink", Icon: Check, icon: "text-ink" },
  problem: { bar: "bg-deny", Icon: X, icon: "text-deny" },
  waiting: { bar: "bg-control/50", Icon: Clock, icon: "text-ink-muted" },
  "not-reached": { bar: "bg-transparent border-t border-dashed border-control", Icon: CircleDashed, icon: "text-ink-muted" },
};

export function StageStrip({ view, events, fill = false }: { view: ClaimView; events: AuditEvent[]; fill?: boolean }) {
  const reduce = useReducedMotion();
  const animate = fill && !reduce;
  const list = stages(view, events);
  let reached = 0;
  return (
    <div className="mb-6 overflow-x-auto rounded-lg border border-rules bg-paper">
      <ol aria-label="Pipeline stages" className="grid min-w-[760px] grid-cols-7">
        {list.map((stage) => {
          const look = LOOK[stage.state];
          const order = stage.state === "not-reached" ? 0 : reached++;
          return (
            <li key={stage.name} className="relative border-r border-rules px-3 pt-4 pb-3 last:border-r-0">
              <span className="absolute inset-x-0 top-0 h-1 overflow-hidden" aria-hidden>
                <motion.span
                  className={`block h-1 w-full origin-left ${look.bar}`}
                  initial={animate ? { scaleX: 0 } : false}
                  animate={{ scaleX: 1 }}
                  transition={{ delay: animate ? order * 0.14 : 0, duration: animate ? 0.2 : 0, ease: "easeOut" }}
                />
              </span>
              <div className="flex items-center gap-1.5">
                <look.Icon aria-hidden className={`size-4 shrink-0 ${look.icon}`} strokeWidth={2.25} />
                <span className={`text-[13px] font-semibold ${stage.state === "not-reached" ? "text-ink-muted" : ""}`}>
                  {stage.name}
                </span>
              </div>
              <motion.p
                className="mt-1 text-[13px] leading-5 text-ink-muted"
                initial={animate ? { opacity: 0 } : false}
                animate={{ opacity: 1 }}
                transition={{ delay: animate ? order * 0.14 + 0.1 : 0, duration: animate ? 0.15 : 0 }}
              >
                <span className="sr-only">{stage.state === "not-reached" ? "" : `${stage.state}: `}</span>
                {stage.result}
              </motion.p>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
