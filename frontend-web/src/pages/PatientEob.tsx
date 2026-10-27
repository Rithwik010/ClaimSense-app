// The patient's explanation of benefits (D-EOB-1): what the plan did with each service on a decided
// claim, for the provider to print or hand to the patient. It is not a bill. Built by the API from
// the decision record; every amount is the calculator's and the page only formats it. Printing
// gives black text on white without the app around it (index.css). A member's own claim page shows
// the same EOB (EobView, D-MEM-2).

import { Printer } from "lucide-react";
import { Fragment } from "react";
import { Link, useParams } from "react-router";

import { usePatientEob } from "@/api/hooks";
import type { EobLine, EobTotals, PatientEob as Eob } from "@/api/types";
import { Chip, OutcomeChip } from "@/components/Chip";
import { PageTitle, Panel, Section } from "@/components/Layout";
import { ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { money } from "@/lib/format";
import type { Label } from "@/lib/labels";

const LINE_STATUS: Record<EobLine["status"], Label> = {
  PAID: { label: "Paid", hint: "The plan paid its share", tone: "approve" },
  NOT_PAID: { label: "Not paid", hint: "The plan did not pay", tone: "deny" },
  PENDING: { label: "Waiting", hint: "Waiting for information", tone: "pend" },
};
const AMOUNTS: [keyof EobLine & `${string}_cents`, string][] = [
  ["billed_cents", "Billed"],
  ["allowed_cents", "Plan allows"],
  ["plan_pays_cents", "Plan paid"],
  ["patient_pays_cents", "Patient owes"],
];

function day(value: string | null): string {
  if (!value) return "—";
  const [y, m, d] = value.split("-");
  return y && m && d ? `${m}/${d}/${y}` : value;
}

function Facts({ eob }: { eob: Eob }) {
  const rows: [string, string][] = [
    ["Patient", eob.patient_name ?? "—"],
    ["Member ID", eob.member_id ?? "—"],
    ["Plan", eob.plan_name ?? "—"],
    ["Provider", [eob.provider_name, eob.provider_npi && `NPI ${eob.provider_npi}`].filter(Boolean).join(", ") || "—"],
    ["Claim", eob.claim_id],
    ["Received", day(eob.received)],
    ["Processed", day(eob.processed)],
  ];
  if (eob.network) rows.push(["Network", eob.network === "IN_NETWORK" ? "In network" : "Out of network"]);
  return (
    <dl className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
      {rows.map(([term, value]) => (
        <div key={term} className="flex flex-wrap gap-x-3">
          <dt className="w-24 shrink-0 text-ink-muted">{term}</dt>
          <dd className="min-w-0 font-semibold break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function LineNotes({ line }: { line: EobLine }) {
  return (
    <>
      {line.notes.length > 0 && (
        <ul aria-label={`Line ${line.line_no} notes`} className="space-y-1 text-[13px] text-ink-muted">
          {line.notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
      {line.codes.length > 0 && <p className="mt-1 text-[13px] text-ink-muted">Codes: {line.codes.join(", ")}</p>}
    </>
  );
}

function Service({ line }: { line: EobLine }) {
  return (
    <>
      <span className="font-semibold">{line.service ?? `Service ${line.procedure_code}`}</span>
      <span className="ml-1.5 text-ink-muted">{line.procedure_code}</span>
    </>
  );
}

/** On a phone: each service as a card. */
function Cards({ eob }: { eob: Eob }) {
  return (
    <ul aria-label="Services" className="space-y-3 md:hidden print:hidden">
      {eob.lines.map((line) => (
        <li key={line.line_no} className="surface rounded-lg p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p>
              <Service line={line} />
            </p>
            <Chip label={LINE_STATUS[line.status]} />
          </div>
          <p className="text-[13px] text-ink-muted">Date of service {day(line.date_of_service)}</p>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1.5 text-[14px]">
            {AMOUNTS.map(([key, label]) => (
              <div key={key} className="flex justify-between gap-2">
                <dt className="text-ink-muted">{label}</dt>
                <dd className="tabular-nums">{money(line[key])}</dd>
              </div>
            ))}
          </dl>
          <div className="mt-3 border-t border-rules pt-3">
            <LineNotes line={line} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function LinesTable({ eob }: { eob: Eob }) {
  return (
    <div className="hidden overflow-x-auto surface rounded-lg md:block print:block">
      <Table aria-label="Services">
        <TableHeader>
          <TableRow>
            <TableHead>Date</TableHead>
            <TableHead>Service</TableHead>
            {AMOUNTS.map(([key, label]) => (
              <TableHead key={key} className="text-right">
                {label}
              </TableHead>
            ))}
            <TableHead>Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {eob.lines.map((line) => (
            <Fragment key={line.line_no}>
              <TableRow className="border-b-0">
                <TableCell className="align-top whitespace-nowrap">{day(line.date_of_service)}</TableCell>
                <TableCell className="align-top">
                  <Service line={line} />
                </TableCell>
                {AMOUNTS.map(([key]) => (
                  <TableCell key={key} className="text-right align-top whitespace-nowrap tabular-nums">
                    {money(line[key])}
                  </TableCell>
                ))}
                <TableCell className="align-top">
                  <Chip label={LINE_STATUS[line.status]} />
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell />
                <TableCell colSpan={AMOUNTS.length + 2} className="pt-0 pb-3 whitespace-normal">
                  <LineNotes line={line} />
                </TableCell>
              </TableRow>
            </Fragment>
          ))}
          {eob.totals && (
            <TableRow className="font-semibold">
              <TableCell colSpan={2}>Total</TableCell>
              {AMOUNTS.map(([key]) => (
                <TableCell key={key} className="text-right whitespace-nowrap tabular-nums">
                  {money(eob.totals?.[key as keyof EobTotals])}
                </TableCell>
              ))}
              <TableCell />
            </TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}

function Totals({ eob }: { eob: Eob }) {
  if (!eob.totals) return null;
  const items: [string, number][] = [
    ["Billed by the provider", eob.totals.billed_cents],
    ["Paid by the plan", eob.totals.plan_pays_cents],
    ["The patient may owe the provider", eob.totals.patient_pays_cents],
  ];
  if (eob.totals.other_plan_paid_cents > 0) items.push(["Paid first by another plan", eob.totals.other_plan_paid_cents]);
  return (
    <dl className="grid gap-4 sm:grid-cols-3">
      {items.map(([term, cents]) => (
        <div key={term}>
          <dt className="text-[13px] text-ink-muted">{term}</dt>
          <dd className="text-[22px] leading-[30px] font-semibold tabular-nums">{money(cents)}</dd>
        </div>
      ))}
    </dl>
  );
}

function YearToDate({ eob }: { eob: Eob }) {
  const ytd = eob.year_to_date;
  if (!ytd) return null;
  return (
    <Section title="This benefit year so far">
      <Panel className="p-5">
        <dl className="grid gap-3 sm:grid-cols-2">
          <div>
            <dt className="text-[13px] text-ink-muted">Deductible met</dt>
            <dd className="tabular-nums">
              <span className="font-semibold">{money(ytd.deductible_met_cents)}</span> of {money(ytd.deductible_cents)}
            </dd>
          </div>
          <div>
            <dt className="text-[13px] text-ink-muted">Out-of-pocket spent</dt>
            <dd className="tabular-nums">
              <span className="font-semibold">{money(ytd.oop_met_cents)}</span> of {money(ytd.oop_max_cents)} maximum
            </dd>
          </div>
        </dl>
        <p className="mt-3 text-[13px] text-ink-muted">
          {ytd.network === "IN_NETWORK" ? "In-network" : "Out-of-network"} amounts for the benefit year starting{" "}
          {day(ytd.period_start)}, as of when this claim was decided.
        </p>
      </Panel>
    </Section>
  );
}

export function PatientEob() {
  const { claimId = "" } = useParams();
  const eob = usePatientEob(claimId);
  if (eob.isPending) return <Skeleton lines={8} />;
  if (eob.error) return <ErrorNotice error={eob.error} onRetry={() => void eob.refetch()} />;
  return <EobView eob={eob.data} />;
}

/** The EOB itself, for the provider's and staff's EOB page and the member's claim page. */
export function EobView({
  eob: data,
  hint = "What the plan did with each service, for the patient.",
  back = { to: "..", label: "Back to the claim" },
}: {
  eob: Eob;
  hint?: string;
  back?: { to: string; label: string };
}) {
  const [notBill, ...notes] = data.notes;
  return (
    <div className="eob">
      <PageTitle
        title="Explanation of benefits"
        hint={`Claim ${data.claim_id}. ${hint}`}
        actions={
          <div className="flex flex-wrap items-center gap-3 print:hidden">
            <OutcomeChip outcome={data.outcome} />
            <Button size="lg" onClick={() => window.print()}>
              <Printer aria-hidden /> Print
            </Button>
          </div>
        }
      />
      <Panel glass className="mb-8 p-5 print:border print:shadow-none">
        <p className="mb-4 text-[18px] leading-[26px] font-semibold">{notBill}</p>
        <Facts eob={data} />
      </Panel>
      {data.totals && (
        <Section title="Summary">
          <Panel className="p-5">
            <Totals eob={data} />
          </Panel>
        </Section>
      )}
      <Section title="Services">
        <Cards eob={data} />
        <LinesTable eob={data} />
      </Section>
      <YearToDate eob={data} />
      {(notes.length > 0 || data.codes.length > 0) && (
        <Section title="About this claim">
          <ul className="max-w-[75ch] list-disc space-y-1 pl-5">
            {notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
            {data.codes.length > 0 && <li>Codes for the whole claim: {data.codes.join(", ")}</li>}
          </ul>
        </Section>
      )}
      <p className="max-w-[75ch] text-[13px] text-ink-muted">
        Questions about this claim: contact the plan and give claim {data.claim_id}. ClaimSense prototype: synthetic data
        only.{" "}
        <Link
          className="font-semibold text-link underline print:hidden"
          to={back.to}
          relative={back.to === ".." ? "path" : "route"}
        >
          {back.label}
        </Link>
      </p>
    </div>
  );
}
