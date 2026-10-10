import { Link } from "react-router";

import { useClaims } from "../api/hooks";
import { StatusChip } from "../components/Chip";
import { PageTitle } from "../components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "../components/States";
import { table, td, th } from "../components/ui";
import { dateTime, money } from "../lib/format";

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
        <EmptyState title="No claims yet">
          <Link className="text-accent underline" to="/submit">Submit a claim</Link> to begin.
        </EmptyState>
      ) : (
        <div className="overflow-auto rounded-md border border-gray-200">
          <table className={table}>
            <thead>
              <tr>
                <th scope="col" className={th}>Claim</th>
                <th scope="col" className={th}>Status</th>
                <th scope="col" className={th}>Source</th>
                <th scope="col" className={`${th} text-right`}>Billed</th>
                <th scope="col" className={`${th} text-right`}>Plan pays</th>
                <th scope="col" className={th}>Updated</th>
              </tr>
            </thead>
            <tbody>
              {claims.data.map((claim) => (
                <tr key={claim.claim_id} className="hover:bg-gray-50">
                  <td className={td}>
                    <Link
                      className="font-medium text-accent hover:underline"
                      to={`/claims/${encodeURIComponent(claim.claim_id)}`}
                    >
                      {claim.claim_id}
                    </Link>
                  </td>
                  <td className={td}>
                    <StatusChip status={claim.status} />
                  </td>
                  <td className={td}>{claim.source_format.replace("_", " ").toLowerCase()}</td>
                  <td className={`${td} text-right tabular-nums`}>{money(claim.total_billed_cents)}</td>
                  <td className={`${td} text-right tabular-nums`}>{money(claim.plan_pays_cents)}</td>
                  <td className={td}>{dateTime(claim.updated)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
