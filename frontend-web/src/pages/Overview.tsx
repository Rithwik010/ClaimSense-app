// Overview (an admin's home, D-AUTH-1): counts over the claims on file in this demo database (GET
// /v1/metrics/overview). Each headline count opens the list behind it, as the tiles' links do
// (D-UI-10): the claims, the claims not processed yet (fix 8), the review queue, the rule outcomes
// and the claims a reviewer finalized. Then the money of the decided claims, how long reviews take,
// how often reviewers change the model's lines, the commonest reasons and the last 14 days
// (D-QLT-1): the API's numbers, formatted only (amounts are the calculator's stored totals).

import { ArrowRight, CircleDashed, ClipboardCheck, Files, Scale, UserCheck } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { Link } from "react-router";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { useOverview } from "@/api/hooks";
import type { ClaimStatus, OverviewExtras, ReviewTier } from "@/api/types";
import { StatusChip } from "@/components/Chip";
import { BlurFade, NumberTicker, Spotlight } from "@/components/fx";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { basisPoints, dateOnly, duration, money } from "@/lib/format";
import { STATUS, TIER } from "@/lib/labels";

/** The one data colour (brand blue, validated on white: lightness band, chroma, 3:1 contrast). */
const SERIES = "#0033ff";

/** "2026-11-16" -> "Nov 16" for the trend's axis. */
function shortDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(y!, m! - 1, d!).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

/** One small multiple of the trend: a single series, so no legend; the title names it. */
function DayBars({
  title,
  dataKey,
  days,
  max,
}: {
  title: string;
  dataKey: "received" | "decided";
  days: OverviewExtras["daily"];
  max: number;
}) {
  const config: ChartConfig = { [dataKey]: { label: title, color: SERIES } };
  return (
    <figure className="min-w-0">
      <figcaption className="mb-1 text-[14px] font-semibold">{title}</figcaption>
      <ChartContainer config={config} className="aspect-auto h-44 w-full">
        <BarChart data={days} margin={{ left: 0, right: 4, top: 8 }} barCategoryGap={2}>
          <CartesianGrid vertical={false} stroke="#ECEEF2" />
          <XAxis
            dataKey="date"
            tickLine={false}
            axisLine={false}
            tickFormatter={shortDay}
            interval="preserveStartEnd"
            minTickGap={24}
            tick={{ fontSize: 12, fill: "#5a5a5a" }}
          />
          <YAxis
            allowDecimals={false}
            domain={[0, max]}
            tickLine={false}
            axisLine={false}
            width={32}
            tick={{ fontSize: 12, fill: "#5a5a5a" }}
          />
          <ChartTooltip
            cursor={{ fill: "#E6EBFF", opacity: 0.6 }}
            content={<ChartTooltipContent labelFormatter={(value) => dateOnly(String(value))} />}
          />
          <Bar dataKey={dataKey} fill={`var(--color-${dataKey})`} radius={[4, 4, 0, 0]} isAnimationActive={false} />
        </BarChart>
      </ChartContainer>
    </figure>
  );
}

/** The last 14 days as two small multiples on one scale, with the numbers as a table. */
function Trend({ days }: { days: OverviewExtras["daily"] }) {
  const max = Math.max(1, ...days.map((d) => Math.max(d.received, d.decided)));
  return (
    <div>
      <div className="grid gap-6 md:grid-cols-2">
        <DayBars title="Claims received" dataKey="received" days={days} max={max} />
        <DayBars title="Claims decided" dataKey="decided" days={days} max={max} />
      </div>
      <details className="mt-3 text-[14px]">
        <summary className="cursor-pointer font-semibold text-link">Show the numbers</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left tabular-nums">
            <thead>
              <tr className="border-b border-rules text-[13px] text-ink-muted">
                <th className="py-1.5 pr-4 font-semibold">Day</th>
                <th className="py-1.5 pr-4 text-right font-semibold">Received</th>
                <th className="py-1.5 text-right font-semibold">Decided</th>
              </tr>
            </thead>
            <tbody>
              {days.map((d) => (
                <tr key={d.date} className="border-b border-rules/60 last:border-0">
                  <td className="py-1 pr-4">{dateOnly(d.date)}</td>
                  <td className="py-1 pr-4 text-right">{d.received}</td>
                  <td className="py-1 text-right">{d.decided}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}

/** A figure that is not a count: money, a time or a rate, as the API gives it, formatted. */
function Figure({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="py-1.5">
      <dt className="text-[14px] text-ink-muted">{label}</dt>
      <dd className="text-[20px] leading-7 font-semibold tabular-nums">{value}</dd>
      {hint && <dd className="text-[13px] text-ink-muted">{hint}</dd>}
    </div>
  );
}

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

/** A headline count: what an admin wants to see first; the whole tile opens the list behind it. */
function Kpi({
  label,
  value,
  hint,
  icon: Icon,
  to,
}: {
  label: string;
  value: number;
  hint: string;
  icon: typeof Files;
  to: string;
}) {
  return (
    <Link
      to={to}
      className="group/kpi block h-full rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-link"
    >
      <Spotlight className="hover-lift h-full px-5 py-4">
        <p className="flex items-center gap-2 text-[14px] text-ink-muted xl:min-h-11">
          <span className="grid size-7 shrink-0 place-items-center rounded-md border border-rules bg-brand-tint text-ink-strong">
            <Icon aria-hidden className="size-4 text-link" />
          </span>
          {label}
          <ArrowRight
            aria-hidden
            className="ml-auto size-4 text-link transition-transform group-hover/kpi:translate-x-0.5"
          />
        </p>
        <p className="mt-3 font-heading text-[34px] leading-10 font-bold text-ink-strong">
          <NumberTicker value={value} />
        </p>
        <p className="mt-1 text-[13px] text-ink-muted">{hint}</p>
      </Spotlight>
    </Link>
  );
}

/** The claims list kept to the claims a reviewer finalized (Claims, ?reviewed=1). */
const REVIEWED_CLAIMS = "/claims?reviewed=1";

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
      />
      {overview.isPending ? (
        <Skeleton lines={6} />
      ) : overview.error ? (
        <ErrorNotice error={overview.error} onRetry={() => void overview.refetch()} />
      ) : overview.data.claims === 0 ? (
        <EmptyState title="No claims on file yet">The counts appear once providers file claims.</EmptyState>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {[
              { label: "Claims on file", value: overview.data.claims, hint: "Filed in this demo", icon: Files, to: "/claims" },
              {
                label: "Not processed",
                value: overview.data.not_processed ?? overview.data.by_status.RECEIVED ?? 0,
                hint: "Filed, waiting for their provider",
                icon: CircleDashed,
                to: "/claims?status=NOT_PROCESSED",
              },
              {
                label: "Waiting for review",
                value: Object.values(overview.data.queue_by_tier).reduce((n, v) => n + (v ?? 0), 0),
                hint: "Across the three tiers",
                icon: ClipboardCheck,
                to: "/queue",
              },
              {
                label: "Decided by rules",
                value: overview.data.decided_by_rules,
                hint: "Final without a model",
                icon: Scale,
                to: "/rule-outcomes",
              },
              {
                label: "Lines overridden",
                value: overview.data.reviewed_overridden,
                hint: "By a reviewer",
                icon: UserCheck,
                to: REVIEWED_CLAIMS,
              },
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
            <Tile title="Reviewed claims" link={{ to: REVIEWED_CLAIMS, label: "Open reviewed claims" }}>
              <dl>
                <Count label="Recommendation accepted" value={overview.data.reviewed_accepted} />
                <Count label="Lines overridden" value={overview.data.reviewed_overridden} />
              </dl>
            </Tile>
          </BlurFade>
          {overview.data.extras && <Extras extras={overview.data.extras} />}
        </div>
      )}
    </>
  );
}

function Extras({ extras }: { extras: OverviewExtras }) {
  const decided = extras.decided_claims;
  return (
    <>
      <BlurFade delay={0.25} className="grid gap-4 md:grid-cols-3">
        <Tile title="Money of the decided claims" link={{ to: REVIEWED_CLAIMS, label: "Open the claims behind these sums" }}>
          <dl>
            <Figure label="Billed" value={money(extras.billed_cents)} hint={`${decided} claim${decided === 1 ? "" : "s"} a reviewer finalized`} />
            <Figure label="Plan paid" value={money(extras.plan_paid_cents)} />
            <Figure label="Members owe" value={money(extras.member_owes_cents)} />
          </dl>
        </Tile>
        <Tile title="Review times" link={{ to: "/quality", label: "Open review quality" }}>
          <dl>
            <Figure
              label="Waiting for review, median"
              value={duration(extras.review_wait_seconds)}
              hint="From processing to the reviewer's decision"
            />
            <Figure
              label="Time a reviewer spends, median"
              value={duration(extras.review_seconds)}
              hint="From opening the claim to finalizing it"
            />
            <Figure
              label="Model lines changed by reviewers"
              value={basisPoints(extras.override_rate_bp)}
              hint="Of the lines the model recommended"
            />
          </dl>
        </Tile>
        <Tile title="Commonest reasons" link={{ to: "/rule-outcomes", label: "Open returned and auto-denied" }}>
          {extras.top_reasons.length === 0 ? (
            <p className="text-ink-muted">No claim has a reason yet: every decided claim was paid as billed.</p>
          ) : (
            <ol className="space-y-2 py-1">
              {extras.top_reasons.map((r) => (
                <li key={r.reason} className="flex items-start justify-between gap-3">
                  <span className="min-w-0">{r.reason}</span>
                  <span className="font-semibold tabular-nums">{r.claims}</span>
                </li>
              ))}
            </ol>
          )}
        </Tile>
      </BlurFade>
      <BlurFade delay={0.3}>
        <section aria-labelledby="trend-title" className="surface rounded-lg p-5">
          <h2 id="trend-title" className="font-semibold">
            The last 14 days
          </h2>
          <p className="mb-4 text-[13px] text-ink-muted">Claims received and claims decided each day, on the same scale.</p>
          <Trend days={extras.daily} />
        </section>
      </BlurFade>
    </>
  );
}
