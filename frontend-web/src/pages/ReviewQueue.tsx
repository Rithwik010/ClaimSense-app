// Review queue (a reviewer's home): the claims waiting for a person, by tier (quick, standard,
// full) with a count on each tab, oldest first within a tier, each with the model's recommendation
// and the member (fix 3) and its flags (an appeal among them, D-APL-1). Reviewers open a claim to
// review it, or "Start next claim" for the oldest one in the tier shown; an admin opens it
// read-only (D-AUTH-1). A search by claim ID, member ID, provider name or NPI, kept in the URL; no
// status filter, since every claim here is in review (D-UI-6). Cards on a phone (D-UI-12).

import { Play } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useQueue } from "@/api/hooks";
import type { QueueItem, ReviewTier } from "@/api/types";
import { ClaimFilters, NoMatch, useClaimFilters } from "@/components/ClaimFilters";
import { Chip, PlainBadge } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useUser } from "@/lib/auth";
import { matches } from "@/lib/filters";
import { age, money } from "@/lib/format";
import { CLAIM_DECISION, FLAGS, OUTCOME, TIER } from "@/lib/labels";

const TIERS: ReviewTier[] = ["QUICK", "STANDARD", "FULL"];

function shortDate(value: string | null): string {
  if (!value) return "—";
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year!, month! - 1, day!).toLocaleDateString("en-US", { dateStyle: "medium" });
}

/** The oldest claim waiting in a tier, the next one to review. */
export function oldestFirst(items: QueueItem[]): QueueItem[] {
  return [...items].sort((a, b) => (a.processed ?? "").localeCompare(b.processed ?? ""));
}

function Recommendation({ item }: { item: QueueItem }) {
  const label = item.claim_decision ? CLAIM_DECISION[item.claim_decision] : undefined;
  return label ? <Chip label={label} /> : <span className="text-ink-muted">No usable answer</span>;
}

function Flags({ item }: { item: QueueItem }) {
  return item.flags.length ? (
    <span className="flex flex-wrap gap-1.5">
      {item.flags.map((flag) => (
        <PlainBadge key={flag}>{FLAGS[flag] ?? flag}</PlainBadge>
      ))}
    </span>
  ) : (
    <span className="text-ink-muted">None</span>
  );
}

function ClaimLink({ item, reviewer }: { item: QueueItem; reviewer: boolean }) {
  return (
    <Link
      className="font-semibold whitespace-nowrap text-link underline-offset-4 transition-colors hover:text-primary-hover hover:underline"
      to={`/${reviewer ? "review" : "claims"}/${encodeURIComponent(item.claim_id)}`}
    >
      {item.claim_id}
    </Link>
  );
}

function Cards({ items, reviewer }: { items: QueueItem[]; reviewer: boolean }) {
  return (
    <ul aria-label="Claims waiting" className="grid gap-3 md:hidden">
      {items.map((item) => (
        <li key={item.claim_id} className="surface rounded-lg p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <ClaimLink item={item} reviewer={reviewer} />
            <Recommendation item={item} />
          </div>
          <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-[15px]">
            <div>
              <dt className="text-[13px] text-ink-muted">Member</dt>
              <dd className="tabular-nums">{item.member_id}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-ink-muted">Service date</dt>
              <dd>{shortDate(item.service_date)}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-ink-muted">Billed</dt>
              <dd className="tabular-nums">{money(item.total_billed_cents)}</dd>
            </div>
            <div>
              <dt className="text-[13px] text-ink-muted">Waiting</dt>
              <dd className="tabular-nums">{age(item.processed)}</dd>
            </div>
          </dl>
          <p className="mt-2 text-[13px] text-ink-muted">{item.provider_name ?? "Provider not in the reference data"}</p>
          <div className="mt-2">
            <Flags item={item} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function Rows({ items, reviewer }: { items: QueueItem[]; reviewer: boolean }) {
  return (
    <div className="surface hidden overflow-x-auto rounded-lg md:block">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Claim</TableHead>
            <TableHead>Recommendation</TableHead>
            <TableHead>Member</TableHead>
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
                <ClaimLink item={item} reviewer={reviewer} />
              </TableCell>
              <TableCell>
                <Recommendation item={item} />
              </TableCell>
              <TableCell className="whitespace-nowrap tabular-nums">{item.member_id}</TableCell>
              <TableCell className="min-w-44">
                {item.provider_name ?? "Not in the reference data"}
                <div className="text-[13px] text-ink-muted tabular-nums">NPI {item.provider_npi ?? "—"}</div>
              </TableCell>
              <TableCell className="whitespace-nowrap">{shortDate(item.service_date)}</TableCell>
              <TableCell className="text-right whitespace-nowrap tabular-nums">{money(item.total_billed_cents)}</TableCell>
              <TableCell className="text-right tabular-nums">{item.lines}</TableCell>
              <TableCell className="min-w-40">
                <Flags item={item} />
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
  const navigate = useNavigate();
  const queue = useQueue(null);
  const filters = useClaimFilters(null);
  const [chosen, setChosen] = useState<ReviewTier | null>(null);
  const items = (queue.data ?? []).filter((item) =>
    matches(item, filters.query, filters.status, "all"),
  );
  const count = (tier: ReviewTier) => items.filter((item) => item.review_tier === tier).length;
  // Most work first: open on the fullest tier that has claims, unless one was chosen.
  const tier = chosen ?? (["FULL", "STANDARD", "QUICK"] as ReviewTier[]).find((t) => count(t) > 0) ?? "QUICK";
  const shown = oldestFirst(items.filter((item) => item.review_tier === tier));
  const next = shown[0];
  return (
    <>
      <PageTitle
        title="Review queue"
        hint={
          role === "reviewer"
            ? "Every model recommendation waits here for a reviewer. Open a claim to review it."
            : "Every model recommendation waiting for a reviewer. Read only."
        }
        actions={
          role === "reviewer" && next ? (
            <Button size="lg" onClick={() => navigate(`/review/${encodeURIComponent(next.claim_id)}`)}>
              <Play aria-hidden /> Start next claim
            </Button>
          ) : undefined
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
                <>
                  <Cards items={shown} reviewer={role === "reviewer"} />
                  <Rows items={shown} reviewer={role === "reviewer"} />
                </>
              )}
            </TabsContent>
          </Tabs>
        </>
      )}
    </>
  );
}
