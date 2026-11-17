// My claims (a provider's home, D-AUTH-1): the claims filed under the provider's ID with the patient,
// the first date of service and the amount billed as filed (D-UI-12). "Not processed" until the
// provider processes a claim, "In review" until a reviewer finalizes it (fix 1). Search by claim ID
// or patient and filter by status (the label set every dashboard uses, D-UI-6), sort by a column,
// all kept in the URL; download the rows shown as CSV. Cards on a phone, a table from 768 px.

import { Link } from "react-router";

import { useMyClaims } from "@/api/hooks";
import type { ProviderClaimSummary } from "@/api/types";
import { ClaimFilters, NoMatch, useClaimFilters } from "@/components/ClaimFilters";
import { OutcomeChip, PlainBadge } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { CsvButton, csvMoney, SortHead, useSort } from "@/components/ListTools";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { matches } from "@/lib/filters";
import { dateOnly, dateTime, money } from "@/lib/format";
import { PROVIDER_FILTERS, providerListOutcome, providerOutcome } from "@/lib/labels";

const SORTS = ["claim", "patient", "service", "billed", "updated"] as const;
type SortKey = (typeof SORTS)[number];

function sortValue(claim: ProviderClaimSummary, key: SortKey) {
  switch (key) {
    case "claim":
      return claim.claim_id;
    case "patient":
      return claim.patient_name ?? null;
    case "service":
      return claim.service_date ?? null;
    case "billed":
      return claim.billed_cents ?? null;
    default:
      return claim.updated;
  }
}

/** What the plan pays, once final; a claim on hold has paid nothing yet, so it says so (fix 7). */
function planPays(claim: ProviderClaimSummary): string {
  if (!claim.final) return "—";
  if (claim.outcome === "PENDED") return "On hold";
  return money(claim.plan_pays_cents);
}

const CSV_COLUMNS = [
  { header: "Claim ID", value: (c: ProviderClaimSummary) => c.claim_id },
  { header: "Patient", value: (c: ProviderClaimSummary) => c.patient_name ?? "" },
  { header: "Date of service", value: (c: ProviderClaimSummary) => c.service_date ?? "" },
  { header: "Billed", value: (c: ProviderClaimSummary) => csvMoney(c.billed_cents) },
  { header: "Status", value: (c: ProviderClaimSummary) => providerOutcome(c.outcome, c.status).label },
  { header: "Plan pays", value: (c: ProviderClaimSummary) => (c.final && c.outcome !== "PENDED" ? csvMoney(c.plan_pays_cents) : "") },
  { header: "Updated", value: (c: ProviderClaimSummary) => c.updated },
];

function ClaimLink({ claim }: { claim: ProviderClaimSummary }) {
  return (
    <Link
      className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-primary-hover hover:underline"
      to={`/my-claims/${encodeURIComponent(claim.claim_id)}`}
    >
      {claim.claim_id}
    </Link>
  );
}

export function MyClaims() {
  const claims = useMyClaims();
  const filters = useClaimFilters(PROVIDER_FILTERS);
  const sort = useSort(SORTS, "updated");
  const listed = (claims.data ?? []).map((c) => ({ ...c, outcome: providerListOutcome(c) }));
  const wanted = filters.query.trim().toLowerCase();
  const found = listed.filter(
    (c) =>
      (!wanted || c.claim_id.toLowerCase().includes(wanted) || (c.patient_name ?? "").toLowerCase().includes(wanted)) &&
      matches(c, "", filters.status, "claim"),
  );
  const shown = sort.apply(found, sortValue);
  return (
    <>
      <PageTitle
        title="My claims"
        hint="The claims you filed. A claim shows its decision once a reviewer has finalized it; a rule outcome is final at once."
        actions={
          <>
            <CsvButton rows={shown} columns={CSV_COLUMNS} fileName="my-claims.csv" />
            <Button asChild size="lg">
              <Link to="/submit">Submit a claim</Link>
            </Button>
          </>
        }
      />
      {claims.isPending ? (
        <Skeleton lines={6} />
      ) : claims.error ? (
        <ErrorNotice error={claims.error} onRetry={() => void claims.refetch()} />
      ) : claims.data.length === 0 ? (
        <EmptyState title="No claims filed yet">Submit a claim and it appears here.</EmptyState>
      ) : (
        <>
          <ClaimFilters
            filters={filters}
            searchLabel="Search by claim ID or patient"
            placeholder="For example CLM-DEMO-01"
            options={PROVIDER_FILTERS}
            label={(outcome) => providerOutcome(outcome)}
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
                      <OutcomeChip outcome={claim.outcome} provider status={claim.status} />
                    </div>
                    <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[15px]">
                      <div>
                        <dt className="text-[13px] text-ink-muted">Patient</dt>
                        <dd>{claim.patient_name ?? "—"}</dd>
                      </div>
                      <div>
                        <dt className="text-[13px] text-ink-muted">Date of service</dt>
                        <dd>{dateOnly(claim.service_date)}</dd>
                      </div>
                      <div>
                        <dt className="text-[13px] text-ink-muted">Billed</dt>
                        <dd className="tabular-nums">{money(claim.billed_cents)}</dd>
                      </div>
                      <div>
                        <dt className="text-[13px] text-ink-muted">Plan pays</dt>
                        <dd className="tabular-nums">{planPays(claim)}</dd>
                      </div>
                    </dl>
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
                      <SortHead sort={sort} column="service">
                        Date of service
                      </SortHead>
                      <SortHead sort={sort} column="billed" className="text-right">
                        Billed
                      </SortHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Plan pays</TableHead>
                      <SortHead sort={sort} column="updated" className="text-right">
                        Updated
                      </SortHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {shown.map((claim) => (
                      <TableRow key={claim.claim_id}>
                        <TableCell>
                          <ClaimLink claim={claim} />
                        </TableCell>
                        <TableCell className="max-w-[16rem] truncate">{claim.patient_name ?? "—"}</TableCell>
                        <TableCell className="whitespace-nowrap tabular-nums">{dateOnly(claim.service_date)}</TableCell>
                        <TableCell className="text-right whitespace-nowrap tabular-nums">{money(claim.billed_cents)}</TableCell>
                        <TableCell>
                          <span className="inline-flex flex-wrap items-center gap-1.5">
                            <OutcomeChip outcome={claim.outcome} provider status={claim.status} />
                            {claim.appeal_open && <PlainBadge>Appeal open</PlainBadge>}
                          </span>
                        </TableCell>
                        <TableCell className="text-right whitespace-nowrap tabular-nums">{planPays(claim)}</TableCell>
                        <TableCell className="text-right text-[13px] whitespace-nowrap text-ink-muted">
                          {dateTime(claim.updated)}
                        </TableCell>
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
