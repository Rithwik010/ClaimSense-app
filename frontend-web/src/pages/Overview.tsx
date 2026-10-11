// Overview (an admin's home, D-AUTH-1): counts over the claims on file in this demo database (GET
// /v1/metrics/overview). Labelled as demo data: they describe what was filed here, not results.

import type { ReactNode } from "react";
import { Link } from "react-router";

import { useOverview } from "@/api/hooks";
import type { ClaimStatus, ReviewTier } from "@/api/types";
import { PlainBadge, StatusChip } from "@/components/Chip";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { STATUS, TIER } from "@/lib/labels";

function Tile({ title, children, link }: { title: string; children: ReactNode; link?: { to: string; label: string } }) {
  return (
    <section aria-label={title} className="flex flex-col rounded-lg border border-rules bg-paper">
      <h2 className="border-b border-rules px-4 py-3 font-semibold">{title}</h2>
      <div className="flex-1 px-4 py-3">{children}</div>
      {link && (
        <Link className="border-t border-rules px-4 py-2.5 text-[13px] font-semibold underline-offset-4 hover:underline" to={link.to}>
          {link.label}
        </Link>
      )}
    </section>
  );
}

function Count({ label, value }: { label: ReactNode; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <dt className="min-w-0">{label}</dt>
      <dd className="text-[18px] font-semibold tabular-nums">{value}</dd>
    </div>
  );
}

const FINAL_ORDER: ClaimStatus[] = [
  "FINAL_APPROVED",
  "FINAL_PARTIAL",
  "FINAL_PENDED",
  "FINAL_DENIED",
  "REJECTED",
  "DENIED_BY_RULE",
  "PENDED_BY_RULE",
];

export function Overview() {
  const overview = useOverview();
  return (
    <>
      <PageTitle
        title="Overview"
        hint="Counts over the claims filed in this demo. You can read everything; filing and reviewing are for providers and reviewers."
        actions={<PlainBadge>Demo data</PlainBadge>}
      />
      {overview.isPending ? (
        <Skeleton lines={6} />
      ) : overview.error ? (
        <ErrorNotice error={overview.error} onRetry={() => void overview.refetch()} />
      ) : overview.data.claims === 0 ? (
        <EmptyState title="No claims on file yet">The counts appear once providers file claims.</EmptyState>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Tile title="Claims by final outcome" link={{ to: "/claims", label: "Open claims" }}>
            <dl>
              {FINAL_ORDER.filter((s) => overview.data.final_outcomes[s]).map((s) => (
                <Count key={s} label={<StatusChip status={s} />} value={overview.data.final_outcomes[s] ?? 0} />
              ))}
              {Object.keys(overview.data.final_outcomes).length === 0 && <p className="text-ink-muted">None final yet.</p>}
            </dl>
          </Tile>
          <Tile title="Review queue by tier" link={{ to: "/queue", label: "Open the review queue" }}>
            <dl>
              {(["QUICK", "STANDARD", "FULL"] as ReviewTier[]).map((tier) => (
                <Count key={tier} label={TIER[tier].label} value={overview.data.queue_by_tier[tier] ?? 0} />
              ))}
            </dl>
          </Tile>
          <Tile title="Decided by the rules alone" link={{ to: "/rule-outcomes", label: "Open rule outcomes" }}>
            <dl>
              <Count label="Claims" value={overview.data.decided_by_rules} />
              <Count label="Of all claims on file" value={overview.data.claims} />
            </dl>
            <p className="mt-2 text-[13px] text-ink-muted">
              {STATUS.REJECTED.label}, {STATUS.DENIED_BY_RULE.label.toLowerCase()} or{" "}
              {STATUS.PENDED_BY_RULE.label.toLowerCase()}: final without a model or a reviewer.
            </p>
          </Tile>
          <Tile title="Reviewed claims">
            <dl>
              <Count label="Recommendation accepted" value={overview.data.reviewed_accepted} />
              <Count label="Lines overridden" value={overview.data.reviewed_overridden} />
            </dl>
          </Tile>
        </div>
      )}
    </>
  );
}
