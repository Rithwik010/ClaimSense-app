// One of the member's claims (D-MEM-2). Once the plan decided it: its explanation of benefits, the
// patient EOB of D-EOB-1 that the provider also gets (EobView), with "This is not a bill." and the
// plain reasons. Otherwise what the API says of it: "Your claim is being processed" until it is
// final (nothing else of its outcome), or why it has no EOB (returned to the provider, or on hold).
// Another member's claim is "Not found", as one that does not exist.

import { Link, useParams } from "react-router";

import { useMemberClaim, useMemberEob } from "@/api/hooks";
import type { MemberClaim as Claim } from "@/api/types";
import { Chip } from "@/components/Chip";
import { PageTitle, Panel } from "@/components/Layout";
import { ErrorNotice, Skeleton } from "@/components/States";
import { dateOnly } from "@/lib/format";
import { memberOutcome } from "@/lib/labels";
import { EobView } from "@/pages/PatientEob";

const BACK = { to: "/member/claims", label: "Back to my claims" };

function Status({ claim }: { claim: Claim }) {
  const facts: [string, string][] = [
    ["Claim", claim.claim_id],
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
  return <EobView eob={eob.data} hint="What your plan did with each service." back={BACK} />;
}
