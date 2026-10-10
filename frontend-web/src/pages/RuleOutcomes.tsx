// Read-only: claims the rules decided on their own (REJECTED, DENIED_BY_RULE, PENDED_BY_RULE).
// They never reach the review queue (§8.8).

import { Link } from "react-router";

import { useClaims } from "../api/hooks";
import type { ClaimStatus } from "../api/types";
import { StatusChip } from "../components/Chip";
import { PageTitle } from "../components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "../components/States";
import { table, td, th } from "../components/ui";
import { reason } from "../lib/labels";

const RULE_STATUSES: ClaimStatus[] = ["REJECTED", "DENIED_BY_RULE", "PENDED_BY_RULE"];

export function RuleOutcomes() {
  const claims = useClaims(RULE_STATUSES);
  return (
    <>
      <PageTitle
        title="Rule outcomes"
        hint="Claims decided automatically by the rules. They are final and never reach review."
      />
      {claims.isPending ? (
        <Skeleton lines={5} />
      ) : claims.error ? (
        <ErrorNotice error={claims.error} onRetry={() => void claims.refetch()} />
      ) : claims.data.length === 0 ? (
        <EmptyState title="No rule outcomes">No claim has been rejected, denied or pended by a rule.</EmptyState>
      ) : (
        <div className="overflow-auto rounded-md border border-gray-200">
          <table className={table}>
            <thead>
              <tr>
                <th scope="col" className={th}>Claim</th>
                <th scope="col" className={th}>Outcome</th>
                <th scope="col" className={th}>Reasons</th>
              </tr>
            </thead>
            <tbody>
              {claims.data.map((claim) => (
                <tr key={claim.claim_id}>
                  <td className={td}>
                    <Link
                      className="font-medium text-accent hover:underline"
                      to={`/claims/${encodeURIComponent(claim.claim_id)}`}
                    >
                      {claim.claim_id}
                    </Link>
                  </td>
                  <td className={td}>
                    <StatusChip status={claim.status} showHint />
                  </td>
                  <td className={td}>
                    <ul className="space-y-1">
                      {claim.failed_rules.map((rule, i) => (
                        <li key={`${rule.rule_id}-${i}`}>
                          <span className="font-mono text-xs">{rule.rule_id}</span>
                          {rule.line_no ? ` · line ${rule.line_no}` : ""}: {reason(rule.reason_code)}
                          <div className="text-gray-600">{rule.detail}</div>
                        </li>
                      ))}
                    </ul>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
