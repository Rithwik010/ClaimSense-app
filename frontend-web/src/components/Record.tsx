// Parts of a decision record: rule checks, each line's recommendation with its criteria, evidence
// and citations, and the calculator's amounts. Everything shown comes from the record.

import type { Amounts, DecisionRecord, FinalLineDecision } from "../api/types";
import { money } from "../lib/format";
import { CRITERION_STATUS, SOURCE, reason } from "../lib/labels";
import { DecisionChip } from "./Chip";
import { table, td, th } from "./ui";

export function RuleChecks({ record }: { record: DecisionRecord }) {
  const rules = record.rules_outcome.rule_results;
  const failed = rules.filter((r) => !r.passed).length;
  return (
    <div>
      <p className="mb-3 text-sm text-gray-600">
        {rules.length} rule checks, {failed ? `${failed} failed` : "all passed"}.
      </p>
      <div className="overflow-auto rounded-md border border-gray-200">
        <table className={table}>
          <thead>
            <tr>
              <th scope="col" className={th}>Rule</th>
              <th scope="col" className={th}>Result</th>
              <th scope="col" className={th}>Line</th>
              <th scope="col" className={th}>Detail</th>
            </tr>
          </thead>
          <tbody>
            {rules.map((rule, i) => (
              <tr key={`${rule.rule_id}-${rule.line_no ?? 0}-${i}`} className={rule.passed ? undefined : "bg-red-50"}>
                <td className={`${td} font-mono text-xs`}>{rule.rule_id}</td>
                <td className={td}>{rule.passed ? "Passed" : `Failed (${rule.outcome})`}</td>
                <td className={td}>{rule.line_no ?? ""}</td>
                <td className={td}>
                  {rule.detail}
                  {rule.reason_code && <div className="text-gray-600">{reason(rule.reason_code)}</div>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const SHOWN: [keyof Amounts, string][] = [
  ["billed_cents", "Billed"],
  ["allowed_cents", "Allowed"],
  ["deductible_cents", "Deductible"],
  ["copay_cents", "Copay"],
  ["coinsurance_cents", "Coinsurance"],
  ["plan_pays_cents", "Plan pays"],
  ["member_pays_cents", "Member pays"],
];

export function AmountsTable({ record }: { record: DecisionRecord }) {
  if (!record.amounts) {
    return <p className="text-gray-600">No amounts: the calculator has not run for this claim.</p>;
  }
  return (
    <div className="overflow-auto rounded-md border border-gray-200">
      <table className={table}>
        <thead>
          <tr>
            <th scope="col" className={th}>Line</th>
            {SHOWN.map(([key, label]) => (
              <th key={key} scope="col" className={`${th} text-right`}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {record.amounts.lines.map((line) => (
            <tr key={line.line_no}>
              <td className={td}>{line.line_no}</td>
              {SHOWN.map(([key]) => (
                <td key={key} className={`${td} text-right tabular-nums`}>{money(line[key])}</td>
              ))}
            </tr>
          ))}
          <tr className="font-medium">
            <td className={td}>Total</td>
            {SHOWN.map(([key]) => (
              <td key={key} className={`${td} text-right tabular-nums`}>
                {money(record.amounts?.totals[key])}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

export function LineDetails({ record, line }: { record: DecisionRecord; line: FinalLineDecision }) {
  const context = record.context_refs?.lines.find((c) => c.line_no === line.line_no);
  const answer = record.slm_output?.lines.find((l) => l.line_no === line.line_no);
  const cited = new Map((context?.criteria ?? []).map((c) => [c.criterion_id, c]));
  const amounts = record.amounts?.lines.find((a) => a.line_no === line.line_no);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-semibold">
          Line {line.line_no}
          {context && <span className="ml-2 font-mono text-sm text-gray-600">{context.procedure_code}</span>}
        </h3>
        <DecisionChip decision={line.decision} showHint />
        <span className="text-sm text-gray-600">by {SOURCE[line.source] ?? line.source}</span>
        {line.benefit_category && (
          <span className="text-sm text-gray-600">· {line.benefit_category.replaceAll("_", " ").toLowerCase()}</span>
        )}
      </div>
      {line.reason_codes.length > 0 && (
        <ul className="list-disc pl-5 text-sm text-gray-700">
          {line.reason_codes.map((code) => (
            <li key={code}>{reason(code)}</li>
          ))}
        </ul>
      )}
      {line.source !== "RULE" && answer && answer.criteria.length > 0 && (
        <div className="overflow-auto rounded-md border border-gray-200">
          <table className={table}>
            <thead>
              <tr>
                <th scope="col" className={th}>Criterion</th>
                <th scope="col" className={th}>Status</th>
                <th scope="col" className={th}>Evidence</th>
                <th scope="col" className={th}>Policy</th>
              </tr>
            </thead>
            <tbody>
              {answer.criteria.map((c) => {
                const source = cited.get(c.criterion_id);
                return (
                  <tr key={c.criterion_id}>
                    <td className={td}>
                      <span className="font-mono text-xs">{c.criterion_id}</span>
                      {source && <div className="text-gray-600">{source.text}</div>}
                    </td>
                    <td className={`${td} whitespace-nowrap`}>{CRITERION_STATUS[c.status] ?? c.status}</td>
                    <td className={td}>{c.evidence}</td>
                    <td className={td}>
                      {source ? `${source.policy_id}: ${source.policy_title}` : c.criterion_id.split(".")[0]}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {line.decision === "PEND" && answer && (
        <p className="text-sm text-gray-700">
          Awaiting documentation for:{" "}
          {answer.criteria
            .filter((c) => c.status === "NOT_DOCUMENTED")
            .map((c) => c.criterion_id)
            .join(", ") || "documentation that supports the service"}
        </p>
      )}
      {amounts && (
        <p className="text-sm text-gray-700">
          Billed {money(amounts.billed_cents)} · allowed {money(amounts.allowed_cents)} · plan
          pays {money(amounts.plan_pays_cents)} · member pays {money(amounts.member_pays_cents)}
        </p>
      )}
    </div>
  );
}
