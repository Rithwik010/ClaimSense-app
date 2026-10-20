// My claims (a member's home, D-MEM-1): the claims in which the member is the patient, the latest
// changed first. A claim shows "Being processed" until it is final, and nothing else of its outcome;
// once final, its outcome and, when the plan calculated it, what the plan paid and what the member
// may owe, as the API sends them (the page computes nothing). Open a claim for its explanation of
// benefits.

import { Link } from "react-router";

import { useMemberClaims } from "@/api/hooks";
import { Chip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateOnly, money } from "@/lib/format";
import { memberOutcome } from "@/lib/labels";

export function MemberClaims() {
  const claims = useMemberClaims();
  return (
    <>
      <PageTitle
        title="My claims"
        hint="The claims your providers sent to your plan for your care. A claim shows its outcome once your plan has decided it; open it for the explanation of benefits."
      />
      {claims.isPending ? (
        <Skeleton lines={6} />
      ) : claims.error ? (
        <ErrorNotice error={claims.error} onRetry={() => void claims.refetch()} />
      ) : claims.data.length === 0 ? (
        <EmptyState title="No claims yet">Claims your providers send to your plan for your care show here.</EmptyState>
      ) : (
        <div className="overflow-x-auto surface rounded-lg">
          <Table aria-label="My claims">
            <TableHeader>
              <TableRow>
                <TableHead>Claim</TableHead>
                <TableHead>Date of service</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Plan paid</TableHead>
                <TableHead className="text-right">You may owe</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {claims.data.map((claim) => (
                <TableRow key={claim.claim_id}>
                  <TableCell>
                    <Link
                      className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-white hover:underline"
                      to={`/member/claims/${encodeURIComponent(claim.claim_id)}`}
                    >
                      {claim.claim_id}
                    </Link>
                  </TableCell>
                  <TableCell className="whitespace-nowrap tabular-nums">{dateOnly(claim.service_date)}</TableCell>
                  <TableCell className="min-w-40">{claim.provider_name ?? "—"}</TableCell>
                  <TableCell>
                    <Chip label={memberOutcome(claim.outcome)} />
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {claim.final ? money(claim.plan_pays_cents) : "—"}
                  </TableCell>
                  <TableCell className="text-right whitespace-nowrap tabular-nums">
                    {claim.final ? money(claim.patient_pays_cents) : "—"}
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
