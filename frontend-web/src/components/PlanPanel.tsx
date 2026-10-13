// The plan a claim was checked against (GET /v1/plans/{plan_id}, reviewers and admins): its terms,
// each benefit category with what it needs, and the codes it excludes. The categories this claim's
// lines could fall under are marked. Values are fictional (data/curated/, DECISIONS.md); the UI
// formats them and computes nothing.

import { usePlan } from "@/api/hooks";
import type { DecisionRecord } from "@/api/types";
import { PlainBadge } from "@/components/Chip";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { basisPoints, money } from "@/lib/format";

const words = (code: string) => code.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase());

export function PlanPanel({ record }: { record: DecisionRecord | null }) {
  const context = record?.context_refs ?? null;
  const plan = usePlan(context?.plan_id ?? null);
  if (!context) {
    return (
      <EmptyState title="No plan lookup for this claim">
        The rules decided the claim before its plan's coverage was needed, or it has not been processed yet.
      </EmptyState>
    );
  }
  if (plan.isPending) return <Skeleton lines={5} />;
  if (plan.error) return <ErrorNotice error={plan.error} onRetry={() => void plan.refetch()} />;
  const p = plan.data;
  const ofThisClaim = new Set(context.lines.flatMap((line) => line.candidate_benefits.map((b) => b.benefit_category)));
  const inNetwork = context.network === "IN_NETWORK";
  const terms: [string, string][] = [
    ["Plan", `${p.name} (${p.plan_type})`],
    ["This claim", inNetwork ? "In network" : "Out of network"],
    ["Deductible, in network", money(p.inn_deductible_cents)],
    ["Coinsurance, in network", basisPoints(p.inn_coinsurance_bps)],
    ["Out-of-pocket maximum, in network", money(p.inn_oop_max_cents)],
    [
      "Out of network",
      p.oon_covered
        ? `Deductible ${money(p.oon_deductible_cents)}, coinsurance ${basisPoints(p.oon_coinsurance_bps)}, out-of-pocket maximum ${money(p.oon_oop_max_cents)}`
        : "Not covered",
    ],
    ["Filing window", `${p.filing_window_inn_days} days in network, ${p.filing_window_oon_days} days out of network`],
    ["Effective from", p.effective_date],
  ];
  return (
    <div className="space-y-4">
      <dl className="surface rounded-lg px-4 py-2">
        {terms.map(([label, value]) => (
          <div key={label} className="grid gap-x-4 border-b border-rules py-2 last:border-b-0 sm:grid-cols-[16rem_1fr]">
            <dt className="text-ink-muted">{label}</dt>
            <dd className="font-semibold tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      <div className="overflow-x-auto surface rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Benefit</TableHead>
              <TableHead>Covered</TableHead>
              <TableHead>Prior auth</TableHead>
              <TableHead className="text-right">Visit limit</TableHead>
              <TableHead>Cost share</TableHead>
              <TableHead className="text-right">Copay</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {p.benefits.map((b) => (
              <TableRow key={b.benefit_category}>
                <TableCell className="min-w-48">
                  {words(b.benefit_category)}
                  {ofThisClaim.has(b.benefit_category) && (
                    <span className="ml-2">
                      <PlainBadge>This claim</PlainBadge>
                    </span>
                  )}
                </TableCell>
                <TableCell>{b.covered ? "Yes" : "No"}</TableCell>
                <TableCell>{b.auth_required ? "Required" : "Not required"}</TableCell>
                <TableCell className="text-right tabular-nums">{b.visit_limit ?? "None"}</TableCell>
                <TableCell>{words(b.cost_share_rule)}</TableCell>
                <TableCell className="text-right tabular-nums">{b.copay_cents === null ? "—" : money(b.copay_cents)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      <p className="text-[13px] text-ink-muted">
        Excluded codes: {p.excluded_codes.length ? p.excluded_codes.join(", ") : "none"}. Plan values are fictional.
      </p>
    </div>
  );
}
