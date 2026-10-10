// Read-only: claims the rules decided on their own (REJECTED, DENIED_BY_RULE, PENDED_BY_RULE).
// They never reach the review queue (§8.8).

import { Link } from "react-router";

import { useClaims } from "@/api/hooks";
import type { ClaimStatus } from "@/api/types";
import { StatusChip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { reason } from "@/lib/labels";

const RULE_STATUSES: ClaimStatus[] = ["REJECTED", "DENIED_BY_RULE", "PENDED_BY_RULE"];

export function RuleOutcomes() {
  const claims = useClaims(RULE_STATUSES);
  return (
    <>
      <PageTitle
        title="Rule outcomes"
        hint="Claims the rules decided automatically. These outcomes are final and never reach review."
      />
      {claims.isPending ? (
        <Skeleton lines={5} />
      ) : claims.error ? (
        <ErrorNotice error={claims.error} onRetry={() => void claims.refetch()} />
      ) : claims.data.length === 0 ? (
        <EmptyState title="No rule outcomes yet">
          A claim that fails a rule (for example a missing field or a lapsed member) appears here after
          processing.
        </EmptyState>
      ) : (
        <div className="overflow-hidden rounded-lg border border-rules bg-paper">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Claim</TableHead>
                <TableHead>Outcome</TableHead>
                <TableHead>Why</TableHead>
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
                  <TableCell className="min-w-72">
                    <ul className="space-y-2">
                      {claim.failed_rules.map((rule, i) => (
                        <li key={`${rule.rule_id}-${i}`}>
                          <span className="font-semibold">
                            Rule {rule.rule_id}
                            {rule.line_no ? `, line ${rule.line_no}` : ""}
                          </span>
                          : {reason(rule.reason_code)}
                          <div className="text-[13px] text-ink-muted">{rule.detail}</div>
                        </li>
                      ))}
                    </ul>
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
