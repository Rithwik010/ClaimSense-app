// Review queue: every claim with a model recommendation, most work first (full, standard, quick;
// then the oldest), with a tier filter and decision badges. Reviewers open a claim to review it;
// an admin reads it (D-AUTH-1).

import { useState } from "react";
import { Link } from "react-router";

import { useQueue } from "@/api/hooks";
import type { ReviewTier } from "@/api/types";
import { Chip, PlainBadge } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { age, money } from "@/lib/format";
import { CLAIM_DECISION, TIER } from "@/lib/labels";
import { useUser } from "@/lib/auth";

const FILTERS: { value: string; label: string }[] = [
  { value: "all", label: "All tiers" },
  { value: "FULL", label: "Full" },
  { value: "STANDARD", label: "Standard" },
  { value: "QUICK", label: "Quick" },
];

export function ReviewQueue() {
  const { role } = useUser();
  const [tier, setTier] = useState<ReviewTier | null>(null);
  const queue = useQueue(tier);
  return (
    <>
      <PageTitle
        title="Review queue"
        hint="Every model recommendation waits here for a reviewer, most work first: full, standard, then quick review."
      />
      <>
          <Tabs value={tier ?? "all"} onValueChange={(value) => setTier(value === "all" ? null : (value as ReviewTier))}>
            <div className="overflow-x-auto">
              <TabsList variant="line" aria-label="Filter by tier" className="mb-4 h-10 gap-4 border-b border-rules px-0">
                {FILTERS.map((f) => (
                  <TabsTrigger
                    key={f.value}
                    value={f.value}
                    className="flex-none px-0 text-[15px] text-ink-muted data-active:font-semibold data-active:text-ink"
                  >
                    {f.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>
          </Tabs>
          {queue.isPending ? (
            <Skeleton lines={5} />
          ) : queue.error ? (
            <ErrorNotice error={queue.error} onRetry={() => void queue.refetch()} />
          ) : queue.data.length === 0 ? (
            <EmptyState title="Nothing to review">
              A claim appears here once a provider files and processes it and the model recommends a decision.
            </EmptyState>
          ) : (
            <div className="overflow-hidden rounded-lg border border-rules bg-paper">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Claim</TableHead>
                    <TableHead>Tier</TableHead>
                    <TableHead>Recommendation</TableHead>
                    <TableHead className="text-right">Total allowed</TableHead>
                    <TableHead className="text-right">Waiting</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {queue.data.map((item) => (
                    <TableRow key={item.claim_id}>
                      <TableCell>
                        <Link
                          className="font-semibold underline-offset-4 hover:underline"
                          to={`/${role === "reviewer" ? "review" : "claims"}/${encodeURIComponent(item.claim_id)}`}
                        >
                          {item.claim_id}
                        </Link>
                      </TableCell>
                      <TableCell>
                        <PlainBadge>{TIER[item.review_tier].label}</PlainBadge>
                      </TableCell>
                      <TableCell>
                        {item.claim_decision && CLAIM_DECISION[item.claim_decision] ? (
                          <Chip label={CLAIM_DECISION[item.claim_decision]!} />
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">{money(item.total_allowed_cents)}</TableCell>
                      <TableCell className="text-right whitespace-nowrap tabular-nums">{age(item.processed)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
      </>
    </>
  );
}
