// Submit claim (providers, D-AUTH-1): drop a JSON claim, a PDF of the form or a scanned form, or the
// form's pages as files (one claim, D-DOC-2, D-DOC-3). "Submit claim" does it in one step (D-UI-12):
// it reads the claim, runs the check (D-CHK-1) and, when the check finds nothing, processes it, and
// the stage strip fills in (motion moment 5); when the check finds something, it stops there with
// the check and the boxes read, to correct any read wrong (D-FIX-1) and process. "Read and check
// first" stops after the check either way. If the model is down (503) the claim stays received and
// "Try again" processes it.

import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { ApiError, request } from "@/api/client";
import { useProcess, useUpload } from "@/api/hooks";
import type { ClaimCheck, FiledWithErrors, IntakeResult } from "@/api/types";
import { OutcomeChip } from "@/components/Chip";
import { ClaimPrep } from "@/components/ClaimPrep";
import { DropZone } from "@/components/DropZone";
import { PageTitle, Panel, Section } from "@/components/Layout";
import { providerStages, StageStrip } from "@/components/StageStrip";
import { ErrorNotice, Note } from "@/components/States";
import { Button } from "@/components/ui/button";
import { providerOutcome } from "@/lib/labels";

const FORMATS: Record<string, string> = {
  JSON: "a JSON claim",
  DIGITAL_PDF: "a digital PDF",
  SCANNED: "a scanned form, read by OCR",
};

export function SubmitClaim() {
  const [files, setFiles] = useState<File[]>([]);
  const [sent, setSent] = useState(0); // how many files the claim was read from
  const [stopped, setStopped] = useState<string | null>(null); // why "Submit claim" did not process
  const upload = useUpload();
  const process = useProcess();
  const client = useQueryClient();
  const filed = upload.data;
  const errors = filed && "contract_errors" in filed ? (filed as FiledWithErrors) : null;
  const read = filed && "claim" in filed ? (filed as IntakeResult) : null;
  const claimId = read ? String(read.claim.claim_id) : errors?.claim_id;
  const duplicate = upload.error instanceof ApiError && upload.error.status === 409;
  const modelDown = process.error instanceof ApiError && process.error.status === 503;
  const result = process.data;

  const choose = (next: File[]) => {
    setFiles(next);
    setStopped(null);
    upload.reset();
    process.reset();
  };
  /** Read the claim, check it, and process it when the check finds nothing (`andProcess`). */
  const submit = async (andProcess: boolean) => {
    setSent(files.length);
    setStopped(null);
    let answer: IntakeResult | FiledWithErrors;
    try {
      answer = await upload.mutateAsync(files);
    } catch {
      return; // the page shows upload.error
    }
    const id = "claim" in answer ? String(answer.claim.claim_id) : answer.claim_id;
    if (!id) return;
    let check: ClaimCheck;
    try {
      check = await client.fetchQuery({
        queryKey: ["check", id],
        queryFn: () => request<ClaimCheck>(`/v1/claims/${encodeURIComponent(id)}/check`),
        staleTime: 0,
      });
    } catch {
      setStopped("The claim was read, but the check could not run. Check it again below, then process it.");
      return;
    }
    if (!andProcess) {
      toast.success("Claim read and checked");
      return;
    }
    if (check.outcome !== "READY" || check.problems.length > 0 || "contract_errors" in answer) {
      setStopped("The check found something to look at, so the claim was not processed. See what it found below.");
      return;
    }
    process.mutate(id, {
      onSuccess: (view) =>
        toast.success(`Claim submitted: ${providerOutcome(view.outcome, view.status).label.toLowerCase()}`),
    });
  };
  const runProcess = () => {
    if (!claimId) return;
    process.mutate(claimId, {
      onSuccess: (view) => toast.success(`Claim processed: ${providerOutcome(view.outcome, view.status).label.toLowerCase()}`),
    });
  };

  return (
    <>
      <PageTitle title="Submit claim" hint="Read the claim, check it and correct any box read wrong, then process it." />
      <Panel className="mb-6 space-y-4 p-5">
        <DropZone files={files} onFiles={choose} />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="lg"
            variant={filed ? "outline" : "default"}
            disabled={files.length === 0 || upload.isPending || process.isPending}
            onClick={() => void submit(true)}
          >
            {upload.isPending ? "Reading" : process.isPending ? "Processing" : "Submit claim"}
          </Button>
          <Button
            size="lg"
            variant="outline"
            disabled={files.length === 0 || upload.isPending || process.isPending}
            onClick={() => void submit(false)}
          >
            Read and check first
          </Button>
          {upload.isPending && (
            <p role="status" className="text-[13px] text-ink-muted">
              {files.length > 1 ? "Reading the files." : "Reading the file."} A scanned form takes a few seconds.
            </p>
          )}
        </div>
      </Panel>

      {upload.error && (
        <div className="mb-6 space-y-2">
          <ErrorNotice error={upload.error} />
          {duplicate && (
            <p className="text-ink-muted">
              A claim with this claim ID is already on file. Find it on{" "}
              <Link className="font-semibold text-ink underline underline-offset-4" to="/my-claims">
                My claims
              </Link>
              .
            </p>
          )}
        </div>
      )}

      {stopped && (
        <div className="mb-6">
          <Note>{stopped}</Note>
        </div>
      )}

      {filed && claimId && (
        <>
          <Panel className="mb-6 p-5">
            <div className="flex flex-wrap items-center gap-4">
              <div className="min-w-0 flex-1 basis-72">
                <p className="font-semibold">
                  Claim {claimId} was filed from {sent > 1 ? `${sent} files, ` : ""}
                  {FORMATS[filed.source_format] ?? filed.source_format}.
                </p>
                <p className="text-[13px] text-ink-muted">
                  Processing runs the rules, the coverage policy lookup, the model recommendation and the calculator.
                </p>
              </div>
              {!result && (
                <Button size="lg" disabled={process.isPending} onClick={runProcess}>
                  {process.isPending ? "Processing" : "Process claim"}
                </Button>
              )}
            </div>
            {process.isPending && (
              <p role="status" className="mt-3 text-ink-muted">
                Processing. The model's recommendation can take up to a minute.
              </p>
            )}
          </Panel>

          {modelDown && (
            <div className="mb-6">
              <Note>
                <p className="font-semibold">The decision model is not available right now.</p>
                <p className="mt-1">
                  The claim is saved as received and nothing was decided. Once Ollama is running again (make ollama-up),
                  process the same claim.
                </p>
                <Button className="mt-3" disabled={process.isPending} onClick={runProcess}>
                  {process.isPending ? "Processing" : "Try again"}
                </Button>
              </Note>
            </div>
          )}
          {process.error && !modelDown && (
            <div className="mb-6">
              <ErrorNotice error={process.error} />
            </div>
          )}

          {result && (
            <Section title="Result">
              <StageStrip list={providerStages(result)} fill />
              <Panel className="flex flex-wrap items-center gap-4 p-5">
                <div className="min-w-0 flex-1 basis-72">
                  <OutcomeChip outcome={result.outcome} provider showHint />
                  <p className="mt-2 text-ink-muted">
                    {result.final
                      ? "The decision is final: the rules decided it."
                      : "A reviewer checks the recommendation; the decision shows on My claims once it is final."}
                  </p>
                </div>
                <Button asChild size="lg">
                  <Link to={`/my-claims/${encodeURIComponent(result.claim_id)}`}>Open claim result</Link>
                </Button>
                <Button size="lg" variant="outline" onClick={() => choose([])}>
                  Submit another claim
                </Button>
              </Panel>
            </Section>
          )}

          <ClaimPrep
            claimId={claimId}
            sourceFormat={filed.source_format}
            claim={read ? read.claim : (errors?.received ?? {})}
            contractErrors={errors?.contract_errors ?? []}
            processed={Boolean(result)}
            autoCheck
          />
        </>
      )}
    </>
  );
}
