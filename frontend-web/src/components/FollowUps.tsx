// What a provider can do with a decided claim (D-FUP-1, D-APL-1), and a claim's appeals:
// - correct and resubmit a claim the checks returned, denied or put on hold: it goes back to
//   "Not processed", its boxes can be corrected (whatever the source) and it is processed again;
// - send documentation for a claim on hold: added to its clinical notes, then processed again;
// - appeal a denied claim: a reviewer other than the one who denied it decides it again, once.
// The API says which apply (follow_ups) and checks them again; nothing here decides anything.

import { FilePlus2, Gavel, RotateCcw } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { useFollowUp } from "@/api/hooks";
import type { Appeal, FollowUps } from "@/api/types";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Panel } from "@/components/Layout";
import { ErrorNotice } from "@/components/States";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { dateOnly, dateTime } from "@/lib/format";
import { APPEAL_OUTCOME } from "@/lib/labels";

export const REASON_MIN = 10;
export const REASON_MAX = 2000;
export const DOCUMENTATION_MAX = 8000;

interface TextDialogProps {
  open: boolean;
  title: string;
  description: ReactNode;
  label: string;
  min: number;
  max: number;
  confirmLabel: string;
  pending: boolean;
  error: unknown;
  onSubmit: (text: string) => void;
  onCancel: () => void;
}

/** A dialog asking for text (an appeal's reason, documentation), with its length rules. Each
 * opening starts empty (the form lives inside the dialog's content). */
export function TextDialog(props: TextDialogProps) {
  return (
    <Dialog open={props.open} onOpenChange={(next) => !next && props.onCancel()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-[18px] font-semibold">{props.title}</DialogTitle>
          <DialogDescription className="text-[15px] text-ink-muted">{props.description}</DialogDescription>
        </DialogHeader>
        <TextForm {...props} />
      </DialogContent>
    </Dialog>
  );
}

function TextForm({ label, min, max, confirmLabel, pending, error, onSubmit, onCancel }: TextDialogProps) {
  const id = useId();
  const hintId = useId();
  const [text, setText] = useState("");
  const length = text.trim().length;
  return (
    <form
      className="grid gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        if (length >= min && length <= max) onSubmit(text.trim());
      }}
    >
      <label htmlFor={id} className="text-[13px] font-semibold">
        {label}
      </label>
      <Textarea
        id={id}
        value={text}
        rows={6}
        maxLength={max}
        aria-describedby={hintId}
        className="bg-paper text-[15px]"
        onChange={(event) => setText(event.target.value)}
      />
      <p id={hintId} className="text-[13px] text-ink-muted tabular-nums">
        {min > 1 ? `At least ${min} characters. ` : ""}
        {length.toLocaleString("en-US")} of {max.toLocaleString("en-US")}
      </p>
      {Boolean(error) && <ErrorNotice error={error} />}
      <DialogFooter className="mt-2 gap-3">
        <Button type="button" variant="outline" onClick={onCancel}>
          Cancel
        </Button>
        <Button type="submit" disabled={pending || length < min || length > max}>
          {pending ? "Sending" : confirmLabel}
        </Button>
      </DialogFooter>
    </form>
  );
}

type Step = "reopen" | "documentation" | "appeal" | null;

/** The provider's follow-up buttons for their claim, with what each does. */
export function FollowUpActions({ claimId, followUps }: { claimId: string; followUps?: FollowUps }) {
  const [step, setStep] = useState<Step>(null);
  const followUp = useFollowUp(claimId);
  if (!followUps || (!followUps.correct && !followUps.documentation && !followUps.appeal)) return null;
  const close = () => {
    setStep(null);
    followUp.reset();
  };
  return (
    <Panel className="mb-8 p-5">
      <h2 className="text-[18px] font-semibold">What you can do next</h2>
      <ul className="mt-3 grid gap-4 md:grid-cols-2">
        {followUps.documentation && (
          <li className="grid content-start gap-2">
            <p className="text-ink-muted">
              Send the documentation the plan asked for. It is added to the claim's clinical notes and the claim is
              processed again, then reviewed.
            </p>
            <Button className="justify-self-start" onClick={() => setStep("documentation")}>
              <FilePlus2 aria-hidden /> Send documentation
            </Button>
          </li>
        )}
        {followUps.correct && (
          <li className="grid content-start gap-2">
            <p className="text-ink-muted">
              Correct what the checks found and send the claim again. It goes back to “Not processed” so you can fix its
              boxes, check it and process it.
            </p>
            <Button className="justify-self-start" variant="outline" onClick={() => setStep("reopen")}>
              <RotateCcw aria-hidden /> Correct and resubmit
            </Button>
          </li>
        )}
        {followUps.appeal && (
          <li className="grid content-start gap-2">
            <p className="text-ink-muted">
              Ask the plan to decide again. A reviewer who did not deny it looks at it; a claim is appealed once.
            </p>
            <Button className="justify-self-start" variant="outline" onClick={() => setStep("appeal")}>
              <Gavel aria-hidden /> Appeal the decision
            </Button>
          </li>
        )}
      </ul>
      <ConfirmDialog
        open={step === "reopen"}
        title="Correct and resubmit this claim?"
        confirmLabel={followUp.isPending ? "Sending back" : "Send it back to me"}
        onCancel={close}
        onConfirm={() =>
          followUp.mutate(
            { kind: "reopen" },
            {
              onSuccess: () => {
                toast.success("The claim is back with you: correct it, check it and process it");
                setStep(null);
              },
              onError: (error) => toast.error(error.message),
            },
          )
        }
      >
        The decision is set aside and the claim goes back to “Not processed”. Correct its boxes, then process it to run
        the checks, the model and the review again.
      </ConfirmDialog>
      <TextDialog
        open={step === "documentation"}
        title="Send documentation"
        description="Type or paste what the notes were missing, for example the exam findings or the test results. It is added to the clinical notes as it is, with today's date."
        label="Documentation"
        min={1}
        max={DOCUMENTATION_MAX}
        confirmLabel="Add to the claim"
        pending={followUp.isPending}
        error={followUp.error}
        onCancel={close}
        onSubmit={(text) =>
          followUp.mutate(
            { kind: "documentation", text },
            {
              onSuccess: () => {
                toast.success("Documentation added: process the claim to send it to review");
                setStep(null);
              },
            },
          )
        }
      />
      <TextDialog
        open={step === "appeal"}
        title="Appeal the decision"
        description="Say what the decision missed. A reviewer who did not deny the claim decides it again; their decision is final."
        label="Why the claim should be decided again"
        min={REASON_MIN}
        max={REASON_MAX}
        confirmLabel="File the appeal"
        pending={followUp.isPending}
        error={followUp.error}
        onCancel={close}
        onSubmit={(reason) =>
          followUp.mutate(
            { kind: "appeal", reason },
            {
              onSuccess: () => {
                toast.success("Appeal filed: a reviewer will decide the claim again");
                setStep(null);
              },
            },
          )
        }
      />
    </Panel>
  );
}

/** A claim's appeals, newest first: who filed, when, and how each was decided. The reason shows
 * to the plan's staff and to whoever filed it (the API leaves it out otherwise). */
export function AppealHistory({ appeals, staff = false }: { appeals?: Appeal[]; staff?: boolean }) {
  if (!appeals || appeals.length === 0) return null;
  return (
    <section aria-label="Appeals" className="mb-8">
      <h2 className="mb-3 text-[21px] leading-[28px] font-bold">Appeal</h2>
      <ul className="grid gap-3">
        {appeals.map((appeal) => (
          <li key={appeal.appeal_id} className="surface rounded-lg p-4">
            <p className="font-semibold">
              {appeal.status === "OPEN"
                ? "Waiting for a reviewer to decide again"
                : (APPEAL_OUTCOME[appeal.outcome ?? ""] ?? "Decided")}
            </p>
            <p className="text-[13px] text-ink-muted">
              Filed by the {appeal.filed_role} on {dateOnly(appeal.filed_at.slice(0, 10))}
              {staff && appeal.previous_reviewer ? `; first decided by ${appeal.previous_reviewer}` : ""}
              {appeal.decided_at
                ? `; decided ${dateTime(appeal.decided_at)}${staff && appeal.decided_by ? ` by ${appeal.decided_by}` : ""}`
                : ""}
            </p>
            {appeal.reason && <p className="mt-2 break-words whitespace-pre-line">{appeal.reason}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}
