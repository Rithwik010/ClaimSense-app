// Submit claim (providers, D-AUTH-1): drop a JSON claim, a PDF of the form or a scanned form; check
// the fields read and their confidence; process the claim, and the stage strip fills in (motion
// moment 4). If the model is down (503) the claim stays received and "Try again" processes it.

import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { useProcess, useUpload } from "@/api/hooks";
import type { FiledWithErrors, IntakeResult } from "@/api/types";
import { Chip } from "@/components/Chip";
import { DropZone } from "@/components/DropZone";
import { FieldsTable } from "@/components/Fields";
import { PageTitle, Panel, Section } from "@/components/Layout";
import { providerStages, StageStrip } from "@/components/StageStrip";
import { ErrorNotice, Note } from "@/components/States";
import { Button } from "@/components/ui/button";
import { providerStatus } from "@/lib/labels";

const FORMATS: Record<string, string> = {
  JSON: "a JSON claim",
  DIGITAL_PDF: "a digital PDF",
  SCANNED: "a scanned form, read by OCR",
};

export function SubmitClaim() {
  const [file, setFile] = useState<File | null>(null);
  const upload = useUpload();
  const process = useProcess();
  const filed = upload.data;
  const errors = filed && "contract_errors" in filed ? (filed as FiledWithErrors) : null;
  const read = filed && "claim" in filed ? (filed as IntakeResult) : null;
  const claimId = read ? String(read.claim.claim_id) : errors?.claim_id;
  const duplicate = upload.error instanceof ApiError && upload.error.status === 409;
  const modelDown = process.error instanceof ApiError && process.error.status === 503;
  const result = process.data;

  const choose = (next: File | null) => {
    setFile(next);
    upload.reset();
    process.reset();
  };
  const runProcess = () => {
    if (!claimId) return;
    process.mutate(claimId, {
      onSuccess: (view) => toast.success(`Claim processed: ${providerStatus(view.status).label.toLowerCase()}`),
    });
  };

  return (
    <>
      <PageTitle title="Submit claim" hint="Read the claim, check the fields, then process it." />
      <Panel className="mb-6 space-y-4 p-5">
        <DropZone file={file} onFile={choose} />
        <div className="flex flex-wrap items-center gap-3">
          <Button
            size="lg"
            variant={filed ? "outline" : "default"}
            disabled={!file || upload.isPending}
            onClick={() => file && upload.mutate(file, { onSuccess: () => toast.success("Claim read") })}
          >
            {upload.isPending ? "Reading" : "Read claim"}
          </Button>
          {upload.isPending && (
            <p role="status" className="text-[13px] text-ink-muted">
              Reading the file. A scanned form takes a few seconds.
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

      {filed && claimId && (
        <>
          <Panel className="mb-6 p-5">
            <div className="flex flex-wrap items-center gap-4">
              <div className="min-w-0 flex-1 basis-72">
                <p className="font-semibold">
                  Claim {claimId} was filed from {FORMATS[filed.source_format] ?? filed.source_format}.
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
                  <Chip label={providerStatus(result.status)} showHint />
                  <p className="mt-2 text-ink-muted">
                    {result.final
                      ? "The decision is final: the rules decided it."
                      : "A reviewer checks the recommendation; the decision shows on My claims once it is final."}
                  </p>
                </div>
                <Button asChild size="lg">
                  <Link to={`/my-claims/${encodeURIComponent(result.claim_id)}`}>Open claim result</Link>
                </Button>
                <Button size="lg" variant="outline" onClick={() => choose(null)}>
                  Submit another claim
                </Button>
              </Panel>
            </Section>
          )}

          {errors && (
            <div className="mb-6">
              <Note>
                <p className="font-semibold">The claim was filed, but the rules will reject it:</p>
                <ul className="mt-1 list-disc pl-5">
                  {errors.contract_errors.map((error) => (
                    <li key={error}>{error}</li>
                  ))}
                </ul>
              </Note>
            </div>
          )}
          <Section title="Fields read">
            <FieldsTable
              claim={read ? read.claim : (errors?.received ?? {})}
              confidences={(read ? read.field_confidences : errors?.field_confidences) ?? {}}
              jsonClaim={filed.source_format === "JSON"}
            />
          </Section>
        </>
      )}
    </>
  );
}
