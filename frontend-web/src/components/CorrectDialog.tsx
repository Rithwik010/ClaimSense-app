// Correct one box of a claim read from our form (D-FIX-1): the value as the form prints it, with a
// hint for the box's format. The API checks it with the same format check as a reading and answers
// with the corrected boxes; a value it refuses keeps the dialog open with the reason.

import { useId, useState } from "react";
import { toast } from "sonner";

import { useCorrect } from "@/api/hooks";
import type { FormBox } from "@/api/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { fieldLabel } from "@/lib/format";

/** How the form prints a box, as a hint under the input. */
export function formatHint(field: string): string {
  const name = field.split(".").pop() ?? field;
  if (/date_of_service|received_date|date_of_birth/.test(name)) return "A date as MM/DD/YYYY, for example 11/20/2026.";
  if (name.endsWith("npi")) return "The 10-digit NPI.";
  if (name === "charge_cents") return "Dollars and cents, for example 132.00.";
  if (field.startsWith("other_coverage.primary_paid.")) return "The line and the amount, for example Line 1: 40.00.";
  if (field.startsWith("diagnoses.")) return "An ICD-10-CM code with its dot, for example M54.5.";
  if (name === "procedure_code") return "The five-character procedure code.";
  if (name === "modifiers") return "Up to four two-character modifiers, one space apart, for example 25 59.";
  if (name === "diagnosis_pointers") return "One to four diagnosis letters, A to L, for example AB.";
  if (name === "units") return "A whole number from 1.";
  if (name === "place_of_service") return "The two-digit place of service code, for example 11.";
  if (name === "subscriber_is_patient") return "SELF or OTHER.";
  if (name === "sex") return "F, M or U.";
  if (name === "billing_tin") return "The 9-digit tax ID.";
  if (name === "zip_code") return "5 digits, or 5 digits, a hyphen and 4 digits.";
  if (name === "state") return "The two-letter state code.";
  return "As the form shows it. Leave it empty to clear the box.";
}

function CorrectForm({ claimId, box, onDone }: { claimId: string; box: FormBox; onDone: () => void }) {
  const inputId = useId();
  const hintId = useId();
  const errorId = useId();
  const [value, setValue] = useState(box.text ?? "");
  const correct = useCorrect(claimId);
  const label = fieldLabel(box.field);
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        correct.mutate([{ field: box.field, value }], {
          onSuccess: () => {
            toast.success(`${label} corrected`);
            onDone();
          },
        });
      }}
    >
      <DialogHeader>
        <DialogTitle className="text-[18px] font-semibold">Correct {label}</DialogTitle>
        <DialogDescription className="text-[15px] text-ink-muted">
          Read as: {box.text ?? "(could not be read)"}. Type the value the form shows. The claim keeps your value
          as entered by you, and the audit trail records the change.
        </DialogDescription>
      </DialogHeader>
      <div className="my-5 space-y-2">
        <label htmlFor={inputId} className="text-[13px] font-semibold">
          {label}
        </label>
        <Input
          id={inputId}
          value={value}
          autoFocus
          autoComplete="off"
          spellCheck={false}
          aria-describedby={correct.error ? `${hintId} ${errorId}` : hintId}
          aria-invalid={correct.error ? true : undefined}
          onChange={(event) => setValue(event.target.value)}
        />
        <p id={hintId} className="text-[13px] text-ink-muted">
          {formatHint(box.field)}
        </p>
        {correct.error && (
          <p id={errorId} role="alert" className="text-[13px] font-semibold text-deny">
            {correct.error.message}
          </p>
        )}
      </div>
      <DialogFooter className="gap-3">
        <Button type="button" variant="outline" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={correct.isPending}>
          {correct.isPending ? "Saving" : "Save correction"}
        </Button>
      </DialogFooter>
    </form>
  );
}

export function CorrectDialog({
  claimId,
  box,
  onClose,
}: {
  claimId: string;
  box: FormBox | null;
  onClose: () => void;
}) {
  return (
    <Dialog open={box !== null} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="sm:max-w-md">
        {box && <CorrectForm key={box.field} claimId={claimId} box={box} onDone={onClose} />}
      </DialogContent>
    </Dialog>
  );
}
