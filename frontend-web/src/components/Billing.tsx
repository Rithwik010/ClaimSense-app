// The provider's billing for a paid claim (D-UI-6): per line and in total, billed, allowed,
// deductible, copay, coinsurance, what the plan pays and what the patient pays, with one plain
// sentence under each line for each reduction that happened. Every amount is the calculator's,
// as the API returns it: the web app formats them and computes none.

import type { BillingAmounts, BillingLine } from "@/api/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { money } from "@/lib/format";

const COLUMNS: [keyof BillingAmounts, string][] = [
  ["billed_cents", "Billed"],
  ["allowed_cents", "Allowed"],
  ["deductible_cents", "Deductible"],
  ["copay_cents", "Copay"],
  ["coinsurance_cents", "Coinsurance"],
  ["plan_pays_cents", "Plan pays"],
  ["patient_pays_cents", "Patient pays"],
];

function Line({ line }: { line: BillingLine }) {
  return (
    <>
      <TableRow className="border-b-0">
        <TableCell className="align-top font-semibold whitespace-nowrap">
          Line {line.line_no}
          {line.procedure_code && <span className="ml-1.5 font-normal text-ink-muted">{line.procedure_code}</span>}
        </TableCell>
        {COLUMNS.map(([key]) => (
          <TableCell key={key} className="text-right align-top whitespace-nowrap tabular-nums">
            {money(line[key])}
          </TableCell>
        ))}
      </TableRow>
      <TableRow>
        <TableCell colSpan={COLUMNS.length + 1} className="pt-0 pb-3 whitespace-normal">
          {line.reductions.length > 0 ? (
            <ul aria-label={`Line ${line.line_no} reductions`} className="max-w-[80ch] space-y-1 text-[13px] text-ink-muted">
              {line.reductions.map((r) => (
                <li key={r.text}>{r.text}</li>
              ))}
            </ul>
          ) : (
            <p className="text-[13px] text-ink-muted">Paid as billed.</p>
          )}
        </TableCell>
      </TableRow>
    </>
  );
}

/** On a phone: each line as a card with its amounts and sentences, then the totals. */
function Cards({ lines, totals }: { lines: BillingLine[]; totals: BillingAmounts }) {
  const amounts = (row: BillingAmounts) => (
    <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[14px]">
      {COLUMNS.map(([key, label]) => (
        <div key={key} className="flex justify-between gap-2">
          <dt className="text-ink-muted">{label}</dt>
          <dd className="tabular-nums">{money(row[key])}</dd>
        </div>
      ))}
    </dl>
  );
  return (
    <ul aria-label="Billing" className="space-y-3 md:hidden">
      {lines.map((line) => (
        <li key={line.line_no} className="surface rounded-lg p-4">
          <p className="font-semibold">
            Line {line.line_no}
            {line.procedure_code && <span className="ml-1.5 font-normal text-ink-muted">{line.procedure_code}</span>}
          </p>
          {amounts(line)}
          <ul className="mt-3 space-y-1 border-t border-rules pt-3 text-[13px] text-ink-muted">
            {line.reductions.length ? line.reductions.map((r) => <li key={r.text}>{r.text}</li>) : <li>Paid as billed.</li>}
          </ul>
        </li>
      ))}
      <li className="surface rounded-lg p-4">
        <p className="font-semibold">Total</p>
        {amounts(totals)}
      </li>
    </ul>
  );
}

export function Billing({ lines, totals }: { lines: BillingLine[]; totals: BillingAmounts }) {
  return (
    <>
      <Cards lines={lines} totals={totals} />
      <BillingTable lines={lines} totals={totals} />
      {totals.other_plan_paid_cents > 0 && (
        <p className="mt-3 text-[13px] text-ink-muted">
          The patient's other plan paid {money(totals.other_plan_paid_cents)} first.
        </p>
      )}
    </>
  );
}

function BillingTable({ lines, totals }: { lines: BillingLine[]; totals: BillingAmounts }) {
  return (
    <div className="hidden overflow-x-auto surface rounded-lg md:block">
      <Table aria-label="Billing">
        <TableHeader>
          <TableRow>
            <TableHead>Line</TableHead>
            {COLUMNS.map(([key, label]) => (
              <TableHead key={key} className="text-right">
                {label}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {lines.map((line) => (
            <Line key={line.line_no} line={line} />
          ))}
          <TableRow className="font-semibold">
            <TableCell>Total</TableCell>
            {COLUMNS.map(([key]) => (
              <TableCell key={key} className="text-right whitespace-nowrap tabular-nums">
                {money(totals[key])}
              </TableCell>
            ))}
          </TableRow>
        </TableBody>
      </Table>
    </div>
  );
}
