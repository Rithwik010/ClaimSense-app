// My claims (a provider's home, D-AUTH-1): the claims filed under the provider's ID, newest first,
// "In review" until a reviewer finalizes them. Search by claim ID and filter by status; open a claim
// for its result.

import { Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { useMyClaims } from "@/api/hooks";
import { Chip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateTime, money } from "@/lib/format";
import { providerStatus } from "@/lib/labels";

const ALL = "all";

export function MyClaims() {
  const claims = useMyClaims();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState(ALL);
  const statuses = [...new Set((claims.data ?? []).map((c) => c.status))];
  const shown = (claims.data ?? []).filter(
    (c) =>
      c.claim_id.toLowerCase().includes(query.trim().toLowerCase()) && (status === ALL || c.status === status),
  );
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
          <div className="mb-4 flex flex-wrap items-end gap-3">
            <label className="grid min-w-0 flex-1 basis-56 gap-1.5 text-[13px] font-semibold" htmlFor="claim-search">
              Search by claim ID
              <span className="relative">
                <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted" />
                <Input
                  id="claim-search"
                  value={query}
                  placeholder="For example CLM-DEMO-01"
                  className="h-10 bg-paper pl-9 text-[15px] font-normal"
                  onChange={(event) => setQuery(event.target.value)}
                />
              </span>
            </label>
            <label className="grid basis-56 gap-1.5 text-[13px] font-semibold" htmlFor="status-filter">
              Status
              <Select value={status} onValueChange={setStatus}>
                <SelectTrigger id="status-filter" className="h-10 w-full bg-paper text-[15px] font-normal">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All statuses</SelectItem>
                  {statuses.map((s) => (
                    <SelectItem key={s} value={s}>
                      {providerStatus(s).label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
          </div>
          {shown.length === 0 ? (
            <EmptyState title="No claim matches">Clear the search or choose all statuses.</EmptyState>
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
                        <Chip label={providerStatus(claim.status)} />
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
