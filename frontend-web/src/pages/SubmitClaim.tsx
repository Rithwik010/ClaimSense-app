// Submit claim: upload a JSON claim, a PDF of the form or a scanned form; check the fields read and
// their confidence; process the claim; then open it, where the stage strip fills in.

import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { toast } from "sonner";

import { ApiError } from "@/api/client";
import { useProcess, useUpload } from "@/api/hooks";
import type { FiledWithErrors, IntakeResult } from "@/api/types";
import { FieldsTable } from "@/components/Fields";
import { PageTitle, Panel, Section } from "@/components/Layout";
import { ErrorNotice, Note } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const FORMATS: Record<string, string> = {
  JSON: "a JSON claim",
  DIGITAL_PDF: "a digital PDF",
  SCANNED: "a scanned form, read by OCR",
};

export function SubmitClaim() {
  const [file, setFile] = useState<File | null>(null);
  const upload = useUpload();
  const process = useProcess();
  const navigate = useNavigate();
  const filed = upload.data;
  const errors = filed && "contract_errors" in filed ? (filed as FiledWithErrors) : null;
  const read = filed && "claim" in filed ? (filed as IntakeResult) : null;
  const claimId = read ? String(read.claim.claim_id) : errors?.claim_id;
  const duplicate = upload.error instanceof ApiError && upload.error.status === 409;

  return (
    <>
      <PageTitle
        title="Submit claim"
        hint="Upload a JSON claim, a PDF of the ClaimSense form, or a scanned form as a PDF, PNG, JPEG or TIFF."
      />
      <Panel className="mb-6 p-5">
        <form
          className="flex flex-wrap items-end gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            if (file) {
              process.reset();
              upload.mutate(file, { onSuccess: () => toast.success("Claim read") });
            }
          }}
        >
          <label className="grid min-w-0 flex-1 basis-72 gap-1.5 font-semibold" htmlFor="claim-file">
            Claim file
            <Input
              id="claim-file"
              type="file"
              name="claim-file"
              accept=".json,.pdf,.png,.jpg,.jpeg,.tif,.tiff,application/json,application/pdf,image/*"
              className="h-10 bg-paper font-normal"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                upload.reset();
              }}
            />
          </label>
          <Button type="submit" size="lg" variant={filed ? "outline" : "default"} disabled={!file || upload.isPending}>
            {upload.isPending ? "Reading" : "Read claim"}
          </Button>
        </form>
        {upload.isPending && (
          <p role="status" className="mt-3 text-[13px] text-ink-muted">
            Reading the file. A scanned form takes a few seconds.
          </p>
        )}
      </Panel>

      {upload.error && (
        <div className="mb-6 space-y-2">
          <ErrorNotice error={upload.error} />
          {duplicate && (
            <p className="text-ink-muted">
              A claim with this claim ID is already on file. Find it under{" "}
              <Link className="font-semibold text-ink underline underline-offset-4" to="/claims">
                Claims
              </Link>
              .
            </p>
          )}
        </div>
      )}

      {filed && claimId && (
        <>
          <Panel className="mb-6 flex flex-wrap items-center gap-4 p-5">
            <div className="min-w-0 flex-1 basis-72">
              <p className="font-semibold">
                Claim {claimId} was filed from {FORMATS[filed.source_format] ?? filed.source_format}.
              </p>
              <p className="text-[13px] text-ink-muted">
                Processing runs the rules, the coverage policy lookup, the model recommendation and the calculator.
              </p>
            </div>
            <Button
              size="lg"
              disabled={process.isPending}
              onClick={() =>
                process.mutate(claimId, {
                  onSuccess: () => {
                    toast.success("Claim processed");
                    navigate(`/claims/${encodeURIComponent(claimId)}`, { state: { justProcessed: true } });
                  },
                })
              }
            >
              {process.isPending ? "Processing" : "Process claim"}
            </Button>
          </Panel>
          {process.isPending && (
            <p role="status" className="mb-6 text-ink-muted">
              Processing. The model's recommendation can take up to a minute.
            </p>
          )}
          {process.error && (
            <div className="mb-6">
              <ErrorNotice error={process.error} />
            </div>
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
