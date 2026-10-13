// My claims (a provider's home, D-AUTH-1): the claims filed under the provider's ID, newest first,
// "In review" until a reviewer finalizes them. Search by claim ID and filter by status (the label set
// every dashboard uses, D-UI-6), both kept in the URL; open a claim for its result.

import { Link } from "react-router";

import { useMyClaims } from "@/api/hooks";
import { ClaimFilters, NoMatch, useClaimFilters } from "@/components/ClaimFilters";
import { OutcomeChip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { matches } from "@/lib/filters";
import { dateTime, money } from "@/lib/format";
import { PROVIDER_FILTERS, providerOutcome } from "@/lib/labels";

export function MyClaims() {
  const claims = useMyClaims();
  const filters = useClaimFilters(PROVIDER_FILTERS);
  const shown = (claims.data ?? []).filter((c) => matches(c, filters.query, filters.status, "claim"));
  return (
    <>
      <PageTitle
        title="My claims"
        hint="The claims you filed. A claim shows its decision once a reviewer has finalized it; a rule outcome is final at once."
        actions={
          <Button asChild size="lg">
            <Link to="/submit">Submit a claim</Link>
          </Button>
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
            searchLabel="Search by claim ID"
            placeholder="For example CLM-DEMO-01"
            options={PROVIDER_FILTERS}
            label={providerOutcome}
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
                    <TableHead className="text-right">Plan pays</TableHead>
                    <TableHead className="text-right">Updated</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {shown.map((claim) => (
                    <TableRow key={claim.claim_id}>
                      <TableCell>
                        <Link
                          className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-white hover:underline"
                          to={`/my-claims/${encodeURIComponent(claim.claim_id)}`}
                        >
                          {claim.claim_id}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <OutcomeChip outcome={claim.outcome} provider />
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">
                        {claim.final ? money(claim.plan_pays_cents) : "—"}
                      </TableCell>
                      <TableCell className="text-right text-[13px] whitespace-nowrap text-ink-muted">
                        {dateTime(claim.updated)}
                      </TableCell>
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
