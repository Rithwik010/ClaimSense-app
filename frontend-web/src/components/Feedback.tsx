// The reviewer's corrections of the model's criteria (D-FBK-1), after they finalized a claim: for
// each model line, each criterion as the model answered it, with what it should have been and, for
// met or not met, a quote copied from the clinical notes. Only the reviewer who finalized the claim
// sends them; the API checks every quote against the notes and keeps positions, never the text, in
// the audit trail. They become labelled examples for the next fine-tune (the admin's export).

import { useState } from "react";
import { toast } from "sonner";

import { useFeedback, type CriterionFix } from "@/api/hooks";
import type { DecisionRecord } from "@/api/types";
import { Panel } from "@/components/Layout";
import { ErrorNotice } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { CRITERION_STATUS } from "@/lib/labels";

const STATUSES = ["MET", "NOT_MET", "NOT_DOCUMENTED", "NOT_APPLICABLE"] as const;
type Status = (typeof STATUSES)[number];
const QUOTED = new Set<Status>(["MET", "NOT_MET"]);

interface Draft {
  status: Status;
  quote: string;
}

export function FeedbackForm({ record }: { record: DecisionRecord }) {
  const feedback = useFeedback(record.claim_id);
  const [open, setOpen] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const lines = (record.slm_output?.lines ?? []).filter((line) => line.criteria.length > 0);
  if (lines.length === 0) return null;
  const texts = new Map<string, string>(
    (record.context_refs?.lines ?? []).flatMap((line) =>
      line.criteria.map((c): [string, string] => [`${line.line_no}:${c.criterion_id}`, c.text]),
    ),
  );
  const changed = lines.flatMap((line) =>
    line.criteria.flatMap((c) => {
      const draft = drafts[`${line.line_no}:${c.criterion_id}`];
      return draft && (draft.status !== c.status || (QUOTED.has(draft.status) && draft.quote.trim()))
        ? [{ line_no: line.line_no, criterion_id: c.criterion_id, draft }]
        : [];
    }),
  );
  const missingQuote = changed.some((c) => QUOTED.has(c.draft.status) && !c.draft.quote.trim());
  const send = () => {
    const byLine = new Map<number, CriterionFix[]>();
    for (const c of changed) {
      const fixes = byLine.get(c.line_no) ?? [];
      fixes.push({
        criterion_id: c.criterion_id,
        status: c.draft.status,
        quote: QUOTED.has(c.draft.status) ? c.draft.quote.trim() : null,
      });
      byLine.set(c.line_no, fixes);
    }
    feedback.mutate(
      [...byLine].map(([line_no, criteria]) => ({ line_no, criteria })),
      {
        onSuccess: (saved) => {
          toast.success(`${saved.criteria_corrected} criteri${saved.criteria_corrected === 1 ? "on" : "a"} corrected`, {
            description: "Kept for the next fine-tune.",
          });
          setOpen(false);
          setDrafts({});
        },
      },
    );
  };
  if (!open) {
    return (
      <Panel className="mt-6 flex flex-wrap items-center gap-4 p-5">
        <p className="min-w-0 flex-1 basis-72 text-ink-muted">
          Did the model get a criterion wrong? Correct it here: your corrections become training examples for the next
          version of the model. This does not change the claim.
        </p>
        <Button variant="outline" onClick={() => setOpen(true)}>
          Correct the model's criteria
        </Button>
      </Panel>
    );
  }
  return (
    <Panel className="mt-6 p-5">
      <h2 className="text-[18px] font-semibold">Correct the model's criteria</h2>
      <p className="mt-1 text-[14px] text-ink-muted">
        Change what the model should have answered. For met or not met, copy the sentence from the clinical notes that
        shows it. This does not change the claim's decision or amounts.
      </p>
      <div className="mt-4 space-y-5">
        {lines.map((line) => (
          <section key={line.line_no} aria-label={`Line ${line.line_no}`}>
            <h3 className="font-semibold">Line {line.line_no}</h3>
            <ul className="mt-2 divide-y divide-rules">
              {line.criteria.map((c) => {
                const key = `${line.line_no}:${c.criterion_id}`;
                const draft = drafts[key] ?? { status: c.status as Status, quote: "" };
                const set = (next: Partial<Draft>) => setDrafts((all) => ({ ...all, [key]: { ...draft, ...next } }));
                return (
                  <li key={key} className="grid gap-2 py-3 md:grid-cols-[minmax(0,1fr)_14rem]">
                    <div className="min-w-0">
                      <p className="text-[13px] text-ink-muted">
                        {c.criterion_id}: the model said {(CRITERION_STATUS[c.status] ?? c.status).toLowerCase()}
                      </p>
                      <p className="text-[14px]">{texts.get(key) ?? ""}</p>
                    </div>
                    <div className="grid content-start gap-2">
                      <label className="sr-only" htmlFor={`fb-${key}`}>
                        What line {line.line_no}, {c.criterion_id} should have been
                      </label>
                      <Select value={draft.status} onValueChange={(value) => set({ status: value as Status })}>
                        <SelectTrigger id={`fb-${key}`} className="w-full bg-paper">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {STATUSES.map((status) => (
                            <SelectItem key={status} value={status}>
                              {CRITERION_STATUS[status]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    {QUOTED.has(draft.status) && (draft.status !== c.status || drafts[key]) && (
                      <div className="grid gap-1 md:col-span-2">
                        <label className="text-[13px] font-semibold" htmlFor={`fb-${key}-quote`}>
                          Quote from the clinical notes
                        </label>
                        <Input
                          id={`fb-${key}-quote`}
                          value={draft.quote}
                          maxLength={600}
                          className="bg-paper"
                          placeholder="Copy the exact sentence"
                          onChange={(event) => set({ quote: event.target.value })}
                        />
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
      {feedback.error && (
        <div className="mt-4">
          <ErrorNotice error={feedback.error} />
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <Button disabled={changed.length === 0 || missingQuote || feedback.isPending} onClick={send}>
          {feedback.isPending ? "Saving" : `Save ${changed.length || ""} correction${changed.length === 1 ? "" : "s"}`.replace("  ", " ")}
        </Button>
        <Button variant="outline" onClick={() => setOpen(false)}>
          Cancel
        </Button>
        {missingQuote && <span className="text-[13px] text-pend">Met and not met need a quote from the notes.</span>}
      </div>
    </Panel>
  );
}
