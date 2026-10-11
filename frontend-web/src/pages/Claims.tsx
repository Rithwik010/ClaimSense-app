import { Link } from "react-router";

import { useClaims } from "@/api/hooks";
import { StatusChip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateTime, money } from "@/lib/format";

const SOURCE: Record<string, string> = { JSON: "JSON", DIGITAL_PDF: "Digital PDF", SCANNED: "Scanned form" };

export function Claims() {
  const claims = useClaims();
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
        <div className="overflow-hidden rounded-lg border border-rules bg-paper">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Claim</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Source</TableHead>
                <TableHead className="text-right">Billed</TableHead>
                <TableHead className="text-right">Plan pays</TableHead>
                <TableHead>Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {claims.data.map((claim) => (
                <TableRow key={claim.claim_id}>
                  <TableCell>
                    <Link
                      className="font-semibold underline-offset-4 hover:underline"
                      to={`/claims/${encodeURIComponent(claim.claim_id)}`}
                    >
                      {claim.claim_id}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <StatusChip status={claim.status} />
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
  );
}
