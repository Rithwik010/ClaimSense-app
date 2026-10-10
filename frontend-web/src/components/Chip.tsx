import type { ClaimStatus, LineDecision } from "../api/types";
import { DECISION, STATUS, type Label, type Tone } from "../lib/labels";

const TONES: Record<Tone, string> = {
  green: "bg-green-50 text-green-800 ring-green-200",
  amber: "bg-amber-50 text-amber-900 ring-amber-200",
  red: "bg-red-50 text-red-800 ring-red-200",
  grey: "bg-gray-100 text-gray-700 ring-gray-200",
  blue: "bg-accent-soft text-accent-strong ring-blue-200",
};

export function Chip({ label, showHint = false }: { label: Label; showHint?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-sm font-medium ring-1 ring-inset ${TONES[label.tone]}`}
        title={label.hint}
      >
        {label.label}
      </span>
      {showHint && <span className="text-sm text-gray-600">{label.hint}</span>}
    </span>
  );
}

export function StatusChip({ status, showHint }: { status: ClaimStatus; showHint?: boolean }) {
  return <Chip label={STATUS[status]} showHint={showHint} />;
}

export function DecisionChip({
  decision,
  showHint,
}: {
  decision: LineDecision;
  showHint?: boolean;
}) {
  return <Chip label={DECISION[decision]} showHint={showHint} />;
}
