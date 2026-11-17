// My benefits (D-MEM-3): the member's benefit year so far. For each network the plan covers, the
// deductible and the out-of-pocket maximum with what is met of each, and each visit-limited
// benefit's visits used, as the API sends them: the plan's terms and the amounts the plan stored
// when it finalized the member's claims, with what is left of each and the share used, which the
// calculator works out (D-MEM-5). The page formats them and computes nothing: each bar's
// length is the API's basis points.

import { useMemberBenefits } from "@/api/hooks";
import type { NetworkProgress } from "@/api/types";
import { PageTitle, Panel, Section } from "@/components/Layout";
import { ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { basisPoints, dateOnly, money } from "@/lib/format";
import { benefitCategory } from "@/lib/labels";

const NETWORKS: Record<string, string> = { IN_NETWORK: "In network", OUT_OF_NETWORK: "Out of network" };

/** How much of a limit is used, as a bar: its length is the API's basis points (0 to 10000). */
export function UsedBar({ bps, label }: { bps: number; label: string }) {
  const share = Math.min(Math.max(bps, 0), 10000);
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={share / 100}
      aria-valuetext={`${basisPoints(share)} used`}
      className="mt-2 h-2 overflow-hidden rounded-full bg-subtle"
    >
      <div className="h-full rounded-full bg-ink-strong" style={{ width: `${share / 100}%` }} />
    </div>
  );
}

function Tile({ label, value, of, left, bps }: { label: string; value: string; of: string; left: string; bps: number }) {
  return (
    <div>
      <dt className="text-[13px] text-ink-muted">{label}</dt>
      <dd>
        <span className="block text-[22px] leading-[30px] font-bold text-ink-strong tabular-nums">{value}</span>
        <span className="text-[13px] text-ink-muted tabular-nums">{of}</span>
        <UsedBar bps={bps} label={label} />
        <span className="mt-1 block text-[14px] font-semibold tabular-nums">{left}</span>
      </dd>
    </div>
  );
}

function Network({ ytd }: { ytd: NetworkProgress }) {
  const name = NETWORKS[ytd.network] ?? ytd.network;
  return (
    <Section title={name}>
      <Panel glass className="p-5">
        <dl className="grid gap-6 sm:grid-cols-2">
          <Tile
            label="Deductible met"
            value={money(ytd.deductible_met_cents)}
            of={`of a ${money(ytd.deductible_cents)} deductible`}
            bps={ytd.deductible_met_bps}
            left={ytd.deductible_left_cents > 0 ? `${money(ytd.deductible_left_cents)} left to meet` : "Met for this year"}
          />
          <Tile
            label="Out-of-pocket spent"
            value={money(ytd.oop_met_cents)}
            of={`of a ${money(ytd.oop_max_cents)} out-of-pocket maximum`}
            bps={ytd.oop_met_bps}
            left={
              ytd.oop_left_cents > 0
                ? `${money(ytd.oop_left_cents)} to go before you pay no more cost share for covered care`
                : "Reached: you pay no more cost share for covered care in this network this year"
            }
          />
        </dl>
      </Panel>
    </Section>
  );
}

export function MemberBenefits() {
  const benefits = useMemberBenefits();
  if (benefits.isPending) return <Skeleton lines={8} />;
  if (benefits.error) return <ErrorNotice error={benefits.error} onRetry={() => void benefits.refetch()} />;
  const data = benefits.data;
  const inNetworkOnly = data.networks.every((n) => n.network === "IN_NETWORK");
  return (
    <>
      <PageTitle
        title="My benefits"
        hint={`${data.plan_name} (${data.plan_type}), benefit year ${dateOnly(data.benefit_year_start)} to ${dateOnly(data.benefit_year_end)}.`}
      />
      {data.networks.map((ytd) => (
        <Network key={ytd.network} ytd={ytd} />
      ))}
      {inNetworkOnly && <p className="-mt-4 mb-8 text-[13px] text-ink-muted">Your plan covers in-network care only.</p>}
      {data.visits.length > 0 && (
        <Section title="Visits">
          <div className="overflow-x-auto surface rounded-lg">
            <Table aria-label="Visits">
              <TableHeader>
                <TableRow>
                  <TableHead>Benefit</TableHead>
                  <TableHead className="text-right">
                    Used<span className="sr-only"> visits</span>
                  </TableHead>
                  <TableHead className="text-right">
                    A year<span className="sr-only"> (visits)</span>
                  </TableHead>
                  <TableHead className="text-right">
                    Left<span className="sr-only"> (visits)</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.visits.map((visit) => (
                  <TableRow key={visit.benefit_category}>
                    <TableCell className="min-w-28">
                      {benefitCategory(visit.benefit_category)}
                      <UsedBar bps={visit.used_bps} label={`${benefitCategory(visit.benefit_category)} visits`} />
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{visit.visits_used}</TableCell>
                    <TableCell className="text-right tabular-nums">{visit.visit_limit}</TableCell>
                    <TableCell className="text-right font-semibold tabular-nums">{visit.visits_left}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Section>
      )}
      <p className="max-w-[75ch] text-[13px] text-ink-muted">
        As your plan recorded them on {dateOnly(data.as_of)}, for the claims it has decided this benefit year; a claim
        still being processed is not counted yet.
      </p>
    </>
  );
}
