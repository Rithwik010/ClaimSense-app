// One of the member's claims (D-MEM-2). Once the plan decided it: its explanation of benefits, the
// patient EOB of D-EOB-1 that the provider also gets (EobView), with "This is not a bill." and the
// plain reasons. Otherwise what the API says of it: "Your claim is being processed" until it is
// final (nothing else of its outcome), or why it has no EOB (returned to the provider, or on hold).
// Its services in plain words (D-MEM-2). A denied claim can be appealed once (D-APL-1): the member
// says why, and a reviewer who did not deny it decides it again; the page shows how the appeal
// stands. Another member's claim is "Not found", as one that does not exist.

import { Gavel } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { toast } from "sonner";

import { useMemberAppeal, useMemberClaim, useMemberEob } from "@/api/hooks";
import type { MemberClaim as Claim } from "@/api/types";
import { Chip } from "@/components/Chip";
import { REASON_MAX, REASON_MIN, TextDialog } from "@/components/FollowUps";
import { PageTitle, Panel } from "@/components/Layout";
import { ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { dateOnly } from "@/lib/format";
import { APPEAL_OUTCOME, memberOutcome } from "@/lib/labels";
import { EobView } from "@/pages/PatientEob";

/** How the claim's appeal stands, and the button to file one when the claim can be appealed. */
function AppealPanel({ claim }: { claim: Claim }) {
  const appeal = useMemberAppeal(claim.claim_id);
  const [open, setOpen] = useState(false);
  if (!claim.appeal && !claim.can_appeal) return null;
  return (
    <Panel className="mb-8 p-5">
      <h2 className="flex items-center gap-2 text-[18px] font-semibold">
        <Gavel aria-hidden className="size-5 text-ink-muted" /> Appeal
      </h2>
      {claim.appeal ? (
        <p className="mt-2 text-ink-muted">
          {claim.appeal.filed_by_you ? "You appealed" : "Your provider appealed"} on {dateOnly(claim.appeal.filed_on)}.{" "}
          {claim.appeal.status === "OPEN"
            ? "A reviewer who did not decide the claim the first time is looking at it again."
            : `Decided on ${dateOnly(claim.appeal.decided_on)}: ${(APPEAL_OUTCOME[claim.appeal.outcome ?? ""] ?? "decided").toLowerCase()}.`}
        </p>
      ) : (
        <>
          <p className="mt-2 max-w-[75ch] text-ink-muted">
            If you think your plan got this wrong, you can ask for it to be decided again. A reviewer who did not deny it
            looks at it; a claim is appealed once.
          </p>
          <Button className="mt-3" onClick={() => setOpen(true)}>
            Appeal this decision
          </Button>
        </>
      )}
      <TextDialog
        open={open}
        title="Appeal this decision"
        description="Tell your plan what the decision missed, in your own words. Your provider and the plan's reviewers see it."
        label="Why it should be decided again"
        min={REASON_MIN}
        max={REASON_MAX}
        confirmLabel="Send my appeal"
        pending={appeal.isPending}
        error={appeal.error}
        onCancel={() => {
          setOpen(false);
          appeal.reset();
        }}
        onSubmit={(reason) =>
          appeal.mutate(reason, {
            onSuccess: () => {
              toast.success("Appeal sent: your plan will decide the claim again");
              setOpen(false);
            },
          })
        }
      />
    </Panel>
  );
}

const BACK = { to: "/member/claims", label: "Back to my claims" };

function Status({ claim }: { claim: Claim }) {
  const facts: [string, string][] = [
    ["Claim", claim.claim_id],
    ["Care", claim.services.join("; ") || "—"],
    ["Date of service", dateOnly(claim.service_date)],
    ["Provider", claim.provider_name ?? "—"],
    ["Received", dateOnly(claim.received)],
  ];
  return (
    <>
      <PageTitle title={`Claim ${claim.claim_id}`} actions={<Chip label={memberOutcome(claim.outcome)} />} />
      <Panel glass className="mb-8 p-5">
        <h2 className="text-[18px] leading-[26px] font-semibold">{claim.heading}</h2>
        <p className="mt-2 max-w-[75ch] text-ink-muted">{claim.message}</p>
        <dl className="mt-5 grid gap-x-8 gap-y-2 border-t border-rules pt-4 sm:grid-cols-2">
          {facts.map(([term, value]) => (
            <div key={term} className="flex flex-wrap gap-x-3">
              <dt className="w-32 shrink-0 text-ink-muted">{term}</dt>
              <dd className="min-w-0 font-semibold break-words">{value}</dd>
            </div>
          ))}
        </dl>
      </Panel>
      <AppealPanel claim={claim} />
      <p>
        <Link className="font-semibold text-link underline underline-offset-4" to={BACK.to}>
          {BACK.label}
        </Link>
      </p>
    </>
  );
}

export function MemberClaim() {
  const { claimId = "" } = useParams();
  const claim = useMemberClaim(claimId);
  const eob = useMemberEob(claimId, claim.data?.eob === true);
  if (claim.isPending) return <Skeleton lines={8} />;
  if (claim.error) return <ErrorNotice error={claim.error} onRetry={() => void claim.refetch()} />;
  if (!claim.data.eob) return <Status claim={claim.data} />;
  if (eob.isPending) return <Skeleton lines={8} />;
  if (eob.error) return <ErrorNotice error={eob.error} onRetry={() => void eob.refetch()} />;
  return (
    <>
      <EobView eob={eob.data} hint="What your plan did with each service." back={BACK} />
      <div className="mt-8">
        <AppealPanel claim={claim.data} />
      </div>
    </>
  );
}
