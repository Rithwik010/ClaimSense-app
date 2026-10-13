// The claim summary (reviewers and admins, D-UI-6): a few short lines the API builds from the decision
// record and the reason table, never the model: at a glance, the checks, each line's decision and
// key reason, the amounts, any flags and the outcome. Rule IDs may show here; this is a staff page.

import { Flag, Gauge, ListChecks, ShieldCheck, Wallet, type LucideIcon } from "lucide-react";

import type { ClaimSummaryLines } from "@/api/types";

const ICONS: Record<ClaimSummaryLines["items"][number]["kind"], LucideIcon> = {
  glance: Gauge,
  checks: ShieldCheck,
  line: ListChecks,
  amounts: Wallet,
  flags: Flag,
  outcome: ShieldCheck,
};

export function ClaimSummary({ summary }: { summary: ClaimSummaryLines }) {
  return (
    <ul aria-label="Claim summary" data-testid="claim-summary" className="space-y-3">
      {summary.items.map((item, i) => {
        const Icon = ICONS[item.kind];
        return (
          <li key={`${item.kind}-${i}`} className="grid grid-cols-[18px_1fr] gap-x-2.5" data-kind={item.kind}>
            <Icon aria-hidden className="mt-1 size-[18px] text-ink-muted" />
            <p
              className={`min-w-0 leading-6 ${item.kind === "glance" ? "font-semibold" : ""} ${item.kind === "line" ? "line-clamp-3" : ""}`}
              title={item.kind === "line" ? item.text : undefined}
            >
              {item.text}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
