import { useState } from "react";
import { Link } from "react-router";

import { useQueue } from "../api/hooks";
import type { ReviewTier } from "../api/types";
import { Chip } from "../components/Chip";
import { PageTitle } from "../components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "../components/States";
import { table, td, th } from "../components/ui";
import { age, money } from "../lib/format";
import { TIER } from "../lib/labels";
import { useSession } from "../lib/session";

const TIERS: (ReviewTier | null)[] = [null, "FULL", "STANDARD", "QUICK"];

export function ReviewQueue() {
  const { role } = useSession();
  const [tier, setTier] = useState<ReviewTier | null>(null);
  const queue = useQueue(tier);
  return (
    <>
      <PageTitle
        title="Review queue"
        hint="Every model recommendation waits here for a reviewer. Most work first: full, standard, then quick."
      />
      {role === "provider" ? (
        <EmptyState title="The review queue is for reviewers">
          Switch the role in the top bar to Reviewer or Admin.
        </EmptyState>
      ) : (
        <>
          <div role="group" aria-label="Filter by tier" className="mb-5 flex flex-wrap gap-2">
            {TIERS.map((value) => (
              <button
                key={value ?? "all"}
                type="button"
                aria-pressed={tier === value}
                onClick={() => setTier(value)}
                className={`rounded-full border px-3 py-1 text-sm transition-colors duration-150 ${
                  tier === value
                    ? "border-accent bg-accent-soft font-medium text-accent-strong"
                    : "border-gray-300 text-gray-700 hover:bg-gray-50"
                }`}
              >
                {value ? TIER[value].label : "All tiers"}
              </button>
            ))}
          </div>
          {queue.isPending ? (
            <Skeleton lines={5} />
          ) : queue.error ? (
            <ErrorNotice error={queue.error} onRetry={() => void queue.refetch()} />
          ) : queue.data.length === 0 ? (
            <EmptyState title="Nothing to review">
              Processed claims with a model recommendation appear here.
            </EmptyState>
          ) : (
            <div className="overflow-auto rounded-md border border-gray-200">
              <table className={table}>
                <thead>
                  <tr>
                    <th scope="col" className={th}>Claim</th>
                    <th scope="col" className={th}>Tier</th>
                    <th scope="col" className={th}>Recommended decision</th>
                    <th scope="col" className={`${th} text-right`}>Total allowed</th>
                    <th scope="col" className={th}>Waiting</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.data.map((item) => (
                    <tr key={item.claim_id} className="hover:bg-gray-50">
                      <td className={td}>
                        <Link
                          className="font-medium text-accent hover:underline"
                          to={`/review/${encodeURIComponent(item.claim_id)}`}
                        >
                          {item.claim_id}
                        </Link>
                      </td>
                      <td className={td}>
                        <Chip label={TIER[item.review_tier]} />
                      </td>
                      <td className={td}>{(item.claim_decision ?? "—").toLowerCase()}</td>
                      <td className={`${td} text-right tabular-nums`}>{money(item.total_allowed_cents)}</td>
                      <td className={td}>{age(item.processed)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </>
  );
}
