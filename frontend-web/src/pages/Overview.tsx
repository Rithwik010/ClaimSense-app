// Overview (an admin's home, D-AUTH-1): counts over the claims on file in this demo database (GET
// /v1/metrics/overview). Labelled as demo data: they describe what was filed here, not results.

import { ArrowRight, ClipboardCheck, Files, Scale, UserCheck } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { useOverview } from "@/api/hooks";
import type { ClaimStatus, ReviewTier } from "@/api/types";
import { PlainBadge, StatusChip } from "@/components/Chip";
import { BlurFade, NumberTicker, Spotlight } from "@/components/fx";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { STATUS, TIER } from "@/lib/labels";

function Tile({ title, children, link }: { title: string; children: ReactNode; link?: { to: string; label: string } }) {
  return (
    <Spotlight className="flex flex-col" aria-label={title} role="region">
      <h2 className="border-b border-rules px-5 py-3.5 font-semibold">{title}</h2>
      <div className="flex-1 px-5 py-3">{children}</div>
      {link && (
        <Link
          className="group/link flex items-center gap-1.5 border-t border-rules px-5 py-3 text-[13px] font-semibold text-link transition-colors hover:text-primary-hover"
          to={link.to}
        >
          {link.label}
          <ArrowRight aria-hidden className="size-3.5 transition-transform group-hover/link:translate-x-0.5" />
        </Link>
      )}
    </Spotlight>
  );
}

function Count({ label, value }: { label: ReactNode; value: number }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <dt className="min-w-0">{label}</dt>
      <dd className="text-[18px] font-semibold">
        <NumberTicker value={value} />
      </dd>
    </div>
  );
}

/** A headline count: what an admin wants to see first. */
function Kpi({ label, value, hint, icon: Icon }: { label: string; value: number; hint: string; icon: typeof Files }) {
  return (
    <Spotlight className="px-5 py-4">
      <p className="flex items-center gap-2 text-[14px] text-ink-muted">
        <span className="grid size-7 place-items-center rounded-md border border-rules bg-brand-tint text-ink-strong">
          <Icon aria-hidden className="size-4 text-link" />
        </span>
        {label}
      </p>
      <p className="mt-3 font-heading text-[34px] leading-10 font-bold text-ink-strong">
        <NumberTicker value={value} />
      </p>
      <p className="mt-1 text-[13px] text-ink-muted">{hint}</p>
    </Spotlight>
  );
}

/** Final outcomes as short bars (counts, so they may grow in once). */
function OutcomeBars({ outcomes }: { outcomes: Record<string, number> }) {
  const reduce = useReducedMotion();
  const rows = FINAL_ORDER.filter((s) => outcomes[s]);
  const max = Math.max(1, ...rows.map((s) => outcomes[s] ?? 0));
  if (rows.length === 0) return <p className="text-ink-muted">None final yet.</p>;
  return (
    <dl className="space-y-3 py-1">
      {rows.map((s, i) => (
        <div key={s} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5">
          <dt className="min-w-0">
            <StatusChip status={s} showHint />
          </dt>
          <dd className="text-[18px] font-semibold">
            <NumberTicker value={outcomes[s] ?? 0} />
          </dd>
          <div className="col-span-2 h-1.5 overflow-hidden rounded-full bg-subtle" aria-hidden>
            <motion.div
              className="h-full origin-left rounded-full bg-ink-strong"
              style={{ width: `${((outcomes[s] ?? 0) / max) * 100}%` }}
              initial={reduce ? false : { scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.6, delay: 0.1 + i * 0.06, ease: [0.22, 1, 0.36, 1] }}
            />
          </div>
        </div>
      ))}
    </dl>
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
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { label: "Claims on file", value: overview.data.claims, hint: "Filed in this demo", icon: Files },
              {
                label: "Waiting for review",
                value: Object.values(overview.data.queue_by_tier).reduce((n, v) => n + (v ?? 0), 0),
                hint: "Across the three tiers",
                icon: ClipboardCheck,
              },
              { label: "Decided by rules", value: overview.data.decided_by_rules, hint: "Final without a model", icon: Scale },
              { label: "Lines overridden", value: overview.data.reviewed_overridden, hint: "By a reviewer", icon: UserCheck },
            ].map((kpi, i) => (
              <BlurFade key={kpi.label} delay={i * 0.05}>
                <Kpi {...kpi} />
              </BlurFade>
            ))}
          </div>
          <BlurFade delay={0.2} className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Tile title="Claims by final outcome" link={{ to: "/claims", label: "Open claims" }}>
              <OutcomeBars outcomes={overview.data.final_outcomes} />
            </Tile>
            <Tile title="Review queue by tier" link={{ to: "/queue", label: "Open the review queue" }}>
              <dl>
                {(["QUICK", "STANDARD", "FULL"] as ReviewTier[]).map((tier) => (
                  <Count key={tier} label={TIER[tier].label} value={overview.data.queue_by_tier[tier] ?? 0} />
                ))}
              </dl>
            </Tile>
            <Tile title="Decided by the rules alone" link={{ to: "/rule-outcomes", label: "Open returned and auto-denied" }}>
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
          </BlurFade>
        </div>
      )}
    </>
  );
}
