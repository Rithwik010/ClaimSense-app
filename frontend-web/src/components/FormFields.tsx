// The boxes of a claim read from our form (D-FIX-1): each as the form prints it, with the
// confidence it was read with. A box read below the threshold is highlighted (§8.2, H5), and so is
// a box the check names. While the claim is not processed, each box (but the claim number, the
// frequency and the clinical notes) has a Correct button; a corrected box shows "Corrected"
// instead of its reading's confidence: the provider entered it.

import { CircleAlert, PencilLine } from "lucide-react";

import type { ClaimForm, FormBox } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { fieldLabel } from "@/lib/format";
import { LOW_CONFIDENCE } from "@/lib/labels";

function shownText(box: FormBox): string {
  if (box.text) return box.text;
  return box.confidence !== null ? "(could not be read)" : "(blank)";
}

export function isLow(box: FormBox): boolean {
  return !box.corrected && box.confidence !== null && box.confidence < LOW_CONFIDENCE;
}

export function FormFields({
  form,
  flagged = new Set<string>(),
  onCorrect,
}: {
  form: ClaimForm;
  flagged?: Set<string>;
  onCorrect?: (field: string) => void;
}) {
  const low = form.boxes.filter(isLow).length;
  const corrected = form.boxes.filter((box) => box.corrected).length;
  return (
    <div>
      <p className="mb-3 max-w-[72ch] text-[13px] text-ink-muted">
        {low
          ? `${low} box${low === 1 ? " was" : "es were"} read with low confidence (below ${LOW_CONFIDENCE}). A rule that fails on one of them rejects the claim instead of denying it.`
          : "Every box was read with high confidence."}
        {corrected > 0 && ` ${corrected} corrected by the provider.`}
        {form.correctable && " Correct any box that was read wrong before processing the claim; type it as the form shows it."}
      </p>
      <div className="max-h-[32rem] overflow-auto surface rounded-lg">
        <Table aria-label="Boxes read from the form">
          <TableHeader className="sticky top-0 z-10 bg-raised">
            <TableRow>
              <TableHead>Box</TableHead>
              <TableHead>As read</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
              {form.correctable && <TableHead className="sr-only">Correct</TableHead>}
            </TableRow>
          </TableHeader>
          <TableBody>
            {form.boxes.map((box) => {
              const lowBox = isLow(box);
              const named = flagged.has(box.field);
              const label = fieldLabel(box.field);
              return (
                <TableRow
                  key={box.field}
                  className={lowBox || named ? "bg-pend-tint hover:bg-pend-tint" : undefined}
                >
                  <TableCell className="align-top whitespace-nowrap text-ink-muted">
                    {label}
                    {named && (
                      <span className="ml-2 inline-flex items-center gap-1 text-[13px] font-semibold text-pend">
                        <CircleAlert aria-hidden className="size-3.5" /> Named by the check
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="max-w-xl align-top break-words whitespace-pre-wrap">
                    {shownText(box)}
                  </TableCell>
                  <TableCell className="text-right align-top whitespace-nowrap tabular-nums">
                    {box.corrected ? (
                      <span className="inline-flex items-center gap-1 text-[13px] font-semibold text-link">
                        <PencilLine aria-hidden className="size-3.5" /> Corrected
                      </span>
                    ) : (
                      <>
                        {lowBox && <span className="mr-2 text-[13px] font-semibold text-pend">Low</span>}
                        {box.confidence === null ? "—" : `${Math.round(box.confidence * 100)}%`}
                      </>
                    )}
                  </TableCell>
                  {form.correctable && (
                    <TableCell className="text-right align-top">
                      {box.correctable && onCorrect && (
                        <Button
                          variant="ghost"
                          size="sm"
                          aria-label={`Correct ${label}`}
                          onClick={() => onCorrect(box.field)}
                        >
                          <PencilLine aria-hidden /> Correct
                        </Button>
                      )}
                    </TableCell>
                  )}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
