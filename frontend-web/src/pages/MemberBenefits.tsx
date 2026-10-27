// My benefits (D-MEM-3): the member's benefit year so far. For each network the plan covers, the
// deductible and the out-of-pocket maximum with what is met of each, and each visit-limited
// benefit's visits used, as the API sends them: the plan's terms and the amounts the plan stored
// when it finalized the member's claims. The page formats them and computes nothing (no amount is
// added or subtracted here).

import { useMemberBenefits } from "@/api/hooks";
import type { YearToDate } from "@/api/types";
import { PageTitle, Panel, Section } from "@/components/Layout";
import { ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { dateOnly, money } from "@/lib/format";
import { benefitCategory } from "@/lib/labels";

const NETWORKS: Record<string, string> = { IN_NETWORK: "In network", OUT_OF_NETWORK: "Out of network" };

function Tile({ label, value, of }: { label: string; value: string; of: string }) {
  return (
    <div>
      <dt className="text-[13px] text-ink-muted">{label}</dt>
      <dd>
        <span className="block text-[22px] leading-[30px] font-semibold tabular-nums">{value}</span>
        <span className="text-[13px] text-ink-muted tabular-nums">{of}</span>
      </dd>
    </div>
  );
}

function Network({ ytd }: { ytd: YearToDate }) {
  const name = NETWORKS[ytd.network] ?? ytd.network;
  return (
    <Section title={name}>
      <Panel glass className="p-5">
        <dl className="grid gap-6 sm:grid-cols-2">
          <Tile
            label="Deductible met"
            value={money(ytd.deductible_met_cents)}
            of={`of a ${money(ytd.deductible_cents)} deductible`}
          />
          <Tile
            label="Out-of-pocket spent"
            value={money(ytd.oop_met_cents)}
            of={`of a ${money(ytd.oop_max_cents)} out-of-pocket maximum`}
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
                  <TableHead className="text-right">Visits used</TableHead>
                  <TableHead className="text-right">Visits a year</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.visits.map((visit) => (
                  <TableRow key={visit.benefit_category}>
                    <TableCell className="min-w-40">{benefitCategory(visit.benefit_category)}</TableCell>
                    <TableCell className="text-right tabular-nums">{visit.visits_used}</TableCell>
                    <TableCell className="text-right tabular-nums">{visit.visit_limit}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </Section>
      )}
      <p className="max-w-[75ch] text-[13px] text-ink-muted">
        As your plan recorded them on {dateOnly(data.as_of)}, for the claims it has decided this benefit year; a claim
        still being processed is not counted yet. Plan values are fictional: ClaimSense prototype, synthetic data only.
      </p>
    </>
  );
}
