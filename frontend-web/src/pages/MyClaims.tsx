// My claims (a provider's home, D-AUTH-1): the claims filed under the provider's ID. A claim still
// being reviewed shows "In review" with no recommendation; a final one shows its decision, the
// plan's payment and the reasons of any rule that decided it. A simple list; the UI pass builds
// the full page.

import { Link } from "react-router";

import { useMyClaims } from "@/api/hooks";
import { Chip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateTime, money } from "@/lib/format";
import { REASONS, providerStatus } from "@/lib/labels";

export function MyClaims() {
  const claims = useMyClaims();
  return (
    <>
      <PageTitle
        title="My claims"
        hint="The claims you filed. A claim in review shows its decision once a reviewer has finalized it."
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
        <EmptyState title="No claims filed yet">Submit a claim to see it here.</EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-rules bg-paper">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Claim</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Plan pays</TableHead>
                <TableHead>Reasons</TableHead>
                <TableHead className="text-right">Updated</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {claims.data.map((claim) => (
                <TableRow key={claim.claim_id}>
                  <TableCell className="font-semibold">{claim.claim_id}</TableCell>
                  <TableCell>
                    <Chip label={providerStatus(claim.status)} />
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {claim.final ? money(claim.plan_pays_cents) : "—"}
                  </TableCell>
                  <TableCell className="max-w-[40ch] text-[13px]">
                    {claim.failed_rules.length
                      ? claim.failed_rules
                          .map((rule) => (rule.reason_code ? (REASONS[rule.reason_code] ?? rule.reason_code) : rule.rule_id))
                          .join("; ")
                      : "—"}
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
  );
}
