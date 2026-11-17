// Formatting only: amounts arrive as integer cents from the calculator and are shown as dollars
// with integer arithmetic; the web app never computes an amount.

export function money(cents: number | null | undefined): string {
  if (cents === null || cents === undefined) return "—";
  const sign = cents < 0 ? "-" : "";
  const whole = Math.abs(cents);
  const rest = whole % 100;
  const dollars = (whole - rest) / 100;
  return `${sign}$${dollars.toLocaleString("en-US")}.${String(rest).padStart(2, "0")}`;
}

/** A rate in integer basis points as a percentage: 2000 -> "20%", 2050 -> "20.5%" (no floats). */
export function basisPoints(bps: number | null | undefined): string {
  if (bps === null || bps === undefined) return "—";
  const rest = bps % 100;
  const fraction = rest ? `.${String(Math.abs(rest)).padStart(2, "0").replace(/0+$/, "")}` : "";
  return `${(bps - rest) / 100}${fraction}%`;
}

/** A calendar date as the forms print it: "2026-10-06" -> "10/06/2026" (anything else as it is). */
export function dateOnly(value: string | null | undefined): string {
  if (!value) return "—";
  const [y, m, d] = value.split("-");
  return y && m && d ? `${m}/${d}/${y}` : value;
}

export function percent(share: number): string {
  return `${(share * 100).toFixed(1)}%`;
}

export function dateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const when = new Date(value);
  return Number.isNaN(when.getTime())
    ? value
    : when.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

/** A time to the second, for the audit trail: "Nov 16, 2026, 4:33:11 PM". */
export function dateTimeSeconds(value: string | null | undefined): string {
  if (!value) return "—";
  const when = new Date(value);
  return Number.isNaN(when.getTime())
    ? value
    : when.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "medium" });
}

/** A duration in seconds in its largest sensible units: "45 s", "12 min", "3 h 5 min", "2 d 4 h". */
export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const whole = Math.max(0, Math.round(seconds));
  if (whole < 60) return `${whole} s`;
  const minutes = Math.round(whole / 60);
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return minutes % 60 ? `${hours} h ${minutes % 60} min` : `${hours} h`;
  const days = Math.floor(hours / 24);
  return hours % 24 ? `${days} d ${hours % 24} h` : `${days} d`;
}

/** How long ago, in the largest whole unit: "5 min", "3 h", "2 d". */
export function age(value: string | null | undefined, now: Date = new Date()): string {
  if (!value) return "—";
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(value).getTime()) / 60000));
  if (minutes < 60) return `${minutes} min`;
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)} h`;
  return `${Math.floor(minutes / (60 * 24))} d`;
}

/** A claim field path as a label: "service_lines.0.procedure_code" -> "Line 1 · Procedure code". */
export function fieldLabel(path: string): string {
  const parts = path.split(".");
  const words: string[] = [];
  for (let i = 0; i < parts.length; i += 1) {
    const part = parts[i] ?? "";
    const next = parts[i + 1];
    if (part === "service_lines" && next !== undefined) {
      words.push(`Line ${Number(next) + 1}`);
      i += 1;
    } else if (part === "diagnoses" && next !== undefined) {
      words.push(`Diagnosis ${"ABCDEFGHIJKL"[Number(next)] ?? next}`);
      i += 1;
    } else if (part === "primary_paid" && next !== undefined) {
      words.push(`Primary payment ${Number(next) + 1}`);
      i += 1;
    } else {
      words.push(FIELD_WORDS[part] ?? sentence(part));
    }
  }
  return words.join(" · ");
}

const FIELD_WORDS: Record<string, string> = {
  claim_id: "Claim ID",
  member_id: "Member ID",
  billing_npi: "Billing NPI",
  billing_tin: "Billing tax ID",
  referring_npi: "Referring NPI",
  rendering_npi: "Rendering NPI",
  prior_auth_number: "Prior authorization",
  subscriber_is_patient: "Patient is the subscriber",
  charge_cents: "Charge",
  zip_code: "ZIP code",
  line1: "Street",
  other_coverage: "Other coverage",
  place_of_service: "Place of service",
  diagnosis_pointers: "Diagnosis pointers",
  date_of_birth: "Date of birth",
};

function sentence(name: string): string {
  const text = name.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
