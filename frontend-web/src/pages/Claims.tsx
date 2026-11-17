// Claims (reviewers and admins; read-only for admins): every claim on file, most recently changed
// first. Search by claim ID, member ID, provider name or NPI and filter by status (D-UI-6), both kept
// in the URL; the Reason column gives one line of plain words for a claim not paid as billed.
// ?reviewed=1 (the Overview's reviewed counts, D-UI-10) keeps the claims a reviewer finalized, with
// a note that shows them all again. The patient and the date of service as filed, sorting and a CSV
// of the rows shown (D-UI-12); "Plan pays" only once a claim is final, and "On hold" for a pended
// one (fix 7). Cards on a phone.

import { Link } from "react-router";

import { useClaims } from "@/api/hooks";
import type { ClaimStatus, ClaimSummary } from "@/api/types";
import { ClaimFilters, NoMatch, useClaimFilters } from "@/components/ClaimFilters";
import { OutcomeChip, PlainBadge } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { CsvButton, csvMoney, SortHead, useSort } from "@/components/ListTools";
import { ReasonCell } from "@/components/ReasonCell";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { matches } from "@/lib/filters";
import { dateOnly, dateTime, money } from "@/lib/format";
import { OUTCOME, STAFF_FILTERS } from "@/lib/labels";

const SOURCE: Record<string, string> = { JSON: "JSON", DIGITAL_PDF: "Digital PDF", SCANNED: "Scanned form" };
const DECIDED_BY_RULES: ReadonlySet<ClaimStatus> = new Set<ClaimStatus>(["REJECTED", "DENIED_BY_RULE", "PENDED_BY_RULE"]);
const SORTS = ["claim", "patient", "service", "billed", "updated"] as const;
type SortKey = (typeof SORTS)[number];

/** Final: a reviewer's decision or a rule outcome. Until then an amount is only a recommendation. */
function isFinal(claim: ClaimSummary): boolean {
  return claim.status.startsWith("FINAL_") || DECIDED_BY_RULES.has(claim.status);
}

/** What the plan pays, once final; a claim on hold has paid nothing yet, so it says so (fix 7). */
function planPays(claim: ClaimSummary): string {
  if (!isFinal(claim)) return "—";
  if (claim.outcome === "PENDED") return "On hold";
  return money(claim.plan_pays_cents);
}

function sortValue(claim: ClaimSummary, key: SortKey) {
  switch (key) {
    case "claim":
      return claim.claim_id;
    case "patient":
      return claim.patient_name ?? null;
    case "service":
      return claim.service_date ?? null;
    case "billed":
      return claim.total_billed_cents;
    default:
      return claim.updated;
  }
}

const CSV_COLUMNS = [
  { header: "Claim ID", value: (c: ClaimSummary) => c.claim_id },
  { header: "Patient", value: (c: ClaimSummary) => c.patient_name ?? "" },
  { header: "Member ID", value: (c: ClaimSummary) => c.member_id },
  { header: "Provider", value: (c: ClaimSummary) => c.provider_name ?? "" },
  { header: "Provider NPI", value: (c: ClaimSummary) => c.provider_npi ?? "" },
  { header: "Date of service", value: (c: ClaimSummary) => c.service_date ?? "" },
  { header: "Status", value: (c: ClaimSummary) => OUTCOME[c.outcome].label },
  { header: "Reason", value: (c: ClaimSummary) => c.reasons.map((r) => r.short).join("; ") },
  { header: "Source", value: (c: ClaimSummary) => SOURCE[c.source_format] ?? c.source_format },
  { header: "Billed", value: (c: ClaimSummary) => csvMoney(c.total_billed_cents) },
  { header: "Plan pays", value: (c: ClaimSummary) => (isFinal(c) && c.outcome !== "PENDED" ? csvMoney(c.plan_pays_cents) : "") },
  { header: "Updated", value: (c: ClaimSummary) => c.updated },
];

function ClaimLink({ claim }: { claim: ClaimSummary }) {
  return (
    <Link
      className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-primary-hover hover:underline"
      to={`/claims/${encodeURIComponent(claim.claim_id)}`}
    >
      {claim.claim_id}
    </Link>
  );
}

// Final after a reviewer's decision; a rule outcome (rejected, denied or pended by rule) is not.
const REVIEWED: ReadonlySet<ClaimStatus> = new Set<ClaimStatus>([
  "FINAL_APPROVED",
  "FINAL_PARTIAL",
  "FINAL_PENDED",
  "FINAL_DENIED",
]);

/** The note over the list while it shows only the claims a reviewer finalized. */
function ReviewedOnly({ onShowAll }: { onShowAll: () => void }) {
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 rounded-lg border border-rules bg-brand-tint px-4 py-2.5 text-[14px]">
      <p>Showing the claims a reviewer finalized. Open one to see what the reviewer accepted or overrode.</p>
      <Button variant="outline" size="sm" onClick={onShowAll}>
        Show all claims
      </Button>
    </div>
  );
}

export function Claims() {
  const claims = useClaims();
  const filters = useClaimFilters(STAFF_FILTERS);
  const sort = useSort(SORTS, "updated");
  const wanted = filters.query.trim().toLowerCase();
  const shown = sort.apply(
    (claims.data ?? []).filter(
      (c) =>
        (!filters.reviewed || REVIEWED.has(c.status)) &&
        (matches(c, filters.query, filters.status, "all") ||
          (wanted !== "" &&
            (c.patient_name ?? "").toLowerCase().includes(wanted) &&
            matches(c, "", filters.status, "all"))),
    ),
    sortValue,
  );
  return (
    <>
      <PageTitle
        title="Claims"
        hint="Every claim on file, most recently changed first."
        actions={<CsvButton rows={shown} columns={CSV_COLUMNS} fileName="claims.csv" />}
      />
      {claims.isPending ? (
        <Skeleton lines={6} />
      ) : claims.error ? (
        <ErrorNotice error={claims.error} onRetry={() => void claims.refetch()} />
      ) : claims.data.length === 0 ? (
        <EmptyState title="No claims yet">Claims appear here once a provider files them.</EmptyState>
      ) : (
        <>
          {filters.reviewed && <ReviewedOnly onShowAll={filters.clear} />}
          <ClaimFilters
            filters={filters}
            searchLabel="Search claims"
            placeholder="Claim ID, patient, member ID, provider name or NPI"
            options={STAFF_FILTERS}
            label={(outcome) => OUTCOME[outcome]}
            shown={shown.length}
          />
          {shown.length === 0 ? (
            <NoMatch onClear={filters.clear} />
          ) : (
            <>
              <ul aria-label="Claims" className="grid gap-3 md:hidden">
                {shown.map((claim) => (
                  <li key={claim.claim_id} className="surface rounded-lg p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <ClaimLink claim={claim} />
                      <OutcomeChip outcome={claim.outcome} />
                    </div>
                    <p className="mt-2 text-[15px]">
                      {claim.patient_name ?? "—"}
                      <span className="text-ink-muted">, {claim.member_id}</span>
                    </p>
                    <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 text-[15px]">
                      <div>
                        <dt className="text-[13px] text-ink-muted">Date of service</dt>
                        <dd>{dateOnly(claim.service_date)}</dd>
                      </div>
                      <div>
                        <dt className="text-[13px] text-ink-muted">Billed</dt>
                        <dd className="tabular-nums">{money(claim.total_billed_cents)}</dd>
                      </div>
                      <div>
                        <dt className="text-[13px] text-ink-muted">Plan pays</dt>
                        <dd className="tabular-nums">{planPays(claim)}</dd>
                      </div>
                      <div>
                        <dt className="text-[13px] text-ink-muted">Source</dt>
                        <dd>{SOURCE[claim.source_format] ?? claim.source_format}</dd>
                      </div>
                    </dl>
                    {claim.reasons.length > 0 && (
                      <div className="mt-2 text-[14px]">
                        <ReasonCell reasons={claim.reasons} />
                      </div>
                    )}
                    {claim.appeal_open && (
                      <p className="mt-2">
                        <PlainBadge>Appeal open</PlainBadge>
                      </p>
                    )}
                  </li>
                ))}
              </ul>
              <div className="surface hidden overflow-x-auto rounded-lg md:block">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <SortHead sort={sort} column="claim">
                        Claim
                      </SortHead>
                      <SortHead sort={sort} column="patient">
                        Patient
                      </SortHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Reason</TableHead>
                      <SortHead sort={sort} column="service">
                        Service date
                      </SortHead>
                      <SortHead sort={sort} column="billed" className="text-right">
                        Billed
                      </SortHead>
                      <TableHead className="text-right">Plan pays</TableHead>
                      <SortHead sort={sort} column="updated">
                        Updated
                      </SortHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {shown.map((claim) => (
                      <TableRow key={claim.claim_id}>
                        <TableCell>
                          <ClaimLink claim={claim} />
                          <div className="text-[13px] text-ink-muted">{SOURCE[claim.source_format] ?? claim.source_format}</div>
                        </TableCell>
                        <TableCell className="min-w-36">
                          {claim.patient_name ?? "—"}
                          <div className="text-[13px] text-ink-muted tabular-nums">{claim.member_id}</div>
                        </TableCell>
                        <TableCell>
                          <span className="inline-flex flex-wrap items-center gap-1.5">
                            <OutcomeChip outcome={claim.outcome} />
                            {claim.appeal_open && <PlainBadge>Appeal open</PlainBadge>}
                          </span>
                        </TableCell>
                        <TableCell className="max-w-[18rem] min-w-44">
                          <ReasonCell reasons={claim.reasons} />
                        </TableCell>
                        <TableCell className="whitespace-nowrap tabular-nums">{dateOnly(claim.service_date)}</TableCell>
                        <TableCell className="text-right whitespace-nowrap tabular-nums">{money(claim.total_billed_cents)}</TableCell>
                        <TableCell className="text-right whitespace-nowrap tabular-nums">{planPays(claim)}</TableCell>
                        <TableCell className="text-[13px] whitespace-nowrap text-ink-muted">{dateTime(claim.updated)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}
