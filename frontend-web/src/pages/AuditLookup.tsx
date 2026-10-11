// Audit lookup (admin): enter a claim ID, see its audit trail as a timeline (time, event, actor,
// versions). Read-only; the trail itself is insert-only on the server (§8.9).

import { Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router";

import { ApiError } from "@/api/client";
import { useAudit } from "@/api/hooks";
import { AuditTimeline } from "@/components/AuditTimeline";
import { PageTitle } from "@/components/Layout";
import { EmptyState, ErrorNotice, Skeleton } from "@/components/States";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function AuditLookup() {
  const [typed, setTyped] = useState("");
  const [claimId, setClaimId] = useState("");
  const audit = useAudit(claimId, claimId !== "");
  const notFound = audit.error instanceof ApiError && audit.error.status === 404;
  return (
    <>
      <PageTitle title="Audit lookup" hint="Every step of a claim: when it happened, who did it, and the versions it ran with." />
      <form
        className="mb-6 flex flex-wrap items-end gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          setClaimId(typed.trim());
        }}
      >
        <label className="grid min-w-0 flex-1 basis-64 gap-1.5 text-[13px] font-semibold" htmlFor="audit-claim">
          Claim ID
          <span className="relative">
            <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-ink-muted" />
            <Input
              id="audit-claim"
              value={typed}
              placeholder="For example CLM-DEMO-03"
              className="h-10 bg-paper pl-9 text-[15px] font-normal"
              onChange={(event) => setTyped(event.target.value)}
            />
          </span>
        </label>
        <Button type="submit" size="lg" disabled={!typed.trim()}>
          Show audit trail
        </Button>
      </form>
      {claimId === "" ? (
        <EmptyState title="Enter a claim ID">Its audit trail appears here, oldest step first.</EmptyState>
      ) : audit.isPending ? (
        <Skeleton lines={5} />
      ) : notFound ? (
        <EmptyState title={`No claim ${claimId} on file`}>Check the claim ID; claim IDs look like CLM-DEMO-01.</EmptyState>
      ) : audit.error ? (
        <ErrorNotice error={audit.error} onRetry={() => void audit.refetch()} />
      ) : (
        <>
          <p className="mb-3 text-ink-muted">
            {audit.data.length} steps for claim{" "}
            <Link className="font-semibold text-ink underline underline-offset-4" to={`/claims/${encodeURIComponent(claimId)}`}>
              {claimId}
            </Link>
            .
          </p>
          <AuditTimeline events={audit.data} />
        </>
      )}
    </>
  );
}
