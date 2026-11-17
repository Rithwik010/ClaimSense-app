// The claim at a glance for the plan's staff (D-REV-10): the patient and member ID, the provider,
// the dates, each diagnosis and each service line's procedure with its plain name (the code tables
// in data/raw, via the API's `names`; paraphrased names, never AMA descriptors). Formatting only.

import type { Claim, CodeNames } from "@/api/types";
import { dateOnly, money } from "@/lib/format";

interface Line {
  line_no: number;
  procedure_code: string;
  date_of_service: string | null;
  units: number | null;
  charge_cents: number | null;
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

/** The claim's service lines as filed: line number, procedure code, date, units and charge. */
export function claimLines(claim: Claim): Line[] {
  const lines = Array.isArray(claim.service_lines) ? (claim.service_lines as Record<string, unknown>[]) : [];
  return lines.map((line, i) => ({
    line_no: typeof line.line_no === "number" ? line.line_no : i + 1,
    procedure_code: text(line.procedure_code) ?? "—",
    date_of_service: text(line.date_of_service),
    units: typeof line.units === "number" ? line.units : null,
    charge_cents: typeof line.charge_cents === "number" ? line.charge_cents : null,
  }));
}

export function patientName(claim: Claim): string | null {
  const patient = (claim.patient ?? null) as Record<string, unknown> | null;
  const name = [text(patient?.first_name), text(patient?.last_name)].filter(Boolean).join(" ");
  return name || null;
}

export function ClaimHeader({ claim, names, providerName }: { claim: Claim; names?: CodeNames; providerName?: string | null }) {
  const diagnoses = Array.isArray(claim.diagnoses) ? (claim.diagnoses as unknown[]).filter((d): d is string => typeof d === "string") : [];
  const lines = claimLines(claim);
  return (
    <section aria-label="Claim at a glance" className="surface mb-6 rounded-lg p-4 md:p-5">
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-[13px] text-ink-muted">Patient</dt>
          <dd className="font-semibold">{patientName(claim) ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">Member ID</dt>
          <dd className="tabular-nums">{text(claim.member_id) ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">Provider</dt>
          <dd>
            {providerName ?? "—"}
            <span className="block text-[13px] text-ink-muted tabular-nums">NPI {text(claim.billing_npi) ?? "—"}</span>
          </dd>
        </div>
        <div>
          <dt className="text-[13px] text-ink-muted">Received</dt>
          <dd className="tabular-nums">{dateOnly(text(claim.received_date))}</dd>
        </div>
      </dl>
      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div>
          <h2 className="text-[13px] font-semibold text-ink-muted">Diagnoses</h2>
          <ul className="mt-1 space-y-1 text-[14px]">
            {diagnoses.map((code, i) => (
              <li key={code} className="grid grid-cols-[auto_1fr] gap-x-2">
                <span className="font-semibold tabular-nums">
                  {"ABCDEFGHIJKL"[i]} {code}
                </span>
                <span className="text-ink-muted">{names?.diagnoses[code] ?? "Name not on file"}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="text-[13px] font-semibold text-ink-muted">Services</h2>
          <ul className="mt-1 space-y-1 text-[14px]">
            {lines.map((line) => (
              <li key={line.line_no} className="grid grid-cols-[auto_1fr] gap-x-2">
                <span className="font-semibold tabular-nums">
                  Line {line.line_no} · {line.procedure_code}
                </span>
                <span className="text-ink-muted">
                  {names?.procedures[line.procedure_code] ?? "Name not on file"}
                  {line.date_of_service ? `, ${dateOnly(line.date_of_service)}` : ""}
                  {line.units && line.units > 1 ? `, ${line.units} units` : ""}
                  {line.charge_cents !== null ? `, ${money(line.charge_cents)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
