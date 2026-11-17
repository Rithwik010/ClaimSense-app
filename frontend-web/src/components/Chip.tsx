// Status and decision badges: pills with text plus an icon on a light tint, never colour alone
// (DESIGN.md, D-UI-7).

import { CircleCheck, CircleHelp, CircleSlash, CircleX, Clock } from "lucide-react";

import type { ClaimStatus, LineDecision, Outcome } from "@/api/types";
import { DECISION, OUTCOME, providerOutcome, STATUS, type Label, type Tone } from "@/lib/labels";

const TONES: Record<Tone, { className: string; Icon: typeof CircleCheck }> = {
  approve: { className: "bg-approve-tint text-approve border-transparent [&_svg]:text-[#3f8a2a]", Icon: CircleCheck },
  pend: { className: "bg-pend-tint text-pend border-transparent [&_svg]:text-[#9a6a00]", Icon: CircleHelp },
  deny: { className: "bg-deny-tint text-deny border-transparent [&_svg]:text-[#b3141f]", Icon: CircleX },
  reject: { className: "bg-reject-tint text-reject border-transparent", Icon: CircleSlash },
  neutral: { className: "bg-brand-tint text-ink-strong border-transparent", Icon: Clock },
};

export function Chip({ label, showHint = false }: { label: Label; showHint?: boolean }) {
  const { className, Icon } = TONES[label.tone];
  return (
    <span className="inline-flex flex-wrap items-center gap-x-2 gap-y-1">
      <span
        className={`inline-flex h-6 items-center gap-1.5 rounded-full border px-2.5 text-[13px] font-semibold whitespace-nowrap ${className}`}
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

/** A claim's outcome, as the API names it (D-UI-6); `provider`: not processed, then in review
 * until final (`status` tells a claim not processed yet apart). */
export function OutcomeChip({
  outcome,
  showHint,
  provider = false,
  status,
}: {
  outcome: Outcome;
  showHint?: boolean;
  provider?: boolean;
  status?: string;
}) {
  return <Chip label={provider ? providerOutcome(outcome, status) : OUTCOME[outcome]} showHint={showHint} />;
}

export function DecisionChip({ decision, showHint }: { decision: LineDecision; showHint?: boolean }) {
  return <Chip label={DECISION[decision]} showHint={showHint} />;
}

/** A plain bordered badge for things that are not decisions (tiers, sources). */
export function PlainBadge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex h-6 items-center rounded-full border border-rules bg-subtle px-2.5 text-[13px] font-semibold whitespace-nowrap text-ink">
      {children}
    </span>
  );
}
