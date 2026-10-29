// Claims (reviewers and admins; read-only for admins): every claim on file, most recently changed
// first. Search by claim ID, member ID, provider name or NPI and filter by status (D-UI-6), both kept
// in the URL; the Reason column gives one line of plain words for a claim not paid as billed.

import { Link } from "react-router";

import { useClaims } from "@/api/hooks";
import { ClaimFilters, NoMatch, useClaimFilters } from "@/components/ClaimFilters";
import { OutcomeChip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { ReasonCell } from "@/components/ReasonCell";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { matches } from "@/lib/filters";
import { dateTime, money } from "@/lib/format";
import { OUTCOME, STAFF_FILTERS } from "@/lib/labels";

const SOURCE: Record<string, string> = { JSON: "JSON", DIGITAL_PDF: "Digital PDF", SCANNED: "Scanned form" };

export function Claims() {
  const claims = useClaims();
  const filters = useClaimFilters(STAFF_FILTERS);
  const shown = (claims.data ?? []).filter((c) => matches(c, filters.query, filters.status, "all"));
  return (
    <>
      <PageTitle title="Claims" hint="Every claim on file, most recently changed first." />
      {claims.isPending ? (
        <Skeleton lines={6} />
      ) : claims.error ? (
        <ErrorNotice error={claims.error} onRetry={() => void claims.refetch()} />
      ) : claims.data.length === 0 ? (
        <EmptyState title="No claims yet">Claims appear here once a provider files them.</EmptyState>
      ) : (
        <>
          <ClaimFilters
            filters={filters}
            searchLabel="Search claims"
            placeholder="Claim ID, member ID, provider name or NPI"
            options={STAFF_FILTERS}
            label={(outcome) => OUTCOME[outcome]}
            shown={shown.length}
          />
          {shown.length === 0 ? (
            <NoMatch onClear={filters.clear} />
          ) : (
            <div className="overflow-x-auto surface rounded-lg">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Claim</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Reason</TableHead>
                    <TableHead>Source</TableHead>
                    <TableHead className="text-right">Billed</TableHead>
                    <TableHead className="text-right">Plan pays</TableHead>
                    <TableHead>Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {shown.map((claim) => (
                    <TableRow key={claim.claim_id}>
                      <TableCell>
                        <Link
                          className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-primary-hover hover:underline"
                          to={`/claims/${encodeURIComponent(claim.claim_id)}`}
                        >
                          {claim.claim_id}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <OutcomeChip outcome={claim.outcome} />
                      </TableCell>
                      <TableCell className="max-w-[18rem] min-w-44">
                        <ReasonCell reasons={claim.reasons} />
                      </TableCell>
                      <TableCell className="whitespace-nowrap">{SOURCE[claim.source_format] ?? claim.source_format}</TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">{money(claim.total_billed_cents)}</TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">{money(claim.plan_pays_cents)}</TableCell>
                      <TableCell className="whitespace-nowrap">{dateTime(claim.updated)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </>
      )}
    </>
  );
}
