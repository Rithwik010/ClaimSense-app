// A claim filed but not processed yet, on the provider's pages: check it (D-CHK-1) and, for a claim
// read from our form, see each box as read and correct any that were read wrong (D-FIX-1). A JSON
// claim is read exactly, so it lists its fields with nothing to correct. After processing, the
// boxes stay listed as read and corrected, without the check or the Correct buttons.

import { useMemo, useState } from "react";

import { useClaimCheck, useClaimForm } from "@/api/hooks";
import type { Claim, SourceFormat } from "@/api/types";
import { ClaimCheckPanel } from "@/components/ClaimCheck";
import { CorrectDialog } from "@/components/CorrectDialog";
import { FieldsTable } from "@/components/Fields";
import { FormFields } from "@/components/FormFields";
import { Section } from "@/components/Layout";
import { ErrorNotice, Note, Skeleton } from "@/components/States";

export function ClaimPrep({
  claimId,
  sourceFormat,
  claim,
  contractErrors = [],
  processed = false,
  reopened = false,
  autoCheck = false,
}: {
  claimId: string;
  sourceFormat: SourceFormat;
  /** The claim as filed: a JSON claim's fields (a claim read from the form is listed box by box). */
  claim: Claim;
  /** A JSON claim's contract errors at filing (a form claim's come with its boxes). */
  contractErrors?: string[];
  processed?: boolean;
  /** Sent back to the provider (D-FUP-1): its boxes are correctable whatever its source. */
  reopened?: boolean;
  /** Run the check at once (Submit claim, D-UI-12). */
  autoCheck?: boolean;
}) {
  const fromForm = sourceFormat !== "JSON" || reopened;
  const form = useClaimForm(claimId, fromForm);
  const checked = useClaimCheck(claimId, false); // what the check panel last found (cached only)
  const [editing, setEditing] = useState<string | null>(null);
  const flagged = useMemo(
    () => new Set((processed ? [] : (checked.data?.problems ?? [])).flatMap((p) => p.fields)),
    [checked.data, processed],
  );
  const correctable = useMemo(
    () => new Set((form.data?.correctable ? form.data.boxes : []).filter((b) => b.correctable).map((b) => b.field)),
    [form.data],
  );
  const errors = fromForm ? (form.data?.contract_errors ?? []) : contractErrors;
  const box = form.data?.boxes.find((b) => b.field === editing) ?? null;

  return (
    <>
      {!processed && (
        <Section title="Check before processing">
          <ClaimCheckPanel claimId={claimId} correctable={correctable} onCorrect={setEditing} autoCheck={autoCheck} />
        </Section>
      )}
      {errors.length > 0 && !processed && (
        <div className="mb-6">
          {/* Plain words only (D-UI-6): the check above says why, without rule IDs. */}
          <Note>
            <p className="font-semibold">The claim was filed, but as it stands the claim checks will reject it.</p>
            <p className="mt-1">
              {fromForm
                ? "Check the claim to see why, correct the boxes below, then check it again."
                : "Check the claim to see why. A JSON claim is read exactly: fix the file and file it under a new claim ID."}
            </p>
          </Note>
        </div>
      )}
      <Section title="Fields read">
        {!fromForm ? (
          <FieldsTable claim={claim} confidences={{}} jsonClaim />
        ) : form.isPending ? (
          <Skeleton lines={6} />
        ) : form.error ? (
          <ErrorNotice error={form.error} onRetry={() => void form.refetch()} />
        ) : (
          <FormFields form={form.data} onCorrect={setEditing} flagged={flagged} />
        )}
      </Section>
      {fromForm && <CorrectDialog claimId={claimId} box={box} onClose={() => setEditing(null)} />}
    </>
  );
}
