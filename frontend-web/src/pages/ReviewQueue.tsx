// Review queue (a reviewer's home): the claims waiting for a person, by tier (quick, standard,
// full) with a count on each tab, oldest first within a tier. Reviewers open a claim to review it;
// an admin opens it read-only (D-AUTH-1). A search by claim ID, member ID, provider name or NPI,
// kept in the URL; no status filter, since every claim here is in review (D-UI-6).

import { useState } from "react";
import { Link } from "react-router";

import { useQueue } from "@/api/hooks";
import type { QueueItem, ReviewTier } from "@/api/types";
import { ClaimFilters, NoMatch, useClaimFilters } from "@/components/ClaimFilters";
import { PlainBadge } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useUser } from "@/lib/auth";
import { matches } from "@/lib/filters";
import { age, money } from "@/lib/format";
import { FLAGS, OUTCOME, TIER } from "@/lib/labels";

const TIERS: ReviewTier[] = ["QUICK", "STANDARD", "FULL"];

function shortDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year!, month! - 1, day!).toLocaleDateString("en-US", { dateStyle: "medium" });
}

function Rows({ items, reviewer }: { items: QueueItem[]; reviewer: boolean }) {
  return (
    <div className="overflow-x-auto surface rounded-lg">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Claim</TableHead>
            <TableHead>Provider</TableHead>
            <TableHead>Service date</TableHead>
            <TableHead className="text-right">Billed</TableHead>
            <TableHead className="text-right">Lines</TableHead>
            <TableHead>Flags</TableHead>
            <TableHead className="text-right">Waiting</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.claim_id}>
              <TableCell>
                <Link
                  className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-primary-hover hover:underline"
                  to={`/${reviewer ? "review" : "claims"}/${encodeURIComponent(item.claim_id)}`}
                >
                  {item.claim_id}
                </Link>
              </TableCell>
              <TableCell className="min-w-44">
                {item.provider_name ?? "Not in the reference data"}
                <div className="text-[13px] text-ink-muted tabular-nums">NPI {item.provider_npi ?? "—"}</div>
              </TableCell>
              <TableCell className="whitespace-nowrap">{shortDate(item.service_date)}</TableCell>
              <TableCell className="text-right whitespace-nowrap tabular-nums">{money(item.total_billed_cents)}</TableCell>
              <TableCell className="text-right tabular-nums">{item.lines}</TableCell>
              <TableCell className="min-w-40">
                {item.flags.length ? (
                  <span className="flex flex-wrap gap-1.5">
                    {item.flags.map((flag) => (
                      <PlainBadge key={flag}>{FLAGS[flag] ?? flag}</PlainBadge>
                    ))}
                  </span>
                ) : (
                  <span className="text-ink-muted">None</span>
                )}
              </TableCell>
              <TableCell className="text-right whitespace-nowrap text-ink-muted tabular-nums">{age(item.processed)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

export function ReviewQueue() {
  const { role } = useUser();
  const queue = useQueue(null);
  const filters = useClaimFilters(null);
  const [chosen, setChosen] = useState<ReviewTier | null>(null);
  const items = (queue.data ?? []).filter((item) =>
    matches(item, filters.query, filters.status, "all"),
  );
  const count = (tier: ReviewTier) => items.filter((item) => item.review_tier === tier).length;
  // Most work first: open on the fullest tier that has claims, unless one was chosen.
  const tier = chosen ?? (["FULL", "STANDARD", "QUICK"] as ReviewTier[]).find((t) => count(t) > 0) ?? "QUICK";
  const shown = items
    .filter((item) => item.review_tier === tier)
    .sort((a, b) => (a.processed ?? "").localeCompare(b.processed ?? ""));
  return (
    <>
      <PageTitle
        title="Review queue"
        hint={
          role === "reviewer"
            ? "Every model recommendation waits here for a reviewer. Open a claim to review it."
            : "Every model recommendation waiting for a reviewer. Read only."
        }
      />
      {queue.isPending ? (
        <Skeleton lines={5} />
      ) : queue.error ? (
        <ErrorNotice error={queue.error} onRetry={() => void queue.refetch()} />
      ) : (queue.data ?? []).length === 0 ? (
        <EmptyState title="Nothing to review">
          A claim appears here once a provider files and processes it and the model recommends a decision.
        </EmptyState>
      ) : (
        <>
          <ClaimFilters
            filters={filters}
            searchLabel="Search the queue"
            placeholder="Claim ID, member ID, provider name or NPI"
            options={null}
            label={(outcome) => OUTCOME[outcome]}
            shown={shown.length}
          />
          <Tabs value={tier} onValueChange={(value) => setChosen(value as ReviewTier)}>
            <div className="overflow-x-auto">
              <TabsList variant="line" aria-label="Review tier" className="mb-4 h-10 gap-6 border-b border-rules px-0">
                {TIERS.map((t) => (
                  <TabsTrigger
                    key={t}
                    value={t}
                    className="flex-none px-0 text-[15px] text-ink-muted data-active:font-semibold data-active:text-ink"
                  >
                    {TIER[t].label} <span className="tabular-nums">({count(t)})</span>
                  </TabsTrigger>
                ))}
              </TabsList>
            </div>
            <TabsContent value={tier}>
              <p className="mb-3 text-[13px] text-ink-muted">{TIER[tier].hint}.</p>
              {shown.length === 0 && filters.active ? (
                <NoMatch onClear={filters.clear} />
              ) : shown.length === 0 ? (
                <EmptyState title={`No ${TIER[tier].label.toLowerCase()} reviews waiting`}>
                  Choose another tier above.
                </EmptyState>
              ) : (
                <Rows items={shown} reviewer={role === "reviewer"} />
              )}
            </TabsContent>
          </Tabs>
        </>
      )}
    </>
  );
}
