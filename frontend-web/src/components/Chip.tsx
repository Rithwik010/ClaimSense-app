// Status and decision badges: text plus an icon on a light tint, never colour alone (DESIGN.md).

import { CircleCheck, CircleHelp, CircleSlash, CircleX, Clock } from "lucide-react";

import type { ClaimStatus, LineDecision, Outcome } from "@/api/types";
import { DECISION, OUTCOME, providerOutcome, STATUS, type Label, type Tone } from "@/lib/labels";

const TONES: Record<Tone, { className: string; Icon: typeof CircleCheck }> = {
  approve: { className: "bg-approve-tint text-approve border-approve/25", Icon: CircleCheck },
  pend: { className: "bg-pend-tint text-pend border-pend/25", Icon: CircleHelp },
  deny: { className: "bg-deny-tint text-deny border-deny/25", Icon: CircleX },
  reject: { className: "bg-reject-tint text-reject border-reject/25", Icon: CircleSlash },
  neutral: { className: "bg-glow-blue/10 text-link border-glow-blue/30", Icon: Clock },
};

export function Chip({ label, showHint = false }: { label: Label; showHint?: boolean }) {
  const { className, Icon } = TONES[label.tone];
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      <span
        className={`inline-flex h-6 items-center gap-1.5 rounded-md border px-2 text-[13px] font-semibold whitespace-nowrap ${className}`}
        title={label.hint}
      >
        <Icon aria-hidden className="size-3.5 shrink-0" strokeWidth={2.25} />
        {label.label}
      </span>
      {showHint && <span className="text-[13px] text-ink-muted">{label.hint}</span>}
    </span>
  );
}

export function StatusChip({ status, showHint }: { status: ClaimStatus; showHint?: boolean }) {
  return <Chip label={STATUS[status]} showHint={showHint} />;
}

/** A claim's outcome, as the API names it (D-UI-6); `provider`: in review until final. */
export function OutcomeChip({
  outcome,
  showHint,
  provider = false,
}: {
  outcome: Outcome;
  showHint?: boolean;
  provider?: boolean;
}) {
  return <Chip label={provider ? providerOutcome(outcome) : OUTCOME[outcome]} showHint={showHint} />;
}

export function DecisionChip({ decision, showHint }: { decision: LineDecision; showHint?: boolean }) {
  return <Chip label={DECISION[decision]} showHint={showHint} />;
}

/** A plain bordered badge for things that are not decisions (tiers, sources). */
export function PlainBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex h-6 items-center rounded-md border border-white/15 bg-white/[0.04] px-2 text-[13px] font-medium whitespace-nowrap text-ink">
      {children}
    </span>
  );
}
