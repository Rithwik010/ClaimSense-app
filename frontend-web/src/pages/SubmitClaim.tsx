// Submit claim: upload a JSON claim, a PDF of the form or a scanned image; check the fields read
// and their confidence; process the claim; then go to the claim.

import { useState } from "react";
import { Link, useNavigate } from "react-router";

import { useProcess, useUpload } from "../api/hooks";
import type { FiledWithErrors, IntakeResult } from "../api/types";
import { FieldsTable } from "../components/Fields";
import { PageTitle, Section } from "../components/Layout";
import { ErrorNotice } from "../components/States";
import { button, card, input } from "../components/ui";
import { ApiError } from "../api/client";

const FORMATS: Record<string, string> = {
  JSON: "JSON claim",
  DIGITAL_PDF: "digital PDF",
  SCANNED: "scanned form (OCR)",
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
        hint="Upload a JSON claim, a PDF of the ClaimSense form, or a scanned form (PDF, PNG, JPEG or TIFF)."
      />
      <form
        className={`${card} mb-8 flex flex-wrap items-end gap-4`}
        onSubmit={(event) => {
          event.preventDefault();
          if (file) {
            process.reset();
            upload.mutate(file);
          }
        }}
      >
        <label className="min-w-72 flex-1 text-sm font-medium text-gray-700">
          Claim file
          <input
            type="file"
            name="claim-file"
            accept=".json,.pdf,.png,.jpg,.jpeg,.tif,.tiff,application/json,application/pdf,image/*"
            className={`${input} mt-1 font-normal`}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              upload.reset();
            }}
          />
        </label>
        <button
          type="submit"
          className={filed ? button.secondary : button.primary}
          disabled={!file || upload.isPending}
        >
          {upload.isPending ? "Reading…" : "Read claim"}
        </button>
      </form>

      {upload.isPending && (
        <p role="status" className="mb-6 text-gray-600">
          Reading the file. A scanned form takes a few seconds.
        </p>
      )}
      {upload.error && (
        <div className="mb-6">
          <ErrorNotice error={upload.error} />
          {duplicate && (
            <p className="mt-2 text-gray-700">
              A claim with this claim ID is already on file; see <Link className="text-accent underline" to="/claims">Claims</Link>.
            </p>
          )}
        </div>
      )}

      {filed && claimId && (
        <>
          <div className={`${card} mb-8 flex flex-wrap items-center gap-4`}>
            <div className="flex-1">
              <p className="font-medium">
                Claim {claimId} filed from a {FORMATS[filed.source_format] ?? filed.source_format}.
              </p>
              <p className="text-sm text-gray-600">
                Processing runs the rules, the model recommendation and the calculator.
              </p>
            </div>
            <button
              type="button"
              className={button.primary}
              disabled={process.isPending}
              onClick={() =>
                process.mutate(claimId, {
                  onSuccess: () => navigate(`/claims/${encodeURIComponent(claimId)}`),
                })
              }
            >
              {process.isPending ? "Processing…" : "Process claim"}
            </button>
          </div>
          {process.isPending && (
            <p role="status" className="mb-6 text-gray-600">
              Processing. The model's recommendation can take up to a minute.
            </p>
          )}
          {process.error && (
            <div className="mb-6">
              <ErrorNotice error={process.error} />
            </div>
          )}
          {errors && (
            <Section title="Contract errors">
              <p className="mb-2 text-gray-700">
                The claim was filed, but these errors mean the rules will reject it:
              </p>
              <ul className="list-disc pl-5 text-gray-800">
                {errors.contract_errors.map((error) => (
                  <li key={error}>{error}</li>
                ))}
              </ul>
            </Section>
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
