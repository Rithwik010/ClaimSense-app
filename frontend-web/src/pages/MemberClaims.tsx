// My claims (a member's home, D-MEM-1): the claims in which the member is the patient, the latest
// changed first. A claim shows "Being processed" until it is final, and nothing else of its outcome;
// once final, its outcome and, when the plan calculated it, what the plan paid and what the member
// may owe, as the API sends them (the page computes nothing). Open a claim for its explanation of
// benefits. On a phone each claim is a card (as on the EOB page), so its status shows at once.

import { Link } from "react-router";

import { useMemberClaims } from "@/api/hooks";
import type { MemberClaim } from "@/api/types";
import { Chip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateOnly, money } from "@/lib/format";
import { memberOutcome } from "@/lib/labels";

function ClaimLink({ claim }: { claim: MemberClaim }) {
  return (
    <Link
      className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-white hover:underline"
      to={`/member/claims/${encodeURIComponent(claim.claim_id)}`}
    >
      {claim.claim_id}
    </Link>
  );
}

/** Below 768 px: each claim as a card. */
function Cards({ claims }: { claims: MemberClaim[] }) {
  return (
    <ul aria-label="My claims" className="space-y-3 md:hidden">
      {claims.map((claim) => (
        <li key={claim.claim_id} className="surface rounded-lg p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <ClaimLink claim={claim} />
            <Chip label={memberOutcome(claim.outcome)} />
          </div>
          <p className="mt-1 text-[13px] text-ink-muted">
            Date of service {dateOnly(claim.service_date)}
            {claim.provider_name ? ` · ${claim.provider_name}` : ""}
          </p>
          {claim.final && claim.plan_pays_cents !== null && (
            <dl className="mt-3 grid grid-cols-2 gap-x-4 border-t border-rules pt-3 text-[14px]">
              <div>
                <dt className="text-ink-muted">Plan paid</dt>
                <dd className="font-semibold tabular-nums">{money(claim.plan_pays_cents)}</dd>
              </div>
              <div>
                <dt className="text-ink-muted">You may owe</dt>
                <dd className="font-semibold tabular-nums">{money(claim.patient_pays_cents)}</dd>
              </div>
            </dl>
          )}
        </li>
      ))}
    </ul>
  );
}

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
        <>
          <Cards claims={claims.data} />
          <div className="hidden overflow-x-auto surface rounded-lg md:block">
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
                      <ClaimLink claim={claim} />
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
        </>
      )}
    </>
  );
}
