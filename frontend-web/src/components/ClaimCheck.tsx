// Check the claim before processing it (D-CHK-1): what the rules would do, in plain words, with
// what to check on the claim and a Correct button for each box the check names that can still be
// corrected (D-FIX-1); then, for lines the rules pass, what the coverage policy asks the clinical
// notes to show. The API runs the same rules as processing and writes nothing; the model does not
// run, so the check never says whether the notes show what the policy asks.

import { ClipboardCheck, PencilLine } from "lucide-react";
import { useState } from "react";

import { useClaimCheck } from "@/api/hooks";
import type { CheckItem, CheckOutcome, CoverageLine } from "@/api/types";
import { Chip } from "@/components/Chip";
import { Panel } from "@/components/Layout";
import { ErrorNotice, Note, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { fieldLabel } from "@/lib/format";
import type { Label } from "@/lib/labels";

export const CHECK_OUTCOME: Record<CheckOutcome, Label> = {
  READY: { label: "Ready to process", hint: "The claim checks pass", tone: "approve" },
  LINES_DENIED: { label: "Some lines would not be paid", hint: "The other lines go on to review", tone: "deny" },
  REJECTED: { label: "Would be rejected", hint: "Returned without being processed", tone: "reject" },
  DENIED: { label: "Would be denied", hint: "The plan would not pay", tone: "deny" },
  PENDED: { label: "Would be put on hold", hint: "Information is missing", tone: "pend" },
};

function Item({
  item,
  correctable,
  onCorrect,
}: {
  item: CheckItem;
  correctable: Set<string>;
  onCorrect?: (field: string) => void;
}) {
  const boxes = item.fields.filter((field) => correctable.has(field));
  return (
    <li className="py-3">
      <p>
        {item.line_no !== null && <span className="font-semibold">Line {item.line_no}: </span>}
        {item.text}
      </p>
      {item.checks.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px] text-ink-muted">
          {item.checks.map((check) => (
            <li key={check}>{check}</li>
          ))}
        </ul>
      )}
      {onCorrect && boxes.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-2">
          {boxes.map((field) => (
            <Button key={field} variant="outline" size="sm" onClick={() => onCorrect(field)}>
              <PencilLine aria-hidden /> Correct {fieldLabel(field)}
            </Button>
          ))}
        </div>
      )}
    </li>
  );
}

function CriteriaList({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="mt-2">
      <p className="text-[13px] font-semibold">{title}</p>
      <ul className="mt-1 list-disc space-y-1 pl-5 text-[14px] leading-[22px]">
        {items.map((text) => (
          <li key={text}>{text}</li>
        ))}
      </ul>
    </div>
  );
}

function Coverage({ lines }: { lines: CoverageLine[] }) {
  return (
    <ul aria-label="Coverage criteria by line" className="divide-y divide-rules">
      {lines.map((line) => {
        const none = !line.needed.length && !line.one_of.length && !line.applies_when.length && !line.not_covered.length;
        return (
          <li key={line.line_no} className="py-3">
            <p className="font-semibold">
              Line {line.line_no} <span className="font-normal text-ink-muted">{line.procedure_code}</span>
            </p>
            {none ? (
              <p className="mt-1 text-[14px] text-ink-muted">
                No coverage policy sets conditions for this service: the claim checks and the reviewer decide it.
              </p>
            ) : (
              <>
                <p className="mt-1 text-[13px] text-ink-muted">{line.policies.join("; ")}</p>
                <CriteriaList title="The clinical notes should show" items={line.needed} />
                <CriteriaList title="At least one of these" items={line.one_of} />
                <CriteriaList title="Only when it applies" items={line.applies_when} />
                <CriteriaList title="Not covered when" items={line.not_covered} />
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export function ClaimCheckPanel({
  claimId,
  correctable = new Set<string>(),
  onCorrect,
}: {
  claimId: string;
  correctable?: Set<string>;
  onCorrect?: (field: string) => void;
}) {
  const [asked, setAsked] = useState(false);
  const check = useClaimCheck(claimId, asked);
  const result = check.data;
  return (
    <Panel className="p-5">
      <div className="flex flex-wrap items-center gap-4">
        <p className="min-w-0 flex-1 basis-72 text-ink-muted">
          See what the claim checks would find and what the coverage policy asks the notes to show, before you
          process the claim. Nothing is decided or saved.
        </p>
        <Button
          variant="outline"
          disabled={check.isFetching}
          onClick={() => (asked ? void check.refetch() : setAsked(true))}
        >
          <ClipboardCheck aria-hidden /> {check.isFetching ? "Checking" : asked ? "Check again" : "Check claim"}
        </Button>
      </div>
      {asked && check.isPending && (
        <div className="mt-4">
          <Skeleton lines={3} />
        </div>
      )}
      {check.error && (
        <div className="mt-4">
          <ErrorNotice error={check.error} />
        </div>
      )}
      {result && (
        <div className="mt-4 space-y-4" aria-live="polite">
          <div className="flex flex-wrap items-center gap-3" title={result.heading}>
            <Chip label={CHECK_OUTCOME[result.outcome]} showHint />
          </div>
          {result.problems.length > 0 && (
            <ul aria-label="What the checks found" className="divide-y divide-rules">
              {result.problems.map((item) => (
                <Item key={`${item.line_no}-${item.text}`} item={item} correctable={correctable} onCorrect={onCorrect} />
              ))}
            </ul>
          )}
          {result.notes.length > 0 && (
            <Note tone="neutral">
              <ul aria-label="Notes" className="divide-y divide-rules">
                {result.notes.map((item) => (
                  <Item key={`${item.line_no}-${item.text}`} item={item} correctable={correctable} onCorrect={onCorrect} />
                ))}
              </ul>
            </Note>
          )}
          {result.coverage && result.coverage.length > 0 && (
            <div>
              <h3 className="font-semibold">What the coverage policy asks for</h3>
              <p className="text-[13px] text-ink-muted">
                Processing checks the clinical notes against these. Make sure the notes say so where it applies.
              </p>
              <Coverage lines={result.coverage} />
            </div>
          )}
          {result.coverage_note && <Note>{result.coverage_note}</Note>}
        </div>
      )}
    </Panel>
  );
}
