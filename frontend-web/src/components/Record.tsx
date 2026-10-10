// Parts of a decision record: the rule checks and the calculator's amounts. The UI formats what
// the record holds; it computes no amount.

import type { Amounts, DecisionRecord } from "@/api/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { money } from "@/lib/format";
import { reason } from "@/lib/labels";

export function RuleChecks({ record }: { record: DecisionRecord }) {
  const rules = record.rules_outcome.rule_results;
  const failed = rules.filter((r) => !r.passed);
  return (
    <div>
      <p className="mb-3 text-[13px] text-ink-muted">
        {rules.length} rule checks, {failed.length ? `${failed.length} failed` : "all passed"}.
      </p>
      <div className="overflow-hidden rounded-lg border border-rules bg-paper">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Rule</TableHead>
              <TableHead>Result</TableHead>
              <TableHead>Line</TableHead>
              <TableHead>Detail</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rules.map((rule, i) => (
              <TableRow key={`${rule.rule_id}-${rule.line_no ?? 0}-${i}`}>
                <TableCell className="font-semibold">{rule.rule_id}</TableCell>
                <TableCell className={`whitespace-nowrap ${rule.passed ? "" : "font-semibold text-deny"}`}>
                  {rule.passed ? "Passed" : `Failed, ${rule.outcome.toLowerCase()}`}
                </TableCell>
                <TableCell className="tabular-nums">{rule.line_no ?? ""}</TableCell>
                <TableCell className="min-w-64">
                  {rule.detail}
                  {rule.reason_code && <div className="text-[13px] text-ink-muted">{reason(rule.reason_code)}</div>}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
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
    return <p className="text-ink-muted">No amounts: the calculator did not run for this claim.</p>;
  }
  return (
    <div className="overflow-hidden rounded-lg border border-rules bg-paper">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Line</TableHead>
            {SHOWN.map(([key, label]) => (
              <TableHead key={key} className="text-right">
                {label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {record.amounts.lines.map((line) => (
            <TableRow key={line.line_no}>
              <TableCell className="tabular-nums">{line.line_no}</TableCell>
              {SHOWN.map(([key]) => (
                <TableCell key={key} className="text-right whitespace-nowrap tabular-nums">
                  {money(line[key])}
                </TableCell>
              ))}
            </TableRow>
          ))}
          <TableRow className="font-semibold">
            <TableCell>Total</TableCell>
            {SHOWN.map(([key]) => (
              <TableCell key={key} className="text-right whitespace-nowrap tabular-nums">
                {money(record.amounts?.totals[key])}
              </TableCell>
            ))}
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
